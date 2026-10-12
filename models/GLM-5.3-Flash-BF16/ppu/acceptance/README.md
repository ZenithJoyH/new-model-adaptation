# GLM-5.3-Flash-BF16 / PPU：验收索引

2026-10-12：本目录已整理为平铺 Markdown 记录；旧脚本、运行配置和过程历史已保留原文归档。[原路径、归档位置与逐文件哈希](../../_shared/local-record-maintenance.md)。历史文中的命令只用于说明当时操作，不应从旧路径直接重放。

返回[平台概览](../README.md)；[运行配置](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/runtime-config.yml)、[问题台账](../adaptation/README.md)。
此页仅导航，不重复维护易过期的进度/分数；阶段状态与证据绑定见 `../platform.yml`。

| 类别 | 文件 | 使用边界 |
|---|---|---|
| 计划 | [acceptance-plan.md](acceptance-plan.md) | 执行模式 → sanity → accuracy → performance/evidence/summary，按选定子步骤执行 |
| 2026-09-08 decode FULL | [full-decode-graph-20260908.md](full-decode-graph-20260908.md) | 无 breakable 的 execution-mode/c8 实现验证；receipt 被既有 deployment identity 哈希不一致阻塞，不替代正式 accuracy/performance |
| 2026-09-10 当前提交 GPQA | [gpqa-current-commits-20260910.md](gpqa-current-commits-20260910.md) | Plugin/FlagGems 已发布 revision 的全量 198 题 c32/60K 诊断；运行中，不冒充正式 acceptance receipt |
| 当前 graph sanity | [graph-sanity-results.md](graph-sanity-results.md)、[graph_sanity.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/graph_sanity.py) | 保留冷态失败与后续复测，不把一次通过解释为正式性能完成 |
| 2026-09-06 BF16 全量轮次 | [gpqa-full-20260906.md](gpqa-full-20260906.md)、[llm_config.json](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/llm_config.json)、[旧启动器原文](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/historical-entrypoints/start_gpqa.sh.md) | 旧 start_gpqa.sh 已拒绝重放；新运行按共享门禁准备独立目录，阶段值不是最终分数 |
| 计分辅助 | [grade_gpqa.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/grade_gpqa.py) | 只独占输出 gpqa-score-review.json（model-accuracy-review），不覆盖/生成正式 acceptance-result.json |
| 2026-09-04 历史轮次 | [gpqa-full-20260904.md](gpqa-full-20260904.md) | 旧权重/故障轮次独立保留，不继承当前 BF16 结论 |
| 总结与复盘 | [adaptation-summary.md](adaptation-summary.md)、[adaptation-retrospective.md](adaptation-retrospective.md) | 文件存在不表示对应阶段已完成 |

目录整理时未改写上述配置、脚本、结果及绑定；2026-09-07 本地安全修复另行停用旧启动器，
没有重启远端评测。正式精度通过需按当前 contract
核实唯一题数、错误/超时、完整样本和既定阈值；不得从目录整理推断 accuracy/performance 通过。
