# GLM-5.3-Flash-BF16 / PPU：环境与设计材料

2026-10-12：本目录已整理为平铺 Markdown 记录；旧脚本、运行配置和过程历史已保留原文归档。[原路径、归档位置与逐文件哈希](../../_shared/local-record-maintenance.md)。历史文中的命令只用于说明当时操作，不应从旧路径直接重放。

本目录保存环境采集、运行配置、适配计划和设计审查；不是问题台账或启动成功证明。
返回[平台概览](../README.md)；问题见[adaptation](../adaptation/README.md)，结果见[acceptance](../acceptance/README.md)。

## 主要入口

| 材料 | 用途 |
|---|---|
| [environment-analysis.md](environment-analysis.md) | 模型、平台和软件环境分析，包含历史及重验信息 |
| [runtime-config.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/runtime-config.yml)、[service-state.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/service-state.yml) | 结构化配置与已记录服务状态；执行前核对现场 |
| [platform-adaptation-plan.md](platform-adaptation-plan.md)、[BF16 差距清单](bf16-gap-analysis-20260906.md) | 实施计划；差距清单不是独立故障或验证通过证明 |
| [plugin-change-review.md](plugin-change-review.md) | 已有真实代码审查及未验证范围；本轮整理未改动其内容 |
| [plugin-backend-contracts.md](plugin-backend-contracts.md) | backend/接口契约与设计约束 |
| [reference-files.md](reference-files.md) | 用户提供及检索参考材料 |
| [collect-ppu13-environment.yml](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/collect-ppu13-environment.yml) | 环境采集入口；索引不代表已重新执行 |

## 历史材料与路径映射

旧记录保留当时的模型/权重、revision、日期及结论。错误 FP8 快照对应结论不能继承为当前 BF16 结果。

| 原位置 | 现位置 | 归位理由 |
|---|---|---|
| `adaptation/004-flaggems-vllm-install-20260904.md` | [库安装记录](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/history/flaggems-vllm-install-20260904.md) | 环境准备，不是独立模型故障 |
| `adaptation/010-hy4-glm53-scope-review-20260904.md` | [历史范围审查](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/history/hy4-glm53-scope-review-20260904.md) | 历史设计分析，不代表当前 PR 审查结论 |
| `adaptation/017-bf16-gap-analysis-20260906.md` | [BF16 差距清单](bf16-gap-analysis-20260906.md) | 平台适配规划 |
| 历史操作记录 | [commands](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/history/commands.md)、[progress](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/history/progress.md) | 追溯使用，不作为最新服务配置 |

上述旧问题编号保留映射、不复用、不重新编号现有问题。已有 `plugin-change-review.md` 中的
旧路径是审查时的定位快照，按本表查现文件；未为排版改动而刷新审查或阶段哈希。

`environment-analysis.md` 中两条历史采集命令曾被重复拼接归档前缀；为保护证据绑定，正文
保持不变。其实际本地取证文件位于仓库根目录相对路径：

- `.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/inspect-ppu13-glm53-baseline.yml`
- `.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/inspect-ppu13-glm53-architecture.yml`

这些归档入口不可直接当作当前操作执行；先核对目标和参数，按当前流程重新准备。
