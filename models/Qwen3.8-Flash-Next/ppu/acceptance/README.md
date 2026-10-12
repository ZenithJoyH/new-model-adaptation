# Qwen3.8-Flash-Next / PPU：验收索引

2026-10-12：本目录已整理为平铺 Markdown 记录；旧脚本、运行配置和过程历史已保留原文归档。[原路径、归档位置与逐文件哈希](../../_shared/local-record-maintenance.md)。历史文中的命令只用于说明当时操作，不应从旧路径直接重放。

返回[平台概览](../README.md)；[运行配置](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/runtime-config.yml)、[问题台账](../adaptation/README.md)。
本页不复制动态分数。旧全量轮次与后续 22 题生成上限试验分别保留，不拼接成一份通过结果。

## 主要记录

| 类别 | 文件 | 使用边界 |
|---|---|---|
| 计划/总结/复盘 | [plan](acceptance-plan.md)、[summary](adaptation-summary.md)、[retrospective](adaptation-retrospective.md) | 历史总结含旧检查点；最新诊断以问题 005 及对应 run-id 为准，空复盘不代表完成 |
| 执行模式与 sanity | [execution-mode.md](execution-mode.md)、[graph-sanity-reviewed.json](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/graph-sanity-reviewed.json)、[原始简要结果](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/graph-sanity-result.txt) | 局部通过不能替代正式精度；不能从文件存在补写绑定 |
| 初次全量轮次 | [llm_config.json](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/llm_config.json)、[accuracy-progress.json](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-progress.json) | TP RPC 超时历史，见问题 003 |
| timeout1800 轮次 | [配置](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/llm_config.timeout1800.json)、[进度](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-timeout1800-progress.json) | 首次调优 SQLite 锁历史，见问题 004 |
| index workaround 后轮次 | [配置](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/llm_config.timeout1800-index.json)、[进度](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-index-progress.json) | 与前两轮保持独立；达到生成上限样本另行诊断 |
| 22 题诊断子集 | [问题 005](../adaptation/005-gpqa-generation-cap.md)、[manifest](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/capped22-manifest.json)、[launch](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/capped22-launch.json)、[progress](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/capped22-progress.json) | 诊断子集，不是正式 198 题全量验收；不能用 subset 结果自动刷新历史通过状态 |
| 2026-09-18 双服务正式轮次 | [结果与归因](gpqa-c64-auto-capture-dual-20260918.md) | 198/198，170/198（85.86%），7 个 60000-token 生成上限；正式精度失败 |

## 验证与辅助入口

- graph 预检：[graph_sanity.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/graph_sanity.py)、[review_graph_sanity.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/review_graph_sanity.py)。
  前台源码须由当前门禁准入；旧 graph_sanity.yml 已停用，不能再覆盖固定历史证据路径。
- 旧全量轮次启动已停用：[start_accuracy.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/start_accuracy.py)；历史监测材料：[monitor_accuracy.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/monitor_accuracy.py)、
  [inspect_accuracy.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_accuracy.py)、[inspect_accuracy_timeout1800.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_accuracy_timeout1800.py)、
  [inspect_accuracy_index.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_accuracy_index.yml)、[inspect_accuracy_index.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_accuracy_index.py)。
- 生成上限诊断：[inspect-capped-samples.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect-capped-samples.yml)、[inspect_capped_samples.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_capped_samples.py)、
  [rerun_capped22.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/rerun_capped22.py)、[start_capped22.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/start_capped22.py)、
  [inspect-capped22.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect-capped22.yml)、[inspect_capped22.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_capped22.py)。
  rerun/start 已停用，其余固定目标与参数仅属于该次试验，不能当成通用正式 runner。
- 结果辅助：[finalize_accuracy.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/finalize_accuracy.py)、[finalize_accuracy_index.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/finalize_accuracy_index.py)。
  只独占写入非正式 model-accuracy-review，不覆盖旧结果；sanity review 同样标记非正式用途。
  名称中的 finalize 不代表满足最新契约；正式通过需共享契约生成 passing `acceptance-result.json`。
- 性能/通信准备：[vllm_perf_qwen38.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/vllm_perf_qwen38.py)、[finalize_performance.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/finalize_performance.py)、
  [communication_graph.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/communication_graph.py)。精度与前置未过不得启动最终性能；本轮未执行。

## 历史与恢复

- `accuracy*-launch.txt`、`accuracy-monitor-launch.txt`、[evaluator-environment.txt](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/evaluator-environment.txt)
  是简要启动/环境证据，不是当前服务存活证明。
- [legacy-common-llm_config.json](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/legacy-common-llm_config.json)、
  [legacy-common-llm_parallel_config.json](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/legacy-common-llm_parallel_config.json)
  是从公共测试目录保留的旧配置，不作为新契约模板。
- 旧 `prepare_evaluator.py/yml` 内嵌整份旧公共 runner/计分源码，不是轻量模型 wrapper；
  本轮移到忽略的可恢复归档，避免再次部署旧测试实现。新准备应引用当前 `test/Accuracy_test/`，
  不复制历史内嵌实现。本轮没有修改已在远端运行的评测器。

2026-09-07 的本地维护另行停用了上述旧启动/执行入口，完整原文及 SHA256 见
[历史入口索引](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/historical-entrypoints/README.md)；没有替换远端运行副本或改写历史结果。
