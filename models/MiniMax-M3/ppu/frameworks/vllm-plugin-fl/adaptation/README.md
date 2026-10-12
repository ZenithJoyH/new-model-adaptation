# PPU-07 适配与诊断问题索引

| ID | 问题 | 状态 | 证据 |
|---|---|---|---|
| 001 | FlagGems-vllm `swigluoai_uninterleave` 空张量/FakeTensor/共享 workspace 别名边界 | 修复已验证并推送；跨平台实机未验 | [001-swigluoai-boundary.md](001-swigluoai-boundary.md) |
| 002 | 固定 GPQA 十题的 `doc_id=8` 超长生成与失分 | 假设；sanity 9/10 | [002-gpqa-first10-doc8-long-generation.md](002-gpqa-first10-doc8-long-generation.md) |
| 003 | GPQA 全量分数达标但 runner 数据集字段冲突 | 已定位；原生回执失败 | [003-gpqa-runner-config-conflict.md](003-gpqa-runner-config-conflict.md) |

本轮的全量诊断 strict 178/198（89.90%）高于用户当前指定的 88%，但此索引不代表适配阶段或正式验收已完成。
