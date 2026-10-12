# Qwen3.8-Flash-Next / PPU：环境与设计材料

2026-10-12：本目录已整理为平铺 Markdown 记录；旧脚本、运行配置和过程历史已保留原文归档。[原路径、归档位置与逐文件哈希](../../_shared/local-record-maintenance.md)。历史文中的命令只用于说明当时操作，不应从旧路径直接重放。

返回[平台概览](../README.md)；故障见[问题台账](../adaptation/README.md)，验证见[验收索引](../acceptance/README.md)。

| 材料 | 用途与限制 |
|---|---|
| [environment-analysis.md](environment-analysis.md) | 模型与平台分析 |
| [runtime-config.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/runtime-config.yml)、[service-state.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/service-state.yml) | 运行配置及状态；区分正式基线与 22 题诊断试验参数 |
| [platform-adaptation-plan.md](platform-adaptation-plan.md) | QSA/PLE/GDN、共享 runner 与算子缺口计划 |
| [plugin-change-review.md](plugin-change-review.md) | 当前 PR diff 尚未审查；按多模型、多平台契约补验 |
| [flaggems-operator-evidence.md](flaggems-operator-evidence.md) | 特定版本的算子检索证据，不能替代后续版本检索 |
| [reference-files.md](reference-files.md) | 模型参考资料 |
| [collect-ppu01.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/collect-ppu01.yml)、[collect_container.py](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/collect_container.py) | 环境采集入口与容器采集 helper |
| [container-baseline.json](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/container-baseline.json) | 首次采集快照，不是当前 PID/配置事实 |
| [revalidate-current-state.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/revalidate-current-state.yml)、[current-state-revalidation.json](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/current-state-revalidation.json) | 已记录的现场复核入口与快照，执行前仍需检查目标 |
| [历史 commands](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/history/commands.md)、[历史 progress](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/history/progress.md) | 故障和操作沿革，当前状态请结合编号问题与验收轮次 |

当前 runtime 中的诊断段明确区分 max-model-len 和生成上限的受控调整；本轮整理不修改参数，
也不把局部重跑合并为全量精度结果。旧配置和失败输出保留在验收目录原路径，避免影响现有引用。

新诊断/修复写入 `adaptation/NNN-*.md`；新验证写入 `acceptance/`；一次性部署/源码快照
不得进入插件仓库。
