# 适配验收索引

2026-10-09 Plugin 0.4 独立 DSpark 服务的
[128 客户端并发精度重测](dspark-c128-plugin04-20261009.md)已完成：
MATH500 72.4%（362/500），MMLU-Pro 每科 50 题原生 42.0%（294/700），
超时均为 0，完整性核对通过；服务端仍最多执行 4 条序列。
首轮缓存故障后的独立本地缓存重跑证据完整，不等于正式验收。

2026-10-08 新容器的双模型整合结果见
[共用代码功能验证](unified-code-validation-2026-10-08.md)：两模型各 TP2 eager 6/6、
FULL_AND_PIECEWISE 19/19，无旧 attention 黑名单。此轮未执行正式精度/性能验收。

本轮已完成的服务及功能检查见 [functional-validation.md](functional-validation.md)。
正式精度与性能尚未执行；项目原生回执未绑定，不能将此报告当作完整验收通过。

2026-10-08 的 FlagGems 算子修复、PR 差异审查及局部回归结果见
[adaptation-summary.md](adaptation-summary.md)；原独立容器的去黑名单重启未执行，
新共用容器整模复验已完成，见上述新记录。
