# 004：index 首次调优 SQLite 锁冲突

## 元数据与现象

Qwen3.8-Flash-Next / PPU-01 / `qwen3.8-flash`，2026-09-06 graph c32。首次真实 GPQA
调度形状在 TP1/TP6/TP7 触发 `sqlite3.OperationalError: database is locked`，EngineCore 退出。
这是独立于 TP RPC 超时的 rank 异常。FlagGems 当时是干净的 `34bd6d68928c8b0039c42987840929da52aa6a62`。

## 诊断与受控尝试

PLE 的 `conv_output[req_indices, col_indices]` 进入 FlagGems index 首次 autotune；
输入 BF16 `[9,551,10240]`，两组 int64 索引。多个 rank 共用 SQLite benchmark 数据库，
RollbackSession.commit 处理 IntegrityError 而未处理数据库锁 OperationalError。
概率多进程复现未稳定触发；随后用独占 SQLite 锁进行受控复现，保留前一失败尝试。

## 解决与验证

通过插件 `thead.yaml` 精确排除 index，回退原生索引；最终集合为
`[slice, conv1d, _conv_depthwise2d, index]`。这是 workaround，没有声称修复共享数据库实现。
原记录覆盖生产形状 BF16/int64 eager、float32、小形状 graph 变输入重放，384 项回归通过。
修复后 c32 混合压力 32/32 成功，7160/7160 tokens、105.557 秒、零错误，服务健康。

## 复现、限制与下一步

- 容器复现包：`/bug/flaggems-index-autotune-sqlite-lock-20260906`；分别保留 eager、首次
  capture 调优及预热后 graph 路径证据。受控锁试验的确切参数见原包 README 和归档 Playbook。
- [症状、尝试、命令定位及生命周期](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/history/progress.md)。
- [完整验收总结](../acceptance/adaptation-summary.md)。
- 本页未执行新验证。当前版本或调优数据库策略变化后需重验；后续正式全量结果不能用压力
测试代替。容器保持运行、vLLM 未变，旧失败结果保留。知识状态：local-only。

## 2026-09-07 重验

FlagGems 更新到 clean `dcd0cfeae8187dee691656c0616c1ed95899c2ae` 后，最终 Plugin
`a5c6f0ca373afa606b68d2daa4bb4a9dcc1833c5` 继续通过运行时 append 回退 `index`。生产 BF16
`[9,551,10240]`、FP32 小形状以及 graph 变输入探针全部通过；整合树 410 项回归和 TP8 graph
全模型冒烟通过。证据位于远端 `05-runs/workaround-probes-dcd0cfe-20260907-1721/`、
`05-runs/plugin-regression-dcd0cfe-20260907-1714/` 和
`05-runs/full-model-smoke-dcd0cfe-20260907-1740/`。共享 SQLite 根因未在 FlagGems 上游修复，
因此仍分类为 workaround。
