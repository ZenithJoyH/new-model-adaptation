# 适配问题索引

| 编号 | 问题 | 状态 |
| --- | --- | --- |
| [001](001-native-registration-and-moe.md) | 4.7 注册、MoE 与 canvas M-RoPE | TP2 eager/graph 功能回归通过 |
| [002](002-parastor-triton-cache-race.md) | 共享 Triton cache 竞争 | TP2 单变量对照复现；进程隔离 mitigation 已验证 |
| [003](003-gdn-full-graph-limit.md) | GDN backend 无法覆盖 prefill full graph | 已验证限制；采用 decode-full |
| [004](004-full-and-piecewise-graph.md) | 用户指定的 FULL_AND_PIECEWISE 图模式 | 诊断通过；prefill PIECEWISE 5/5、decode FULL 4/4 |
| [005](005-user-launcher-startup-blocked.md) | 用户调整的 8020 脚本启动卡住 | 原始失败已记录；仅恢复 Triton 进程隔离后 8020 就绪、请求回归通过 |
