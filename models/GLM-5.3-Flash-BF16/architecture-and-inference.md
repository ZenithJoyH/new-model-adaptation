# GLM-5.3-Flash-BF16 模型结构与推理链路分析

## 2026-10-27 MetaX 双机复核

本次范围为 `mx-101`、`mx-102`，目标权重为两机共享 NFS 的
`/public-flash/models/GLM-5.3-Flash-BF16`。现场配置与索引 SHA-256 分别为
`33e63ec7fe607658be712bd6dd3c16c6549960d8e7f0483d34b939881b55f943`、
`e6007bd58fb7e07f9fe69544257ee2713f252ef5855bbf685b48c991d524ef0f`，
与下述历史 BF16 快照一致；120 个分片完整，索引权重大小为 642646653816 bytes
（约 598.5 GiB）。两机各有 8 张 64 GiB C550；仅权重就超过单机总显存，需双机布局。
16 卡平均权重约 37.4 GiB/卡只是容量估算，不能代替加载、通信、状态缓存与图模式验证。

本次安装基线 Plugin 主线 `4e23ae8f` 尚无 `glm5_next` 模型目录或其注册入口；已有
`GlmMoeDsa` 接入不等于支持本模型。FlagGems-vllm `ddce1d66` 已包含 KDA、KPool、mHC
及 GLM 数值测试，须逐项核对参数/缓存/状态契约及 MetaX 实现后复用。现有 HY4 路径也
只能作为可复用接口的候选，不能把该模型当作 HY4 的改名版本。

本次初始上下文按配置最大值 1048576 和流程约束取 50000，后续以真实加载和验证结果
确定并行布局。eager/graph、多模态、MTP、正式精度及性能均未在本次 MetaX 范围内验收。
以下 2026-09 的实现、路径和运行结论属于 PPU 历史，不作为本次通过证据；本次进展见
[MetaX framework 工作区](metax/frameworks/vllm-plugin-fl/README.md)。

### MetaX模型编排与组件验证（2026-10-27）

本次双机采用TP8/PP2进入加载，真实worker rank为PP0/PP1各8卡；每rank KDA和MLA
各8个head。KDA conv按实际SD/DS缓存方向形成 `[slots,3×8×128,3]` 的逻辑view；
recurrent state为dense HVK、FP32 `[slots,8,128,128]`，允许slot间page padding。
混合batch的decode先用自身slot/CU走recurrent，prefill再用框架已有prefill_*与64-token
chunk metadata走bounded-gate scan，不把只覆盖prefill的chunk索引用到decode。

Indexer保留模型32×128投影与KPool4；当前库公共协议为FP8 E4M3值及FP32 scale的132字节
slot，压缩页32/64条，尾部为独立BF16 K/score ring。Q和压缩K在相同Hadamard基底，
Q逐头scale恰好折入weights一次，prefill gather读取真实scale。池top-k通过现有融合
`expand_pools_and_append_tail` 还原token级候选并加入因果尾部。主MLA缓存仍BF16，
压缩Q/K宽512；head8由正式vendor adapter补至64，复用既有稀疏数学kernel，输出裁回8头。
MetaX资源候选按64KiB共享内存选16×16/stage1，未据此宣称性能最优。

mHC在每层保留4路残差；PP边界先完成出站层post mix，再将 `[T,4,4096]` flatten为
16384宽的一个IntermediateTensor，下一stage恢复4路后进入其首层pre。此协议避免丢弃
post/comb；已用实际mHC运算对三种切分与完整执行进行数值/变输入graph对照。

实际Plugin通过惰性registry接入conditional/text配置和模型，视觉权重/processor保留，
没有将checkpoint改成纯文本架构。两机各28项组合回归包含配置、非目标选择隔离、
packed KDA、PP mHC、主KV/sparse adapter及已有Qwen注册；此前库级算子对照另见对应问题。
它们是组件/编排证据，不是整模服务验收。图像/视频整模和MTP尚未验证；当前GLM bounded
KDA对spec metadata显式拒绝，不以未实现的state路由静默运行。完整eager/graph、GPQA198
及性能结论须以MetaX工作区后续原生证据为准。

## 2026-09-06 当前快照复核

此前文档中的“当前插件不含 GLM 文件”已经被后续适配事实取代，不能继续作为 architecture
通过证据。本轮先只读复核唯一 BF16 权重的配置/索引哈希、分片完整性、实际模型类与当前
plugin 中的 GLM5 实现/注册路径，再据结果修正文档并生成新的 evidence binding：

```bash
ssh PPU-13 "docker exec glm5.3-flash python3 -c 'import hashlib,json,pathlib; root=pathlib.Path(\"/mnt/cpfs/models/GLM-5.3-Flash-BF16\"); cfg=json.loads((root/\"config.json\").read_text()); text=cfg[\"text_config\"]; idx=root/\"model.safetensors.index.json\"; shards=sorted(root.glob(\"model-*.safetensors\")); print(\"CONFIG_SHA256\",hashlib.sha256((root/\"config.json\").read_bytes()).hexdigest()); print(\"INDEX_SHA256\",hashlib.sha256(idx.read_bytes()).hexdigest()); print(\"ARCH\",cfg.get(\"architectures\"),cfg.get(\"model_type\")); print(\"TEXT\",{k:text.get(k) for k in (\"model_type\",\"num_hidden_layers\",\"hidden_size\",\"max_position_embeddings\",\"index_topk\",\"index_kpool\")}); print(\"LAYER_TYPES\",{x:text[\"layer_types\"].count(x) for x in set(text[\"layer_types\"])}); print(\"SHARDS\",len(shards),sum(p.stat().st_size for p in shards),all(p.stat().st_size>0 for p in shards))'; docker exec glm5.3-flash bash -lc 'git -C /workspace/vllm-plugin-FL-glm53-hy4-adaptation rev-parse HEAD; git -C /workspace/vllm-plugin-FL-glm53-hy4-adaptation branch --show-current; find /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl -type f | grep -E \"glm5_next|kpool\" | sort; grep -RInE \"Glm5Next|glm5_next|register_model\" /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl --include=\"*.py\" | head -n 320'"
```

> 运行标识：`glm53-bf16-architecture-revalidation-20260906`。重新核验确认唯一目标
> `/mnt/cpfs/models/GLM-5.3-Flash-BF16` 已下载完整，
> 配置 SHA256 为 `33e63ec7fe607658be712bd6dd3c16c6549960d8e7f0483d34b939881b55f943`；
> 120/120 分片存在且非空，总计 642652070880 bytes。以下结论与该正确 BF16 快照一致，
> 错误 FP8 路径的量化结论、补丁和测试不沿用。

## 分析对象与证据

- 模型：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`，顶层架构 `Glm5NextForConditionalGeneration`，`model_type=glm5_next`。
- 快照身份：目录没有可核实的 Git revision；`config.json` SHA-256 为 `33e63ec7fe607658be712bd6dd3c16c6549960d8e7f0483d34b939881b55f943`，权重索引 SHA-256 为 `e6007bd58fb7e07f9fe69544257ee2713f252ef5855bbf685b48c991d524ef0f`。
- 分析日期：2026-09-06；证据来自配置、38,770 个权重键、120 个 safetensors 分片的索引、模型 README，以及容器内当前 plugin 注册和实现路径的只读复核。
- 已验证：权重索引 `total_size=642646653816` bytes，BF16 约 321.3B 参数；README 称总参数 320B、激活 18B。后者属于发布方声明，尚未通过运行时 profiler 独立验证。
- 实现状态：上游 Transformers 5.8.1 和 vLLM `ee0da84a` 本身仍不提供该架构；当前 plugin
  `support-hy4-preview@5329cb1` 的工作树已经包含 `glm5_next` 配置、模型、多模态、算子、
  kernel、v0.24 patch 和注册入口。TP16 文本服务、最小 eager/graph 与 graph c8 sanity 已经
  跑通；graph c64 长负载仍在 plugin-owned kpool decode kernel 暴露非法访存。因此当前
  实现可加载、可基础推理，但尚未完成正式精度验收；视觉/视频与 MTP 也未形成验收证据。

## 模型整体结构

模型是原生图文/视频多模态 conditional generation 模型，由视觉编码器、45 层语言主干、1 层 next-token prediction（MTP）头和独立 `lm_head` 组成，词表大小 154,880，文本隐藏维 4,096，权重 dtype 为 BF16，不共享输入 embedding 和输出头。

语言主干采用混合 attention：45 层中第 3、7、11、…、43 层共 11 层为 `deepseek_sparse_attention`，其余 34 层为 `linear_attention`（配置中的 KDA layers）。线性 attention 为 64 heads、head dim 128，并带 kernel size 4 的短卷积；权重键验证存在 `A_log`、`dt_bias`、Q/K/V conv1d、Q/K/V projection、门控投影、`o_norm` 和输出投影。稀疏 attention 使用 MLA 风格低秩投影（`q_lora_rank=1536`、`kv_lora_rank=512`），64 个 Q/KV heads，QK/V head dim 均为 256，`mla_use_nope=true` 且 RoPE dim 为 0；每个稀疏层都有 32×128 的 Indexer，`index_topk=2048`、4 路 k-pool 压缩并总选尾部 token。配置声明最大位置 1,048,576。

MLP 前 3 层为 dense，后 42 层为 sparse MoE。每个 MoE 层有 288 个 routed experts 和 1 个 shared expert，每 token 选 8 个专家；router 使用 FP32、sigmoid scoring、`noaux_tc`、归一化 top-k 概率与 2.5 scaling。dense intermediate 为 12,288，expert intermediate 为 2,048，激活为带 `swiglu_limit=10` 的 SwiGLU。输入/后 attention 使用 RMSNorm；此外启用 mHC（`hc_mult=4`、`hc_eps=1e-6`、20 次 Sinkhorn），其具体张量重排需以引入的模型实现为准。

视觉分支为 24 层 ViT：448 图像、patch 14、temporal patch 2、hidden 1,024、16 heads、intermediate 4,096，经 spatial merge 2 和 10,240 维投影映射到文本 hidden 4,096。图像/视频 start/end/token ID 已在配置中固定。

## 端到端推理链路

1. tokenizer/processor 将文本与可选图像、视频转成 token 和视觉张量；视觉 encoder 生成 4,096 维 embedding，并在专用 image/video token 位置与文本 embedding 合并。
2. 模型加载把 120 个 BF16 分片映射到 embedding、视觉塔、45 层语言主干、MTP 和 `lm_head`；TP16 下需要对投影、attention heads 与专家权重做符合插件约束的分片。
3. prefill 逐层执行 mHC/RMSNorm，再依据 `layer_types` 走 KDA 线性状态更新或稀疏 MLA。稀疏层先构造/缓存 KV 与 Indexer 表示，计算候选分数并选 top-2048，再对选中 KV 做 attention；线性层维护卷积和 recurrent/state cache。随后进入 dense 或 MoE MLP。
4. decode 每次为新 token 更新两类 cache。线性层复用固定形状状态；稀疏层更新 paged KV/index cache、执行 k-pool/index top-k 和 sparse attention。mHC 合并 residual streams，最终 norm 和 `lm_head` 生成 154,880 logits。
5. runtime 对 logits 做惩罚、temperature、top-k/top-p/softmax 和 multinomial/greedy sampling，解码 token 并流式输出。MTP 若由 vLLM speculative path 启用，则复用 Indexer 并需要额外接受性判断；是否启用须由实际实现和启动参数验证。
6. 当前 plugin 已实例化并运行上述文本 prefill/decode 主链。配置及权重仍是模型结构事实的
   主证据；c64 失败表明 sparse indexer 的 kpool decode 地址合约尚未闭环，不能把整个链路
   视为已验收。多模态和 MTP 路径仍需独立验证。

## 关键算子清单

| 阶段/组件 | 算子 | dtype/shape 线索 | TP/graph 影响 | 证据 |
|---|---|---|---|---|
| embedding/输出 | embedding lookup、`lm_head` GEMM | vocab 154880 × hidden 4096，BF16 | vocab/tensor parallel 与 logits gather | 配置及权重键已验证 |
| 视觉塔 | patch/temporal projection、RMSNorm、QKV GEMM、scaled dot-product attention/softmax、SwiGLU、spatial merge/projector | hidden 1024，16 heads，输出 4096 | 可变视觉 token 数须转为 graph bucket | 配置和 plugin 实现路径已核对；未验收 |
| mHC/residual | Sinkhorn、归一化、受约束 residual mixing | 4 路 expansion，20 iters | 循环与临时张量必须 graph-safe | 配置和 plugin 实现路径已核对；文本 sanity 覆盖整模 |
| norm | RMSNorm、attention `o_norm`、Indexer K norm | BF16 输入，FP32 accumulation 需数值验证 | 融合及原地行为影响 capture | 权重键已验证 |
| KDA 线性 attention | Q/K/V projection、depthwise conv1d(k=4)、gate projection、state scan/update、`A_log`/`dt_bias`、output projection | 64×128 heads | 34 层状态 cache；prefill scan 与 decode update 都需专用 PPU kernel | 配置/权重键和 plugin 实现已核对；整模 sanity 已运行 |
| 稀疏 MLA | low-rank Q/KV projection、cache write、Indexer projection/k-pool、paged logits、top-k 2048、sparse attention、output projection | q rank 1536、kv rank 512、64×256；Indexer 32×128 | TP16 后本地 heads、固定 cache 地址、top-k 宽度和 graph replay 是关键 | 配置已验证；可复用 Hy4 部分路径是假设 |
| dense MLP | gate/up/down GEMM、limited SwiGLU | 4096→12288→4096 | column/row parallel 与 all-reduce | 配置/权重键已验证 |
| MoE | router GEMM、sigmoid、grouped top-k/noaux_tc、dispatch/alignment、expert grouped GEMM、combine、shared expert | 288 experts，top-8，expert dim 2048，router FP32 | TP/EP 布局及 all-to-all/all-reduce；动态 token routing 必须 graph-safe | 配置/权重键已验证 |
| cache | KDA conv/state cache、MLA paged KV/index cache、MTP cache sharing | 上限 1,048,576；初始服务 50,000 | 预分配、block table、capture 地址稳定性 | layout 已实现；kpool tail/cache slot 边界仍在诊断 |
| sampling | penalties、temperature、top-k/top-p、softmax、multinomial/argmax | logits `[batch,154880]` | TP gather 与批量动态形状 | 通用 vLLM 路径推断，待集成验证 |
| 通信 | TP all-reduce/all-gather/reduce-scatter，MoE 可能 all-to-all | TP16 | PYNCCL/accl-lite，graph capture 能力需实测 | 平台既有能力；本模型映射待验证 |

## Plugin、FlagGems 与运行时依赖

- 模型注册/加载：当前 plugin 已提供 `Glm5NextForConditionalGeneration` 入口与 vLLM 0.24
  注册 patch；vLLM 源树保持只读。
- Plugin：当前可修改树为 `/workspace/vllm-plugin-FL-glm53-hy4-adaptation`，基于
  `support-hy4-preview@5329cb1`；GLM5 实现沿既有 dispatch 分层组织。该工作树包含本次尚未
  提交的必要适配改动，不能当作干净上游基线或丢弃。
- FlagGems：`/workspace/FlagGems` 当前 revision 为 `34bd6d68928c8b0039c42987840929da52aa6a62`；
  `/workspace/FlagGems-vllm` 为 `255ab5601b8002b32044fa3632e63eb1b3d45f4e`。已有兼容算子
  经 dispatch 接入；本次首发非法访存已定位到 plugin-owned kpool Triton kernel，而非
  FlagGems clamp/gather。
- 风险：KDA scan/state update、mHC Sinkhorn、复杂多模态 bucket、top-2048 Indexer、288-expert routing、TP16 通信与 MTP 都可能导致 capture-time host sync、动态分配或形状/地址不稳定。

## 适配风险与最小验证

| 项目 | 风险 | 最小验证 |
|---|---|---|
| 上游 Transformers/vLLM 未原生提供 `glm5_next` | 脱离 plugin 会配置加载失败 | plugin 注册/加载已经跑通；持续验证 vLLM 工作树不变 |
| BF16 权重约 598.5 GiB | TP16 平均约 37.4 GiB/卡，仍需视觉、cache、workspace | 只加载配置→逐层 weight mapping→最小 50K 服务显存记录 |
| 新 KDA 线性 attention | 平台可能无 fused scan/update | 与 CPU/PyTorch reference 做 dtype/shape/eager/graph 测试 |
| mHC | 数值敏感且有固定迭代 | 固定 seed 比对每层 mixing 输出和 graph replay |
| sparse MLA/Indexer 与 Hy4 不完全同构 | 错误复用会静默损害精度 | 从权重 shape 到 cache layout 逐项 contract test |
| MoE `noaux_tc`/288 experts/top-8 | routing/布局/通信差异 | router、dispatch、expert、combine 分层数值测试 |
| 多模态 | 文本跑通不代表图像/视频可用 | 文本、单图、短视频各一条最小用例 |

## 结论

架构与实现边界已重新核验：该模型不是 Hy4 的改名版本，而是包含 34 层 KDA、11 层
稀疏 MLA、mHC、288-expert MoE 和视觉塔的新混合架构。当前 plugin 已完成文本主链的注册、
加载和基础推理实现，且复用了经核对的 Hy4 dispatch；仍未关闭的是 c64 下 kpool decode
非法访存、多模态/MTP 验证和正式精度验收。后续修改只针对已证明的运行时缺陷，不再重做
已通过的模型注册或错误 FP8 前缀适配。
