# 新模型适配项目：性能评测适配契约

本文件把 `inference-performance-evaluation` 的跨项目接口映射到当前仓库。执行前还必须读取
`AGENTS.md`、`docs/model-adaptation-workflow.md`、`docs/workflow-guide.md` 和
`test/perf_test/README.md`；用户指令优先。

## 模式映射

| Skill 模式 | 当前项目入口 |
|---|---|
| `baseline` | 正确性基线通过后，为尚无可比数据的 graph 服务和冻结工况建立无 profiler 基线 |
| `targeted` | 一次 Plugin/算子/配置优化后的直接受影响工况和廉价 sentinel 验证 |
| `checkpoint` | 多个保留修改或跨场景机制变化后的受影响工况集合复验 |
| `formal` | 验收 `performance`：正式精度 gate-check 通过后，在同一已验收 graph 配置上运行最终性能套件并导出正式回执 |

## 当前项目硬约束

- 验收顺序固定为 `execution-mode` → `sanity` → `accuracy` → `performance` →
  `evidence` → `summary`。正式性能不能先于正式精度；用户只选性能时，其他步骤只读检查。
- `execution-mode` 要求 eager 和 graph 都跑通，之后所有性能验收只使用通过的 graph 配置。
- 正式性能前使用 `inference-accuracy-evaluation` 的 `gate-check`。当前服务、配置或产物不完全
  匹配时停止；不得把历史 passed、sanity 或最小回归当作正式精度门禁。
- vLLM 使用 `test/perf_test/vllm_perf.py`，SGLang 使用 `sglang_perf.py`；`all_perf.py` 仅作为
  其文档约束内的兼容批量入口。先使用 `--dry-run` 检查命令。
- `--model`、`--tokenizer`、`--max-model-len` 必须来自当前服务核实结果；每个
  `INPUT+OUTPUT` 不得超过服务上下文预算。每轮使用新输出目录，不覆盖历史结果。
- `vllm_profile.py`/`sglang_profile.py` 和 profiler-on 轮次仅用于诊断。正式性能回执应来自
  完整、无 profiler 的最终套件；若用户另行指定 profiling，结论和产物必须隔离。
- 使用 `perf_common.validate_report` 完整校验 `benchmark-result.json` 及其引用产物后，再运行
  `test/perf_test/perf_acceptance.py` 导出 `kind=formal_performance` 的紧凑回执。Markdown、CSV、
  `SUMMARY` 文本或进程退出码不能替代该回执。
- 当前项目的正式回执验证单个已绑定服务及其冻结工况，不自动证明另一个项目所用的
  baseline/candidate/revert 归因契约。需要优化收益归因时，必须使用相同 workload 分别保留
  可比基线和候选结果，并将结论限制在已验证对比；缺少可比数据时返回 `incomplete`。
- 前缀缓存和其他缓存状态必须记录并在比较中保持一致，除非其本身是唯一实验变量。当前
  项目不默认强制关闭前缀缓存；不要无依据增加启动参数。

## 路径与记录

- 远端性能计划/包装放在 `<host_root>/03-acceptance/`，原始报告、CSV、stdout/stderr、trace
  和正式回执放在 `<host_root>/04-runs/<run_id>/`，缓存放在 `06-cache/`。核实所有容器路径
  及映射，并为每条远端命令设置明确 workdir。
- 一次性分析脚本放在 `02-issues/` 或 `05-tmp/`，不得放进本地平台记录或 vLLM 源码。
- 本地 `models/<model>/<platform>/acceptance/` 只保存 Markdown 计划、关键指标、结论、准确
  远端路径和 SHA-256；不得复制原始 JSON/CSV/trace/日志。
- 新模型适配的平台阶段通过自然语言调用；不得为了旧版 `adapt-model` 门禁恢复精简目录已
  移除的 YAML 或过程文件。允许的只读检查仍可使用 `--check-only` 和 `audit-workspace`。
