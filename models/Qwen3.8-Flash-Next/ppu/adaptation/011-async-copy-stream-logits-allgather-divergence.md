# 011：uniform decode graph replay 后 logits all-gather rank 分叉

## 元数据

- 状态：`hypothesis`；关闭异步调度已验证异步路径是必要条件，关闭实际使用的 FlagGems ATen
  替换后 full198 也已稳定完成，说明故障需要 async 与至少一个普通 FlagGems ATen 替换共同出现；
  正在对实际调用集合做分组定位
- 首次出现时间：2026-09-14
- 最后验证时间：2026-09-15
- 模型：Qwen3.8-Flash-Next，BF16
- 平台与 Host 别名：T-Head PPU，`PPU-01`，仅使用 PPU 8–15
- 容器名称：`qwen3.8-flash`
- Plugin / FlagGems / vLLM revision：Plugin 基线
  `939600b323c02c21916f1f76bfb4cd8c2b02578d`，候选 diff SHA-256
  `86fab0c11bac4dba8ab414e8bef55e3a9923b54c0c3c920552af51687530d7e7`；新增通用异步事件补丁
  SHA-256 `09a4bb630fe8ebd82e3d5794b6c546ce013bf9151dfc9bcffdc4a61bf52de539`；FlagGems
  `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：TP8、`FULL_AND_PIECEWISE`、max model len 65536、max seqs 32、max batched
  tokens 4096、capture 1/2/4/8/16/32；GPQA Diamond full198、c64、max generation 60000

## 问题现象

- common-slot graph replay 后增加 T-Head 设备级同步的 full198 运行约 2 小时 29 分后停止推进。
  最终 198 个样本中 110 个记为 timeout，strict 83/198（41.92%）。
- NCCL/PCCL watchdog 报 PG2 `_ALLGATHER_BASE` SeqNum 101524 超过 600000 ms。rank 1–7 已进入该
  collective，rank 0 没有对应 work；input 993280、output 7946240 精确匹配 batch 32 的 logits
  all-gather，即 `32 × 31040` 与 `32 × 248320`。
- 失败不是 top-k kernel 本身：单 PPU 精确 `[32, 248320]`、top-k 20、top-p 0.95 连续 2000 次
  全部通过；真实 TP8 graph replay、graph all-reduce、同 shape logits all-gather、rank 0 采样组合
  连续 120000 轮也在运行期通过。
- 原始服务和正式结果位于
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/accuracy-diagnosis-source-fix-common-slot-sync-20260914/`；
  结果与 samples SHA-256 分别为
  `3e129f7a260f605ad1d97e86543d3c9cce1e4998a4a69a00d70479c768f9da6b` 与
  `28d654e070b41755e09db38a913cbaf69fd8c0f094000d072282cab35026542c`。
- 当前流同步 full198 在约 2 小时 11 分后复现同一签名：PG2 `_ALLGATHER_BASE` SeqNum 85169，
  rank 1–7 的 last completed 为 85168 并已 enqueue 85169，rank 0 没有 enqueue；输入/输出仍为
  993280/7946240。原生 lm-eval 覆盖 198/198，99 timeout，strict 95/198（47.98%）。结果与
  samples SHA-256 为 `fa50e131ea862d94fbce0b1b8f8972346f09b63dad1542294fc8fef8a883bcde`、
  `b87e1e6e26abc84b8fdf3dc4e5e39c0828d5bb419d519d82dfa73585b326a154`。
- `--no-async-scheduling` 单变量 full198 完成 198/198 个 HTTP 200，用时约 3 小时 56 分；全程无
  NCCL/PCCL watchdog、EngineCore fatal、TP rank 分叉或服务端 timeout，服务终态 health 200。
  它把旧故障时间边界从约 2 小时 11 分推进到全量完成，验证异步调度相关路径是服务端停滞的必要
  条件。该轮 strict 114/198（57.58%），73 条输出被原生评测记为 timeout/refusal，低于 88%；这是
  独立的长输出无最终答案问题，不能把通信稳定性对照误记为精度通过。
- blocking event 产品源码 full198 在约 2 小时 15 分后再次停止推进。有效覆盖仍为 198/198，但
  115 条 timeout/refusal，strict 80/198（40.404%）；PG2 `_ALLGATHER_BASE` SeqNum 88432 的 input
  993280、output 7946240，rank 0 再次缺席。结果目录为
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/Qwen3.8-Flash-Next-async-blocking-product-v2-c64-maxgen60000/gpqa-full-c64-maxgen60000-async-blocking-product-20260915-v2/`，
  acceptance-result SHA-256 为
  `6f5c2d242742d107560208eaea91335941377cf63e7b7d450a1c28e3781cb0df`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [003：TP sample_tokens 超时](003-tp-sample-tokens-timeout.md) | 最终由 `sample_tokens` RPC timeout 暴露 | 本轮取得准确 collective shape、sequence 和 rank 缺席信息 | 高 | timeout 只作外层症状，继续查最早 rank 分叉 |
| [008：PCCL graph replay 后 collective work FIFO 停滞](008-pccl-graph-eager-collective-stall.md) | graph、PCCL、长负载和 rank 无进展 | 本轮 ranks 1–7 已进入捕获外 logits all-gather，rank 0 未进入；真实组合最小复现运行期通过 | 高 | 不再把通用 PCCL FIFO 当作唯一解释 |
| [010：Common slot replay 可见性](010-common-slot-graph-replay-visibility.md) | 故障由 replay 后新增同步触发 | metadata 正确性需要 producer 流完成，但不要求等待所有设备流 | 很高 | 把设备级同步缩小为当前流同步 |

## 诊断与假设

已验证调用链如下：vLLM 在所有 TP rank 上执行 `sample_tokens`。各 rank 的异步 runner output 会让
copy stream 等待 default stream，再发起 sampled IDs 的 D2H 并记录 event；只有 output rank 0 把
结果交给异步输出线程，后者调用 `get_output()` 等待该 event。T-Head 使用 logits all-gather，位置在
`execute_model` 的 `compute_logits` / `LogitsProcessor._gather_logits`，早于 sampler。

设备级同步覆盖 copy stream 的解释已被当前流同步反例推翻：只同步 producer 当前流后仍出现同形状、
同 rank 缺席的 logits all-gather。异步调度本身是已验证必要条件，因为所有 TP rank 执行采样，但只有
output rank 把 `AsyncGPUModelRunnerOutput` 交给异步线程并等待 event；它不再与 common-slot 的同步
范围绑定。

源码审查进一步把该变量拆成三个差异：EngineCore 从 `Scheduler` 切为会提前加入 output placeholder
的 `AsyncScheduler`；所有 rank 直接复用前一步 GPU sampled token 作为下一步输入并创建独立 copy
stream；只有 output rank 0 会在 `WorkerAsyncOutputCopy` 线程调用
`AsyncGPUModelRunnerOutput.get_output()`，等待 `async_copy_ready_event`。当前 vLLM v0.24.0 的该 event
以及 `prepare_inputs_event` 都使用默认非阻塞等待。vLLM 后续提交
[`f5ba5da988`](https://github.com/vllm-project/vllm/commit/f5ba5da988fd164b98c6f74e8c0bc241f100ce08)
（PR #47081）把这些 event 改为 `blocking=True`，提交说明明确指出默认 busy-poll 会竞争 CUDA driver
lock，在 TP 竞争下可能放大为单 rank straggler。该上游改动尚未包含在当前 `ee0da84a` 中，且它正好
覆盖 rank 0 独有的 event wait。

现场继续确认 FL 平台不会执行上游 `vllm.v1.worker.gpu_model_runner.GPUModelRunner`：
`vllm_fl/platform.py` 将 worker class 指向 `vllm_fl.worker.worker.WorkerFL`，后者使用插件内约 4900 行的
`vllm_fl.worker.model_runner.ModelRunnerFL` 副本。该副本的两个
`Async*ModelRunnerOutput.async_copy_ready_event` 和 `ModelRunnerFL.prepare_inputs_event` 仍是
`torch.Event()`，所以仅升级或临时修改上游文件不会覆盖实际路径。首次诊断 hook 指向上游类时服务
可启动但 marker 始终为 0；把同一 hook 改到 FL 类后，8 个 TP 进程各记录 hook 安装、blocking
prepare event 和 blocking async-copy event，共 24 条，直接验证实际调用路径和三个事件替换。

具体线程关系也与 rank 分叉方向一致：异步模式下每个 rank 的主线程在每个输入准备临界区调用
`prepare_inputs_event.synchronize()`；只有 rank 0 还会由 `WorkerAsyncOutputCopy` 线程并行调用
`async_copy_ready_event.synchronize()`。在当前版本中两者都是默认 busy-poll event，因此 rank 0 是
唯一可能同时有两个线程竞争同一设备 driver lock 的 rank。若该竞争使 rank 0 未能从 graph replay
或 launch 前返回，ranks 1–7 就会先进入下一次 graph 外 logits all-gather，恰好形成现有 watchdog
签名。该链条已由源码、上游修复说明和本机 blocking-event 压力对照共同支持；full198 仍用于确认
长时间稳态边界。

失败时 scheduler dump 是 32 个 cached request、每个 `num_scheduled_tokens=1`、总 token 32，明确是
batch32 uniform decode。由此排除 mixed prefill/decode 和 graph→eager 转换作为必要条件。更可能的
顺序是：rank 0 在整模型 FULL graph replay 或它之前的 host/device 边界没有返回；rank 1–7 已从 graph
返回并 enqueue graph 外 logits all-gather。由于 captured graph 内部 PCCL work 不会为每次 replay
生成可见的 PyTorch WorkNCCL，十分钟后报告的 logits all-gather 可能只是首个可见的下游受害者。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 采样 kernel | 整模 timeout | 单 PPU 精确 logits shape，top-k 20/top-p 0.95，2000 轮 | `07-bugs/` 下独立 top-k/topp 复现 | 2000/2000，约 2.44 秒 | 排除 top-k 算子单独必现 |
| 2 | graph/PCCL/采样组合 | 整模长负载 | TP8 真实 replay + graph all-reduce + logits all-gather + rank0 采样，120000 轮 | `07-bugs/pccl-graph-sampling-sync-20260914/` | 运行期 120000/120000；只在销毁 communicator 时停滞 | 排除该组合在短时固定次序下必现 |
| 3 | 同步范围 | replay 后设备级同步 | replay 后仅 `current_stream().synchronize()` | `vllm_fl/worker/common_slot_mapping.py` | 单测 4/4；代表 9 题 9/9 HTTP 成功，无异常短输出 | 当前流同步满足 metadata 正确性，并排除显式等待 copy stream |
| 4 | 长稳态 | 设备级同步 full198 在约 2h29m 失败 | 当前流同步；其余服务与 full198/c64/60K 配置不变，增加只读诊断探针 | `04-runs/accuracy-diagnosis-current-stream-flightrecorder-20260914/` | 约 2h11m 后复现；198/198 中 99 timeout，strict 95/198；PG2 `_ALLGATHER_BASE` SeqNum 85169，rank 0 缺席 | 当前流同步未消除长稳态 TP 分叉，common-slot 同步范围不是 timeout 根因 |
| 5 | 异步调度 | 默认 async scheduling | `--no-async-scheduling`，其余服务、源码、graph 和 full198/c64/60K 不变 | `04-runs/accuracy-diagnosis-noasync-flightrecorder-20260914/` | 198/198 HTTP 200，约 3h56m；无 watchdog、EngineCore fatal 或 rank 分叉，终态 health 200；strict 114/198，73 timeout/refusal，精度未过 88% | 验证异步调度相关路径是服务端停滞的必要条件；该开关同时改变三组路径，尚不能单独归因到 event |
| 6 | event 等待语义 | FL runner 三处默认 `torch.Event()` | 仅将真实 FL runner 的 prepare/output-copy event 替换为 `torch.cuda.Event(blocking=True)`；async scheduling、TP8 和 graph 保持开启；诊断长负载专用服务显式关闭 prefix caching | `04-runs/async-blocking-event-stress-service-v4-20260915/` 与 `04-runs/async-blocking-event-stress-c64x6000-20260915/attempt-1/` | 64/64 HTTP 200，384000 completion tokens，64 条均以 length=6000 结束；总耗时 1103.45s，fatal=0，health 200，90s stall monitor 未触发 | blocking event 在真实 FL 执行路径上消除了该固定长度压力负载中的 rank0 停滞；通过两批 32 请求切换边界 |
| 7 | 产品代码归属 | `sitecustomize` 诊断替换 | 把同样三处改动移植到插件通用 `ModelRunnerFL`，移除 hook 后直接重启 | `04-runs/async-blocking-event-product-service-v1-20260915/` | 8 workers、FULL_AND_PIECEWISE capture、async scheduling、HTTP health 和 4-token 推理通过；hook line=0、fatal=0；通用 AST 回归 1/1 | 正式行为来自 Plugin 产品代码，不依赖诊断注入；仍需 full198 长稳态回归 |
| 8 | full198 长稳态 | 修复后仅完成 c64×6000 压力回归 | 产品源码服务保持 async scheduling，执行 GPQA Diamond 198 题、c64、max generation 60000 | `04-runs/Qwen3.8-Flash-Next-async-blocking-product-v2-c64-maxgen60000/gpqa-full-c64-maxgen60000-async-blocking-product-20260915-v2/` | 约 2h15m 后复现；198 有效样本中 115 timeout/refusal，strict 80/198；PG2 `_ALLGATHER_BASE` SeqNum 88432，rank0 缺席，shape 仍为 993280/7946240 | 推翻 blocking event 已根治的假设；短固定长度压力通过不足以覆盖长稳态故障 |
| 9 | FlagGems 普通 ATen 替换 | full FlagGems、async graph 长稳态失败 | 白名单仅保留 8 个 Qwen 必需 ABI 与运行时 5 个 MoE ABI，普通 ATen 替换回退 reference；按项目规则启用 prefix caching | `04-runs/async-minimal-flaggems-service-v3-20260915/` 与 `04-runs/async-minimal-flaggems-stress-c64x30000-20260915/attempt-1/` | 服务完成 TP8 编译、FULL_AND_PIECEWISE capture、async 启动和 health 200；首批请求前在 `mamba_utils.get_mamba_groups` 断言 GDN 与 PLE 的两个 MambaSpec 相等而退出，64/64 客户端连接错误 | 故障发生在算子执行前，不能判断 FlagGems 白名单是否消除长稳态故障；暴露 prefix caching `align` 模式不支持异构 GDN/PLE MambaSpec 的独立适配缺口 |
| 10 | FlagGems ATen 替换 | async blocking-event full198 失败基线 | 精确白名单仅保留 8 个 Qwen 必需 ABI 与运行时 5 个非 ATen 自定义算子；其他服务参数保持一致 | 服务 `04-runs/async-flaggems-no-aten-service-v4-20260915/`；评测 `04-runs/Qwen3.8-Flash-Next-async-no-flaggems-aten-c64-maxgen60000/gpqa-full-c64-maxgen60000-async-no-flaggems-aten-20260915-v1/` | full198 完成，服务终态 health 200，无 collective fatal；strict 173/198（87.37%），9 timeout；结果 SHA-256 `bf7f031e7921448c7153bb33cdf29d6e350083af7953e98f9a2f408435d3bfd7` | ordinary FlagGems ATen 替换是当前 async 长稳态故障的必要交互条件；仍需定位具体算子 |
| 11 | 独立适配实现在线对照 | `qwen3.8-flash` 当前候选，PPU 8–15 | 用户在 `qwen3.8-flash-test` 中维护的 editable Plugin/FlagGems 工作树，PPU 0–7；按用户给定 100000、0.85、19 个 capture size 启动 | 服务 `04-runs/test-container-alt-adaptation-service-v2-20260915/`；评测 `04-runs/Qwen3.8-Flash-Next-alt-test-c64-maxgen60000/gpqa-full-alt-test-c64-maxgen60000-20260915-v1/` | full198 完成，strict 181/198（91.41%），0 timeout；结果 SHA-256 `889ee7b406340b0d0d298ed65cd650885110525da45682cc7a86797abe42e548` | B 稳定且超过 88%；容量和源码均不同，因此只作为对照，不直接证明单项根因 |
| 12 | 实际 ATen 调用集合 | 全部 ATen 关闭时稳定 | 完整 FlagGems 服务记录实际 oplist；随后仅启用运行期/采样/状态更新组，模型数学组回退原生 ATen | oplist `04-runs/flaggems-aten-oplist-discovery-20260915-v1/flaggems-oplist.log`；分组服务 `04-runs/flaggems-aten-runtime-group-20260915-v1/`；full198 run `gpqa-full-c64-maxgen60000-aten-runtime-group-20260915-v4` | oplist 共 73 条记录，短负载 396/396 成功；分组 full198 已启动，响应缓存 0 命中 | 正在定位；`scatter_` 位于 async request reorder 专用输入复用路径，是第一优先候选，不能在长跑结论前标为根因 |

## 根因

- 已验证直接故障：rank 0 没有与 rank 1–7 一同进入 batch32 logits all-gather，导致 PG2
  `_ALLGATHER_BASE` watchdog 超时。
- 已排除：设备级 common-slot 同步和 graph→mixed 路径都不是必要条件。
- 已验证条件：默认异步调度下 rank 0 在 batch32 FULL model graph replay 或之前停住，ranks 1–7
  enqueue 的 logits all-gather 是下游观测点；关闭异步调度后同一 full198 负载完成且无服务端分叉。
- 上游 #47081、FL 副本缺失的三处 `blocking=True`、24 条运行时 marker 和 c64×6000 通过曾支持
  event busy-poll 假设，但产品源码 full198 的同签名反例已证明它不是充分根因。blocking event 可保留
  为与上游一致的通用修复候选，不能再作为本问题根因结论。
- 当前根因仍为开放假设：已验证异步调度和至少一个普通 FlagGems ATen 替换都是必要交互条件；
  FlagGems 单独不是充分条件，因为关闭异步调度的 full198 能完成。源码映射显示 `scatter_` 只在
  async request reorder 的 GPU sampled-token 复用慢路径出现，且固定长度压力负载很少触发该路径，
  因此列为第一候选；需要分组 full198 与单算子复现确认。
- 90 秒 active-request-aware 监控在修复负载中未触发，因此没有新故障栈；这是持续有吞吐的正确结果，
  不能人为触发栈转储替代真实故障现场。

## 解决方法或 Workaround

- common-slot 修复保持在 Plugin 通用 graph wrapper 中；异步修复移植上游 #47081 到 Plugin 通用
  `ModelRunnerFL` 的三个 event 创建点。两者都不含模型名、服务名、机器名或权重路径特判，不修改
  dispatch、模型语义、FlagGems kernel 或 vLLM 工作树。
- 异步补丁位于
  `/mnt/nfs/users/jinghao/qwen3.8-flash/02-issues/async-scheduling-blocking-events-20260915/fl-async-blocking-events.patch`，
  SHA-256 `09a4bb630fe8ebd82e3d5794b6c546ce013bf9151dfc9bcffdc4a61bf52de539`；新增模型通用测试
  `tests/unit_tests/worker/test_async_blocking_events.py`，1/1 通过，`git diff --check` 通过。
- focused tests 覆盖 T-Head 当前流同步、非 T-Head miss path 及原 capture/replay 数值路径，4/4 通过。
- 诊断服务增加 `TORCH_NCCL_TRACE_BUFFER_SIZE=200000`、timeout dump、desync debug、C++ stack 和
  `PYTHONFAULTHANDLER=1`；`sitecustomize.py` 只注册 SIGUSR2 全线程栈，不改执行语义，位于
  `/mnt/nfs/users/jinghao/qwen3.8-flash/02-issues/worker-stack-probe-20260914/`。
- 正式配置位于
  `/mnt/nfs/users/jinghao/qwen3.8-flash/03-acceptance/gpqa-full-c64-maxgen60000-currentstream-86fab0c-20260914.json`；
  SHA-256 `cc158486349ce8ec1aceabf81ebc5dcb9f699b7f3aa5ec73ec12cbfb7db689c2`。
- no-async 正式配置位于
  `/mnt/nfs/users/jinghao/qwen3.8-flash/03-acceptance/gpqa-full-c64-maxgen60000-noasync-86fab0c-20260914.json`；
  SHA-256 `18d604d30370f59932cd58654d13e14ec21ed102a8a73a05b0312047fdf2b9f5`。
- async blocking-event 产品源码正式配置位于
  `/mnt/nfs/users/jinghao/qwen3.8-flash/03-acceptance/gpqa-full-c64-maxgen60000-async-blocking-product-20260915-v2.json`；
  SHA-256 `88b3dd0b77241656fd5b653122c37e3e3f31ccf6b7fdf9e59941ed8735137a1d`；正式 preflight
  SHA-256 `9d3809900904ca7bbd4e1adce160946554cf47a31c460f7fc2814eda0d5ccc32`。
- 适配容器始终保持 running；仅停止并重启了本任务服务进程组以载入诊断环境。vLLM 和 FlagGems
  工作树保持 clean。

## FlagGems 证据

- FlagGems 为 clean `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`；实际调用记录共 73 行，含 5 个
  Plugin 自定义 MoE 调用及普通 ATen 替换。短生成只能证明这些算子可启动和执行，不能替代长稳态验证。
- 精确 top-k/topp 和真实 TP8 sampling 组合均通过，当前无证据把修复放入 FlagGems。

## 验证结果

- 最小回归：当前流同步 focused tests 4/4；代表 9 题 9/9 HTTP 成功，7 stop + 2 length。
- `graph`：`FULL_AND_PIECEWISE` 启动、capture、代表请求和服务 health 通过。
- 长稳态：no-async full198/c64/60K 完成 198/198，服务端稳定性通过；strict 114/198、73 timeout，
  精度低于 88%。结果与 samples SHA-256 分别为
  `ba9f8ec82310b9e87d7dc79ffe712b233a0f4677e9940c89afffed9f4e4754b5`、
  `b5ad2fba48e5c4e11d702d4f4ab8be4942dce4575be9fb551e0a2e5d4b186c1e`；验收收据 SHA-256
  `d6dcc3c5a3ce2dde65b99a9c0c08c594f6ded4add341f42dd1ae16ffec4c46e2`。
- async blocking-event 压力收据：64/64、errors 0、384000 completion tokens、duration
  1103.445s；summary SHA-256
  `db77210009bcd0b937f2e95383b4784c83963b6d3a9945b7d8850652d3a44809`，responses SHA-256
  `29046f55161c17726fb8e74d6a9d0346639f4146fce2a73f8ec09a093c3f3ee3`，runtime markers SHA-256
  `a7f7d79a4fb03066774003ee0d15368fe81ae406a91009da72c7478708613396`。
- 产品源码服务实例 `PPU-01:qwen3.8-flash:2928812:215227663` 直接从四文件候选工作树启动；
  launcher SHA-256 `f45f9d103494e2f0e94482ea48aabd620f516aa819d421371dd43e0db97a06f2`，
  async scheduling、8 workers、graph capture、HTTP 200 和最小推理通过，未加载诊断 hook。
- async blocking-event full198 未通过长稳态：约 2h15m 后相同 collective rank 分叉；blocking event
  短压测证据继续保留，但候选不能据此标为 root-cause fix。
- FlagGems 最小白名单服务的 effective dispatch 只显示 `topk_softmax`、`moe_align_block_size`、
  `invoke_fused_moe_triton_kernel`、`silu_and_mul`、`moe_sum` 使用 `default.flagos`，普通算子已回退；
  首请求在模型 forward 前因异构 MambaSpec 断言退出，尚无算子级归因结论。
- no-ATen 服务实例 `PPU-01:qwen3.8-flash:3089653:216647180` 使用同一精确白名单；启动脚本
  SHA-256 `24a01986efb6c507783b5184a52b305ab768b6c33175282565bdc464590a7a0d`。最小推理通过，
  full198 preflight SHA-256 `bb5ea5b64d330d63c77d86be2a22b7b5034aad7b7a493997a94ef836b2c9097e`；
  本轮配置 SHA-256 `bf8a9eda48d673bfb8b9aebce999dc4355c6819e14971e2610663fb35bf46f30`；
  full198 已完成且无服务挂起，strict 173/198、9 timeout。
- 测试容器对照实例 `PPU-01:qwen3.8-flash-test:1587:216875414` 使用 Plugin branch
  `qwen4-day0-ppu`、HEAD `d3b772acb10d7d5d8196a0975dbffc636a391d8d` 和 10 项现存 dirty 状态；
  tracked diff SHA-256 为 `cdd17a5f7c35f4595266c3db0fd12cf02df262e896454314c611400491bf0b35`。
  vLLM 与当前环境同为 clean `ee0da84ab9e04ac7610e28580af62c365e898389`。FlagGems HEAD 为
  `04fd2407d6cd96280b43346e16895f9106873c15`，工作树报告 4612 项 dirty、tracked diff SHA-256
  `d21b1b7fc92c6db628f42f6970a38bcd85d4af8d054e89bc02db92b7ddaa13be`，在清理来源和变更归属前
  不能把整棵 FlagGems diff 作为可移植修复。
- 对照 Plugin 的可见实现差异包括：T-Head 配置静态 blacklist 大量 ATen op；QSA、PLE custom op
  显式传入并声明修改 KV/state cache；PPU graph output 使用 non-owning tensor view；另有独立
  common-slot graph runner。当前在线日志最终仍只 dispatch `topk_softmax`、`moe_align_block_size`、
  `invoke_fused_moe_triton_kernel`、`silu_and_mul`、`moe_sum`，因此“关闭 ATen 替换后的有效算子集合”
  在两套服务间相同，下一层差异主要落在 graph storage/cache ABI/common-slot 实现和服务容量参数。
- 当前分组 full198 的服务和评测分别位于 `04-runs/flaggems-aten-runtime-group-20260915-v1/` 与
  `04-runs/Qwen3.8-Flash-Next-aten-runtime-group-c64-maxgen60000-v4/`。候选必须越过旧
  2h11m/2h29m 边界并完成全部请求且无 collective fatal。

## 限制与下一步

- 当前流同步仍会阻塞 producer stream，blocking event 会把 CPU busy-poll 改成睡眠等待；性能影响需
  在 correctness 通过后按性能专用服务配置单独测量。
- 产品源码 full198/c64/60K async graph 已失败，不能把 blocking event 作为最终解决方法。
- prefix caching 把该模型切到 Mamba cache `align` 模式；Qwen 适配显式返回 GDN 与 PLE 两种不同
  `MambaSpec`，而当前 vLLM `MambaCopyBuffers` 要求所有 Mamba group spec 完全相等。须先补齐多 spec
  buffer 处理或经设计审查采用等价的统一布局，随后才能继续 FlagGems 单变量对照。
- 如果 full198 再次出现零吞吐，先由 active-request-aware 监控向精确 rank0/rank1 发送 SIGUSR2，
  再核对首个 collective sequence divergence；不通过提高 RPC timeout 隐藏停滞。
- no-async 运行结束后，自动栈监控把服务正常空闲的连续零吞吐误判为停滞并发送 SIGUSR2；触发时
  running/waiting 已为 0、198 个响应已完成、health 仍为 200，因此该栈不是故障现场。后续监控必须
  增加 `Running > 0` 条件，避免把终态空闲当成 stall。
- 当前分组若复现，下一轮只启用 `scatter_`；若不复现，再测模型数学组。定位到单算子后，以请求重排
  压力复现、原生 ATen 对照及 full198 验证闭环。full198 完成前不提交候选。

## 经验沉淀

- 是否可跨模型或平台复用：异步事件修改位于 Plugin 通用 ModelRunner，可复用于所有启用该 FL
  runner 异步调度的模型；当前运行证据仅覆盖 T-Head PPU、Qwen3.8、TP8 graph。common-slot 同步
  仍只验证 T-Head wrapper。
- 知识库处理状态：`rejected-as-sufficient-root-cause-by-full198`
- 候选知识库条目：异步 CUDA event busy-poll、TP driver-lock 竞争与 graph replay 后下游 collective
  rank 分叉。
