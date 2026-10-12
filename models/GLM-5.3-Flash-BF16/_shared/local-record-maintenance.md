# GLM-5.3-Flash-BF16：本地记录整理

整理日期：2026-10-12。范围为目录、索引和已有 framework 契约；没有远端执行或新的适配/验收。

PPU-13 的功能适配已有记录；最新记录的 GPQA 为 172/198（86.87%），低于 88% 阈值，保留失败结论。

## 记录来源与适用范围

| 平台 | 来源 | 已记录 Host | 原记录状态 / 当前契约 |
| --- | --- | --- | --- |
| ppu | [legacy 平台记录](../ppu/README.md) | PPU-13 | functional |

## 现有契约与人工协作

本模型尚无显式 framework 工作区；保留原 legacy 布局和状态，不为整理而创建新适配、推断 framework/Host 或批量迁移历史阶段。后续用户选定新工作时使用 `new-framework`。

[人工接管与交回](../../../docs/human-collaboration.md)；[v2 证据契约](../../../docs/evidence-contract-v2.md)。只有用户选定实际阶段和 Host 后才推进适配。

## 文件归档与恢复

[整理前完整快照](../../../.local/adaptation-history/20261012-model-layout-080344/snapshot/models/GLM-5.3-Flash-BF16)；[逐文件哈希清单](../../../.local/adaptation-history/20261012-model-layout-080344/before-manifest.json)；[归档与恢复说明](../../../.local/adaptation-history/20261012-model-layout-080344/README.md)。
归档位于 Git 忽略的 `.local/adaptation-history/`，仅本机可用，不等于已部署到远端或已持久交付。

本模型归档 20 个过程文件。保留全部原文和权限，没有删除试验数据；以下材料只用于历史查询，不作为当前运行入口。

| 原模型内路径 | 归档文件 | SHA-256 |
| --- | --- | --- |
| `ppu/acceptance/grade_gpqa.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/grade_gpqa.py) | `1fe1ddceb2c285f87c8afff94803d10fcb75614b3e84651d63c059e7439f0f4e` |
| `ppu/acceptance/graph_sanity.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/graph_sanity.py) | `99d70fdbc3f5f5f4bd99fc2ba8ff93ece56d662177f76f59eeed3c540042c5e1` |
| `ppu/acceptance/graph_sanity_65k.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/graph_sanity_65k.py) | `fd12b8126a2fb2ab8b8a9befd671de535c677c7c9a63c646a508f64c74b08eec` |
| `ppu/acceptance/historical-entrypoints/README.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/historical-entrypoints/README.md) | `8bd42b2f0f39043ae033f78453ea382ced5845fa5e1263d39a268e0ffceb7e6d` |
| `ppu/acceptance/historical-entrypoints/start_gpqa.sh.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/historical-entrypoints/start_gpqa.sh.md) | `6d7741c0c87f99778612cbdc0ba101cb3441e132fb028606cd53a2f2d2f62533` |
| `ppu/acceptance/llm_config.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/llm_config.json) | `25dc0fcadf90e50a43e4038f02847e9250134b37fd0e43ded3f20327a3d1e0dc` |
| `ppu/acceptance/rerun_truncated_40k.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/rerun_truncated_40k.py) | `202b9bc0f2e982168480e6c310070023feb69898fdc0f3ddff5fbea2da793973` |
| `ppu/acceptance/start_gpqa.sh` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/start_gpqa.sh) | `43541a9c7ed913123d0b81011c762936947c551599bec164002147c2b05a2957` |
| `ppu/acceptance/trigger-ppu13-gpqa-truncated19-40k.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/trigger-ppu13-gpqa-truncated19-40k.yml) | `a7e0f0914cab0a9a638faab6a7d52ae1d4e02de88c866cf6ae5378b497940231` |
| `ppu/acceptance/trigger-ppu13-graph65k-sanity.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/trigger-ppu13-graph65k-sanity.yml) | `d36e523f9964189d1df6379fe8055cd53e133faec9efb26c504104cf41a37a5d` |
| `ppu/environment/collect-ppu13-environment.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/collect-ppu13-environment.yml) | `4b43294423f4677763ded01ef2918cbc9af66f125b3e3ea6b7fb219b074d5df5` |
| `ppu/environment/deploy-ppu13-graph65k-targeted40k.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/deploy-ppu13-graph65k-targeted40k.yml) | `aaed6d16861f0279b56435649f42bb237423899c78aa8c7819edea51389bcae6` |
| `ppu/environment/deployment-identity.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/deployment-identity.yml) | `5ebf964ec9e69a4d20809c6fa491bb483b9e67abecd17015629bfad7b975a456` |
| `ppu/environment/environment-target.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/environment-target.yml) | `6fd475c386986162cd0982cd69ebffa2a3a59c72f6934a43cf696d8fe2a5cd20` |
| `ppu/environment/history/commands.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/history/commands.md) | `40813c8b00a72772a10be9d5384e2249992c858d41bb3b1115e0d933f4ad7bb1` |
| `ppu/environment/history/flaggems-vllm-install-20260904.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/history/flaggems-vllm-install-20260904.md) | `864352543a82cf157662e06c53703f392933b08d0cce06a0af8c69f7c8b22acb` |
| `ppu/environment/history/hy4-glm53-scope-review-20260904.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/history/hy4-glm53-scope-review-20260904.md) | `06b4b85f63fa0cc8b1aa248cc8a746f1082536b4a647e7a5511c53e5b42a77b6` |
| `ppu/environment/history/progress.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/history/progress.md) | `a6da4613cdd8f4fc03f26480625b0199b8ea6cc7eb5b3b72bfa14a93313fdfc0` |
| `ppu/environment/runtime-config.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/runtime-config.yml) | `70555316ae3055010df91219dec5ccdb681ecadc67497ba3522f42cb9714a3c8` |
| `ppu/environment/service-state.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/service-state.yml) | `9268cc4dccfc43dae8004a97d114a0eb9d66d555034fdee9d3ff65a9873e35d4` |

## 保留的验证边界

legacy `platform.yml` 仍保留历史状态及绑定；本次不把人工接受结果或旧 Markdown 总结改写为原生通过。未选择的阶段不补跑。
结构审计只能证明目录和链接一致；profile 升级不能证明当前服务身份、权重、已安装代码、图模式、精度、性能或镜像交付已验证。
