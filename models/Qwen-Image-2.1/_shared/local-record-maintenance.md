# Qwen-Image-2.1：本地记录整理

整理日期：2026-10-12。范围为目录、索引和已有 framework 契约；没有远端执行或新的适配/验收。

PPU 的 Torch-FL / Diffusers eager 完整出图、配对验证及性能实验已有记录。保留各实验容器的独立身份；不套用 vLLM 服务验收，不宣称 graph 或正式整体验收完成。

## 记录来源与适用范围

| 平台 | 来源 | 已记录 Host | 原记录状态 / 当前契约 |
| --- | --- | --- | --- |
| ppu | [legacy 平台记录](../ppu/README.md) | PPU-07 | functional |
| ppu | [torch-fl](../ppu/frameworks/torch-fl/README.md) | PPU-07 | v2 `not_started`；原记录 `not_started` |

## 现有契约与人工协作

现有 framework 已通过 `workspace-control handoff → upgrade → resume` 显式采用 v2，原状态、失败、verification 和 run ID 保存在 `control.history`；完整旧 YAML 同时保留在快照中。
当前阶段的 `not_started` 表示尚未建立 v2 证据，不抹去历史工作；`blocked` 表示不能凭旧回执继续宣称新版门禁通过。没有刷新旧证据哈希或补写通过回执。

| 工作区 | Profile 版本 | 整理后状态 |
| --- | --- | --- |
| [ppu/frameworks/torch-fl](../ppu/frameworks/torch-fl/framework.yml) | 2 → 3 | `not_started` |

[人工接管与交回](../../../docs/human-collaboration.md)；[v2 证据契约](../../../docs/evidence-contract-v2.md)。只有用户选定实际阶段和 Host 后才推进适配。

## 文件归档与恢复

[整理前完整快照](../../../.local/adaptation-history/20261012-model-layout-080344/snapshot/models/Qwen-Image-2.1)；[逐文件哈希清单](../../../.local/adaptation-history/20261012-model-layout-080344/before-manifest.json)；[归档与恢复说明](../../../.local/adaptation-history/20261012-model-layout-080344/README.md)。
归档位于 Git 忽略的 `.local/adaptation-history/`，仅本机可用，不等于已部署到远端或已持久交付。

本模型未发现需要迁出的非 Markdown 过程材料；保留原有分析、问题编号和验收文档。

## 保留的验证边界

legacy `platform.yml` 仍保留历史状态及绑定；本次不把人工接受结果或旧 Markdown 总结改写为原生通过。未选择的阶段不补跑。
结构审计只能证明目录和链接一致；profile 升级不能证明当前服务身份、权重、已安装代码、图模式、精度、性能或镜像交付已验证。
