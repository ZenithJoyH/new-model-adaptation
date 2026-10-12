# 008：PCCL graph replay 后 collective work FIFO 停滞

## 元数据

- 状态：`partially-verified`；PCCL work FIFO 直接卡点已验证，graph→eager 边界假设已被后续
  `FULL_AND_PIECEWISE` uniform-decode 反例推翻
- 首次出现时间：2026-09-11 18:08:37 +08:00
- 最后验证时间：2026-09-14
- 模型：Qwen3.8-Flash-Next，BF16，served model `Qwen3.8-Flash-Next`
- 平台与 Host 别名：T-Head PPU，`PPU-01`，仅使用 PPU 8–15
- 容器名称与镜像：`qwen3.8-flash`；容器 ID
  `806fa222e7bfdbc074ed1d29ec50f7b1bbb1f7d3a8730e3340700807f0923cac`
- Plugin / FlagGems / vLLM revision：Plugin `939600b323c02c21916f1f76bfb4cd8c2b02578d`；
  FlagGems `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 通信运行时：`libpccl.so.2.1.0` 报告 `PCCL 2.1.0-11-accl-p`、commit `bc333f0`、
  build time `2026-04-28 11:09:52`；PyTorch `2.10.0` 的 `torch.cuda.nccl.version()` 报告
  `(2, 27, 3)`。两个版本标识属于不同层，不能据此推断 vendor PCCL 已包含对应 NCCL 修复。
- 执行模式与负载：TP8、`FULL_DECODE_ONLY` graph、max model len 65536、max seqs 32、
  max batched tokens 4096；GPQA Diamond 198 题、客户端并发 64、`max_gen_toks=60000`

## 问题现象

- FlagGems `vstack` 分桶修复后的正式 v3 在 113/198 个请求返回后再次停止生成。服务吞吐从
  约 340 token/s 降到 9.4，再降为 0；1800 秒无进展后 EngineCore 报
  `TimeoutError: RPC call to sample_tokens timed out` 并退出。
- 最后一步为 31 个 decode token 与 1 个 340-token 新 prefill，共 371 tokens；32 running、
  31 waiting，KV usage 20.51%，没有 preemption、recompute 或 eviction。最长两个请求已计算
  58285 与 57095 tokens。
- API/EngineCore 退出后八个 TP worker 成为 PPid=1 的孤儿进程，持续高 CPU 自旋且 PPU 利用率
  为 0。现场采样确认 TP0 主线程在 `sched_yield`，直接调用者是
  `libpccl.so.2.1.0!ncclLaunchKernelBefore_NoUncapturedHggc+0xb5`。
- v3 receipt 为 failed：113 条 HTTP 响应、85 条服务失败，strict 86/198。该分数受服务退出污染，
  不能代表模型精度。
- 精简现场证据：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/02-issues/pccl-graph-eager-transition-20260911/v3-live-orphan-stack-summary.txt`，
  SHA-256 `92ea1360ec84dd2d5ca2c855c9497d5be6e518a7f195a189738ee4451b3b5e2a`；原始服务日志位于
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/gpqa-formal-service-2aacb2ed-20260911/service.log`。
- 上游修复与 PCCL 二进制对比证据：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/02-issues/pccl-graph-eager-transition-20260911/upstream-fifo-fix-comparison.txt`，
  SHA-256 `158cff1612ecb356fa13059c78c44ae42bbdafe0d21b14f959e0769ef91316d6`。
- `qwen3.8-flash-test` 与正式适配容器的镜像、源码 revision、PCCL 二进制及 vLLM graph mode
  对比证据：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/02-issues/pccl-graph-eager-transition-20260911/test-container-graph-mode-comparison.txt`，
  SHA-256 `979c1605300a8b32772f406e1b758602a1e449efbb778cd7f33a000b61d5303a`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [003：TP sample_tokens 超时](003-tp-sample-tokens-timeout.md) | TP worker 不返回，随后 RPC timeout | v3 没有已记录的 work sequence 分叉；现场栈给出 PCCL work FIFO 等待 | 中 | 保留通信死锁诊断方法，不继续放大 timeout |
| [007：vstack 动态特化](007-vstack-dynamic-shape-stall.md) | 都在混合 prefill/decode 长负载停滞 | v3 cache 保持 115，18:00 后没有任何 Triton cache 写入 | 高 | `vstack` 修复有效但不是完整根因 |
| Hy4 018 长输出停滞 | 都是长输出后混合步骤无返回 | Hy4 为 99% KV 与 recompute；本轮只有 20.5% KV 且无 preemption | 高 | 排除 Hy4 的 KV 满载/重算触发链 |
| [NVIDIA NCCL #1251](https://github.com/NVIDIA/nccl/issues/1251) | 栈同为 `sched_yield` → work FIFO available 等待 → `ncclLaunchKernelBefore_NoUncaptured*`，并在多 rank graph 执行后确定性发生 | 本轮为 vendor PCCL/PPU，尚未取得其源码或确认派生版本 | 很高 | 判定为同一类 FIFO 消费停滞机制，具体补丁归属仍待最小复现与 vendor revision 核验 |
| [NCCL commit ee3d92b](https://github.com/NVIDIA/nccl/commit/ee3d92b8063059813636045697b2704d0b9d4e49) | 修复 persistent graph plan 的 channel `workFifoSent` 与 device ACK 不一致，正好解释后续 uncaptured launch 等不到可用 slot | PCCL 使用 Hggc 专用 graph 队列，源码结构并非逐行等同 | 很高 | 作为最可能的软件根因；在最小复现前不宣称厂商库缺少相同一行代码 |
| [TGI #2099](https://github.com/huggingface/text-generation-inference/pull/2099) | TP4/TP8 CUDA graph 推理出现相同栈；其复现由 NCCL 2.22.3 消除 | TGI 为 NVIDIA H100，当前是 PPU/PCCL 2.1.0 | 高 | 将通信库修复版本核验列为首选根因方向，不直接替换当前共享运行时 |

## 诊断与假设

已验证事实：TP0 和 TP1 在两秒 syscall 采样中均大量调用 `sched_yield`；TP0 为 160851 次。
TP0 主线程的立即调用点解析为 PCCL 的
`ncclLaunchKernelBefore_NoUncapturedHggc(pcclComm*, ncclKernelPlan*)`。反汇编显示该位置循环检查
PCCL work FIFO slot 的 byte `+0xe`，只要设备侧未清除“已消费”标志就持续 yield，下一条非捕获
collective 无法入队。proxy/UDS 线程仍存活，未见 Python 异常、OOM、非法内存或 JIT 进展。

公开上游问题给出了近乎相同的现场栈与行为：NVIDIA NCCL #1251 在 graph 执行若干轮后停在
`waitWorkFifoAvailable`，随后进入 `ncclLaunchKernelBefore_NoUncapturedCuda`；其最小复现先捕获一次
100000 元素 BF16 all-reduce，再循环执行 49000 元素的非捕获 all-reduce，并注明由 commit
`ee3d92b` 修复。该 commit 的具体改动是：persistent mode 不再增加
`comm->channels[c].workFifoSent`，否则 host sent counter 会与 device ACK 不一致。TGI #2099 记录
其 TP4/TP8 推理复现通过升级到 NCCL 2.22.3 消失。该对应关系强烈支持“通信运行时的 graph
work FIFO 消费/复用缺陷”，但当前库是 vendor PCCL，仍需本机最小复现或 vendor 变更记录来
确认它是否携带同类错误。

PCCL 二进制对比进一步确认了状态边界：`ncclPrepareGraphWorks` 位于 `0x184ab0`，
`ncclLaunchKernelBefore_NoUncapturedHggc` 位于 `0x185710`；两者访问相同的每通道 FIFO 计数区
（channel stride `0x200`，相对 channel base `+0x120/+0x128`）。后者按 `+0x128` 选择 slot，
在 `0x1857b0` 检查 slot `+0xe`，并于 `0x1857c0` 在标志未清零时持续 `sched_yield`。这与现场
PC `0x1857c5` 完全相符，但 PCCL 的 Hggc 队列结构不同于上游 CUDA 实现，仅凭反汇编不能确认
缺失的是同一行 guard。

vLLM `FULL_DECODE_ONLY` 的首次失败发生在从 uniform decode graph 转 mixed eager 的附近，因此该
边界曾被列为高可信触发条件。后续反例已经推翻“必须切换到 mixed eager”：采用
`FULL_AND_PIECEWISE` 的 current-stream 候选在失败时，scheduler dump 明确为 32 个 cached request、
每个各调度 1 token、`total_num_scheduled_tokens=32`，即完整 batch32 uniform decode；rank 1–7 已
enqueue graph 外 logits all-gather SeqNum 85169，rank 0 没有 enqueue。当前结论收敛为长时间整模型
graph replay/PCCL graph work 生命周期问题；可见 logits all-gather 是第一个被 watchdog 观测到的
下游 collective，不足以证明最早停点就在 `_gather_logits`。

用户提供的 `qwen3.8-flash-test` 启动命令与上述失败路径并不等价。检查时该容器内没有 vLLM
服务，只能确认这组参数曾完成加载与 graph capture，尚无同一 full198/c64/60K 长负载证据。两个
容器使用相同 vLLM revision `ee0da84a`，`libpccl.so.2.1.0` 的 SHA-256 也相同；因此现有证据不支持
由新版 vLLM 或 PCCL 解释差异。测试容器的镜像以及 dirty Plugin/FlagGems 工作树与正式适配容器
不同，不能作为干净源码对照。2026-09-12 22:41 再次检查时，测试容器仍只有入口 shell，没有
vLLM 服务进程。更关键的是，`FULL_AND_PIECEWISE` 会让 mixed prefill/decode 使用
piecewise graph，而正式 v3 的 `FULL_DECODE_ONLY` 会让同一步转入 uncaptured `NONE` 路径。前者
可能绕开已经观测到的 graph→uncaptured PCCL FIFO 边界，但必须在正式 clean revisions 上以相同
全量负载受控复测，启动成功本身不能证明该边界长期稳定。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 现场栈采样 | 仅有 `sample_tokens` RPC timeout | 保留已退出父进程的 TP worker 并解析 host/container PID、pstack、strace 与 PCCL 符号 | 精简证据见上 | TP0/TP1 均在 PCCL launch 前 busy-spin；work slot 未清除 | 将直接卡点从 RPC 收敛到 PCCL work FIFO |
| 2 | 执行模式 | `FULL_DECODE_ONLY` graph | `--enforce-eager`，其余服务、全量 GPQA、c64、60K 与采样参数不变 | 启动脚本 `02-issues/pccl-graph-eager-transition-20260911/start-model-eager.sh`；配置 `03-acceptance/gpqa-full-c64-maxgen60000-2aacb2ed-eager-ab-20260911.json` | 完成 198/198，服务无 fatal；39 条客户端最终 timeout，strict 153/198=77.27% | eager 越过 graph 的 113 响应停滞点并完成服务侧工作，支持 graph 路径是停滞必要条件；该轮精度低于 88% |
| 3 | PCCL graph 生命周期 | 纯 eager TP8 all-reduce | 先 capture 一次 100000 元素 BF16 all-reduce，再做 100000 次 49000 元素 eager all-reduce | `07-bugs/pccl-graph-eager-fifo/run.sh`；结果 `04-runs/pccl-fifo-eager-r2-20260912/` 与 `04-runs/pccl-fifo-capture-20260912/` | eager 基线 100000/100000 且 exit 0；capture 用例也完成 100000/100000，但 8 rank 卡在 `destroy_process_group()`，采样后精确终止 | 小张量用例未复现整模 launch 前 FIFO 停滞，但 graph capture 会导致 communicator 清理异常，支持 PCCL graph 生命周期缺陷方向 |
| 4 | mixed-step graph 模式 | `FULL_DECODE_ONLY`，mixed prefill/decode 为 uncaptured | `FULL_AND_PIECEWISE`，其余 maxlen 65536、maxseq 32、maxbatch 4096、0.90、capture 1–32 不变 | `02-issues/pccl-graph-eager-transition-20260911/start-model-full-and-piecewise.sh` | clean revisions 下连续两次在启动 profile 的 FlagGems `normal_` HGGC ELF 加载中段错误；只将通用 `normal_` 回退原生后，PIECEWISE mixed 与 FULL decode 的 6 个尺寸均捕获成功，服务 200，确定性最小推理返回 `2` 后仍健康 | 该模式能够启动并执行，且避免 mixed step 转入 uncaptured；`normal_` 是独立启动缺陷，full198/c64/60K 长负载仍待验证 |
| 5 | 真实 replay、collective 与采样组合 | 旧最小用例只 capture graph，未执行 `graph.replay()` | 每轮依次执行 graph replay、graph-captured all-reduce、精确 `[32, 31040] → [32, 248320]` logits all-gather、rank 0 top-k/top-p 采样和同步，共 120000 轮 | `07-bugs/pccl-graph-sampling-sync-20260914/`；结果 `04-runs/pccl-graph-sampling-sync-120k-20260914/` | 八个 rank 均在约 459.46 秒完成 120000 轮，运行期无 collective 分叉；随后卡在 `destroy_process_group()`，采样后只终止该复现 worker | 排除“graph replay + PCCL + 精确 logits all-gather + top-k/top-p 本身必然在运行期停滞”；communicator 销毁异常是独立的 graph 生命周期问题 |

## 根因

- 已验证直接根因：PCCL 在新的非捕获 collective launch 前等待 work FIFO slot 被设备消费；该
  标志持续不清零，TP workers 忙等，最终由 1800 秒 `sample_tokens` RPC timeout 暴露并终止服务。
- 当前假设与缺失证据：`FULL_AND_PIECEWISE` current-stream full198 的失败调度是 batch32 纯
  decode，并非 mixed step，因此 graph→uncaptured 边界不是必要条件。eager 全量对照已经完成，
  2026-09-14 的 120000 轮真实 replay/collective/sampling 组合又未在运行期复现，说明整模停滞还依赖
  vLLM 异步调度、流依赖、主机线程竞争或更完整的 Qwen collective 次序。下一步必须在吞吐刚变为零
  时取得 rank 0 Python/C 栈，判断它是否仍停在 `graph.replay()` / PCCL launch 前；不能用十分钟后的
  logits all-gather watchdog 代替最早卡点。communicator 销毁异常继续单独保留。

## 解决方法或 Workaround

- 当前不修改 Plugin、FlagGems 或 vLLM 源码，也不再增大 timeout；1800 秒内完全没有设备进展。
- 相同 full198/c64/60K 的 eager 对照已经完成。它只用于定位，不替代最终 graph 验收。
- 已将 NCCL #1251 的 Python 复现按 TP8/PPU 改写到
  `/mnt/nfs/users/jinghao/qwen3.8-flash/07-bugs/pccl-graph-eager-fifo/`。runner 会在 vLLM 或
  GPQA 仍运行时拒绝启动，并将输出写入 `04-runs/`。eager-only 基线已正常退出；capture→eager
  完成全部 collective 后卡在 communicator 销毁。runner 的 rendezvous 已从无法解析的 standalone
  主机名改为显式 `127.0.0.1:29538`，该改动只修复进程初始化，不改变 PCCL 被测变量。
- 已在正式 clean revisions 上完成 `FULL_AND_PIECEWISE` 启动与最小推理。启动期间发现并单独记录
  FlagGems `normal_` HGGC 加载段错误；运行时追加通用 `normal_` 原生回退后通过，详见
  [009：FULL_AND_PIECEWISE 启动时 FlagGems normal_ HGGC 加载段错误](009-full-piecewise-flaggems-normal-hggc-segfault.md)。
  下一步运行 `FULL_AND_PIECEWISE` 单变量全量对照：保留 v3 的
  full198/c64/60K、max model len 65536、max seqs 32、max batched tokens 4096、GPU memory 0.90
  与 capture sizes 1/2/4/8/16/32，只改变 graph/compile 模式。用户命令中的 100000、0.85 与
  capture sizes 至 128 暂不同时引入，以免混淆变量。
- 现场采样后只终止容器内 PID 2038557–2038564 及对应 resource tracker；验证端口 8038 空闲、
  无本任务 worker，容器 ID 与 running 状态不变。PPU 0–7 的其他任务未操作。
- vLLM 工作树保持 clean `ee0da84ab9e04ac7610e28580af62c365e898389`。

## FlagGems 证据

- FlagGems 工作树保持 clean `support-qwen3.8-flash@2aacb2ed7b116baee0acc147cdc770b4176a6cdd`；
  本轮只通过既有通用 blacklist 机制让 `normal_` 走原生实现，没有修改源码。
- v3 停滞时 `vstack` cache 为 115，未继续增长；18:00 后无新 Triton cache 文件。当前没有证据
  指向新的 FlagGems 算子缺陷，不新增 FlagGems 补丁。

## 验证结果

- 最小回归：eager 100000/100000、exit 0；capture→eager 100000/100000 运算完成，但 communicator
  销毁超过 4 分钟仍未退出，采样后终止，exit 1。两轮日志 SHA-256 分别为
  `c216e85c7c9cfefd8d51a53ea42b802ef9cf62b9838c5a4ca7a2d1500a9e234e` 与
  `06cd7f864d2b255d7835fa76eac1eecdb0e241e765ff16948abbf419055c54e5`。
- 2026-09-14 更正：上述 capture 用例没有调用 `graph.replay()`，不能支持“replay 后运行期正常”的
  结论。新的真实 replay/collective/sampling 用例完成 120000/120000，八 rank 运行期均正常；仅
  `destroy_process_group()` 未返回。`repro.py`、`run.sh`、运行日志 SHA-256 分别为
  `b54c652edca4c0bf78947a80cc00535fd424d0eb9258648663766230723011e4`、
  `6f346ec9f59b067080fe8dbac167f33115c601c3b87995f5d5fe17c10fc9cbab`、
  `345c1679d2a76ec4d8038b03e71f729beb69536b793285907721f195b6c8fc45`。
- `eager`：全量 198/198 结束，服务无 RPC/EngineCore fatal；39 个客户端 timeout 计零后 strict
  153/198（77.27%），低于 88% 门槛。eager 已越过 graph v3 的停滞边界。
- `graph` capture/replay：启动阶段 1/2/4/8/16/32 均成功；正式 v3 长时间运行后在 graph→eager
  混合步骤失败。
- `FULL_AND_PIECEWISE`：在 `normal_` 通用原生回退下，mixed PIECEWISE 与 decode FULL 的
  1/2/4/8/16/32 全部捕获成功；最小请求返回 `2`，HTTP 200，随后 health 200。响应 SHA-256
  `d65c19d081ae31583502469051bb801083718991ef9b1ea4bbbd242c204dc8db`。
- 最终结论与通过标准：只有 eager 对照越过至少 v3 的 58K/57K 最长序列区间，或更小固定负载
  稳定复现 graph 失败且 eager 通过，才能把状态提升为 verified。

## 限制与下一步

- 当前 pstack 因容器与宿主机 PID namespace/调试符号限制，完整 C++ caller chain 不可得；但主线程
  PC、PCCL 函数、work-slot 循环和 syscall 计数均已解析。
- 根据已完成的 eager 对照构造 31 decode + 1 prefill 的固定负载；若只在 graph 失败，再核对
  PCCL 版本已知修复或 vLLM graph 边界同步点，避免在模型通用 Plugin dispatch 中加入模型名例外。
- `FULL_AND_PIECEWISE` 启动和最小推理已通过，但仍需同一 full198/c64/60K 全量对照。若通过，
  则将其作为候选运行配置，
  再分别评估其精度、吞吐和资源开销；只有完成全量负载才可替代当前正式 graph 配置。
- run id `gpqa-full-c64-maxgen60000-2aacb2ed-fullpiecewise-normal-aten-20260912` 曾完成
  198/198，无请求错误、客户端 timeout 或服务 fatal；它只证明该次随机序列没有在旧的
  graph→uncaptured 边界停住。其 strict 仅 114/198（57.58%），随后加入 common-slot 可见性修复的
  `FULL_AND_PIECEWISE` current-stream full198 又在 batch32 纯 decode 复现 rank 分叉，因此该模式
  不能继续记作通信稳定性 workaround，也不能作为已验收运行配置。
- `NCCL_GRAPH_MIXING_SUPPORT` 文档描述的是多个 graph 与非捕获 collective 的重叠控制；当前
  vendor `libpccl.so` 未发现该环境变量字符串，且 NCCL #1251 的报告在该开关启用时仍可复现，
  因此不把设置该变量当作已验证修复。
- 当前证据不改变 Plugin PR 范围；任何修复归属需由最小复现决定。

## 经验沉淀

- 是否可跨模型或平台复用：PCCL work FIFO 与 graph/uncaptured 边界的取栈方法可复用；具体故障
  目前仅验证于 Qwen3.8-Flash-Next、当前 PPU SDK/PCCL revision。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：`sample_tokens` 超时后通过孤儿 worker 主线程解析 PCCL work FIFO 停滞。
