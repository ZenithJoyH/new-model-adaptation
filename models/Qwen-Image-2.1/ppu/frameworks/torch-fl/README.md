# 框架适配记录

记录于 2026-10-12 显式升级为 evidence v2 / profile v3。当前 `not_started` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

本目录只保存当前模型、平台和 framework profile 的精简记录。框架定义见 `framework.yml`
引用的仓库级 profile；远端运行产物仍保存在该框架独立的已批准工作根目录。

- `environment/`：框架、容器、组件、Host 和平台环境分析。
- `adaptation/`：仅保存编号问题记录及解决结论。
- `acceptance/`：仅保存验收计划、结果、总结和复盘。

不要在这里保存脚本、源码、补丁、JSON 结果、原始日志、缓存或临时文件。

2026-09-21：已完成 Qwen-Image-2.1 PPU CPU-wheel follow-up 的源码审查、变基和聚焦回归；上游 issue/PR 待创建后回填。本次是 PR 准备而非用户选定的正式适配阶段，因此 workflow 状态保持 `not_started`，不把历史模型运行当作最终 commit 的 formal acceptance。
