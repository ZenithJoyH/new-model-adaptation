# Xing4.0-29B-A4B：本地记录整理

整理日期：2026-10-12。范围为目录、索引和已有 framework 契约；没有远端执行或新的适配/验收。

PPU-13 的独立 Xing4.0 实现已有验证，最新重构后 graph 尚未重跑；NVIDIA H100-145 另有 MATH-500 432/500（86.40%）独立评测，不作为正式 acceptance。与 XingChen4 保持独立目录。

## 记录来源与适用范围

| 平台 | 来源 | 已记录 Host | 原记录状态 / 当前契约 |
| --- | --- | --- | --- |
| nvidia | [独立评测记录](../nvidia/README.md) | H100-145（独立评测） | 正式阶段 not_started |
| ppu | [legacy 平台记录](../ppu/README.md) | PPU-13 | environment_ready |

## 现有契约与人工协作

本模型尚无显式 framework 工作区；保留原 legacy 布局和状态，不为整理而创建新适配、推断 framework/Host 或批量迁移历史阶段。后续用户选定新工作时使用 `new-framework`。

[人工接管与交回](../../../docs/human-collaboration.md)；[v2 证据契约](../../../docs/evidence-contract-v2.md)。只有用户选定实际阶段和 Host 后才推进适配。

## 文件归档与恢复

[整理前完整快照](../../../.local/adaptation-history/20261012-model-layout-080344/snapshot/models/Xing4.0-29B-A4B)；[逐文件哈希清单](../../../.local/adaptation-history/20261012-model-layout-080344/before-manifest.json)；[归档与恢复说明](../../../.local/adaptation-history/20261012-model-layout-080344/README.md)。
归档位于 Git 忽略的 `.local/adaptation-history/`，仅本机可用，不等于已部署到远端或已持久交付。

本模型未发现需要迁出的非 Markdown 过程材料；保留原有分析、问题编号和验收文档。

## 保留的验证边界

legacy `platform.yml` 仍保留历史状态及绑定；本次不把人工接受结果或旧 Markdown 总结改写为原生通过。未选择的阶段不补跑。
结构审计只能证明目录和链接一致；profile 升级不能证明当前服务身份、权重、已安装代码、图模式、精度、性能或镜像交付已验证。
