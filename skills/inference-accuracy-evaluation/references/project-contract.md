# 新模型适配项目：精度评测适配契约

本文件把 `inference-accuracy-evaluation` 的跨项目接口映射到当前仓库。执行前还必须读取
`AGENTS.md`、`docs/model-adaptation-workflow.md` 和 `docs/workflow-guide.md`；用户指令优先。

## 模式映射

| Skill 模式 | 当前项目入口 |
|---|---|
| `baseline-sanity` | 适配阶段的服务 smoke，或验收 `sanity`：已通过执行模式验收的 graph 服务上执行固定 8 并发简单请求，并同时观察明显性能异常 |
| `minimal-regression` | Plugin 必要产品改动后的定向算子、模型链路和请求回归；按影响面覆盖 eager/graph，不能代替验收 `sanity` 或正式精度 |
| `formal-gate` | 验收 `accuracy`：在 `execution-mode`、`sanity` 通过后运行正式全量精度 |
| `gate-check` | 正式性能前，只读核验当前 `acceptance-result.json` 及其服务、配置、样本和哈希绑定 |

## 当前项目硬约束

- 验收顺序固定为 `execution-mode` → `sanity` → `accuracy` → `performance` →
  `evidence` → `summary`。只执行用户选择的子步骤；前置失败时停止，不自动补跑。
- 执行模式验收要求 `eager` 和 `graph` 都能跑通。之后的 sanity、正式精度和正式性能只使用
  已通过的 graph 配置，不在 eager 重复正式评测。
- `sanity` 使用固定简单请求、并发 8，逐条检查正确性，并记录错误、超时、时延、吞吐、
  加速卡利用率和内存。正确性异常返回适配；性能明显异常先修复再做全量精度。
- 正式精度在目标机上进入基于
  `harbor.baai.ac.cn/flageval/flageval-llmeval:v1` 或适用的 `arm64` 镜像容器，使用
  `test/Accuracy_test/llmrun.py`。先运行 `--preflight-only`，再正式运行。
- 正式配置必须使用 graph、`limit=0`、并发至少 32、正整数 `expected_samples`、
  `allow_timeouts=false`，并预先固定每项 metric 和 minimum。GPQA Diamond 完整样本数为 198。
- 默认正式入口不是 `llmrun_parallel.py`。只有用户明确要求多服务或多 shard，且完整性和
  合并契约得到验证时才能使用该入口。
- 只有 `llmrun.py` 生成且完整校验通过的 `acceptance-result.json` 才是正式精度回执。
  部分得分、Markdown 结论、日志退出码或历史 passed 文件不能替代它。

## 路径与记录

- 远端配置/包装放在 `<host_root>/03-acceptance/`；本轮完整输出放在
  `<host_root>/04-runs/<run_id>/`；通用缓存放在 `06-cache/`。若 runner 契约要求评测专属
  cache 与显式 run 绑定，则放在该 `04-runs/<run_id>/` 内，并核实容器映射和存储语义。
- 一次性诊断代码放在 `02-issues/` 或 `05-tmp/`。不得写入 vLLM；只有必要、可维护的产品
  实现和聚焦回归测试进入已核实的 editable-installed Plugin 源码。
- 本地 `models/<model>/<platform>/acceptance/` 只保存 Markdown 计划/结论以及准确远端路径、
  SHA-256、关键指标和身份，不复制完整样本、日志、JSON 或缓存。
- 新模型适配的平台阶段通过自然语言调用。当前 `adapt-model` 的旧结构化门禁不得用于创建
  精简平台步骤 2～5 的过程文件；可以使用 `--check-only` 和 `audit-workspace` 做允许的检查。

## 正式性能放行

只有 `gate-check` 对当前候选、当前 graph 服务实例、当前配置和当前正式精度产物返回
`passed`，才能启动正式性能。任一绑定缺失或变化返回 `incomplete`；用户只要求检查时不得
自动重跑正式精度。
