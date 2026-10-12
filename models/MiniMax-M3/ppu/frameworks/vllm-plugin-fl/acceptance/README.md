# 适配验收索引

当前仅为 PPU-07 最新代码诊断，不是正式验收回执。记录执行模式、小批量与全量诊断的远端原生证据；文件存在不代表通过。

- 2026-09-24：整模 eager 与显式 `FULL_AND_PIECEWISE` 图服务真实推理通过；`FULL` 请求自动降为 `FULL_DECODE_ONLY`，不算 full graph 通过。服务日志：`/mnt/nfs/users/jinghao/minimaxM3-new/04-runs/validation-decode-piecewise-graph-target-20260924.log`。
- 固定前十题（`doc_id=0..9`）10 并发、`max_gen_toks=30000`：完整 10/10、无超时，strict 9/10，未满足逐题全对。原生结果：`/mnt/nfs/users/jinghao/minimaxM3-new/04-runs/gpqa-sanity-first10-latest-20260924/`。
- 198 题、64 并发、strict 阈值 80% 的 30,000-token 全量尝试刚启动便因用户改为 50,000 token 而精确终止，退出码 143，不能评分。其目录 `/mnt/nfs/users/jinghao/minimaxM3-new/04-runs/gpqa-diamond-c64-latest-20260924/` 保留。
- 用户授权在十题 9/10 情况下仍跑全量诊断。50,000-token 全量 run 已完成：198 个唯一题目、零 timeout/空响应，strict 178/198＝89.90%，高于用户当前指定的 88%。但外层 runner 的 legacy `dataset_path` 与正规化 `datasets` 字段校验冲突导致退出码 1、原生回执 `failed`；运行前冻结的 minimum 仍为 80%，不能事后改写。完整证据见 [2026-09-24 全量诊断报告](gpqa-diamond-gen50k-diagnostic-20260924.md)。
- architecture/environment/adaptation 前置回执仍不完整，execution-mode/sanity 及性能/最终启动脚本亦未正式验收；本轮只可标记“诊断分数达到 88%”，不能更改 `framework.yml` 的正式通过状态。
