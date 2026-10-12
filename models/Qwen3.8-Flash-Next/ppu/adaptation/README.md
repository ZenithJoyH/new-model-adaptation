# Qwen3.8-Flash-Next / PPU 问题索引

2026-09-06 整理历史材料。编号是本次整理顺序，原记录中的日期和结论保留；不代表重新执行验证。

当前操作请先核对 `../environment/runtime-config.yml` 和阶段门禁。

原始过程脚本与完整旧目录保存在控制端 `.local/adaptation-history/20260906-workspace-repair/`，
仅用于历史取证，不作为当前启动入口；该本地归档不提交到 Git。

- [001：FlagGems slice 不支持 bool](001-flaggems-slice-bool.md)
- [002：深度卷积通道填充导致显存膨胀](002-depthwise-conv-memory.md)
- [003：TP sample_tokens 超时与缓解](003-tp-sample-tokens-timeout.md)
- [004：index 首次调优 SQLite 锁冲突](004-index-autotune-sqlite-lock.md)
- [005：GPQA 长推理达到生成上限](005-gpqa-generation-cap.md)
- [006：Qwen3.8 新算子迁移至 FlagGems](006-flaggems-qwen38-operator-ownership.md)
- [007：GPQA c64 混合 prefill/decode 停滞与 vstack 动态特化](007-vstack-dynamic-shape-stall.md)
- [008：PCCL graph replay 后 collective work FIFO 停滞](008-pccl-graph-eager-collective-stall.md)
- [009：FULL_AND_PIECEWISE 启动时 FlagGems normal_ HGGC 加载段错误](009-full-piecewise-flaggems-normal-hggc-segfault.md)
- [010：Common slot graph replay 完成性导致 GDN 状态污染](010-common-slot-graph-replay-visibility.md)
- [011：uniform decode graph replay 后 logits all-gather rank 分叉](011-async-copy-stream-logits-allgather-divergence.md)
- [历史算子检索证据](../environment/flaggems-operator-evidence.md)

环境计划、参考材料和历史进度已归入 `../environment/`；验收结论见 `../acceptance/`。
