# 模型适配记录

目录整理日期：2026-10-12。合并后模型导航共 14 项、15 个已有 framework 工作区；本轮仅整理本地记录，没有执行远端适配或评测。

## 模型导航

| 模型 | 已有记录范围 | 结果与限制 |
| --- | --- | --- |
| [DeepSeek-V4-Flash](DeepSeek-V4-Flash/README.md) | metax | MetaX 的 eager 与 decode FULL graph 有最小请求记录；全链路图模式、正式精度与性能尚未完成。目标为 V4 INT8，不与 V4.1 混用。 |
| [DeepSeek-V4.1-Flash](DeepSeek-V4.1-Flash/README.md) | nvidia；metax 仅为 V4 误存历史 | NVIDIA 原生 vLLM 已有最小功能与 GPQA 176/198（88.89%）记录；execution-mode/sanity 的正式前置绑定及性能未闭环。Plugin 工作区单独保留。 |
| [GLM-5.3-Flash-BF16](GLM-5.3-Flash-BF16/README.md) | ppu | PPU-13 的功能适配已有记录；最新记录的 GPQA 为 172/198（86.87%），低于 88% 阈值，保留失败结论。 |
| [Hy4-preview](Hy4-preview/README.md) | ppu | PPU-07 历史服务的 strict 90.91% 精度由用户按 87% 业务阈值接受；原生通过回执缺失，部分性能场景超时且用户已停止继续测试。新版 BF16/INT8 来源分析与旧运行结果分别保留。 |
| [MiniCPM-V-4.7-1B](MiniCPM-V-4.7-1B/README.md) | nvidia, ppu | 分别保留 NVIDIA 原生 vLLM、NVIDIA Plugin、PPU Plugin 和 PPU 原生框架记录。已有小样本功能结果不代表完整精度、性能或其他框架通过。 |
| [MiniCPM-V-4.7-35B-A3B](MiniCPM-V-4.7-35B-A3B/README.md) | nvidia, ppu | 已合并旧名 MiniCPM-V-4.7-35B；分别保留 NVIDIA 原生 vLLM、NVIDIA Plugin、PPU Plugin 与 PPU 原生框架。功能或诊断结果不等于正式整体验收。 |
| [MiniMax-M3](MiniMax-M3/README.md) | ppu | PPU-13 旧工作区与 PPU-07 新适配分别保留。PPU-07 的 GPQA 178/198（89.90%）达到用户指定目标，但 sanity 9/10 和原生配置冲突使正式验收仍未闭环。 |
| [MiniMax-M3.1](MiniMax-M3.1/README.md) | ppu | 已完成（2026-10-08 用户验收确认）。GPQA 84.8484% 与三组性能结果的完成结论保持不变；原生证据和镜像验证限制继续作为维护备注，不自动重开评测。 |
| [Qwen-Image-2.1](Qwen-Image-2.1/README.md) | ppu | PPU 的 Torch-FL / Diffusers eager 完整出图、配对验证及性能实验已有记录。保留各实验容器的独立身份；不套用 vLLM 服务验收，不宣称 graph 或正式整体验收完成。 |
| [Qwen3.6-27B](Qwen3.6-27B/README.md) | metax | MetaX mx-58 的模型结构、环境及 Plugin 适配过程已有记录；正式精度、性能与完整验收尚未闭环。 |
| [Qwen3.6-35B](Qwen3.6-35B/README.md) | metax | 旧 mx-104 平台记录与 mx-59 Plugin 优化记录分别保留。mx-59 三组吞吐改善为 21.3% / 65.2% / 49.0%，但部分尾延迟上升；正式整模精度及镜像验收未执行。 |
| [Qwen3.8-Flash-Next](Qwen3.8-Flash-Next/README.md) | ppu | PPU-01 的功能与算子归属整理已有记录；最新双实例正式精度为 171/198（86.36%），低于 88% 阈值。跨实例数值差异和生成上限问题保持未关闭。 |
| [Xing4.0-29B-A4B](Xing4.0-29B-A4B/README.md) | nvidia, ppu | PPU-13 的独立 Xing4.0 实现已有验证，最新重构后 graph 尚未重跑；NVIDIA H100-145 另有 MATH-500 432/500（86.40%）独立评测，不作为正式 acceptance。与 XingChen4 保持独立目录。 |
| [XingChen4-29B-A4B](XingChen4-29B-A4B/README.md) | nvidia, ppu | NVIDIA / PPU 历史功能、GPU Xid、长生成和跨请求 graph 分叉分别保留；正式验收未闭环，PPU 仍有明确阻塞。NVIDIA 旧概览与平台配置的 Host 不一致，接续前需核对。 |

## 目录与接续规则

- 模型根：`model.yml`、`README.md`、已有的 `architecture-and-inference.md`；`_shared/` 放精简跨平台分析和维护索引。
- 新布局：`<platform>/frameworks/<framework>/`；`framework.yml` 固定 profile 快照与 evidence v2，`environment/`、`adaptation/`、`acceptance/` 均为平铺 Markdown。问题编号保持原值。
- 旧布局：平台根下已有阶段记录保持原位，明确为 legacy；不为了统一目录而批量迁移到猜测的 framework 或 Host。后续新工作先明确框架与准确主机。
- 历史脚本、配置、快照和过程子目录已迁入 Git 忽略的本地归档。它们不是当前执行入口；新执行材料仍应位于任务批准的远端工作根。
- 保留未开展平台的已有骨架，不新增任务。实验 profile、诊断子集、人工验收与完整原生验收分别说明。
- 不存放模型权重、密钥、完整日志或大型评测产物，不在本次整理中提交或推送。

## 历史结果与 v2 状态

已有 framework 通过显式交接升级，原通过、失败、未完成状态及 verification 保存在 `control.history` 和完整快照。当前阶段 `not_started` 表示 v2 证据尚未建立，`blocked` 表示无法仅用旧回执通过新门禁；不表示历史工作被删除或实际模型重新失败。
MiniMax-M3.1 的用户验收完成结论保持 **complete**；Hy4 的精度业务接受、性能失败和停止继续测试决定也保持原状。任何契约整理都不自动安排重跑。
部分 legacy 验收仍缺少正式前置或原生回执，保留待复核项，不刷新哈希来制造通过。不同 Host、容器、权重和框架的记录不互相继承。

[人工接管与交回](../docs/human-collaboration.md) · [v2 证据契约](../docs/evidence-contract-v2.md) · [适配流程](../docs/adaptation-policy.zh-CN.md)

## 归档与恢复

[本次完整快照、迁移清单与恢复说明](../.local/adaptation-history/20261012-model-layout-080344/README.md)。每个模型 `_shared/local-record-maintenance.md` 提供其原状态、契约变更和归档文件哈希。
归档只在当前本机，克隆仓库不包含这些文件。本次未把材料上传到服务器，也未验证远端历史产物仍然可读。

## 新模型和新框架入口

```bash
./scripts/new-model <model-name>
./scripts/new-framework <model-name> <platform> <framework-id>
```

阶段 1 可用 `adapt-model --steps architecture` 初始化；阶段 2～5 的旧创建入口已停用。执行时只选择用户要求的阶段，先检查现有进程和前置证据，不重放历史启动命令。

## 本轮本地检查

此前目录整理时审计为 0 个错误、9 个待复核项。此次 MiniCPM 35B 别名合并前后审计均为 **2 个既有错误、9 个待复核项，无新增问题**：两个错误来自项目根 README 与本页指向当前缺失的 XingChen4-29B-A4B 目录；待复核项仍为 DeepSeek-V4.1 的 legacy 前置/精度绑定 8 项、Hy4 的原生精度回执缺口 1 项。MiniCPM 合并范围的本地链接与框架配置校验通过；目录与链接通过不等于远端验收通过。
