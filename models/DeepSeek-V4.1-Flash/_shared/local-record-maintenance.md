# DeepSeek-V4.1-Flash：本地记录整理

整理日期：2026-10-12。范围为目录、索引和已有 framework 契约；没有远端执行或新的适配/验收。

NVIDIA 原生 vLLM 已有最小功能与 GPQA 176/198（88.89%）记录；execution-mode/sanity 的正式前置绑定及性能未闭环。Plugin 工作区单独保留。

## 记录来源与适用范围

| 平台 | 来源 | 已记录 Host | 原记录状态 / 当前契约 |
| --- | --- | --- | --- |
| nvidia | [legacy 平台记录](../nvidia/README.md) | H100-149 | functional |
| nvidia | [vllm-plugin-fl](../nvidia/frameworks/vllm-plugin-fl/README.md) | H100-149 | v2 `blocked`；原记录 `model_loading` |
| metax（实际目标为 V4） | [误存历史材料](../metax/README.md) | mx-59（V4 历史记录） | 不属于 V4.1 验收 |

MetaX 的 001—004 问题在原索引中已明确更正为 **DeepSeek-V4-Flash INT8**，此处只保留原历史位置，不能据此认定 V4.1 开展了 MetaX 适配。接续入口为 [V4 工作区](../../DeepSeek-V4-Flash/metax/frameworks/vllm-plugin-fl/README.md)。

## 现有契约与人工协作

现有 framework 已通过 `workspace-control handoff → upgrade → resume` 显式采用 v2，原状态、失败、verification 和 run ID 保存在 `control.history`；完整旧 YAML 同时保留在快照中。
当前阶段的 `not_started` 表示尚未建立 v2 证据，不抹去历史工作；`blocked` 表示不能凭旧回执继续宣称新版门禁通过。没有刷新旧证据哈希或补写通过回执。

| 工作区 | Profile 版本 | 整理后状态 |
| --- | --- | --- |
| [nvidia/frameworks/vllm-plugin-fl](../nvidia/frameworks/vllm-plugin-fl/framework.yml) | 4 → 7 | `blocked` |

[人工接管与交回](../../../docs/human-collaboration.md)；[v2 证据契约](../../../docs/evidence-contract-v2.md)。只有用户选定实际阶段和 Host 后才推进适配。

## 文件归档与恢复

[整理前完整快照](../../../.local/adaptation-history/20261012-model-layout-080344/snapshot/models/DeepSeek-V4.1-Flash)；[逐文件哈希清单](../../../.local/adaptation-history/20261012-model-layout-080344/before-manifest.json)；[归档与恢复说明](../../../.local/adaptation-history/20261012-model-layout-080344/README.md)。
归档位于 Git 忽略的 `.local/adaptation-history/`，仅本机可用，不等于已部署到远端或已持久交付。

本模型未发现需要迁出的非 Markdown 过程材料；保留原有分析、问题编号和验收文档。

## 保留的验证边界

legacy `platform.yml` 仍保留历史状态及绑定；本次不把人工接受结果或旧 Markdown 总结改写为原生通过。未选择的阶段不补跑。
结构审计只能证明目录和链接一致；profile 升级不能证明当前服务身份、权重、已安装代码、图模式、精度、性能或镜像交付已验证。

## 本地审计待复核

本地审计保留 8 项 legacy 警告：architecture/environment/adaptation 前置未闭环，accuracy 缺少有效 verification，execution-mode/sanity 未正式绑定。176/198 的历史分数不据此撤销，也不补写当前通过回执。
