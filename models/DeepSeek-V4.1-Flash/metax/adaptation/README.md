# MetaX 适配问题索引

身份更正（2026-09-21）：以下 001—004 实际针对 `DeepSeek-V4-Flash-Quant-W-INT8-PerChannel-A-INT8-PerToken`，不是 V4.1。保留历史位置，不批量迁移，不用于 V4.1 验收。后续工作使用 [V4 / MetaX / vllm-plugin-fl](../../../DeepSeek-V4-Flash/metax/frameworks/vllm-plugin-fl/README.md)。

- [001：PR 427 的 DeepSeek-V4 INT8 scale mapper 不匹配](001-pr427-int8-scale-mapper.md)
- [002：MetaX hash top-k 路由无效](002-metax-hash-topk-routing.md)
- [003：MetaX hc_head MM 编译失败](003-metax-mm-hc-head.md)
- [004：Q/KV 插入 ABI 不匹配](004-qnorm-kv-insert-abi.md)
