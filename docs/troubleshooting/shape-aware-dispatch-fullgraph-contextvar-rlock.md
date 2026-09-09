# Shape-aware Plugin dispatch 进入 fullgraph 后触发 ContextVar/RLock

- 状态：`verified`
- 可信度：`high`（故障归属与诊断方法）；`medium`（候选缓存修复尚需按调用方复验）
- 平台：与硬件无关的 Plugin/Python dispatch 问题；首次验证于 T-Head PPU
- 模型范围：使用 `torch.compile(fullgraph=True)`，且算子通过输入 `supports` predicate
  动态选择 backend 的模型
- 软件及 revision：`vllm-plugin-FL support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8`
  加 GLM-5.3-Flash 适配；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 首次验证日期：2026-09-08
- 最近复验日期：2026-09-08

## 症状与识别条件

该条目只适用于以下完整特征，不能仅凭日志中出现 `RLock` 套用：

1. eager 或允许断图的 PIECEWISE/breakable graph 能运行；切换到 decode full graph 后，
   Dynamo 在 Plugin dispatch 路径失败。
2. 堆栈包含 `CachedOp -> OpManager.call()`，随后进入 policy、manager 或 registry。
3. 最早错误可能是 `ContextVar.get()` 不可追踪，也可能继续表现为
   `threading.RLock`、context manager 或可变 Python 状态不可追踪。
4. 对照实现的 `CachedOp` 在 eager 首次解析后直接调用缓存的 `impl.fn`；问题实现因为候选带
   输入 `supports`，把 `_use_manager_call` 设为真并在每次 forward 重新进入 manager。

已验证的最早关键错误为：

```text
torch._dynamo.exc.Unsupported: Unsupported method call
Dynamo does not know how to trace method get of class ContextVar
```

如果最早失败发生在算子 kernel、tensor 数据依赖控制流、CUDA/PPU graph capture 或状态
buffer replay，本条目不直接适用，应继续按分层隔离顺序定位。

## 最小复现与证据

- 复现脚本宿主机与容器路径：
  `/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/023-full-decode-graph/repro_cached_op_compile.py`
- 原始结果：
  `/mnt/nfs/users/jinghao/glm5.3-flash/05-runs/023-full-decode-graph/cached-op-baseline/`
- `07-bugs/`：不适用；本例是 Plugin dispatch 控制流复现，不是 FlagGems 算子复现。上方
  `03-issues/` 是迁移前的历史证据路径；按当前工作区规则，新复现应保留在 `02-issues/`，
  且不复制到 `/bug`。
- 对照方法：使用同一 fake manager 和同一 `torch.compile(backend="eager", fullgraph=True)`
  workload，先 eager warmup；唯一变量是候选是否携带 `supports`。
- 期望结果：HY4 fast path 与 shape-aware path 都不在已 warmup 的编译热路径调用 manager。
- 实际结果：无 `supports` 的 HY4 fast path 编译和 changed-input 调用通过；带 `supports` 的
  GLM path 设置 `_use_manager_call=True`，稳定进入 `OpManager.call()` 并在
  `ContextVar.get()` 失败。

## 根因

已验证根因不是模型计算或 FlagGems kernel 自身持有 RLock，而是 Plugin 把 dispatch 控制面
带进了 fullgraph 执行面：

```text
HY4 fast path
eager resolve -> cache impl.fn -> compiled forward calls impl.fn directly

问题路径
supports candidate -> _use_manager_call=True -> every forward calls manager
                   -> policy ContextVar -> initialization/cache/registry RLock
```

manager 中的锁对于 eager 初始化、并发缓存更新、日志和失败记录是合理的。问题在于这些
Python 控制逻辑出现在需要完整追踪的模型 forward 中。`ContextVar` 通常是当前版本最早暴露
的失败点；绕过它后，`ensure_initialized()`、registry snapshot、首次使用记录或失败缓存中的
锁仍可能成为下一个失败点。因此，不应把问题窄化成“替换某一把 RLock”。

引入 `supports` 的原始需求也是合理的：不同 dtype、shape、layout、page size 或设备能力
可能需要不同 backend。错误在于为了每次重新判断输入能力而永久退回 manager，而不是
`supports` 本身。

## 诊断顺序

1. 确认失败模式确实是 FULL decode；保存 eager、PIECEWISE/breakable 与 FULL 的单变量
   对照，不同时修改 batch、并发、算子或 timeout。
2. 找到最早的 Dynamo 堆栈，区分 `ContextVar/RLock` dispatch 失败和后续 kernel/capture
   失败；不要从 EngineCore 或 RPC timeout 倒推根因。
3. 比较 `CachedOp` 首次调用和后续调用，检查是否因 `supports`、IO dump、fast-path opt-out
   或 runtime fallback 而持续进入 `OpManager.call()`。
4. 构造已 eager warmup 的最小 fullgraph 对照：无 `supports` 与带 `supports` 各跑一次，
   还要使用不同输入 metadata 验证是否错误复用了旧实现。
5. 若移除 manager 后仍失败，再检查 `supports` 是否为纯 metadata predicate，以及 kernel
   是否含 `.item()`、主机同步、动态分配、捕获期 Python 状态或不稳定 state/cache 地址。

## 根因修复原则

- 类型：`root-cause-fix` 的设计约束；具体实现必须在当前调用方上验证后才能接受
- 在 graph 外解析并缓存按 policy 排序的候选集合。
- 热路径只执行纯输入 metadata `supports(*args, **kwargs)`，随后直接调用匹配的
  `impl.fn`；不得重新进入 manager、policy ContextVar、registry、日志或失败缓存。
- policy/manager epoch 变化仍必须使缓存失效，但策略更新和重新解析应发生在 graph 外。
- 保留 shape 切换语义，不能为绕过 manager 而删除 `supports` 或永久固定首次实现。
- 保留 strict、backend allowlist 和 `allow_runtime_fallback=False` 语义。对会写 cache/state
  的 kernel，启动后异常不得自动尝试第二个实现，以免重复写入。
- IO dump、调试与 runtime fallback 可继续使用 manager，但这些模式不得被宣称支持
  fullgraph，除非另有独立验证。

以下动作只能作为诊断或临时 workaround，不能标为根因修复：

- 设置 `VLLM_USE_BREAKABLE_CUDAGRAPH`、退回 PIECEWISE 或关闭 compile；
- suppress Dynamo errors 或放宽 fullgraph；
- 删除 input `supports`、无条件固定 backend；
- 修改执行超时；
- 只替换或绕过报错位置的一把 RLock。

## 验证标准

候选修复至少需要以下证据：

1. dispatch 单测覆盖：无 `supports` fast path、带 `supports` 的 shape A/B/A 切换、policy
   epoch 失效、allowlist、strict/fallback 和 stateful no-retry。
2. 已 warmup 的 `torch.compile(..., fullgraph=True)` changed-input 测试证明编译区不调用
   `OpManager.call()`，且不同 metadata 选择正确实现。
3. 当前平台分别验证 eager 与 graph capture/replay；只通过 `backend="eager"` 的 Dynamo
   测试不能证明设备 graph 已正确。
4. 模型级至少完成两次变输入 decode replay，并核对输出；有 state/cache 时确认 replay
   使用 caller 提供的稳定 buffer，且没有捕获期 Python 状态泄漏。
5. 最终服务在不依赖 breakable workaround 的目标 execution mode 启动并通过并发正确性
   回归；另行记录性能变化。

截至 2026-09-08，最小负对照已验证故障归属，但 GLM FULL decode、真实设备 graph、并发
正确性和性能仍待来源问题记录完成，因此本条目不构成该模型的验收结论。

## 停止条件与回退

- 如果候选 guard 读取 tensor 值、执行 `.item()`、同步设备或依赖可变全局状态，停止将其
  放入 fullgraph；先改成纯 metadata contract。
- 如果 shape/provider 切换、policy epoch 或 stateful no-retry 任一回归，回退本次 dispatch
  修改并保留已验证的旧 execution mode。
- 如果 manager 已移出热路径但仍出现错误，不继续围绕 RLock 打补丁，转向最早的新失败层。
- 未完成设备 capture/replay 和输出回归前，不删除已知健康配置，也不更新最终启动脚本。

## 适用限制与性能影响

- 该经验适用于 Python Plugin dispatch 与 Dynamo/fullgraph 的边界，不证明任一具体硬件
  kernel 支持 graph capture。
- 未 eager warmup 的首次解析仍可能进入 manager；实际框架必须证明编译前初始化契约，
  或提供显式 graph 外 prepare 阶段。
- 缓存候选会减少每 token 的 manager 开销，理论上有利于 decode，但尚无正式性能数据，
  不据此宣称优化收益。

## 复验与反例

| 日期 | 模型/平台 | revision | 结果 | 新增约束或反例 |
|---|---|---|---|---|
| 2026-09-08 | GLM-5.3-Flash-BF16 / T-Head PPU | Plugin `d56f7b2` + GLM diff；vLLM `ee0da84a` | HY4 fast path 正对照通过；GLM supports path 在 `ContextVar.get()` 稳定失败 | 只验证 dispatch 最小复现；整模 FULL decode 尚未通过 |

## 来源记录

- [`models/GLM-5.3-Flash-BF16/ppu/adaptation/023-full-decode-graph-without-breakable-20260908.md`](../../models/GLM-5.3-Flash-BF16/ppu/adaptation/023-full-decode-graph-without-breakable-20260908.md)
- HY4 基线：`ZenithJoyH/vllm-plugin-FL` 的 `support-hy4-preview` 分支，revision
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`。
