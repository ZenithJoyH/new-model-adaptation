# MiniCPM-V-4.7-35B-A3B 架构与推理链路

## 模型身份与证据范围

2026-10-12 按用户确认，将旧名 `MiniCPM-V-4.7-35B` 合入本目录。
以下公共结构整合两份已有分析；[合并记录及原始快照](_shared/model-directory-merge.md)
保留来源，本次没有重新执行模型或远端检查。

两份分析均记录了 2026-09-28 在 `H100-149` 只读检查
`/data/models/MiniCPM-V-4.7/weights/35b-a3b` 的配置、参考实现和 checkpoint。

| 文件 | 已记录 SHA-256 |
| --- | --- |
| config.json | `3973e7ad0bd9f96887341cb134173118b0e445695014a73e736de48e9a9b5646` |
| model.safetensors.index.json | `9908f05c01616fdcce1a5f6b60e5cbfceb8f6bf908ca80552cb39954b6aa2a27` |
| modeling_minicpmv4_7.py | `398ec5cf6a8b31d136fbcaf3671c1be2bc25d3ffc77aa457feec185d26999bd2` |
| mrope_minicpmv4_7.py | `cf6d70719e9e58bbab40612e56efeb6fb5cb7019b0aa780e1536aedb5023b1c3` |

上游权重 revision 尚未核实，文件时间不能代替 revision。以下参数统计仅绑定上述
NVIDIA 本地 checkpoint；模型名称统一不证明其他 Host 的权重文件逐字节相同。

## 模型结构与参数

顶层类 `MiniCPMV4_7ForConditionalGeneration` 包含视觉塔、两级视觉 merger、
Qwen3.5 MoE 文本骨干和独立 `lm_head`，输入支持文本、图像和视频。

- checkpoint 为 1,152 个 BF16 tensor，共 **35,212,875,824** 个参数，
  tensor 数据占 **70,425,751,648** 字节。语言骨干为 34,151,690,880 参数，
  视觉塔 522,299,312，merger 30,686,720，`lm_head` 508,198,912。
  索引引用 17 个 shard，记录中所列 shard 全部存在；文件名带 `of-00018`
  不单独构成缺失证据。
- 文本骨干 `model_type=qwen3_5_moe_text`，共 40 层、hidden size 2,048、
  16 个 attention head、2 个 KV head，head dim 256，词表大小 248,144。
  每四层前三层为 gated delta/卷积线性注意力，第四层为全注意力，
  即 30 个线性注意力层与 10 个全注意力层；线性注意力卷积核维度为 4。
  线性状态与全注意力 KV cache 需要并存。
- 每层有 256 个路由专家，每 token 选择 8 个，另带共享专家。权重包含 packed
  `experts.gate_up_proj`、`experts.down_proj` 和 router。
  “A3B”为变体名称，实际活跃参数量尚未按前向路径统计，不能据此声称精确 3B。
- 视觉塔为 27 层、hidden size 1,152、16 heads、patch size 14 的 ViT。
  第 6 层后可进入窗口注意力 merger，第二级 merger 映射到 2,048 维文本空间。
  此 checkpoint 默认 `downsample_mode=16x`；配置允许 `4x` 保留更多视觉 token。

## 输入与位置编码

1. 图像处理与视频逐帧路径将可变网格 patch 打包成 NaViT 输入，并生成占位符。
   `image_token_id=248056`、`video_token_id=248057`；处理器负责切片、patch 排布，
   视觉特征必须与占位符逐一对应。
2. 视觉塔、窗口 merger 与下采样 merger 产生文本维度特征，替换对应 image/video
   embedding，再进入 Qwen3.5 MoE 骨干及独立输出头。
3. `mrope_mode=canvas`。处理器提供 `image_bounds`、`target_sizes_mrope` 和特殊
   token ID；参考实现按图像边界、视觉网格及结构 token 生成三通道空间位置。
   纯文本使用顺序位置，prefill 计算视觉空间位置，decode 复用 `rope_deltas`。
   简单复制顺序文本位置到 M-RoPE 三通道会改变图像语义。
4. 配置最大位置为 262,144。旧 Plugin 初始分析中的 50,000 上下文目标，与后续
   启动器采用默认 262,144 的记录属于不同轮次；配置上限不代表满长度输入已验证。
   接续时按所选框架和 Host 核对 TP、混合 cache、graph、显存和已接受的上下文要求。

## 并行、算子与框架实现

共同关键路径包括视觉 patch embedding、自注意力和窗口 merger、MoE 路由与 packed
专家矩阵、gated delta/conv 线性注意力、全注意力、canvas M-RoPE、混合 cache 与权重映射。
BF16 是上述 checkpoint 的存储类型，运行时 dtype 和算子选择需分别绑定服务证据。

早期 NVIDIA 分析以 8 张 H100 80GB 为背景，TP8 仅是候选；后续记录包含 TP2，以及
DSpark TP1/TP2 的功能验证，不能将其扩展成 TP8 验证。四套实现入口如下：

| 框架记录 | 实现与历史范围 |
| --- | --- |
| [NVIDIA Plugin](nvidia/frameworks/vllm-plugin-fl/README.md) | 早期 vLLM 0.24.0 wheel 仅有 4.6 adapter，Plugin 尚无 4.7 注册；后续包含 MoE、canvas M-RoPE、统一 adapter 和 DSpark 适配记录 |
| [NVIDIA 原生 vLLM](nvidia/frameworks/vllm-native/README.md) | 早期 vLLM 0.24.0 有 4.6 adapter 和 Qwen3.5 MoE，未注册 4.7；GPU 2/3 TP2 的 eager、图模式及文本/图像/视频结果按各轮次保留 |
| [PPU Plugin](ppu/frameworks/vllm-plugin-fl/README.md) | 独立记录视觉输出、GDN、算子归属、精度及性能问题，不继承 NVIDIA 的通过结论 |
| [PPU 原生框架](ppu/frameworks/vllm-ppu/README.md) | experimental profile 的 eager、图像/视频及图模式功能记录；不代表正式整体验收 |

4.6 adapter 可以作为多模态接口、视觉路径与权重映射参考，但顺序 M-RoPE 和文本骨干
需逐项对照，不能仅登记模型别名。Plugin 的 general plugin 注册入口历史记录为
`vllm_fl:register_model`；具体安装版本与修改范围以选定工作区的环境记录为准。

## 仍需核实的边界

- 上游权重 revision、实际活跃参数量、各 Host 的 checkpoint 身份与每设备内存占用。
- 复杂、高分辨率图像切片及视频帧的 canvas 元数据正确性；原生历史小样本图像和两帧
  视频通过，不代表任意多模态输入均通过。
- 早期 GDN 的 full graph 降级、后续 `FULL_AND_PIECEWISE`、decode-full 等记录
  均按具体轮次解释；prefill 全图、满长度输入和长期稳定性不能从配置名推断。
- 各框架当前服务、正式精度、性能与镜像交付是否满足其 profile，需使用各自证据。
  此次公共分析合并没有改变阶段状态或重算历史证据哈希。
