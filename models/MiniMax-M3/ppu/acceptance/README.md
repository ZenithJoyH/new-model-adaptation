# MiniMax-M3 / PPU 验收索引

| 记录 | 文件 | 结论 |
|---|---|---|
| 验收计划 | [acceptance-plan.md](acceptance-plan.md) | 严格按 execution-mode → sanity → accuracy → performance → evidence → summary 执行 |
| 执行模式 | [execution-mode-results.md](execution-mode-results.md) | 当前 redesign：TP16 eager 与 graph、65K context、changed-input 已通过 |
| sanity 结果 | [sanity-results.md](sanity-results.md) | 当前 redesign 固定前 10 题以确定性 greedy 得到 10/10，通过 |
| accuracy 结果 | [accuracy-results.md](accuracy-results.md) | 当前 redesign 全量 198 题 c64 为 177/198（89.39%），通过 80% 门限 |
| 门禁记录 | [acceptance-blockers.md](acceptance-blockers.md) | 记录原阻塞、用户冻结输入与解除依据 |
