# Hy4-preview 新版模型结构与推理链路

## 2026-09-04 当前修复对象核实

本轮对象是 PPU-07 容器 `hy4` 正在加载的 `/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`，不是待提供的 BF16 产物。实读 config SHA256 `894bbe4e1dea2ac68993891795d3397f71bd2e4c92aae89ba443c10ebca462c2`，权重索引 SHA256 `14694cc4639eb2f8c9996d4674ad24927b690b0f8441f3f30d31912988bbb9c1`，122290 个索引项、131 分片。该身份不等同于全量 payload checksum 或已核实上游 revision；后文旧产物122287项仅为历史比较。

核实当前结构仍为下文78层、6144 hidden、64头、512维MLA latent、32×128 Indexer、top2048、IHC四路、256专家/top8、dense首层和77 MoE层。`use_mla/use_dsa=true`；配置声明的最大位置1048576，RoPE default/theta10000000。初始服务上限应为50000；现有用户服务使用100000，故复现不能暗中降长掩盖问题。

量化为 compressed-tensors/int-quantized，配置组 `w8a8_channel_token` 覆盖专家、shared及attention投影；router、Indexer和linear_gate等在ignore列表。当前缓存与Indexer使用BF16，不走FP8。`swiglu_limit=10`确实存在，但插件dense/shared实现明确为unclamped，不能把配置值等同于已生效clamp；本轮不未经对照改动此数值语义。LM head按 `enable_lm_head_fp32` 分支执行。tokenizer类TokenizersBackend，BOS/EOS/PAD与下文一致；tokenizer_config SHA256 `15267c495102b0ce259408a0b3a9dc11a6de74dd7dd8ef5b9757f64252a9b2df`。

当前实现映射：`vllm_fl/models/hy_v4.py`完成IHC、full/shared Indexer、MLA、dense/shared/MoE、输出；`configs/hy_v4.py`解析配置；attention backend已默认FlagGems，cache和query concat随attention backend；Indexer cache/logits/top-k经过插件dispatch；W8A8使用已有custom-op编译边界，TP16每卡4个attention头，FlagGems路径补齐到64。需要重点验证变长、padded batch、cache布局、head padding以及graph replay；存在乱码说明先前单算子通过不能代替组合正确性。以上为结构/链路分析完成，不代表精度验收通过。证据命令见 `ppu/adaptation/verify-ppu07-current-prerequisites.yml`，环境与修复记录见ppu子目录。

核对日期：2026-08-28。本文分析模型本身；PPU 环境、插件及实施安排放在 `ppu/`。

## 1. 来源、范围与证据等级

固定仓库版本：`Tencent-Hunyuan/Hy4-preview@ada7b1faf9b70585edc90a9ef552d0059fb246e7`，由仓库 `master` ref 核对。不要用某个文件的最后修改 revision 替代整库版本。

主要来源为 [官方配置](https://modelscope.cn/api/v1/models/Tencent-Hunyuan/Hy4-preview/repo?Revision=ada7b1faf9b70585edc90a9ef552d0059fb246e7&FilePath=config.json)、[权重索引](https://modelscope.cn/api/v1/models/Tencent-Hunyuan/Hy4-preview/repo?Revision=ada7b1faf9b70585edc90a9ef552d0059fb246e7&FilePath=model.safetensors.index.json)、[官方中文模型卡](https://modelscope.cn/api/v1/models/Tencent-Hunyuan/Hy4-preview/repo?Revision=ada7b1faf9b70585edc90a9ef552d0059fb246e7&FilePath=README_CN.md)和全部分片头。精简证据摘要见 [_shared/model-reference-analysis.md](_shared/model-reference-analysis.md)。

- **已验证**：配置字段，全部分片的名称、形状、dtype、offset/index 一致性，tokenizer JSON 内容，模板变化。
- **由结构推导**：参数元素总数、投影分解、存储量、并行切分要求。
- **现有实现参考**：旧版插件的 IHC、routing、prefill/decode 运算顺序；这不是新版官方数值行为已被验证的证明。
- **未验证**：新旧权重数值是否相同、新版 BF16 参考输出、新 INT8 的量化格式与误差、新版 SwiGLU 截断行为、MTP 实际推理及 1M context 可用性。

## 2. 权重与配置差异

全部 131 个分片仅通过 HTTP Range 读取头部，共 233,072 bytes（含每片 8-byte 长度字段）；没有读取参数 payload。权重 index 的 `metadata` 是空对象，容量是通过分片头与文件大小求和得到的，不是读出的 `metadata.total_size`。

| 项目 | 新版 BF16 | 旧版 W8A8 产物 |
|---|---:|---:|
| 参数元素数（排除量化 scale） | 779,960,992,733 | 779,960,992,733 |
| 存储张量数 / 分片数 | 2,006 / 131 | 122,287 / 131 |
| 参数 payload bytes | 1,559,983,576,308 | 791,073,955,444（含 scale） |
| 分片文件 bytes | 1,559,983,809,380 | 此处不混用旧目录总大小 |
| 专家存储 | 每层两个 packed BF16 张量 | 逐专家 gate/up/down INT8 + F32 scale |
| 量化配置 | 无 | compressed-tensors W8A8 |
| `transformers_version` | 5.16.2 | 5.10.2 |
| 新增字段 | `use_mla=true`, `use_dsa=true`, `bitwise_backward_align=false` | 未声明 |

去掉旧 `quantization_config` 后，对完整配置逐字段比较仅有上述四个字段差异。`bitwise_backward_align` 是否影响特定实现尚未核实；不能根据名称直接断言无效。

新权重 1,380 个 BF16 张量有 779,930,197,312 个元素；626 个 F32 张量有 30,795,421 个元素。主层 router weight 和 LM-head weight 的存储 dtype 都是 BF16，与旧产物抽查结果一致；**FP32 计算不等于 FP32 存储**。MTP 的 `e_score_correction_bias` 和 sink 新版为 BF16，旧产物为 F32，这是已核实的 dtype 差异。

头部结构一致不等于权重内容 checksum 已验证；没有对约 1.56 TB 的 payload 做全量哈希。官方主模型约 770B、激活约 49B，加上约 10B 的 MTP，与这里含 MTP 的约 779.961B 不矛盾。

## 3. 完整结构分解

| 组件 | 配置和权重证据 | 数据形状/作用 |
|---|---|---|
| 输入/输出 | vocab 120,832，hidden 6,144，不共享 embedding | embedding、LM head 均 `[120832,6144]` BF16 |
| 主干 | `num_hidden_layers=78` | 第 0 层 dense；第 1–77 层 MoE |
| IHC | `hc_mult=4`, `hc_magnitude=2`, `hc_eps=1e-6` | 四路 residual stream；每个 attention/MLP 分支各有读写参数 |
| IHC 参数 | `hc_fn=[8,24576]`, base `[8]`, scale `[2]` | F32；head 聚合参数 `[4,24576]`, `[4]`, `[1]` |
| 归一化 | RMSNorm eps `1e-5` | block input/post-attention、Q/KV latent norm；Indexer 另有带 bias 的 k_norm |
| Q 投影 | q rank 2,048，64 heads，QK dim 256 | q_a `[2048,6144]`；q_b `[16384,2048]` |
| KV 投影 | kv rank 512，RoPE dim 64，non-RoPE dim 192，V dim 256 | kv_a `[576,6144]`；kv_b `[28672,512]` |
| Attention 输出 | gated MLA、elementwise gate、learnable sink | o_proj `[6144,16384]`，linear_gate `[16384,6144]`，sink `[64]` |
| 位置编码 | RoPE default、theta 10,000,000 | 64 维旋转子空间；理论最大位置 1,048,576 |
| 稀疏 Indexer | 32 heads × 128 dim，top-2,048 | wq_b `[4096,2048]`、wk `[128,6144]`、weights_proj `[32,6144]`、k_norm `[128]` |
| Index Cache 复用 | 21 个 full、57 个 shared 层 | full 层为 0、1、5、9、…、77；shared 层复用选中位置，不等于不计算本层 attention |
| 第 0 层 dense | intermediate 18,432，hidden_act=silu | gate/up `[18432,6144]`，down `[6144,18432]` |
| MoE router | 256 experts、top-8、n_group=topk_group=1 | gate `[256,6144]`，correction bias `[256]`；归一化后 routed scaling 2.827 |
| Routed expert | intermediate 2,048 | packed gate/up `[256,4096,6144]`，down `[256,6144,2048]` |
| Shared expert | 每层 1 个 | gate/up `[2048,6144]`，down `[6144,2048]` |
| 输出聚合 | IHC head + final normalization + 独立 LM head | `enable_lm_head_fp32=true`，具体计算 dtype 需要实现落实 |
| MTP | `num_nextn_predict_layers=1` | embedding/hidden norm、eh_proj `[6144,12288]`，独立 attention/MoE/final norm 张量 |

`num_key_value_heads=8` 和 `head_dim=64` 不能脱离 MLA 专用字段，解释为普通 GQA 的实际 cache 或全部 QK head dimension；投影 shape 支持的是上表的 latent MLA 分解。

## 4. 端到端推理链路

### 初始化与加载

读取新版配置与模板，注册 `HYV4ForCausalLM` / `hy_v4`，构建 IHC 主干、专用 attention、MoE 和输出模块。根据 checkpoint 的真实格式选择 BF16 或 INT8 loader；BF16 配置本身不会自动生成可用的 W8A8 权重。专家 packed gate/up 在 intermediate 维度拆分，随后按 expert ID、TP/EP 方案切片。量化后还必须同步切分每个输出通道的 scale。

### Prefill

消息经模板变为 token IDs，embedding 得到 `[T,6144]`，四路 IHC residual 表示可记为 `[T,4,6144]`。以下运算顺序来自当前 HYV4 实现，待新版参考对齐：

1. IHC 读出单路 hidden，RMSNorm 后进入 attention。
2. q_a → latent norm → q_b 得到 Q；kv_a 分出 512 维 latent 和 64 维 RoPE K，执行相应 norm/RoPE；同时生成 attention gate。
3. full Indexer 执行 query/key 投影、key norm、位置处理、QK 点积、逐 head ReLU 和加权归约，causal mask 后选 top-k；shared 层复用索引。
4. sparse MLA 对有效位置计算 QK、包含 sink 的 softmax 和加权 V；gate 调制后 o_proj 返回 hidden。具体是否吸收 kv_b、以何种 cache 布局执行由 backend 决定。
5. attention 输出写回 IHC；再次 IHC 读出与 norm 后进入 dense/MoE。当前 router 是 sigmoid scoring 加 correction bias 选择 top-8、按原始概率归一化/缩放，执行 routed experts，并与 shared expert 合并。
6. MLP 输出写回 IHC；重复 78 层，IHC head 聚合、final norm、LM-head logits，之后采样。

### Decode 与缓存

逐 token 复用 paged MLA latent/RoPE cache 和 Indexer key cache；按 `slot_mapping` 写入新位置，按 block table 读取历史位置。Indexer 仅在有效 seq_len 内选择位置；padding 索引及无效 slot 不得被读作正常 token。后续 attention、MoE 和 logits 与 prefill 保持同一数值语义。

W8A8 是投影/专家计算量化，不自动意味着 INT8 KV cache，更不意味着 FP8 Indexer。缓存 dtype 和布局必须单独定义。

MTP 需要额外的 draft/verification、状态和 KV 管理。权重存在不代表引擎启用了 MTP；应先完成普通自回归基线，再独立验证 speculative decode。

### 并行与 graph

64 query heads 可按 TP16 分为每卡 4 heads，backend 可能需要 head padding；MLP、vocab 和专家输出也要按各自维度切片。TP 使用 all-reduce/all-gather；只有明确开启 EP 才引入对应 expert dispatch/combine 通信，不能仅凭 256 experts 断言当前采用 EP。

Graph capture/replay 要求 shape、地址、workspace 稳定；top-k、cache 更新和 mask 不能在捕获期间按设备数据做 host 分支或同步。必须覆盖 padded batch、不同 seq_len、跨 cache block、prefill/decode 切换；启动时打印 graph enabled 不构成数值验收。

## 5. 由结构及实现导出的关键算子清单

| 阶段 | 需要的算子 | 新版验证重点 |
|---|---|---|
| Tokenizer/embedding | 模板渲染、BPE、embedding lookup | high/no_think、EOS、工具/思考标签 |
| IHC | flatten、FP32 GEMM、square/mean/rsqrt、sigmoid、加权 sum、residual add | 四路读写、累积 dtype 和 eps |
| Norm | RMSNorm、Indexer key LayerNorm | norm 的维度、bias、累积精度 |
| Q/KV/输出投影 | GEMM；INT8 时动态 per-token quant、INT8 dot、channel/token scale | q_a/q_b/kv_a/kv_b/o_proj 及单独 BF16 gate |
| 位置编码 | RoPE、split/concat/reshape | 192+64 QK 分区、旋转方式、长位置 |
| Indexer | BF16 GEMM、paged QK、ReLU、weighted reduce、causal mask、top-k | shared 索引复用、有效长度、padding |
| Sparse MLA | cache gather、QK、sink-aware softmax、PV、sigmoid gate | sink dtype、稀疏位置、head padding |
| Dense/shared MLP | gate/up GEMM、SiLU × up、down GEMM | `swiglu_limit=10` 的真实语义尚未确认 |
| Router | GEMM、sigmoid、bias add、top-k、sum/div、scale | top-8 选择与概率计算不能混淆 |
| Routed MoE | expert dispatch、grouped GEMM、SiLU/mul、weighted combine | expert 顺序、gate/up 顺序、INT8 scale 布局 |
| KV/cache | scatter/write、block/slot mapping、gather | stable buffer、无效 slot、eager/graph 一致 |
| 输出与采样 | IHC head、norm、LM-head GEMM、gather、softmax、top-p/top-k、argmax/随机采样 | lm_head_fp32 是否落实、停止 token |
| 通信 | TP all-reduce/all-gather；可选 EP collectives | 并行分区与规约精度；graph 下通信支持 |

## 6. Tokenizer、版本和精度风险

新旧 `tokenizer.json` 的原始 SHA 不同，但 version、normalizer、pre_tokenizer、post_processor、decoder、model（含 vocab/merges）、added_tokens、padding、truncation 各部分规范化 JSON SHA 全部相同：120,000 基础词项 + 832 added tokens。BOS/EOS/PAD 为 120000/120025/120002，think 标签为 120029/120030。

新版 `tokenizer_config.json` 指定 `TokenizersBackend`；模板唯一文本差异为移除 `low`，只接受 high/no_think。默认 generation 仍是 temperature 0.9、top_p 1、top_k -1、do_sample=true。精度比较必须显式固定模板、推理模式、seed、长度与采样参数，不能只比较自然语言 prompt。

模型目录没有可直接使用的 `modeling_*.py` / `auto_map`。官方 finetune 依赖声明 Transformers >=5.16.2；这不是“任何推理框架必须升级到 5.16.2”或“低版本一定不兼容”的证据。模型卡部署例使用专用 NVIDIA/FP8 路径，不能把示例参数直接套在 INT8 推理上。

重点未决项是 `swiglu_limit=10`：旧插件使用不截断 SwiGLU，但本次未取得能够确认新版前向行为的官方推理源码/参考 logits。不能擅自打开 clamp，也不能无条件沿用去 clamp。IHC、router、shared/routed 合并和 LM head 的计算精度同样需要新 BF16 数值基线。

## 7. 后续 INT8 产物应携带的信息

至少提供：BF16 来源 revision、量化工具 revision、量化配置/报告、校准集与参数、ignore 列表、weight/activation/scale dtype 和轴、专家布局、完整索引、tokenizer/template、预期精度容差和参考输出。旧 scales 不能复用到新权重。

“INT8”不足以判定兼容：W8A8 与 W8A16、per-channel 与 group-wise、动态与静态激活、对称与非对称，以及 packed 与逐专家格式均可能走不同推理路径。具体 PPU 复用方案见 `ppu/adaptation/new-bf16-int8-readiness.md`。
