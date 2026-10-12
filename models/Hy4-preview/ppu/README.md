# Hy4-preview / ppu

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)


旧平台阶段记录按原位置保留（不作为新增执行入口）：
- [环境与设计](environment/README.md)。
- [问题台账](adaptation/README.md)。
- [验收记录](acceptance/README.md)。

## 整理前平台说明（历史原文）

## 当前状态

| 项目 | 状态 |
|---|---|
| 目标 Host | `PPU-07` |
| 适配容器 | `hy4` |
| 平台状态 | `functional` |
| 模型结构分析 | 已完成 |
| 环境分析 | 已完成 |
| 适配 | 已完成 |
| 验收 | c64、80K 全量 strict 90.91%，用户已确认精度通过；性能长上下文三档超时并停止 |
| 最后核对日期 | 2026-09-14 |

Plugin `2fa5f18` 加通用 `index` blacklist 的最新 graph 实例已通过 19 个聚焦 UT 和 c8 sanity，
并完成 GPQA Diamond 全量 198 题、并发 64、thinking/high、80K 轮次。服务始终健康且未再复现
EngineCore 卡死；strict 180/198（90.91%）超过 87% 业务基线。不过 doc_id 81 有一个唯一
`<TIMEOUT>`，违反 `allow_timeouts=false`，runner exit 1 且没有 passing acceptance receipt。
用户于 2026-09-11 明确接受 90.91% 超过 87% 业务基线，将 accuracy 判为通过；上述
timeout/receipt 限制继续保留。最终 graph launcher 已安装并通过同映射、SHA、语法、服务拒绝
保护和 health 验证，因此 adaptation 保持完成。正式性能只有 `1024/4096 → 1024` 两档成功，
`16384/32768/65536 → 1024` 三档按场景标记超时；用户于 2026-09-14 决定停止后续性能测试，
所以 performance 为 failed，平台保持 `functional`，不标记 `optimized`。状态详情以
[platform.yml](platform.yml) 为准。

## 目录导航

- [模型结构与推理链路](../architecture-and-inference.md)
- [环境与平台分析](environment/README.md)
- [适配问题台账](adaptation/README.md)
- [验收计划与结果](acceptance/README.md)

## 当前关键问题

- [W8A8 根因修复](adaptation/003-flaggems-w8a8-fix-installed-20260904.md)
- [GPQA 乱码与大 M 问题](adaptation/005-gpqa-corruption-triage-20260904.md)
- [FlagGems SQLite 并发锁复现](adaptation/002-flaggems-sqlite-lock-reproducer.md)
- [Sparse MLA 小 head](adaptation/013-flaggems-sparse-mla-small-head.md)
- [BF16 Indexer decode 职责收敛](adaptation/014-bf16-indexer-topk-ownership.md)
- [bool slice 服务故障与安全回退](adaptation/016-flaggems-bool-slice-service-failure.md)
- [GPQA c32/c8 与 W8A8 large-M 修复](adaptation/017-gpqa-temp0-length-preemption.md)
- [最新 `sample_tokens` 超时](adaptation/018-latest-accuracy-eval-failure-20260908.md)
- [正式精度结果汇总](acceptance/accuracy-results.md)

## 下一步

1. 本轮不再继续性能测试；保留已有 CSV、stdout、stderr、error JSON 和终态记录作为失败证据。
2. 当前存活服务是关闭 prefix caching 的性能专用 profile；若开展任何非性能测试，必须先切回通用
   `start-model.sh` 对应的正常 prefix-cache-enabled profile。
3. 后续若重新开启性能验收，必须作为新 run 执行并重新验证全部工况，不得把本轮超时档伪装为通过。

所有远端操作继续遵守用户指定工作根、容器不得停启、vLLM 源码只读等仓库规则。
