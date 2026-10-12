# DeepSeek-V4-Flash：本地记录整理

整理日期：2026-10-12。范围为目录、索引和已有 framework 契约；没有远端执行或新的适配/验收。

MetaX 的 eager 与 decode FULL graph 有最小请求记录；全链路图模式、正式精度与性能尚未完成。目标为 V4 INT8，不与 V4.1 混用。

## 记录来源与适用范围

| 平台 | 来源 | 已记录 Host | 原记录状态 / 当前契约 |
| --- | --- | --- | --- |
| metax | [vllm-plugin-fl](../metax/frameworks/vllm-plugin-fl/README.md) | mx-59 | v2 `blocked`；原记录 `blocked` |

001—004 的早期 MetaX 诊断曾误存于 [V4.1 目录](../../DeepSeek-V4.1-Flash/metax/adaptation/README.md)，真实目标已更正为本模型。原位置与编号保留，后续从本模型 framework 工作区接续。

## 现有契约与人工协作

现有 framework 已通过 `workspace-control handoff → upgrade → resume` 显式采用 v2，原状态、失败、verification 和 run ID 保存在 `control.history`；完整旧 YAML 同时保留在快照中。
当前阶段的 `not_started` 表示尚未建立 v2 证据，不抹去历史工作；`blocked` 表示不能凭旧回执继续宣称新版门禁通过。没有刷新旧证据哈希或补写通过回执。

| 工作区 | Profile 版本 | 整理后状态 |
| --- | --- | --- |
| [metax/frameworks/vllm-plugin-fl](../metax/frameworks/vllm-plugin-fl/framework.yml) | 2 → 7 | `blocked` |

[人工接管与交回](../../../docs/human-collaboration.md)；[v2 证据契约](../../../docs/evidence-contract-v2.md)。只有用户选定实际阶段和 Host 后才推进适配。

## 文件归档与恢复

[整理前完整快照](../../../.local/adaptation-history/20261012-model-layout-080344/snapshot/models/DeepSeek-V4-Flash)；[逐文件哈希清单](../../../.local/adaptation-history/20261012-model-layout-080344/before-manifest.json)；[归档与恢复说明](../../../.local/adaptation-history/20261012-model-layout-080344/README.md)。
归档位于 Git 忽略的 `.local/adaptation-history/`，仅本机可用，不等于已部署到远端或已持久交付。

本模型未发现需要迁出的非 Markdown 过程材料；保留原有分析、问题编号和验收文档。

## 保留的验证边界

legacy `platform.yml` 仍保留历史状态及绑定；本次不把人工接受结果或旧 Markdown 总结改写为原生通过。未选择的阶段不补跑。
结构审计只能证明目录和链接一致；profile 升级不能证明当前服务身份、权重、已安装代码、图模式、精度、性能或镜像交付已验证。
