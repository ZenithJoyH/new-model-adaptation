# 018：2026-09-08 精度评测新故障

## 元数据

- 状态：`verified`（根因修复已通过定向回归；正式全量 acceptance 待执行）
- 首次出现时间：2026-09-08 11:50:14 +08:00
- 最后验证时间：2026-09-10
- 模型：Hy4-preview W8A8 linear MoE，served model `hy4`
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器名称与镜像：`hy4`，镜像 ID
  `sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f`
- Plugin / FlagGems / vLLM revision：Plugin
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`，`support-hy4-preview` ahead 1 且保留既有
  `PROVENANCE.md` 删除和 `thead.yaml` 修改；FlagGems 位于
  `sparse-mla-opt-w8a8-moe-fix@bca444b8569294e7d4e4deff7ddfec7f05682033`；vLLM detached
  `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 执行模式与负载：精度评测失败时 scheduler 为 48 个 running、16 个 waiting，
  KV cache usage `0.9922091412742382`，已记录 1 次 preemption

## 问题现象

- 用户报告：重启服务进行精度评测时出现新的报错。
- 当前直接致命签名：`TimeoutError: RPC call to sample_tokens timed out.`。
- 发生顺序：当前已见 shared-memory dequeue 超时，随后 EngineCore fatal、worker 收到父进程
  退出、API 批量 HTTP 500 并关闭；最早 worker 异常和 TP work 序号仍待聚焦核实。
- 检查时容器仍运行，但无 vLLM/EngineCore/API 进程，8010 未监听；`hy4-preview.log`
  大小 1,674,604 bytes，mtime 为 2026-09-08 11:50:17 +08:00。
- 超时前 11:20:09 的 generation throughput 仍为 211.2 token/s，11:20:19 降为
  119.9 token/s，11:20:29 变成 0.0；从 11:21:15 到 11:49:16 每分钟持续出现
  `No available shared memory broadcast block found in 60 seconds`，11:50:14 命中 1800 秒
  RPC timeout。其间没有新的完成吞吐记录。
- fatal dump 中 47 个请求各调度 1 个 decode token，另一个被恢复请求一次重算 4441 tokens，
  单步总调度量 4488；多数请求已生成约 7287 tokens，说明再次进入长输出与 KV 压力场景。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 002 SQLite 并发锁 | 都发生在精度评测期间并可能导致服务退出 | 当前尚无错误签名 | 低 | 仅在首错包含同一 SQLite DDL 锁链时复用 |
| 016 bool slice | 都可能在首批请求准备阶段击穿 TP worker | 当前服务应使用修复后的 FlagGems 分支，启动 blacklist 未核实 | 低 | 核对首错 dtype、调用栈和 launcher 环境 |
| 017 c32/W8A8 large-M | 都与 GPQA 并发和修复分支后的服务有关 | 当前尚不清楚是数值、超时还是进程退出 | 中 | 核对当前 revision、并发、最早异常与 worker 状态 |
| `distributed-sample-tokens-timeout.md` | 若出现 worker/RPC timeout 可能相关 | 尚未满足完整三段签名 | 低 | 不先调大 timeout；先找最早失败 rank |

## 诊断与假设

已验证直接失败为 EngineCore 等待 `sample_tokens` worker RPC 超过 launcher 已配置的 1800 秒。
超时前服务已经有 48 个 running、16 个 waiting 请求，KV 使用约 99.2%，大多数运行请求已生成
约 7.3K tokens；一个被 preempt 的请求恢复时需重算 4441 tokens，使本步总 token 数达到 4488。
服务在本步前仍有吞吐，进入本步后 30 分钟没有完成记录。

当前高可信假设：017 的长输出/KV 压力在更大在途请求集合下触发 preemption/recompute，形成一个
超大混合 prefill+decode 步；某个或多个 TP worker 在该步的模型执行/采样路径挂起或耗时超过
1800 秒。日志没有 worker 异常栈和 work 序号分叉，因此尚不能定位到具体 FlagGems kernel、
Plugin dispatch 或 collective，也不能把 `sample_tokens` timeout 自身当作最终根因。

已排除：SQLite 锁、bool slice、显式 OOM/非法内存、服务启动失败。本轮 FlagGems DB mtime 未变化，
而且没有数据库错误。Triton `tl.where` warning 在多个 rank 出现，但没有时间戳，不能证明 30 分钟
内仍有有效编译进展，也不能单独定位故障算子。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 无，只读现场检查 | 用户报告的新失败 | 不重启、不改代码/配置/数据库 | `./scripts/playbook /private/tmp/inspect-ppu07-hy4-latest-eval-failure-20260908.yml --limit PPU-07` | 首轮因 YAML regex 歧义按规则停止；修正后成功，确认 `sample_tokens` RPC timeout 与服务退出 | 不是 SQLite/bool slice；还不能区分慢算、worker 异常或 TP 分叉 |
| 2 | 无，聚焦首错上下文 | 轮次 1 的 2400 行尾部 | 超时前 120 行、全局错误索引、完整 revision、当前 PPU 状态 | `./scripts/playbook /private/tmp/inspect-ppu07-hy4-sample-timeout-context-20260908.yml --limit PPU-07`；`./scripts/accelerator-check --limit PPU-07` | 直接错误仅为 sample_tokens timeout；未命中 SQLite、bool slice、OOM、非法内存或 work 序号；检查时 PPU 已空闲 | 不满足已知三段式 timeout 条目的完整签名 |
| 3 | 无，压缩关键证据 | 轮次 2 输出含长 scheduler dump | 仅取最终 160 行、启动脚本、准确 commit 与最近 run 名称 | `./scripts/playbook /private/tmp/inspect-ppu07-hy4-sample-timeout-compact-20260908.yml --limit PPU-07` | launcher 已设 1800 秒；fatal 步为 47 decode + 4441-token recompute，准确 revision 如元数据 | 不能再通过盲目增大 timeout 处理 |
| 4 | 无，区分慢编译与卡死 | 已确认 launcher timeout 为 1800 秒 | 只读提取最后 autotune/compile、吞吐/preemption 事件及缓存文件元数据 | `./scripts/playbook /private/tmp/inspect-ppu07-hy4-timeout-progress-20260908.yml --limit PPU-07` | 11:20:29 后吞吐无完成进展；FlagGems DB mtime 仍为 09-02，未发生本轮持久化调优写入；仅见无时间戳 Triton warning | 按停止条件，不把 timeout 继续调大；当前更像高压重算步挂起而非 SQLite 调优 |

## 根因

- 已验证根因：直接终止原因是 `sample_tokens` RPC 超过已配置 1800 秒；服务退出和 HTTP 500
  是其后果。形成该超长步的确定条件是长输出、接近满载 KV、一次 preemption/recompute 和
  4488-token 混合调度。
- 当前假设与缺失证据：具体卡住的 rank、调用和 kernel 未被现有日志记录；需要用更小的受控
  请求集合和按 rank 进度/stack 采样重现，不能仅凭 EngineCore dump 指认 FlagGems 或 Plugin。

## 解决方法或 Workaround

- 不增大 timeout：当前已为 1800 秒且最后 30 分钟无完成进展，符合停止该 mitigation 的条件。
- 建议的下一受控对照是保持 revision、采样和 graph 配置不变，只把在途并发恢复到 017 已验证
  的 c8 小批量；若通过，再以 c16/c32 阶梯找出触发 preemption/recompute 和挂起的最小负载。
  这属于后续诊断建议，本轮没有执行或重启服务。
- 本轮当前只读，不修改 Plugin、FlagGems、vLLM、服务、容器或生产数据库。

## FlagGems 证据

- 当前没有确定的 FlagGems 算子异常或数值错误，暂不新增 `08-bugs` 用例。FlagGems DB
  `/root/.flaggems/hy4-tp16.db` mtime 仍为 2026-09-02 18:06:25，排除本次 SQLite 调优写入。

## 验证结果

- 只读诊断完成：PPU-07 reachable；`hy4` 容器 alive；服务进程已退出、8010 未监听；评测容器
  仅有历史 defunct Python 进程；当前 PPU 空闲。未修改远端文件、数据库、源码或进程。

## 限制与下一步

- 尚存限制：失败后的日志无法恢复具体 rank 的 Python/C++ stack 或当时 PPU 利用率；当前只能
  确认负载条件和直接超时，不能声称具体 kernel 根因。
- 后续动作：若用户要求继续修复，先在新服务上做 c8 小批量健康对照，再阶梯增加并发并在
  触发前采集每 rank stack/PPU 状态；一旦某个 rank 报算子异常或 work 序号分叉，立即停止并
  转入对应最小复现。不得直接恢复全量高并发或继续增大 1800 秒 timeout。

## 经验沉淀

- 是否可跨模型或平台复用：尚未判断。
- 知识库处理状态：`local-only`
- 候选知识库条目：无。

## 2026-09-08：用户重启后的阶梯复验与 80K 全量轮

用户重启服务后，本轮先核对服务实例
`PPU-07:550e93f0ba4c:2724059:155832651` 为 TP16、100K、`FULL_DECODE_ONLY` graph，health 200，
并确认主机、模型容器、评测容器看到的批准根 device/inode 均为 `41:21477849219`。保持 revision
和服务配置不变，短请求 c8、c16、c32 分别达到 8/8、16/16、32/32，耗时 25.6828、28.2953、
69.7900 秒；c32 后服务 0 running、0 waiting、0 preemption，未出现本问题的致命签名。

按用户授权随后启动 GPQA Diamond 全量 198 题、并发 32、thinking/high、模型默认采样和
`max_gen_toks=80000`。preflight 验证数据集 198 条、模型 health 200；0 个历史响应缓存命中，
已发出 198 请求。启动后快照为 27 running、5 waiting、KV 2.6320%、0 preemption，服务继续
健康且无新增致命错误。运行与配置证据见
[本轮 sanity 与 GPQA 启动记录](../acceptance/sanity-and-gpqa-launch-20260908.md)。

当前问题状态仍保持 `hypothesis`：短请求阶梯通过不等于长输出高 KV 路径已修复。只有本轮
`acceptance-result.json`、198 个唯一样本、零无效响应、服务终态和实际分数均完成核验后，才能
调整该结论；正式性能测试仍不得开始。

## 2026-09-08：c32/80K 全量轮再次复现

全量轮最终 receipt 为 `failed`。只有 doc 0、2、4 三条请求实际返回，strict 分别为 D/D、B/B、
A/A，即 3/3 正确；另外 195 条因 EngineCore 退出被计为 timeout/refusal。最终 strict 3/198 和
flexible 1/198 都不是可信的模型精度。flexible 少计两条是裸字母结尾与过滤器格式不一致，不是
三条返回的语义错答。

本轮在大多数运行请求约 16.2K 输出时进入 22 running、10 waiting、KV 98.49% 和 1 次 preemption；
一个恢复请求需重算 8171 tokens，与 21 个 decode token 组成 8192-token 步骤。吞吐从 118.8 降到
32.9，再降为 0；随后 32 次 shared-memory 等待覆盖约 30 分钟，最终再次出现
`TimeoutError: RPC call to sample_tokens timed out.`。未命中 SQLite、bool slice、OOM、非法内存或
work 序号分叉。与上一轮 4441-token 重算相比，本轮在更长输出下形成更大的 8171-token 重算，
使“长输出 + 近满 KV + preemption/recompute 超大步骤”成为高可信触发链；具体卡住的 rank/kernel
仍未定位。完整 receipt 与响应证据见
[GPQA 80K 失败结果](../acceptance/gpqa-80k-failure-20260908.md)。

## 2026-09-08：2048-token 调度上限受控缓解验证

继续诊断后确认 vLLM 的 `sample_tokens` RPC 是拆分式执行的第二段：EngineCore 先等待
`execute_model()` 的 future，再对所有 TP worker 调用 `sample_tokens()`；因此该超时名称不能单独证明
采样算子故障，前一轮异步设备工作也可能在此处暴露。两次失败分别把 4441-token 和 8171-token
recompute 与 decode 混合成 4488/8192-token 调度步，而相同服务上的短请求 c32 已通过。基于这一
完整签名，本轮选择调度层 mitigation，暂不修改 vLLM、Plugin 或 FlagGems 源码。

- 唯一模型执行变量：在原 TP16、100K、0.9 显存预算、`FULL_DECODE_ONLY` graph 配置上增加
  `--max-num-batched-tokens 2048`；客户端并发、采样参数和 80K 上限均不变。
- 诊断 launcher：
  `/mnt/nfs/users/jinghao/hy4-preview/02-environment/service-maxbatched2048-20260908-2151/start.sh`。
  首次执行因 PPU SDK `envsetup.sh` 在 nounset 下读取空 `$1` 而在拉起服务前退出，随后仅将
  `set -euo` 修正为 `set -eo` 并重新通过 check/diff；该失败没有启动服务或影响容器。
- 服务生命周期：确认 8010 无 listener、无旧 Hy4 vLLM 进程后，只在现有 `hy4` 容器内启动
  推理服务 PID 4162728；没有停止、重启或移除容器。22:19:53 +08:00 完成 51/51 graph capture，
  `/health=200`，日志位于
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/service-maxbatched2048-20260908-2151/service.log`。
- 固定 c8 sanity：
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/sanity-c8-maxbatched2048-20260908-2151/result.json`，
  8/8 严格答案与 `finish_reason=stop` 均通过，总耗时 89.7373 秒；包含首次请求 JIT 开销。
- 长输出诊断：preflight 已确认 GPQA Diamond 缓存数据集 198 条、服务模型 `hy4`、health 200；
  22:25 +08:00 启动前 32 题、c32、high、temperature 0.9、80K 的诊断运行：
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/gpqa-limit32-graph-c32-high80k-t09-maxbatched2048-20260908-2151/`。
  22:33 +08:00 已进入 9 running/23 waiting，首次 2048-token prefill JIT 日志持续增长，RPC timeout
  为 0。该运行尚未完成，不能据此把 mitigation 标为通过，也不能启动正式全量。

当前 launcher 是诊断配置，不是最终 `start-model.sh`。启动日志显示 vLLM 编译缓存仍使用既有
`/root/.cache/vllm`；正式接受前必须将所有新缓存收口到批准根的 `07-cache/`，重新验证启动、
sanity 和长输出稳定性，并完成最终 launcher 的最小参数审查。当前问题状态保持 `hypothesis`。

## 2026-09-09：2048-token 诊断轮失败与触发链收敛

前 32 题的 c32/high/80K 诊断轮最终以 runner exit 1 结束。样本文件包含两个过滤器产生的
64 行、32 个唯一 doc，其中 24 个为服务退出后的 `<TIMEOUT>`，8 个获得真实响应；8 个真实响应的
strict 判分均正确，因此本轮不能支持“模型答案精度下降”的结论。最长真实响应的最终可见答案仍
正确，但隐藏 reasoning 达到 169,810 字符、25,655 completion tokens，尾部出现明显退化；其余
真实响应的 completion 长度为 873 至 5,533 tokens。长 reasoning 退化是本轮 KV 压力的重要输入
条件，但不是对已返回最终答案的错答证据。

服务 fatal scheduler dump 给出了完整的触发状态：失败批次有 15 个驻留请求，其中 14 个各调度
1 个 decode token，另一个被 preempt 后恢复的请求调度 2,034 个 recompute tokens，合计严格等于
`--max-num-batched-tokens 2048`。14 个活跃请求各已生成约 25,656 至 25,660 tokens；恢复请求已
生成 24,337 tokens，但 scheduler 中仅保留 6,898 computed tokens，说明其 KV 已被驱逐并正在从
较早位置重算。失败前 KV usage 在 95% 至 99.9% 间反复波动并发生 preemption，最后有效吞吐约为
85.5 token/s；随后吞吐归零并持续 shared-memory 等待，约 1,800 秒后
`sample_tokens` collective RPC 超时，EngineCore 退出。

由此验证：`--max-num-batched-tokens 2048` 只把先前 4,441/8,171-token 的大重算拆成分块，不能
限制驻留长序列数、KV 总占用或阻止 RECOMPUTE preemption；第一个“14 decode + 2,034 recompute”
混合步骤仍未从 PPU TP16 graph 执行路径返回。`sample_tokens` 是拆分式异步执行最终等待到的 RPC
边界，不能据其名称断言纯采样算子本身卡死。

本轮所有 TP rank 对称出现 FlagGems `index_select.py` 的 `rows_mask and ...` warning，且相同 warning
也出现在此前能够继续执行的阶段。因此它是待修复的 shape/JIT 防护问题，但当前没有调用栈或 rank
差异把它与本次 30 分钟停滞直接关联，不能作为根因。日志仍未命中 SQLite lock、bool slice、显式
OOM、illegal memory、worker traceback 或 work-sequence divergence。

当前高可信系统触发链更新为：并发长 reasoning 使约 15 个 25K 级序列耗尽约 395,521-token KV
容量 → vLLM V1 驱逐某请求的 KV 并执行全量 RECOMPUTE → PPU TP16 graph 的混合 recompute+decode
步骤不返回 → `sample_tokens` RPC 在 1,800 秒边界暴露超时并终止服务。具体卡住的设备 kernel 或
collective 仍缺少失败时的 rank stack/PPU 快照，保持为未验证的底层假设。

下一单变量验证应保持客户端 c32、采样、80K、revision、graph 和 2,048-token 上限不变，只把服务
`--max-num-seqs` 限为 12，让其余请求在 scheduler 等待队列中排队。该值按本次 15 个约 25.6K 序列
接近填满 KV 的现场留出经验性余量，属于 mitigation 而非最坏 80K 输出的容量保证。若相同 32 题
在零 preemption 下通过，可确认 RECOMPUTE 路径是必要触发条件；若仍在无 preemption 时卡死，则
转入 graph/eager 单变量对照并在挂起窗口采集各 rank stack 和 PPU 状态。暂不以增大 RPC timeout
或 blacklist `index_select` 代替该验证。

## 2026-09-09：FlagGems 全局算子启用范围复核

进一步只读核对发现，失败服务没有设置 `VLLM_FL_FLAGOS_BLACKLIST`，因此实际读取 Plugin 工作区
中未提交的 `vllm_fl/dispatch/config/thead.yaml`。该文件 mtime 为 2026-09-08 10:24:03 +08:00，
相对 Plugin HEAD 的默认 T-Head blacklist 删除了 34 个算子：`zeros`、`fill_scalar_`、`sum_dim`、
`exponential_`、`mm`、`resolve_neg`、`resolve_conj`、`eq_scalar`、`floor_divide`、`cumsum`、`mul`、
`reciprocal`、`repeat`、`randn`、`add`、`ge_scalar`、`sub`、`bitwise_and`、`bitwise_not`、
`slice_scatter`、`fill_tensor_`、`conv1d`、`conv2d`、`uniform_`、`prod`、`max`、`amax`、`cat`、
`stack`、`flatten`、`reshape`、`view`、`tensor`、`topk`；当前仅禁用 `to_copy`、`_to_copy`、
`copy_`、`index`、`slice`。

失败日志证明确有额外 FlagGems ATen 替换被执行：`flag_gems/ops/amax.py` warning 1,072 次，
`flag_gems/ops/index_select.py` warning 128 次；后者最后一组紧邻进入最终停滞的调度阶段。warning
本身仍不能证明对应 kernel 卡死，但结合问题 016 已验证“只补 `slice`、其余默认保护仍放开”会让
首批 c32 请求超过 1,800 秒，而“Plugin HEAD 完整默认 blacklist + index”能完成相同 TP16 graph
c32/512 请求并保持 worker 健康，不能再把大量 FlagGems 算子启用视为无关背景。

此外，失败日志显示 T-Head native extension bundle 仍不完整，vendor 实现被禁用，执行更依赖
FlagGems/reference fallback。当前修正判断为：KV 满载与 RECOMPUTE 是已验证的上层触发状态；底层
不返回可能由额外启用的某个 FlagGems ATen 算子、graph/PPU backend，或二者组合造成。尚无原生
对照，不能确认“不是 FlagGems”。

因此后续验证顺序调整为：第一步不改工作区 dirty 文件，使用已有环境变量扩展点恢复“Plugin HEAD
完整默认 blacklist + index”，保持同一 revision、graph、客户端 c32/high/80K、temperature 0.9、
`--max-num-batched-tokens 2048` 和服务端默认 `max_num_seqs`，重跑相同 32 题。这是隔离 34 个额外
ATen 替换的单变量 A/B。若通过相同高 KV/preemption 步骤，则对 blacklist 差集按算子组二分；若
仍以相同签名失败，再执行 `--max-num-seqs 12` 单变量来隔离 RECOMPUTE。完全禁用 FlagGems 当前
不可作为直接对照，因为 W8A8 MoE、Sparse MLA 等主路径缺少等价且已验证的 PPU vendor 实现。

## 2026-09-09：关闭全部 FlagGems ATen 注册的受控对照

按用户要求扩大隔离范围，并明确授权直接修改 `thead.yaml`。本轮利用 Plugin rank 0 的
`FLAGGEMS_ENABLE_OPLIST_PATH` 记录机制核对上一实例实际调用，同时从当前 FlagGems
`FULL_CONFIG_BY_FUNC` 解析完整注册函数集合。完整集合为 982 个函数名；上一实例记录到 66 个
`flag_gems.ops.*` 调用。为避免只关闭已观察路径造成漏项，已把 982 个函数名全部写入
`vllm_fl/dispatch/config/thead.yaml::flagos_blacklist`，只替换该 YAML block。

- 修改前 SHA-256：`9a46de13ea7ec0237dd0a1b475c66d6f442f94a24e2aa42383cfeaf6804af77b`；
  修改后：`4cc93058eed4c95f4157886cfd20c66ec3a8a1174c7dc4b79809a36174bb79ea`。
- 原文件备份：
  `/mnt/nfs/users/jinghao/hy4-preview/06-tmp/service-all-flaggems-aten-off-20260909/thead.yaml.before`；
  未修改既有 `PROVENANCE.md` 删除或 Plugin 其他文件。
- 诊断 launcher：
  `/mnt/nfs/users/jinghao/hy4-preview/02-environment/service-all-flaggems-aten-off-20260909/start.sh`；
  保持 TP16、100K、0.9、FULL_DECODE_ONLY graph 和 `--max-num-batched-tokens 2048`，新增批准根内
  `FLAGGEMS_ENABLE_OPLIST_PATH`。启动 API PID 3344304；容器未停止、重启或删除。
- 服务完成 51/51 graph capture，`/health=200`，KV capacity 403,134 tokens。固定 c8 sanity 为
  8/8 正确、7.2899 秒、零新 fatal；结果位于
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/sanity-c8-all-flaggems-aten-off-20260909/result.json`，
  SHA-256 `23766c79690de203b89af1c6e222a5e699995b1006990c290e1b68cc150f5237`。

新的记录文件仍有 `scaled_mm` 和 `cat_out` 两条 `flag_gems.ops.*`，但二者在完整函数 blacklist 中，
是 Plugin 的量化/MLA 实现直接调用 FlagGems Python API，不是全局 ATen dispatcher 注册漏网；显式
`flag_gems.fused.*` 和 Plugin dispatch 路径按本对照设计继续保留，否则当前 W8A8/Sparse MLA 栈
缺少等价可运行实现。

首次 32 题 wrapper 因只复制 `llmrun.py`、缺少同目录 `acceptance_contract.py`，在发请求前以
`ModuleNotFoundError` 退出；该 setup failure 保留且不作为模型结果。补齐 `acceptance_contract.py`
和 `score_progress.py` 后，独立 rerun1 通过 dataset 198、limit 32、服务/模型健康 preflight，并于
2026-09-09 09:30:47 +08:00 启动相同 c32/high/temperature 0.9/80K 请求：
`/mnt/nfs/users/jinghao/hy4-preview/05-runs/gpqa-limit32-graph-c32-high80k-t09-maxbatched2048-all-aten-off-20260909-rerun1/`。
启动后 runner PID 18602 存活，服务 health 200、preemption 0、RPC timeout 0；运行尚未进入长输出
高 KV 阶段，暂不能判断是否消除卡死。已建立独立只读 heartbeat `hy4-all-aten-off`，不恢复旧的
`hy4-gpqa` 监控，只在完成、服务退出或持续零吞吐时通知。

该 rerun1 随后正常完成：32/32 唯一题均获得有效响应、timeout 0、runner exit 0，服务终态
health 200，未出现 RPC timeout、EngineCore fatal 或 preemption；观察到的 KV 峰值约 66%，因此
它验证了关闭全局 FlagGems ATen 替换后的低于满载场景可完成，但没有跨过失败轮的 99.9% KV 与
RECOMPUTE 条件，尚不能锁定具体算子或排除并发/KV 触发因素。

为提高压力并仍保持单变量可解释性，2026-09-09 11:01 +08:00 启动全量 GPQA Diamond c64 对照；
除并发由 32 提至 64、样本由限制 32 改为完整 198 外，继续使用同一服务实例、graph、TP16、
100K context、`--max-num-batched-tokens 2048`、thinking/high、temperature 0.9 与 80K 输出上限。
本轮属于 adaptation 诊断，不据此绕过当前正式 acceptance 的前置门禁。

- 配置：
  `/mnt/nfs/users/jinghao/hy4-preview/03-acceptance/gpqa-full-graph-c64-high80k-t09-all-aten-off-20260909/llm_config.json`，
  SHA-256 `2ba783b1ac1f7af41f9463f1e17d4984e5a05455f8325789088baddd00c29f46`。
- 结果根目录：
  `/mnt/nfs/users/jinghao/hy4-preview/04-runs/gpqa-full-graph-c64-high80k-t09-all-aten-off-20260909/`；
  临时目录和新缓存分别收口到当前规范的 `05-tmp/` 与 `06-cache/`。
- preflight：离线数据集严格为 198 条，模型列表包含 `hy4`，服务 health 200，确认 `limit=0`、
  `num_concurrent=64`、`expected_samples=198`、`allow_timeouts=false`。
- 启动后 runner PID 19400 存活；首轮观测为 24 running、40 waiting、KV 2.1%，服务 health 200，
  RPC timeout 0、preemption 0。最终结论需等待 198 题完整覆盖、实际分数、服务终态及高 KV 阶段。

## 2026-09-09：FlagGems `topk` 单算子定位实验

全量 c64/all-ATen-off 对照最终完成 198/198、timeout 0、runner exit 0；strict 为
178/198（89.90%），运行跨过 100% KV，服务保持 health 200，且没有 RPC timeout、EngineCore
fatal 或 preemption。该结果确认“额外启用的全局 FlagGems ATen 替换”是故障必要条件之一，随后
在同一 Plugin、FlagGems、vLLM revision、TP16、100K、FULL_DECODE_ONLY graph、2,048-token 调度
上限和批准根缓存布局下进行固定输入单算子定位。

实验从 198 题成功样本中固定抽取 32 条长输出输入，保持 c32、thinking/high、temperature 0.9、
`max_tokens=80000`、固定 seed 和 2,100 秒客户端超时。正向配置恢复此前仅含
`to_copy/_to_copy/copy_/index/slice` 的五项黑名单，SHA-256 为
`9a46de13ea7ec0237dd0a1b475c66d6f442f94a24e2aa42383cfeaf6804af77b`；运行证据位于
`/mnt/nfs/users/jinghao/hy4-preview/04-runs/flaggems-aten-bisect-20260909/full-enabled-capture/`。
该组 32/32 请求均在 2,100 秒超时，成功响应为 0；服务 health 仍为 200，但最多只接纳
16 running/16 waiting，KV 约 1.88%，生成吞吐长期为 0，TP worker 持续占用 CPU。

正向组的 Triton 缓存持续生成 `flag_gems/ops/topk.py::topk_single_stage_kernel`。已解析的 514 个
source 文件对应 514 个唯一 `(N, k)`，全部满足 `N == k`，并连续覆盖 `1..513`，另含 graph
capture 的 `(2048, 2048)`。FlagGems 通用 topk wrapper 把 `N` 和 `k` 都作为 `tl.constexpr` 传入
bitonic kernel，因此候选宽度每增长 1 都产生一个新 kernel。直接调用者为 Plugin
`vllm_fl/dispatch/backends/flaggems/impl/bf16_indexer.py:177-183`：融合
`top_k_per_row_decode` 生成候选后，再调用 `torch.topk(candidate_logits, indices.shape[1], sorted=True)`
对整行候选排序；候选宽度随 decode 有效上下文增长，且这里 `k` 恰等于整行宽度。

关键反向配置从同一五项黑名单逐字复制，仅新增 `topk`，语义差异已由容器内 YAML 解析校验，
SHA-256 为 `c36e84b1638da6cf371b8d2cc4a1e93e440bbd6358c4f8f996864b0b9dd51ca2`。证据位于
`/mnt/nfs/users/jinghao/hy4-preview/04-runs/flaggems-aten-bisect-20260909/all-except-topk/`。
该组保持其余 FlagGems ATen 与融合算子启用；实际 oplist 中保留
`TOP_K_PER_ROW_DECODE`、`cumsum`、`index_select`、`amax` 等，仅没有通用 `topk`。首次请求因有限
batch-shape JIT 约 9 分钟后进入稳定解码，随后持续约 163--166 token/s、缓存文件数不再增长，
32/32 请求均已接纳、waiting 归零、preemption 0、RPC timeout 0，KV 从约 4.1% 平滑增长到
38.1%。该组固定样本在 all-ATen-off 基线中的输出总量为 1,406,239 tokens，单条为
26,752--76,126 tokens；按反向组稳定吞吐无法在 2,100 秒客户端期限内全部返回，因此在证明持续
推进且缓存停止增长后由操作者结束客户端诊断请求，服务排空到 0 running/0 waiting，未停止或重启
`hy4` 容器。该操作停止不能计作 32 个响应完成，仅用于长序列持续进展判据。

为完成响应级闭环，在同一未重启服务、同一输入集合中另取 8 题，保持 c8/high/temperature 0.9，
仅把 `max_tokens` 收敛到 2,048、单请求超时设为 600 秒。结果 8/8 HTTP 200、失败 0、runner exit
0，总耗时 402.819 秒；6 个请求以 `stop` 结束，2 个请求正常达到 2,048-token `length` 上限。
终态 health 200、0 running/0 waiting、preemption 0、服务错误签名 0。运行时 oplist 仍包含融合
`grouped_topk` 与 `TOP_K_PER_ROW_DECODE`，但不包含 `flag_gems.ops.topk`；当前配置 SHA-256 仍为
`c36e84b1638da6cf371b8d2cc4a1e93e440bbd6358c4f8f996864b0b9dd51ca2`。短闭环证据位于
`/mnt/nfs/users/jinghao/hy4-preview/04-runs/flaggems-aten-bisect-20260909/all-except-topk-short8/stress/`。

截至当前的高可信结论是：导致“服务看似卡死”的主算子为全局替换后的 FlagGems 通用 `topk`，
不是 Plugin 的融合 `top_k_per_row_decode`。`cumsum/index_select/amax` 会带来有限的新 shape 预热和
warning，但在反向组缓存稳定后可以持续解码，现有证据不支持把它们列为持续卡死根因。当前
mitigation 是在 T-Head `flagos_blacklist` 中保留 `topk`；最终根因修复应避免 BF16 indexer 的
全行排序进入形状特化的通用 FlagGems topk，或由 FlagGems 提供不按每个 `N/k` 重新编译的实现。

## 2026-09-10：Plugin 根因修复、设计审查与提交

已在 Plugin 的 FlagGems BF16 indexer 后端修复最终候选排序的职责边界。融合
`top_k_per_row_decode` 仍负责从有效上下文选候选；随后仅用于候选重排的动态全宽排序通过 ATen
`CompositeExplicitAutograd` keyset redispatch 到原生实现，不再重新进入全局 FlagGems
`torch.topk` 注册。该位置属于 composite backend 的内部实现责任，修改没有加入模型名、机器名或
T-Head 特判，也没有绕开 Plugin 的公开 dispatch/registration 路径。配置中 blacklist `topk` 仍是
安全 workaround；代码修复使显式开启该全局算子时也不会由此调用点产生逐 decode-length 的无界
specialization。

- 实现：`vllm_fl/dispatch/backends/flaggems/impl/bf16_indexer.py`。
- 回归测试：`tests/unit_tests/dispatch/test_bf16_indexer_backend_ownership.py`；覆盖候选宽度
  1/3/4，显式把全局 `torch.topk` 替换为抛错桩，证明 backend 不会重新进入全局注册；同时保留
  reference 有效长度和 PPU graph capture/replay 合同。
- 修复前负向证据：只加入保护测试时 3/3 在原 `torch.topk` 调用处失败，日志为
  `/mnt/nfs/users/jinghao/hy4-preview/04-runs/plugin-topk-fix-20260910/negative-before-fix.log`。
- 修复后聚焦测试：5 passed，含 PPU graph replay；ruff 与 `git diff --check` 通过，日志为
  `/mnt/nfs/users/jinghao/hy4-preview/04-runs/plugin-topk-fix-20260910/focused-after-fix.log`。
- 算子级实机对照：在 `flag_gems.use_gems(include=["topk"])` 下，控制调用确认进入 FlagGems
  `TOPK`，修复 helper 不进入；宽度 1..64、127、255、513、2048 共 68 组数值和排列均通过。
  脚本位于
  `/mnt/nfs/users/jinghao/hy4-preview/02-issues/plugin-topk-fix-20260910/test_native_candidate_order.py`，
  日志位于
  `/mnt/nfs/users/jinghao/hy4-preview/04-runs/plugin-topk-fix-20260910/topk-enabled-integration.log`。
- 服务级定向闭环：使用仅比安全配置少 blacklist `topk` 的完整隔离 YAML，SHA-256
  `9a46de13ea7ec0237dd0a1b475c66d6f442f94a24e2aa42383cfeaf6804af77b`，TP16、100K、
  `FULL_DECODE_ONLY` graph、2,048-token 调度上限。固定 8 条 GPQA、c8、max tokens 2,048 在
  552.55 秒内 8/8 HTTP 200、失败 0、runner exit 0，终态 health 200、0 running/0 waiting。
  结果位于
  `/mnt/nfs/users/jinghao/hy4-preview/04-runs/plugin-topk-fix-20260910/codefix-topk-enabled-short8/stress/`。
- 服务生命周期：仅停止已核实空闲的实验 API PID 1647374，理由为
  `restore-safe-config-after-plugin-validation`；随后用既有安全 launcher 启动 PID 2249974，
  `/health=200`，EngineCore PID 2250454。`hy4` 容器未停止、重启或删除。
- 提交基于验证期间更新后的远端 tip
  `48b55050d3f983ae152432358b408544fc734db2`，没有把旧工作树的 3 个历史本地提交带入远端。
  最终提交 `56000bf7cb3c926e62cca33ca2769dfa0ccdfaf9` 已 fast-forward 推送到
  `ZenithJoyH/vllm-plugin-FL::support-hy4-preview`；作者与提交者均为
  `ZenithJoyH <1355922182@qq.com>`。提交严格只有上述实现与当前仓库布局下的 UT 两个文件。
  既有 `thead.yaml` 修改、`PROVENANCE.md` 删除均未暂存或提交，`pyproject.toml` 未修改。
- vLLM 仍为 `ee0da84ab9e04ac7610e28580af62c365e898389`，FlagGems 仍为
  `bca444b8569294e7d4e4deff7ddfec7f05682033`，本修复未修改两者。

影响范围限于 Plugin 的 FlagGems BF16 indexer decode 最终候选排序；reference backend、融合候选
选择、其他全局 `topk` 调用方均保持原行为。当前已验证 PPU eager helper、PPU graph replay 和真实
TP16 服务；未在 NVIDIA、MetaX、Ascend 等其他硬件验证，也尚未用代码修复配置重新执行 198 题
正式全量 acceptance，因此本记录把根因修复与正式精度验收分开，不据定向 8 题声明全量精度通过。

## 2026-09-10：同步提交版本与 FlagGems 功能分支后启动全量 GPQA

部署源已更新为 Plugin `ff87b683ec9c6c1925dbedf12261914e45569b52`、FlagGems
`bca444b8569294e7d4e4deff7ddfec7f05682033` 和原 vLLM
`ee0da84ab9e04ac7610e28580af62c365e898389`，三者工作树均 clean。FlagGems 使用包含已验证
W8A8 MoE 分类修复的跟踪功能分支最新提交；没有切换到缺少该修复的官方 master。新 TP16 graph
服务完成 51/51 capture 并 health 200，固定 c8 sanity 为 8/8 HTTP 200、失败 0、exit 0。

在相同服务上通过离线数据集 198 条和服务模型 preflight 后，于 2026-09-10 13:37 +08:00 启动
GPQA Diamond 全量 c64、thinking/high、temperature 0.9、80K 轮次，runner PID 21634。配置与证据见
[本轮启动记录](../acceptance/gpqa-plugin-ff87-flaggems-bca-launch-20260910.md)。当前只确认首批请求已
进入服务且 health 200；完整性、实际 strict-match 分数与终态待运行完成后更新，不提前标记
accuracy passed。

## 2026-09-10：同步用户最新提交并保留通用 index 黑名单后重启评测

Plugin 已 fast-forward 到用户重新提交的
`2fa5f1816fe0e9a08fd66f515c5de28e9c8199e2`，仅保留经授权的 `thead.yaml` 通用
`index` blacklist 修改；FlagGems 与 vLLM 分别保持
`bca444b8569294e7d4e4deff7ddfec7f05682033` 和
`ee0da84ab9e04ac7610e28580af62c365e898389`。更新后 19 个聚焦 UT 全部通过，TP16 graph
服务完成 51/51 capture 并 health 200。固定 8 条 c8/high/2,048-token sanity 为 8/8 HTTP
200、失败 0、exit 0，未发现 fatal。

随后通过离线 GPQA Diamond 198 条和服务 preflight，于 2026-09-10 20:48 +08:00 启动全量
c64、thinking/high、temperature 0.9、80K 轮次，runner PID 22842。首批 64 个客户端并发均已
进入 running 或 capacity waiting，服务 health 200、preemption 0、fatal 0，并持续生成 token。
完整性、strict-match 分数和服务终态仍待运行完成，不提前标记 accuracy passed。配置、路径和
证据见[本轮启动记录](../acceptance/gpqa-plugin-2fa-indexoff-launch-20260910.md)。

## 2026-09-11：Plugin `2fa5f18` 全量轮终态

全量 c64/high/80K 轮完成 198 个唯一 doc_id，服务未复现此前的 `sample_tokens`/EngineCore 卡死；
最后一条请求返回后正确端口 8010 的 `/health` 仍为 200，服务日志终态为 0 running、0 waiting。
这验证了 Plugin 修复加通用 `index` blacklist 已消除本记录所跟踪的服务停滞路径，不能把本轮
runner 非零退出误报为模型服务挂掉。

正式 strict-match 为 180/198（90.9091%），高于用户指定的 87% 基线；flexible-extract 为
96/198（48.4848%）。但 doc_id 81 被记录为一个唯一 `<TIMEOUT>`，在 strict/flexible 两个过滤器
样本行中各出现一次。`allow_timeouts=false` 因而使结果校验失败，runner exit 1，未生成 passing
`acceptance-result.json`。2026-09-11 用户明确接受 90.91% 为精度达标并要求进入下一步，因此本地
工作流把 accuracy 标记 passed，同时将 timeout 与原生 receipt 缺失保留为已接受限制。

精确结果、样本、runner log 与哈希见
[Plugin 2fa / index 黑名单版 GPQA 全量记录](../acceptance/gpqa-plugin-2fa-indexoff-launch-20260910.md)。
适配阶段按用户纠正保持 `in_progress`；accuracy 已按业务判定完成。性能前置检查因 adaptation
尚未 complete 而拒绝继续，正式性能未启动。后续报告不得把本轮描述为零 timeout 或原生
receipt pass。

## 2026-09-11：最终 launcher 与适配阶段完成

按用户授权，将完成全量 GPQA 的同一 graph 配置从
`/mnt/nfs/users/jinghao/hy4-preview/01-environment/service-plugin-2fa5f18-fgbca-indexoff-20260910/start.sh`
固化为 Host 根入口 `/mnt/nfs/users/jinghao/hy4-preview/start-model.sh`；`hy4` 容器内对应路径同为
`/mnt/nfs/users/jinghao/hy4-preview/start-model.sh`。变更先经 Ansible check/diff，确认目标不存在且
唯一计划变更为复制已验证源，再以单 Host 执行。

- Host root 与容器 root 的 device/inode 均为 `41:21477849219`；launcher 两侧 device/inode 均为
  `41:21506731259`，证明是同一 RW 映射。
- launcher mode `0755`、大小 2,097 bytes，Host/容器 SHA-256 均为
  `6bf2e151423f65f860d6f7e45e164e29ee99ca0de656cdd32150cf6bffd02748`，容器内 `bash -n` 通过。
- 白名单式静态审查确认敏感赋值 0、破坏性命令 0；日志路径均在 `04-runs/`，缓存路径均在
  `06-cache/`。显式参数保留模型路径、served name、8010、TP16、100K context、2,048-token
  调度上限、0.9 显存预算和 `FULL_DECODE_ONLY` graph，它们分别用于模型身份、服务协议、设备
  拓扑、已验证上下文、避免超大混合调度步、KV 容量与 graph 执行复现。
- 在已有 Hy4 服务运行时实际执行根 launcher，返回码 1 并明确输出
  `Refusing to start: another Hy4 inference process exists.`；之后 8010 `/health` 仍为 200，匹配
  服务进程仍严格为 1。未停止、重启或移除 `hy4` 容器，也没有覆盖当前服务。
- 终态 revision：Plugin `2fa5f1816fe0e9a08fd66f515c5de28e9c8199e2`，仅有经授权的
  `vllm_fl/dispatch/config/thead.yaml` 修改；FlagGems
  `bca444b8569294e7d4e4deff7ddfec7f05682033` clean；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389` clean。

Plugin topk 职责修复、通用 index blacklist、聚焦 UT、graph sanity、c64/80K 服务稳定性、用户接受
的 90.91% 精度以及最终 launcher 均已形成闭环。按用户当前指令，适配阶段标记 complete；精度的
单条 timeout/缺失原生 passing receipt 仍是验收限制，不因阶段完成而删除。
