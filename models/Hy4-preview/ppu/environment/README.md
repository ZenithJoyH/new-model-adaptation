# Hy4-preview / PPU：环境分析

2026-10-12：本目录已整理为平铺 Markdown 记录；旧脚本、运行配置和过程历史已保留原文归档。[原路径、归档位置与逐文件哈希](../../_shared/local-record-maintenance.md)。历史文中的命令只用于说明当时操作，不应从旧路径直接重放。

返回[平台概览](../README.md)。本目录只保留环境和平台能力分析文档，不保存命令脚本、
Playbook、运行配置、服务快照、原始采集结果或历史过程记录。

| 文档 | 内容 |
|---|---|
| [environment-analysis.md](environment-analysis.md) | PPU-07 硬件、容器、软件栈和当前环境结论 |
| [bf16-direct-run-readiness.md](bf16-direct-run-readiness.md) | BF16 容量与直接启动可行性 |
| [new-bf16-int8-readiness.md](new-bf16-int8-readiness.md) | 新 BF16/INT8 权重与现有适配能力差距 |
| [native-operator-inventory-ppu07-20260903.md](native-operator-inventory-ppu07-20260903.md) | PPU 原生算子能力分析 |
| [ppu-native-mla-aux-ops-analysis-20260903.md](ppu-native-mla-aux-ops-analysis-20260903.md) | MLA 辅助算子兼容性分析 |

实际采集命令、运行配置、一次性脚本和原始结果应保存在用户批准的远端工作根目录中；
本地分析文档只记录结论、必要证据摘要及准确远端路径。
