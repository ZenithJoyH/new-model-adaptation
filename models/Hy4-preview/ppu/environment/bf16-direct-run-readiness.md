# 官方新版 BF16 在当前 PPU 容器中的直接启动可行性

核对日期：2026-08-28。目标：`PPU-13` / `hy4-graph`。权重是 `Tencent-Hunyuan/Hy4-preview@ada7b1faf9b70585edc90a9ef552d0059fb246e7`，不是 Eco-Tech W8A8。仅做只读分析，没有加载权重或更改服务。

## 结论

**不能在当前启动参数不变、仅替换模型路径的情况下直接提供 BF16 服务。** 模型架构和 packed BF16 loader 有可复用实现，插件也有 BF16 未量化 MoE 分支；这不等于新版全模型 eager/graph 已经运行成功。当前首先存在明确的显存预算缺口。

## 当前启动参数已重新核实

`/mnt/nfs/users/jinghao/hy_v4/start_hyv4_final.sh`：TP16，max_model_len=50000，max_num_seqs=32，max_num_batched_tokens=1024，gpu_memory_utilization=0.8，no-Inductor + FULL_DECODE_ONLY，capture sizes=[1,32]；没有显式指定 quantization、dtype 或 CPU offload。

因此不是启动命令强制 INT8 而无法解析 BF16；量化选择依赖权重配置。不能通过只添加 `--dtype bfloat16` 解决内存预算或运行路径问题。

## 容量估算（乐观下界，不是实测显存）

由前次全部 131 分片头统计，总 payload 为 1,559,983,576,308 bytes。保存的完整 MTP 张量集合共 27 项，10,053,583,936 个元素、20,107,167,872 bytes。当前普通模型 loader 跳过 MTP，因此同时给出排除 MTP 的估算，不能把全部 MTP 权重一律算入服务。

| 项目 | 数值 |
|---|---:|
| 含 MTP 全权重 payload | 1,452.85 GiB |
| 不含 MTP 主模型 payload | 1,434.12 GiB |
| 主模型理想 TP16 均分 | 89.63 GiB/卡 |
| 单卡物理容量（历史 ppu-smi） | 96 GiB |
| 当前 0.8 的单卡预算 | 76.8 GiB |
| 权重均分已超预算 | 约 12.83 GiB/卡 |

89.63 GiB 尚未计算复制参数、FP32 router/LM-head 的运行时存储变化、临时 workspace、通信缓冲、KV cache 和 graph 开销。即使设备完全空闲、跳过 MTP，当前预算也不足；实际失败阶段可能是加载、显存规划或 KV-cache 初始化，未启动实测，不能编造某条 OOM 日志。

把利用率直接提高到 0.95 也不能保证当前 50K/32 并发/graph 能运行：91.2 GiB 的预算相对理想权重只多约 1.57 GiB，尚未扣上述开销。

## BF16 执行路径证据及边界

当前插件 baseline `85754c1f7884e2f2c85edf4af52e20211d46c22e`（既有 dirty 工作树）：

- `models/hy_v4.py` 的 packed expert loader 支持 gate/up 拆分及 expert 加载；模型结构识别与官方新版一致。
- `ops/fused_moe/layer.py` 为未量化 MoE 选择 `UnquantizedFusedMoEMethodFL`，保留量化方法的独立分支。
- `ops/fused_moe/fused_moe.py` 在 quant_config=None 时使用未量化配置，允许 BF16 dtype。
- `ops/fused_moe/fused_moe_utils.py` 包含 OOT/FlagGems 的 TritonExpertsFL 选择路径。

这证明代码并非只支持 INT8，**不证明新版 HYV4 的全部 BF16 GEMM/MoE shapes、backend 选择、数值精度和 graph 已验收**。swiglu_limit 的新版语义也仍需核对。

## 下一步边界

若要尝试 BF16，需另行做资源方案：短上下文、单请求、eager 起步，评估更高显存预算、更多卡/节点或受支持的 CPU offload，然后定向验证未量化 MoE、加载和数值。CPU offload 是否适合此平台/graph 及性能成本尚未测试，不作为现成解决方案承诺。

复查命令：`./scripts/playbook .local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-bf16-readiness.yml --limit PPU-13`。最终只读检查 ok=4、changed=0、unreachable=0、failed=0；公共 syntax-check 和新增 playbook syntax-check 均通过。本轮没有服务生命周期操作、性能测试或模型运行验收。

## 双机方案补充（2026-08-28，静态可行性）

用户计划使用双机。**若两台均为 16 × 96 GiB PPU，且用一个跨机模型实例将权重切分到 32 张卡，容量上可行。** 第二台 host alias、设备空闲情况、互联和容器尚未提供或检查，不能记录为已验证主机。

| 容量项 | 估算 |
|---|---:|
| 32 卡物理显存合计 | 3,072 GiB |
| 0.8 利用率下合计预算 | 2,457.6 GiB |
| 主模型（不含 MTP）理想均分 | 44.82 GiB/卡 |
| 含 MTP 全部权重理想均分 | 45.40 GiB/卡 |
| 主模型权重以外的预算余量 | 约 31.98 GiB/卡，尚需扣除复制参数、workspace、KV 与 graph 开销 |

不能把“两台各启动一份 TP16 服务”视为解决方案：那是复制完整模型，不会降低单实例每卡的权重需求。

### 并行方案候选

- **TP32、PP1、暂不开 EP/MTP**：可作为首轮兼容性验证候选。保留一条完整主干，避免新的流水线状态传递；64 attention heads 可按 32 rank 分成每 rank 2 heads，hidden/intermediate 等主要维度可整除。不过相较已测试 TP16，BF16 MoE 分片形状、2-head sparse MLA padding、跨机 collectives 和 graph 都需要定向验证；不声称性能最优。
- **TP16、PP2**：可保留机内 TP、以流水线边界承载跨机通信，但当前 HYV4 的 Index Cache 复用不能被忽略。2026-08-28 源码快照中 `HYV4Model` 的 PP intermediate 仅包含四路 `streams`，没有传 top-k indices；默认均分 78 层若采用 39/39，第二段从 shared Indexer 第 39 层开始，会依赖前段第 37 层的索引。需要核对/处理边界（例如选择 full Indexer 层起始的合法分段，或实现明确的索引状态传递）并做数值测试；`SupportsPP` 声明不等于已验证该切分正确。此为源码推导风险，未启动 PP2 复现。

### 双机成立的前提与验证边界

两机须具备匹配的 PPU runtime/通信库、推理依赖和插件工作树；只使用相同镜像 tag 不足以保证既有插件补丁相同。需要可访问同一固定版 BF16 权重、匹配的分布式启动方式及可用跨机互联。不得假定现有 IB/IPv6 配置能在未指定的第二台机器上原样成立。

实施先做环境和 `test/nccl_test/` 通信连通性验证，再做 BF16 代表算子/加载、短上下文单请求 eager 正确性，随后验证跨机 graph 与并发；正式精度通过后才开始最终性能测试。容量可行不代表已经验收 50K 上下文、32 并发、graph、MTP 或吞吐指标。

本次只补充静态分析；未访问第二台机器、未更改容器或服务、未运行跨机推理。
