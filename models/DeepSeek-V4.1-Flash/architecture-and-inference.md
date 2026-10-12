# DeepSeek-V4.1-Flash 模型结构与推理链路分析

## 分析对象与证据

- 模型名称：`DeepSeek-V4.1-Flash`
- 目标现场：SSH Host `H100-145`，远端权重目录 `/public/models/DeepSeek-V4.1-Flash`
- 分析日期：2026-09-15（Asia/Shanghai）
- 模型身份：远端目录没有可核实的 Git revision，以关键文件哈希固定本次快照：
  - `config.json`：`8be45ce0476004a3f529fd896115a4a2e800a129ad2d3ec05b16050f52e21879`
  - `model.safetensors.index.json`：`74b0686a3d2891980d5e303251b075a3bccae2c2ff650747db2620a649b98fa8`
  - `README.md`：`347c9db4e5506acb531cbc3b724407ab88e9af8781679152f0823d7bac16d251`
  - `DeepSeek_V41_Tech_Report.pdf`：`ba68e2e40408125ae6d2f63a9a241b61c73910691c74ec1a2a7023c851eac08d`
- 主要现场证据：`config.json`、`tokenizer_config.json`、`model.safetensors.index.json`、48 个
  safetensors 分片、`README.md`、`encoding/` 和 `inference/` 参考实现。
- 公开交叉证据：[DeepSeek 官方发布说明](https://www.deepseek.com/en/news/deepseek-v4-1-flash/)、
  [Hugging Face 模型页](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)、
  [vLLM 官方 recipe](https://github.com/vllm-project/recipes/blob/main/models/deepseek-ai/DeepSeek-V4.1-Flash.yaml)。
- 证据边界：技术报告文件的存在、大小和哈希已在远端核实，但远端缺少 PDF 文本提取工具，且
  安全策略不允许把文件复制到本机。本分析的结构结论以已读取的模型卡、配置、权重张量头和参考
  实现为主；报告全文中未被这些证据复核的细节不作为已验证事实。

## 核心结论

DeepSeek-V4.1-Flash 不是传统的 552B 稠密或普通 MoE 模型，而是一个原生多模态的
`Causal Encoder-Decoder (CED) + CSA2 + MoE + mHC + Engram + DSpark` 组合系统。官方所称
552B 是主干规模；按现场 96,085 个张量头计算，包含 Engram、DSpark/MTP 和视觉组件的完整
逻辑参数量约为 **763.205B**。检查点张量数据为 510,286,023,000 字节，即约
**475.241 GiB**；48 个分片连同头部约 **475.251 GiB**。

官方声明每个输入 token 在 prefill 激活约 8B 参数、每个输出 token 在 decode 激活约 16B
参数。这一不对称性来自 20 层因果编码器和 20 层解码器的 CED 组织方式；它不等于模型只需
8B/16B 的驻留权重。完整权重、Engram 查找表、缓存、算子工作区和图捕获内存仍需单独规划。

H100-145 具有 8×NVIDIA H100 80GB HBM3 和全 GPU `NV18` 互联，张量/专家维度均满足 TP8
整除约束。按随模型发布的 `convert.py` 静态模拟，TP8 转换后每 rank 约需 **62.548 GiB**
权重，距每卡 81,559 MiB 物理显存仅余约 **17.10 GiB**，尚未计入 CUDA context、KV cache、
激活、通信缓冲、TileLang/vLLM 工作区和 CUDA Graph 私有池。因此 TP8 是这台单机的合理起点，
但“权重理论可放入”不等于“1M 上下文服务可运行”。当前 8 张卡还被无关的
`xingchen4-dianxin` 容器占用，每卡约 72.6 GiB，本次未启动或加载该模型。

## 参数与存储构成

下表来自逐个解析 48 个 safetensors 文件头。逻辑参数不计量化 scale 张量；FP4 expert 权重在
文件中以 `I8` 打包，每个字节表示两个 E2M1 值，因此逻辑参数按存储 shape 的两倍计算。

| 组件 | 逻辑参数量 | 当前检查点张量存储 | 说明 |
|---|---:|---:|---|
| 40 层 routed experts | 543.582B | 268.945 GiB | 每层 384 专家，FP4 打包权重与 E8M0 scale |
| 2 个 Engram 表及投影 | 196.929B | 189.127 GiB | 主表为 FP8，按行带 E8M0 scale |
| 主干 attention | 5.127B | 4.798 GiB | 主要投影 FP8，部分输出低秩矩阵为 BF16 |
| 40 层 shared expert | 1.416B | 1.320 GiB | 每层 1 个共享专家，FP8 |
| embedding、最终 norm/head | 1.324B | 2.466 GiB | embedding 与未绑定的 LM head 均为 BF16 |
| router、mHC 与其余主干参数 | 0.118B | 0.294 GiB | 含 FP32 bias、Sinkhorn mixing 参数和 norms |
| DSpark/MTP | 14.225B | 7.388 GiB | 3 个 draft 层，128 routed experts、Top-3 |
| DeepSeek-ViT 与 aligner | 0.485B | 0.904 GiB | BF16 视觉塔、2 层投影和图像边界向量 |
| **合计** | **763.205B** | **475.241 GiB** | 分片文件头另占约 0.010 GiB |

主干去除 Engram、DSpark/MTP 和视觉组件后约为 551.566B，与官方“552B backbone”四舍五入
声明一致；这也解释了模型卡数字与完整权重逻辑参数量之间的差异。

## 模型整体结构

### 文本主干与 CED

- 顶层类为 `DeepseekV41ForCausalLM`，文本配置类型为 `deepseek_v41_text`。
- 主干共 40 层，官方将其组织为 20 层 causal encoder（0–19）和 20 层 decoder（20–39）。
  解码器的全局 KV 从编码器最终隐状态投影，而不是每个解码层独立保存一套全局 KV。
- `hidden_size=5120`，词表大小 129,280；输入 embedding 与输出 LM head 不绑定。
- 每个 block 的 residual stream 使用 `hc_mult=4` 个并行副本。attention 和 FFN 前后分别计算
  `pre/post/comb` 混合系数，`comb` 通过 20 次 Sinkhorn 迭代形成双随机混合；官方称为
  Single-Pass mHC，参考实现由 `hc_split_sinkhorn` TileLang kernel 承担核心计算。
- normalization 为 RMSNorm，文本主干 `rms_norm_eps=1e-20`。这个极小 epsilon 是训练语义的
  一部分，不能用框架常见的 `1e-6` 默认值替代。

### CSA2 压缩稀疏注意力

- 64 个 query heads，每头 512 维；共享 latent KV 为 512 维，配置中
  `num_key_value_heads=1`。每头仅 64 维参与 RoPE，其余 448 维为 NoPE 部分。
- query 投影采用 `q_lora_rank=1280`；输出投影采用 8 组、`o_lora_rank=1024` 的分组低秩路径。
- 所有层均保留 128-token sliding window。具有全局路径的层还从压缩 KV 中选择最多 512 个位置，
  再与窗口 KV 拼接进入同一次 `sparse_attn`。
- 位置编码采用 YaRN：原始长度 65,536，扩展因子 16，最大位置 1,048,576；窗口路径使用
  `rope_theta=10000`，压缩 KV 使用 `compress_rope_theta=160000`。

根据 `compress_ratios`、`kv_source_layer_ids`、`index_source_layer_ids` 和代码中共享运行时，可把
实际静态模式还原如下：

| 层 | 压缩比 | 模式 | 共享行为 |
|---|---:|---|---|
| 0–1 | 0 | SWA-only | 只有 128-token 窗口，无压缩全局 KV |
| 2，8，14 | 2 | Full | 各自产生 2:1 压缩 KV、index K 和 Top-K indices |
| 3–7，9–13，15–19 | 2 | Reuse | 复用最近 Full 层的压缩 KV 与 Top-K indices |
| 20 | 1 | Full + candidate source | 产生解码器共享 KV/index，并建立层级候选块池 |
| 21–23 | 1 | Reuse | 复用第 20 层结果 |
| 24，28，32，36 | 1 | Reindex | 复用第 20 层 KV，在候选池内重算 Top-K |
| 25–27，29–31，33–35，37–39 | 1 | Reuse | 复用最近 Reindex 的 indices |

第 20 层先从最多 2,048 个 block 中构造候选池，每个 block 含 8 个位置；更深的 Reindex 层只在
该候选池内评分，因此索引器开销不会随完整上下文无界增长。压缩器以 learned softmax gate 对
连续 token 分组池化；ratio=1 时退化为一次投影与归一化。

官方给出的持久化 global KV 为 890 bytes/token，并声明相对 V4-Flash 的 HBM 为约 1/4、SSD 为
约 1/8。需要注意，随权重提供的 readable reference 会把 FP4/FP8 cache 量化后再写回 BF16
buffer，用来对齐数值而非复现生产存储占用；它也没有实现 README 所述 SWA Bounded Replay
的持久化/回放管理。因此 890 bytes/token 不能从这份参考代码的 buffer 大小直接复算。

### MoE 与路由

- 每个主干层都有 384 个 routed experts 和 1 个 shared expert；每个 token 激活 6 个 routed
  experts，再叠加 shared expert。
- 每个 expert 是 `5120 -> 2304 -> 5120` 的 SwiGLU：`w1` 为 gate、`w3` 为 up、`w2` 为 down。
  `swiglu_limit=10.0`，up 分支双侧 clamp、gate 分支只做上界 clamp。
- router 使用 `sqrt(softplus(score))`，选择时加入训练得到的 correction bias；视觉 token 使用
  独立的 `bias_vl`。Top-K 权重来自未加 bias 的原始 score，归一化后乘 `routed_scaling_factor=1.5`。
- 官方配置写明 `topk_method=noaux_tc`。任何后端若只支持 softmax/sigmoid router、忽略
  `bias_vl`、省略归一化或 clamp，都会改变模型语义。
- 参考实现按 rank 连续分配专家，局部 expert 输出后执行 `all_reduce`；它用 Python expert loop、
  `torch.where` 和 `.tolist()` 做 dispatch，只适合作为可读性/数值参考，不是生产吞吐实现。

### Engram 条件记忆

- Engram 插入在主干第 1、14 层之前，两张表分别有 384,006,168 和 384,016,682 行，每行
  256 维；总逻辑参数约 196.929B。
- 最多使用 4-gram，8 个 hash heads，基础 hash vocab 为 16,000,000，压缩 tokenizer vocab
  必须精确为 99,092。实现对 token 映射后进行乘法、XOR、素数取模和 offset 组合。
- 图像 span 被标为 dead token，不参与 n-gram，也不接收 Engram contribution，n-gram 不跨越图像。
- 表按行切分到 TP ranks；lookup 后对 FP8 行和 scale 解量化为 BF16，再用 `all_reduce` 合并。
  tokenizer 压缩映射不匹配会让整张表静默重哈希，因此 tokenizer 不是可替换的普通附属文件。

### DSpark speculative decoding

- 配置包含 3 个 MTP/draft 层，读取主干第 37、38、39 层 attention 输入；draft block size 为 5。
- draft 层使用 128 个 routed experts、每 token Top-3，另有 256 维 Markov embedding/head 和最终
  confidence head，用于置信度调度验证。
- `Transformer.forward_spec` 已实现 draft forward，但随附 `generate.py` 从未调用它，实际生成仍是
  plain autoregressive sampling。生产服务若要获得官方 DSpark 加速，必须由引擎补齐 draft 调度、
  acceptance/verification、KV 状态与失败回退；不能把参考脚本的运行速度视为 DSpark 性能。

### 多模态路径

- DeepSeek-ViT 共 32 层，hidden 1024、16 heads、MLP intermediate 2816、patch size 14。
- 每幅图先做 patch projection，再经过带 2D RoPE 的全双向 SDPA 和 SwiGLU MLP。
- aligner 先进行 3×3 `unfold`/pixel-unshuffle，把 9 个视觉 token 合并后，经
  `9216 -> 5120 -> 5120` 两层 MLP 投到语言空间；每图最多 1,024 个视觉 token。
- `<｜deepseek_image｜>` 在预处理阶段扩展为图像 span，语言 embedding 对应位置被视觉 embedding
  和学习到的 start/end/newline 向量覆盖。图像必须完整位于首次 prefill chunk。
- 视觉 token 与文本从语言主干第一层起联合处理，但使用独立的 MoE routing bias。

## 端到端推理链路

1. **协议编码**：模型没有 Jinja chat template。`encoding/encoding.py` 负责多轮会话、工具调用、
   thinking/chat 模式、1–100 数值 reasoning effort、mid-conversation system message 和交错图片。
   V4.1 的 DSML tag 带空格，和 V4 格式不兼容；字符串别名 low/high/max 映射为 50/75/100。
2. **视觉预处理**：图片切成 14×14 patch，经 DeepSeek-ViT 和 3×3 downsample aligner 变成 5120
   维 token；图像边界和换行 token 使用独立学习向量。
3. **Embedding/Engram 准备**：文本 token 做 vocab-parallel embedding；同时根据 tokenizer 压缩
   映射生成每层 Engram hash ids。跨 rank 的 embedding 与 Engram lookup 都用 `all_reduce` 汇合。
4. **mHC 展开**：每个 `[B,S,5120]` embedding 扩展为 `[B,S,4,5120]` residual copies，初始
   `pre_mix` 为 one-hot。
5. **40 层主干**：每层依次执行 Engram（仅层 1/14）、mHC pre-mix、RMSNorm、CSA2 attention、
   mHC post/comb、下一组 mix、RMSNorm、MoE、mHC post/comb。
6. **Prefill cache**：每层写入 128-token ring window；Full 层生成共享压缩 KV，Full/Reindex 层
   生成或更新 index Top-K。官方 CED 优化只需约 8B active parameters/token，但随附 reference 的
   `Transformer.forward` 仍顺序遍历 40 层，不能用于验证生产 CED 计算节省。
7. **Decode**：逐 token 更新窗口 ring；压缩比为 2 的层每两步产生一个新 latent，压缩比为 1 的
   解码器层每步产生；全局 KV 和 indices 在层组间复用。官方声明 decode 激活约 16B/token。
8. **输出头与通信**：最终 mHC collapse、RMSNorm、vocab-parallel LM head；各 rank 通过
   `all_gather` 拼接 129,280 维 FP32 logits。
9. **采样**：temperature=0 时 argmax；否则 FP32 softmax 后以 exponential-noise/Gumbel-max 等价
   方式采样。官方推荐 `temperature=1.0`、`top_p=0.95` 或 1.0，但 reference `sample()` 本身未实现
   top-p 截断。
10. **解码与协议解析**：tokenizer 解码后由 encoding parser 提取 reasoning、正文和 DSML tool
    calls。parser 只处理格式正确的输出，生产前端需额外处理畸形或未闭合结构。

## 关键算子清单

| 阶段/组件 | 算子或符号 | 现场代码位置 | dtype/shape/layout | 并行或 graph 影响 | 证据状态 |
|---|---|---|---|---|---|
| 文本输入 | tokenizer lookup、DSML 编解码 | `encoding/encoding.py` | 129,280 vocab，V4.1 专用格式 | 需前端严格对齐，无 Jinja fallback | 已验证 |
| 视觉 patch | flatten + `nn.Linear` | `inference/vision.py::PatchEmbed` | BF16，588→1024 | 每幅图独立预处理 | 已验证 |
| 视觉 attention | 2D RoPE + SDPA | `vision.py::Attention` | 16 heads×64 | 全双向，图像 token 数影响二次复杂度 | 已验证 |
| 视觉 aligner | pad、`F.unfold`、GELU、GEMM | `vision.py::Aligner` | 3×3，9216→5120→5120 | dynamic image shape/graph bucket 风险 | 已验证 |
| Embedding | `F.embedding` + all-reduce | `model.py::ParallelEmbedding` | BF16，vocab-sharded | TP collective | 已验证 |
| Engram hash | gather、multiply、bitwise XOR、mod | `engram.py::NgramHashState` | int64，[B,S,2,24] | 长上下文 hash cache；tokenizer 强绑定 | 已验证 |
| Engram lookup | embedding、FP8 dequant、all-reduce | `model.py::ParallelEngramEmbedding` | FP8/E8M0→BF16，row-sharded | 约 189 GiB 存储与 TP collective | 已验证 |
| Norm | mean-square、rsqrt、multiply | `model.py::RMSNorm` | FP32 accumulate→原 dtype，eps=1e-20 | 需精确 epsilon/融合语义 | 已验证 |
| mHC | linear、Sinkhorn、加权 sum | `hc_split_sinkhorn` | FP32 mixes，4 residual copies | 自定义 TileLang kernel；图捕获重点 | 已验证 |
| Q/linear | `act_quant` + `fp8_gemm` | `model.py::linear` | FP8 E4M3，32×32 block scale | H100 FP8 路径；动态量化工作区 | 已验证 |
| RoPE | complex multiply / inverse rotate | `apply_rotary_emb` | 每 head 尾部 64 维 | in-place cache 更新与 position binding | 已验证 |
| KV 压缩 | projection、softmax pooling、RMSNorm | `model.py::Compressor` | ratio 2 或 1，FP32 pooling | decode state 与分组边界固定 | 已验证 |
| 稀疏索引 | einsum、ReLU、topk、sort | `model.py::Indexer` | 32 heads×128，Top-512 | TP score all-reduce；动态 top-k | 已验证 |
| 层级候选 | amax、topk、scatter、mask | `select_candidate_blocks` | 2048 blocks×8 positions | shape/bucket 与 graph 固定化风险 | 已验证 |
| 稀疏 attention | `sparse_attn` | `inference/kernel.py` | window KV + compressed KV | 自定义 TileLang kernel，核心正确性/性能点 | 已验证 |
| 输出低秩 | grouped einsum + row-parallel GEMM | `Attention.forward` | 8 groups，rank 1024 | `wo_a` 转换时反量化为 BF16；all-reduce | 已验证 |
| Router | linear、sqrt-softplus、bias、topk | `model.py::Gate` | 384 logits，Top-6 | `bias_vl` 与 noaux_tc 语义不可丢失 | 已验证 |
| Routed experts | FP8 act × FP4 weight GEMM、SwiGLU | `fp4_gemm` / `Expert` / `MoE` | E2M1 packed，K block 32 | H100 上先 FP4→FP8，再做 FP8 GEMM；reference dispatch 不可 graph | 已验证 |
| Shared expert | FP8 GEMM + SwiGLU | `model.py::MoE` | 每层固定 1 expert | 与 routed 输出相加 | 已验证 |
| DSpark | draft blocks、Markov head、confidence | `Transformer.forward_spec` | block=5，3 层，Top-3/128 | 调度/verification 未接入 reference generate | 已验证 |
| LM head | FP32 linear + all-gather | `ParallelHead` | rank-sharded vocab→129,280 logits | 大 logits collective | 已验证 |
| Sampling | softmax、exponential、argmax | `model.py::sample` | FP32 | RNG 与 graph replay 需显式管理 | 已验证 |

## TP8 映射与 H100-145 容量判断

官方转换脚本按如下方式切分：vocab embedding/head、`wq_b`、`wo_a`、`wo_b`、attention sink 和
index weights 按指定维度做 tensor parallel；routed experts 按编号连续分给 ranks；Engram 表按行
切分；`wq_a`、shared expert、router、mHC、norm、视觉塔等未映射模块在每个 rank 复制。

TP8 的整除关系全部成立：129,280/8=16,160 vocab rows，64/8=8 attention heads，8/8=1 output
group，384/8=48 backbone experts，128/8=16 DSpark experts，32/8=4 index heads。按 `convert.py`
处理 `wo_a` 为 BF16、保留 FP4 experts 后，每 rank 的静态权重估算为 62.548 GiB，总转换权重约
500.388 GiB。相比原始 475.251 GiB 增长主要来自复制的小模块和 `wo_a` 反量化。

本机单卡物理容量 81,559 MiB（约 79.65 GiB），因此静态余量约 17.10 GiB/rank。这个余量对
长上下文、CUDA Graph、较大 batch 或 production scheduler 很紧。尤其 readable reference：

- 在构造模型时按 `max_seq_len` 预分配压缩 KV/index buffers；
- FP4/FP8 cache 是量化后回写 BF16，而非真正 packed cache；
- mHC 把 residual stream 扩成 4 份；
- prefill 路径仍遍历 40 层，未体现 CED 的生产计算裁剪；
- MoE dispatch 含 `.tolist()` 和数据依赖 Python loop，无法直接作为 CUDA Graph serving 路径。

所以在 H100 上需要生产级 vLLM 实现和专用 kernels，不能直接把 `inference/model.py` 当作服务
实现。公开 vLLM recipe 要求 vLLM 0.30.0+ 和专用镜像，注明模型不支持 `torch.compile`；其已验证
硬件列表没有 H100。H100 也没有 Blackwell 原生 FP4 Tensor Core，参考 `fp4_gemm` 明确把 FP4
tile 转为 FP8 后再执行 FP8 GEMM，因此仍可利用 H100 FP8，但不能期待原生 FP4 算力收益。

## Plugin、FlagGems 与运行时依赖

- Transformers 配置声明 `transformers_version=5.6.0`，模型类型与类名均为新接口；旧版本
  AutoConfig/AutoModel 不应假定能够注册。
- readable reference 依赖 PyTorch 的 FP8、`float4_e2m1fn_x2`、NCCL、safetensors、Pillow、
  Transformers 和 TileLang 自定义 kernels。
- 本次未选择 environment/adaptation 阶段，未核实任何目标适配容器、editable Plugin checkout、
  vLLM revision 或 FlagGems revision，因此不能声明当前 Plugin 已支持这些新算子。
- 当前占卡容器 `xingchen4-dianxin` 与本模型无关，不能复用其进程、服务或显存作为验证证据。
- vLLM/Plugin 适配必须覆盖 text 与 image 两条路径；只做文本 smoke test 不证明视觉塔、图像 span、
  `bias_vl` 或 2D RoPE 正确。

## 适配风险与待验证项

| 项目 | 依据 | 风险 | 建议的最小验证 |
|---|---|---|---|
| H100 权重与运行时余量 | TP8 估算 62.548 GiB/rank | 图池、workspace 或长上下文 OOM | 先核实专用镜像与真实 loader，记录 load peak；后续初始服务长度按项目规则取 50,000 |
| FP4 expert on H100 | reference 明确 FP4→FP8 | 可运行不代表吞吐优势；kernel 兼容性未知 | 单 expert 数值测试与 H100 kernel 编译，再测 eager/graph |
| CED 执行语义 | README 声明 20+20，reference 仍遍历 40 层 | 生产优化缺失会丢掉 8B prefill 优势 | 与 vLLM CED scheduler/cache 实现逐段对照 |
| SWA Bounded Replay | README 有声明，reference 无对应实现 | 1M 持久化 cache/恢复路径不完整 | 冷/热 KV 恢复、窗口边界和长上下文回放测试 |
| CSA2 层模式 | 4 个 Full、4 个 decoder Reindex、大量 Reuse | source/reuse 错一层即可静默降精度 | 每组层检查 KV、candidate 和 Top-K 一致性 |
| Router 语义 | sqrt-softplus、noaux_tc、bias/bias_vl | 通用 MoE kernel 可能不支持 | 固定输入比较 router scores/indices/weights |
| Engram | 196.929B、tokenizer 强绑定 | 查表驻留、I/O、hash 或 shard 错误 | tokenizer map hash、lookup、跨 TP 合并的逐层对照 |
| mHC | 4 路 residual + Sinkhorn20 | 普通 residual fusion 不兼容 | 参考 kernel 与后端 eager/graph 数值对照 |
| DSpark | forward 有、调度无 | 可能只能普通 AR，或 speculative 接入出错 | 先关闭 DSpark 验主干，再单独验证 draft acceptance |
| 多模态 | 独立 ViT/aligner、VL router bias | 文本通过但视觉失败 | 独立图像 embedding，再做图文一致性 smoke test |
| Prompt protocol | 无 Jinja；V4.1 DSML 与 V4 不同 | 工具调用/思考模式格式错误 | 运行官方 `encoding/test_encoding.py` 并冻结协议版本 |
| Graph | `.tolist()`、Python expert loop、动态 top-k/图片 shape | readable reference 不可直接 capture | 使用生产 backend，逐算子后组合验证 eager 与 graph |
| 当前资源冲突 | 8 卡均被无关 vLLM 服务占用 | 不能安全加载或做性能判断 | 用户明确运行窗口和容器/工作根后再进入 environment 阶段 |

## 已验证事实、推断和未解决问题

已验证事实：远端目录完整包含 48 个权重分片和 96,085 个张量；配置、权重 shape/dtype、参数与
存储分解、参考 forward/量化/TP 切分逻辑、H100-145 的 8 卡拓扑及当前资源占用均通过只读命令
核实。公开官方资料确认 552B backbone、CED、8B/16B active、原生多模态和 KV cache 缩减声明。

基于证据的推断：在所有 GPU 空闲且使用随模型设计的生产 backend 时，TP8 是 H100-145 单机
最合理的首次加载拓扑；权重能放入，但显存余量不足以在没有专用 cache/kernel 设计的情况下
直接保证 1M 服务。H100 上 FP4 的主要收益更可能是权重带宽/容量，而不是原生 FP4 Tensor Core。

尚未解决：当前可用 vLLM/Plugin/FlagGems revision 与专用镜像、生产 CED/SWA replay/DSpark
实现、转换后真实权重峰值、50K/1M cache 占用、text/vision 正确性、eager/graph、精度与性能均
未验证。解决这些问题属于后续 environment、adaptation 和 acceptance 阶段，本次没有执行。

## 2026-09-23 补充：H100-145 W8A8-BF16 变体

上文的 475.251 GiB、FP4 expert、FP8 Engram 与 `wo_a` 转 BF16 的定量分析仅属于
`/public/models/DeepSeek-V4.1-Flash` 原始检查点，不能当作以下量化变体的实测值。
本次选定权重为 `/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`config.json`
SHA-256 为 `319a455c36424ca5bceef21eadfed8572c316d80afc3f79259730fd2e1b4b4ba`。
其文本模型仍声明 `DeepseekV41ForCausalLM` / `deepseek_v41`、40 层、
`max_position_embeddings=1048576` 和 Engram 层 `[1,14]`，因此 CED、CSA2、mHC、
Engram hash、视觉与 V4.1 DSML 的结构语义不能改用 V4。配置 `text_config` 承载
最大位置数；只读查看顶层 `max_position_embeddings` 会得到空值，不能据此猜测上限。

量化协议变为 compressed-tensors `int-quantized`：单一
`w8a8_channel_token` 配置组含 1,478 个 target，权重是静态、对称、逐输出通道
INT8，输入激活是动态、对称、逐 token INT8；另有 76 项排除规则。
这些规则覆盖 MoE expert、共享 expert、attention 的 `wq_a/wq_b/wkv/wo_a/wo_b`、
视觉/aligner 的部分线性层，不能把 FP4/FP8 原版 loader 直接套入。配置的
`flagos_bf16_engram=true` 表示 Engram 表为 BF16，加载器不得强制要求原版的
FP8 scale。H100-149 NV-native 已验证该变体需要视觉 W8A8、BF16 Engram 与分组
INT8 `wo_a` 三项特定兼容路径；该经验仅为 H100-145 Plugin 实现候选，必须在
当前锁定 vLLM、Plugin 和 FlagGems revision 上重新测试。

H100-145 当前 8 张 H100 在本轮环境查看时均为空闲，先前“`xingchen4-dianxin`
占满 GPU”的记录是 2026-09-15 快照，不代表本轮状态。当前 Plugin 路线的
主要前置问题不是显存，而是锁定的 vLLM 0.24.1 安装尚无 V4.1 模型/配置/tokenizer。
Plugin 必须独立提供这些语义并与引擎的模型、分词器和 KV cache 扩展接口对接；
现有 V4 Plugin PR #427 只能作为算子/量化接入参考。由于本轮尚未加载模型，
H100-145 变体的每 rank 权重、运行时峰值、50K 上下文与 graph 池大小仍待实测，
不能沿用原始 FP4 估算或 H100-149 的服务结果。

## 2026-09-24 补充：V4.1 W8A8 的 SWA Q 语义

H100-149 的选定 W8A8-BF16 变体以 TP8 真实权重运行时，首层纯 SWA 的
`q/kv/indices` 对照揭示了一个与 V4 不同的算子协议：V4.1 的 Q 在应用
64 维 interleaved RoPE 前不做 Q RMSNorm，KV 侧仍做自身的旋转和 FP8
缓存写入。H100-149 NV-native V4.1 在其融合算子调用中显式传入
`apply_q_norm=False`；H100-149 FlagOS Plugin 先前复用的 V4 版
FlagGems-vllm 融合算子没有这个开关，总会归一化 Q。相同的 186-token
提示在两边拥有完全相同的 token ID、SWA 有效索引、长度和缩放参数，
但 Plugin 八个有效 Q head 的 RMS 约为 1，原生为 1.37–2.62，首层
注意力输出已分叉。原始张量和结构化对照位于
`H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-attnraw-compare-20260924/summary.json`，
其输入张量分别引用 `h100149-plugin-attnraw-20260924` 与
`h100149-native-attnraw-20260924` 下的文件和 SHA-256。

本变体的 H100 Q RoPE/KV 写入合同应明确区分 Q 与 KV：保留真实 Q 的幅值，
只旋转后 64 维；KV 仍按现有缓存格式写入。FlagGems-vllm 现有融合算子
负责 KV，FlagGems 通用 interleaved RoPE 负责真实 Q；与原生
`apply_q_norm=False` 算子在 1/17/33/64/186-token 输入上得到逐元素相同的
Q 和 KV 缓存，原始结果在同根 `04-runs/h100149-v41-qrope-contract-20260924/`。
这确定了可复用算子合同，不代表长上下文、完整图覆盖或模型精度已通过。
