# 适配问题索引

- [005：FlagGems sparse MLA 接线与 MetaX 共享内存阻塞](005-flaggems-sparse-mla-bridge.md)。历史阻塞由 006 的受控 MetaX 配置修复。
- [006：获授权的 MetaX sparse MLA 配置与边界修复](006-metax-sparse-mla-config.md)。prefill/decode 聚焦设备回归通过。
- [007：MetaX partial-state Triton launch_pdl 兼容](007-metax-save-partial-states-pdl.md)。NVIDIA-only 能力守卫已由整模 eager 验证。
- [008：MetaX W8A8 scaled-mm 与整模 eager 闭环](008-metax-w8a8-scaled-mm.md)。TP8+EP eager 真实请求精确返回 `OK`。
- [009：MetaX 图模式编译正确性与最终运行配置](009-metax-graph-correctness.md)。decode FULL graph 真实请求 `OK`/`5` 通过；标准 torch.compile 语义错误保留为已知限制。
- [010：MetaX TP8 启动时 FlagGems SQLite WAL 锁竞争](010-flaggems-sqlite-startup-lock.md)。GPQA 后安全服务首次恢复失败；预初始化独立数据库后恢复，根因修复仍待验证。
- [011：GPQA Diamond 低分的评测模式与剩余精度差距](011-gpqa-reasoning-mode-score-gap.md)。官方 88.1 对应 Think Max；当前全量任务缺省为非思考模式，剩余差距另需同口径对照。
- [012：GPQA Max 阶段评分口径漂移与格式漏判](012-gpqa-max-partial-score-drift.md)。61 题中止批次按原生 strict 为 50/61；阶段脚本正则不等价，另有 4 条星号格式漏判。
- [013：GPQA 续跑直调缺少 API key 占位值及异常伪装超时](013-gpqa-resume-api-key-timeout-masking.md)。首次直调 137 条伪超时已作废；补齐原 Runner 的非秘密占位值后新 attempt 续跑中。
- 001—004 的历史诊断误存于 [V4.1/MetaX 旧索引](../../../../../DeepSeek-V4.1-Flash/metax/adaptation/README.md)，其中已注明真实目标是 V4。按项目要求不批量迁移历史记录，不复用 V4.1 身份或验收结论。
