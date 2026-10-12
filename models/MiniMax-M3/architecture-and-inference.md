# MiniMax-M3 架构与推理链路

核对日期：2026-09-15。本文只描述模型结构与推理链路；PPU 环境、Plugin 差距、实施和验收分别记录在 `ppu/` 下。

## 1. 对象、来源与证据等级

本轮对象是 `PPU-13` 上容器 `minimaxM3` 可读的 `/mnt/cpfs/models/MiniMax-M3`。该目录没有可核实的 Git revision，当前快照由以下只读证据固定：

- `config.json` SHA-256：`c9c97ce1e4eece60012d5a10ea87717458bfb1f19c2c7a615a3dbff83d090c6b`；
- `model.safetensors.index.json` SHA-256：`54dbde502126d07f6999077437a06b5df1f71e317518956d0aad1c8197df524e`；
- 权重索引声明 `23,416` 个 tensor、`869,157,697,024` bytes，目录实际占用约 `796G`；
- 59 个 safetensors 分片，配置架构为 `MiniMaxM3SparseForConditionalGeneration`，内层文本架构为 `MiniMaxM3SparseForCausalLM`；
- 模型卡声明总参数约 `428B`、每 token 激活参数约 `23B`、原生支持文本/图像/视频与 1M context。参数量声明尚未通过逐 tensor 元素重算，不能代替权重完整性校验。

当前 vLLM 源码 revision `ee0da84ab9e04ac7610e28580af62c365e898389` 已包含 MiniMax-M3 的 config、registry、文本/视觉模型、MSA indexer、稀疏 attention、MTP、reasoning parser 与 tool parser。下文“当前实现”指这个只读源码；是否可在 PPU 上工作必须由后续环境与适配阶段实测，不能由 NVIDIA/ROCm 代码存在推断。

证据分级：

- **已验证事实**：当前远端配置字段、权重索引名称/数量/总字节、小文件哈希，以及上述 vLLM revision 中的实际类和调用路径。
- **结构推导**：各 TP rank 的 head/张量分片、KV 与 index cache 需求、主要 collective 和 graph 稳定性要求。
- **上游声明**：428B/23B、1M context 和 MSA 加速倍率；本轮尚未独立复现。
- **未验证项**：完整 payload checksum、图像/视频质量、MTP/speculative decode、1M 实际服务能力以及 PPU 上稀疏内核的数值和性能。

## 2. 配置与完整结构

### 2.1 顶层多模态结构

顶层 `MiniMaxM3SparseForConditionalGeneration` 由视觉塔、图像 token 压缩/投影和文本语言模型组成：

| 组件 | 已核实配置 | 作用与主要形状 |
|---|---|---|
| Vision encoder | hidden 1280，32 层，16 heads，MLP 5120，patch 14，最大图像边 2016 | 图像/视频 patch embedding、32 层视觉 attention/MLP、3D RoPE |
| Patch merge | spatial merge 2，temporal patch 2 | 将空间 2×2 patch 以及视频时间 patch 压缩为视觉 token |
| Multimodal projector | projection/输出 hidden 6144，带 bias，GELU | 把视觉特征对齐到语言模型 hidden |
| Modality token | image `200025`，video `200026` | 处理器把图像/视频占位符替换为相应 embedding 序列 |
| Text backbone | hidden 6144，60 层，vocab 200064 | 融合文本与视觉 embedding 后执行自回归解码 |

当前 vLLM 多模态 wrapper 对 image/video 注册 processor；视觉塔可在 `mm_encoder_tp_mode=data` 下按 rank 分配样本，否则各 rank 复制执行。图像/视频 grid、动态分辨率、3D RoPE、patch merge 后 token 数和占位 token 对齐均属于后续组合验证范围。

### 2.2 文本主干

| 项目 | 配置与权重协议 |
|---|---|
| 输入/输出 | vocab `200064`，hidden `6144`，embedding 与 LM head 不共享 |
| 主干 | `60` 层；第 0–2 层为 dense FFN，第 3–59 层为 sparse MoE |
| Attention | `64` query heads、`4` KV heads、head dim `128`，GQA scale 为 `128^-0.5` |
| 位置编码 | partial RoPE，只旋转 `64/128` 维；`rope_theta=5,000,000` |
| 长度 | `max_position_embeddings=1,048,576`；按项目规则初始服务应使用 `--max-model-len 50000`，不能以缩短上下文掩盖问题 |
| 归一化 | Gemma-style RMSNorm，eps `1e-6`；Q/K 为 per-head norm |
| Dense FFN | 中间维 `12288`，`SwiGLU-OAI`，`alpha=1.702`、`beta=1.0`、clamp limit `7.0` |
| Routed MoE | `128` experts，top-4，expert 中间维 `3072`，sigmoid router，FP32 gate/logits，带 FP32 correction bias |
| Shared expert | 每个 MoE 层 1 个 shared expert，中间维 `3072` |
| Routed scale | top-k 权重归一化，输出乘 `2.0` |
| MTP | 配置含 `7` 个 MTP module，`num_nextn_predict_layers=1`；普通自回归加载器当前显式跳过 `mtp.*`，需作为独立 speculative 范围验证 |

### 2.3 MiniMax Sparse Attention（MSA）

前三层使用普通 dense GQA；第 3–59 层启用额外 index branch 和 block-sparse attention：

- 主 Q/K/V 与 index Q/K 由一个融合投影产生；主 Q heads 为 64，KV heads 与 index heads 都为 4，主/索引 head dim 都为 128。
- Q/K 先做 per-head Gemma RMSNorm，再执行 64 维 partial RoPE；index Q/K 具有独立 norm，并复用同一位置编码。
- index key 使用独立的 key-only side cache。Indexer 对历史 KV block 打分，选择 top-16 blocks，并包含配置规定的 local block；block/page size 都为 128。
- `sparse_disable_index_value` 在全部稀疏层为 1，因此本 checkpoint 不创建 index value/output projection。
- main KV cache 与 index side cache 分开分配。Indexer 把 top-k block id 写入持久 buffer，稀疏 attention 从同一稳定地址读取，以避免 graph replay 冻结 Python 值。
- 当前非 SM100 路径选择 Triton indexer 和 Triton sparse attention；SM100 才可能选择专用 MSA 实现。PPU 虽使用 CUDA-like PyTorch 接口，也不能被当作 SM100，需验证 capability guard 与 Triton 内核是否可编译执行。
- 当前实现把 indexer 与 sparse attend 包在 `eager_break_during_capture` 区间；这意味着外层 graph 可以工作不等于稀疏内核已被完整捕获，验收需要分别记录实际 graph coverage 和 replay 正确性。

## 3. 端到端推理链路

### 3.1 初始化与加载

1. tokenizer/chat template 将 messages、thinking 模式、图像/视频占位符编码为 token 与多模态输入。
2. `MiniMaxM3Config` 解析顶层 `minimax_m3_vl`，把 `text_config` 转为文本 config；registry 构造 conditional-generation wrapper。
3. 视觉塔、projector、文本 embedding、60 层 decoder、final norm、LM head 和两类 KV cache 按配置初始化。
4. loader 把 `q_proj/k_proj/v_proj/index_q_proj/index_k_proj` 装入融合 QKV+index projection，把 dense/shared 的 gate/up 装入 fused gate-up；expert `w1/w2/w3` 映射为 gate/down/up。普通主模型路径跳过 `mtp.*`。
5. TP 分片投影、vocab、LM head 和 MoE 权重；加载后地址与 graph buffer 必须保持稳定。

### 3.2 Prefill

文本 embedding 与视觉 projector 输出在占位 token 处合并成 `[T,6144]` hidden states。每层执行：input Gemma RMSNorm → dense 或 sparse GQA → row-parallel output → fused all-reduce + post-attention norm → dense FFN 或 MoE。前三层执行完整 dense GQA；后 57 层先写 main/index cache，再用 indexer 选择 top-16 blocks，只对选中块执行稀疏 attention。MoE 对每 token 计算 128 路 FP32 router logits，sigmoid + correction bias 选择 top-4，执行 routed experts，与 shared expert 合并后进入下一层。

### 3.3 Decode 与缓存

每个新 token 通过 `slot_mapping` 写入主 paged K/V cache 和 index key cache。Indexer 基于当前 `seq_lens`、`block_table`、init/local block 与 top-k 规则生成选中块；sparse attention 只读取这些块。Decode-first mixed batch、uniform speculative batch、跨 128-token block、padding/空 slot、不同长度请求及 cache dtype 都会改变 metadata，必须在 eager 与 graph replay 中覆盖。

### 3.4 输出、采样和接口

60 层后执行 final Gemma RMSNorm、TP vocab-parallel LM head、logits processor，再按 generation config 进行采样。当前快照建议 `temperature=1.0`、`top_p=0.95`，BOS/EOS 为 `200019/200020`。服务层还会经过 MiniMax-M3 reasoning parser 与 tool parser；内容正确但 thinking/tool 边界解析错误仍是功能失败。

## 4. 并行、资源与 graph 约束

- 目标容器通过 PyTorch runtime 实测可见 `16` 张 PPU-ZW810E，每卡 96 GiB，总原始显存约 1.5 TiB。约 809.47 GiB 的权重索引总字节按 TP16 粗分约 50.6 GiB/rank，静态容量上可容纳权重，但仍须为 KV cache、activation、vision、collective 与编译 workspace 留余量；不能仅凭总容量宣称加载必然成功。
- TP16 时 64 Q heads 每 rank 4 heads；4 KV/index heads 小于 TP world size，因此按当前 vLLM 逻辑复制 KV/index heads，每四个 rank 共享一个逻辑 head。hidden `6144`、dense intermediate `12288`、expert intermediate `3072` 均可被 16 整除。
- 当前 MoE 构造使用 FusedMoE；是否启用 expert parallel 必须由实际 launch config 与 worker topology 证明，不能由 128 experts 推断。
- RowParallel attention/FFN、vocab/LM head 和专家组合需要 TP all-reduce/all-gather；rank 分支与 collective 顺序必须一致。
- graph 要求 top-k buffer、main/index cache、metadata buffer、workspace 与 tensor shape/address 稳定；不得在 capture 中读取 device scalar 做 host 分支、动态分配或依赖数据变化的 Python 控制流。

## 5. 关键算子清单

| 阶段 | 关键算子 | PPU 验证重点 |
|---|---|---|
| Tokenizer/processor | BPE、chat template、image/video resize/patchify/grid、占位替换 | thinking/tool token、动态分辨率、图像/视频 token 数 |
| Vision | Conv/patch embedding、QKV GEMM、3D RoPE、softmax/PV、LayerNorm、GELU MLP、patch merge | 多帧与 grid 形状、BF16 数值、graph/DP encoder 模式 |
| Embedding/LM head | embedding lookup、vocab-parallel GEMM、logits gather | vocab 200064 的 TP padding、权重不共享 |
| Norm/残差 | Gemma RMSNorm、fused add+norm、fused all-reduce+norm | 权重的 `1+weight` 语义、in-place alias、FP32 累积 |
| Projection | QKV+index fused GEMM、row/column parallel GEMM | 5 路切片、KV/index head 复制、weight loader 映射 |
| RoPE | partial NeoX RoPE、Q/K 与 index Q/K norm+rotation、cache insert | rotary dim 64、长位置、slot mapping |
| Indexer | paged score、max reduce、mask、top-k、init/local block 合并 | top-16、block 128、有效长度、稳定 out buffer |
| Sparse attention | selected-block QK、scale、causal mask、softmax、PV、split-K decode | GQA head 映射、BF16/FP8 cache、eager break 与 replay |
| Dense/shared FFN | fused gate/up GEMM、clamp、sigmoid/SiLU、mul、down GEMM | SwiGLU-OAI `alpha=1.702,beta=1,limit=7` |
| Router/MoE | FP32 gate GEMM、sigmoid、bias、top-k、normalize、expert dispatch/grouped GEMM/combine | top-4、128 experts、shared expert、routed scale 2 |
| KV/cache | scatter/write、block table、slot mapping、paged gather | main K/V 与 index key cache 的独立布局和生命周期 |
| Sampling/API | softmax、top-p、RNG、EOS、reasoning/tool parser | 固定 seed、结束条件、OpenAI-compatible schema |
| 通信 | TP all-reduce/all-gather；可选 EP collectives | 16 rank 顺序、错误传播、graph 下通信与超时 |

## 6. 已确认风险与初始适配决策

- vLLM 已有 MiniMax-M3 模型代码，但 Plugin README 尚未把 M3 列为端到端支持模型；“代码存在”不等于 PPU 可用。
- 当前文本实现直接依赖 `flashinfer.norm`、`vllm._custom_ops.fused_minimax_m3_qknorm_rope_kv_insert`、Triton index/sparse kernels 和 FusedMoE。每一项都可能在 PPU 的 empty-device vLLM + Plugin override 下缺实现或 ABI。
- `vllm` 安装包来自 `/workspace/vllm` 的非 editable direct URL，而 import spec 指向 site-packages；必须把源码 revision、安装产物与实际调用路径分别记录，且禁止修改 vLLM。
- TP16 的静态权重容量可行，但约 50.6 GiB/rank 的粗分尚未计入视觉塔复制、KV/index cache、activation 与 runtime workspace；完整加载前仍要做资源 admission，不得靠把 `--max-model-len` 调小来掩盖其他内存问题。
- 配置声明 1,048,576 context，但项目规定初始服务取 50,000；这只是初始正确性配置，不代表 1M 已验证。
- 当前普通 loader 跳过 MTP 权重；首轮先建立非 speculative 自回归正确性。MTP、视觉、视频和 1M long-context 分别列为独立能力，不由文本 smoke test 推断通过。
- 正式验收必须先通过 eager 与 graph，再在 graph 服务做并发 10 sanity、至少并发 32 的完整精度，最后切换到显式 `--no-enable-prefix-caching` 的性能专用服务；任何较早阶段通过都不能替代后续证据。
