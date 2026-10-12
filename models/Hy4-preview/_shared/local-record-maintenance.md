# Hy4-preview：本地记录整理

整理日期：2026-10-12。范围为目录、索引和已有 framework 契约；没有远端执行或新的适配/验收。

PPU-07 历史服务的 strict 90.91% 精度由用户按 87% 业务阈值接受；原生通过回执缺失，部分性能场景超时且用户已停止继续测试。新版 BF16/INT8 来源分析与旧运行结果分别保留。

## 记录来源与适用范围

| 平台 | 来源 | 已记录 Host | 原记录状态 / 当前契约 |
| --- | --- | --- | --- |
| ppu | [legacy 平台记录](../ppu/README.md) | PPU-07 | functional |

## 现有契约与人工协作

本模型尚无显式 framework 工作区；保留原 legacy 布局和状态，不为整理而创建新适配、推断 framework/Host 或批量迁移历史阶段。后续用户选定新工作时使用 `new-framework`。

[人工接管与交回](../../../docs/human-collaboration.md)；[v2 证据契约](../../../docs/evidence-contract-v2.md)。只有用户选定实际阶段和 Host 后才推进适配。

## 文件归档与恢复

[整理前完整快照](../../../.local/adaptation-history/20261012-model-layout-080344/snapshot/models/Hy4-preview)；[逐文件哈希清单](../../../.local/adaptation-history/20261012-model-layout-080344/before-manifest.json)；[归档与恢复说明](../../../.local/adaptation-history/20261012-model-layout-080344/README.md)。
归档位于 Git 忽略的 `.local/adaptation-history/`，仅本机可用，不等于已部署到远端或已持久交付。

本模型归档 4 个过程文件。保留全部原文和权限，没有删除试验数据；以下材料只用于历史查询，不作为当前运行入口。

| 原模型内路径 | 归档文件 | SHA-256 |
| --- | --- | --- |
| `ppu/environment/deployment-identity.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Hy4-preview/ppu/environment/deployment-identity.yml) | `825eba8dbd5e3adce17e3392db33514af7debeb6c6e44a0fe199ba9f02276ac7` |
| `ppu/environment/environment-target.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Hy4-preview/ppu/environment/environment-target.yml) | `052d47bc7629bc144b81dab757e93422d414e0baf3dd8318d0b886860c5f9422` |
| `ppu/environment/runtime-config.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Hy4-preview/ppu/environment/runtime-config.yml) | `5d5f3ec658170c6ab205e0575b6a69cd9c645dc1145d008b22bcfabd3a296951` |
| `ppu/environment/service-state.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Hy4-preview/ppu/environment/service-state.yml) | `8d6b2e0983462b30bcce663a510431d80ad1f61f717e4eb53d1e2350444c4b3a` |

## 保留的验证边界

legacy `platform.yml` 仍保留历史状态及绑定；本次不把人工接受结果或旧 Markdown 总结改写为原生通过。未选择的阶段不补跑。
结构审计只能证明目录和链接一致；profile 升级不能证明当前服务身份、权重、已安装代码、图模式、精度、性能或镜像交付已验证。

## 本地审计待复核

本地审计保留 1 项 legacy 警告：accuracy 只有 compact Markdown，缺少原生 passing receipt。用户的 90.91% 业务接受结论与停止后续性能测试的决定保持原状，不自动安排重跑。
