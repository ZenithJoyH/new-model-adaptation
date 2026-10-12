# MiniMax-M3.1 W8A8 架构与推理链路

核对日期：2026-09-29。对象为 PPU-07 上 `minimaxM3.1` 容器可读的 `/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`。此目录没有已核实的 Git revision；`config.json` SHA-256 为 `01ea36d8f4b5e3d382beec760def868d4801ca14f143700b8d28a3daa2f137d5`，实际模型代码参考 vLLM 源码 revision `ee0da84ab9e04ac7610e28580af62c365e898389`。实际 `model.safetensors.index.json` 映射 45,856 个 tensor 到 48 个 safetensors 分片，所列分片均存在，metadata 总字节为 430,879,800,832；尚未逐分片验 hash 或完成整模加载。M3 历史记录仅供结构对照，不作为本模型通过证据。

## 配置和组件

| 组件 | 当前配置 | 推理作用 |
| --- | --- | --- |
| 多模态入口 | `MiniMaxM3SparseForConditionalGeneration`，`minimax_m3_vl` | 文本、图像/视频占位与视觉特征合并 |
| 视觉塔 | 32 层，hidden 1280，16 heads，patch 14，3D RoPE；spatial merge 2，temporal patch 2 | 图像/视频编码、patch 压缩并投影到 6144 维文本空间 |
| 文本主干 | 60 层，hidden 6144，vocab 200064，64 Q heads、4 KV heads、head dim 128 | 自回归 prefill/decode；Q/K per-head norm 与 Gemma RMSNorm |
| FFN | 0–2 层 dense，3–59 层 MoE；128 routed experts、top-4、1 shared expert、每专家 intermediate 3072 | sigmoid 路由、FP32 gate/bias、top-k 与 shared expert 合并；`SwiGLU-OAI` alpha 1.702、beta 1、clamp 7 |
| 稀疏注意力 | `sparse_attention_freq` 全 60 层为 1，index dim 128、4 heads，top-16 blocks、block 128 | 主 K/V 与 index-key 独立缓存；每步选择局部/历史块后做稀疏注意力 |
| 位置与上下文 | partial RoPE 64/128，`rope_theta=10000000`，最大位置 1,048,576 | 当前服务初始配置应按项目规则取 `--max-model-len 50000`；这不证明百万长度可运行 |
| MTP | `num_mtp_modules=0`、`num_nextn_predict_layers=0` | 本 checkpoint 无 MTP 验收目标 |

本模型与仓库内旧 M3 记录至少有三处配置差异：本 checkpoint 是 compressed-tensors W8A8，RoPE theta 为 1,000 万，MTP 数量为 0。稀疏注意力配置逐层启用，不能沿用旧 M3“前三层 dense attention”的结论；前三层的 `moe_layer_freq=0` 只说明 FFN 为 dense。

## W8A8 权重契约

`quantization_config` 使用 `compressed-tensors` / `int-quantized`，一个配置组包含 428 项 target 规则：权重为对称 INT8、逐输出通道静态 FP32 scale，输入激活为对称 INT8、逐 token 动态量化；另有 255 项 ignore 规则。量化说明称原有 22,428 个低精度权重已量化为 INT8、其余 1,000 个参数保持原精度；这是交付方验证报告，尚待本容器的实际装载与抽样数值复核。不能通过仅改 metadata 把 MXFP8/NVFP4 当作当前 W8A8 权重，也不能采用参考 Plugin 补丁中独立的 GPTQ/W8A16 示例作为本 checkpoint 的装载方案。

融合 QKV 投影需把文本 Q/K/V 与 index Q/K 五路权重正确映射；视觉 QKV 是三路。gate/up 融合投影以及 routed/shared expert 的量化权重、scale、bias、SwiGLU-OAI 参数必须共同传递到 W8A8 MoE 内核。未量化的 embedding、norm、router 和 LM head 必须维持其原始 dtype 与方法选择。

## 推理链路与验证重点

1. tokenizer/chat template 与多模态 processor 构造 token、视觉 grid 和占位符；视觉塔通过 patch embedding、attention、3D RoPE、MLP、patch merge 和 projector 生成 6144 维特征。
2. 模型 registry 创建 conditional-generation wrapper，compressed-tensors 配置为各层选择量化方法，loader 把五路文本 QKV/index、gate/up 与专家权重装入融合层。分片数量与每张量形状必须以实际权重索引/装载回执核实。
3. Prefill 时每层执行 norm、QKV/index 投影、partial RoPE、写入主与 index cache、top-16 block 选择、稀疏 attention、row-parallel 输出和 FFN/MoE；decode 重用 paged cache 与 block table。PPU graph capture 必须核实 index buffer、cache 与 workspace 地址稳定及 replay 结果不陈旧。
4. 末端执行 final norm、vocab-parallel LM head、采样及 reasoning/tool parser。文本正确性不能单独证明图像/视频、多模态 token 对齐或解析正确。

TP16 的理论切分为每 rank 4 个 Q heads；4 个 KV/index heads 少于 rank 数，需按实际 vLLM 分配与复制规则核实。401.288 GiB 载荷均摊约 25.1 GiB/rank，但视觉复制、KV/index cache、量化 scale、activation 和 graph workspace 尚未计入，不能据此声称显存充足。PPU 后端的 Triton、FlagGems W8A8 GEMM、Plugin dispatch 和 collective 均需分层验证 eager 与 graph；全量 graph 须先覆盖 prefill/decode，失败时按 profile 保存准确阻塞证据后才能讨论 decode-full。

## 证据界限

已核实项为本次 `config.json`、量化说明、权重索引及所列分片存在性、容器可见模型目录以及上述 vLLM revision 中的 MiniMax M3 代码位置。权重内容完整性、W8A8 数值、TP16 资源、整模推理、图像/视频、图覆盖、精度和性能均属于后续阶段，不能由结构分析推断通过。
