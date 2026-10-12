# MiniMax-M3 / PPU-07 / vllm-plugin-fl

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

2026-09-24：新容器的算子、Plugin 设备测试、整模 eager 与目标 graph 实推已验证；全量 GPQA 198 题诊断 strict 178/198＝89.90%，高于用户当前指定的 88%。据此，**PPU-07 本轮新代码重新适配的功能与 GPQA 目标判定通过**。固定 GPQA 十题 strict 9/10，未通过逐题全对 sanity；原生 runner 回执因配置字段冲突失败，framework 前置阶段亦未完成。因此本次判定不等于项目正式验收通过，也不证明其他平台已验证。

- Host `PPU-07`；模型容器 `minimaxM3-latest-20260924`，评测容器 `minimax-m3-eval-latest-20260924`，两者保持运行。批准的 host/container 工作根均为 `/mnt/nfs/users/jinghao/minimaxM3-new`，映射设备号/inode 为 `41:12343954721`。
- 评测时固定源码：Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c`；FlagGems-vllm 基线 `1f9ac0e0caf3c32111f6be44c8e4d2fef2359546` 加本轮两文件边界修复；FlagGems `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389` 未修改。修复内容已通过隔离本地 checkout 提交并推送至用户 FlagGems-vllm fork `support-minimaxM3` 的 `e7a88149c3ca73b23f03f14e9a1bc6b21981015a`；运行容器的 detached HEAD 未更改。Plugin 没有新增 tracked diff。详见 [001-swigluoai-boundary.md](adaptation/001-swigluoai-boundary.md)。
- FlagGems-vllm 聚焦测试 21/21、Plugin PPU 测试 22/22 通过。`FULL` 请求被 MiniMax-M3 注意力后端自动降级成 `FULL_DECODE_ONLY=(FULL,NONE)`；依用户纠正，改以显式 `FULL_AND_PIECEWISE=(FULL,PIECEWISE)` 为目标，日志分别显示 mixed prefill-decode 的 PIECEWISE 捕获与 decode 的 FULL 捕获，服务健康且真实问题回答 `4`。eager 实推同样通过。服务 TP16、BF16、`max_model_len=65536`、prefix caching 开启，端口 8024。
- 固定题清单为 `03-acceptance/gpqa-sanity-first10-manifest-20260924.json`（`doc_id=0..9`）。10 并发 sanity 原始结果在 `04-runs/gpqa-sanity-first10-latest-20260924/`：10/10 样本完整、零超时、strict 9/10；`doc_id=8` 目标 C、输出 D，且生成达到 30,000-token 上限。见 [002-gpqa-first10-doc8-long-generation.md](adaptation/002-gpqa-first10-doc8-long-generation.md)。
- 初始 30,000-token 全量评测在用户更改参数后精确终止，退出码 143，原始目录 `04-runs/gpqa-diamond-c64-latest-20260924/` 保留。50,000-token 全量诊断在 `04-runs/gpqa-diamond-c64-gen50k-20260924/` 完成，冻结配置 SHA-256 `03182d8c03d71759ed9088426e42480c138874122059d2e9f201e9c603ebab20`；198 题、64 配置并发，strict 178/198、零 timeout/空响应。原生 runner 退出码 1、回执 `failed`，原因是数据集字段校验冲突；冻结阈值为 80%，用户此后指定 88%，观测分数高于两者，但不能追溯改写。详见 [全量诊断报告](acceptance/gpqa-diamond-gen50k-diagnostic-20260924.md)。

所有上述相对路径均位于批准的远端根 `/mnt/nfs/users/jinghao/minimaxM3-new/`，本地仅保留结论与证据引用，不复制原始日志。原旧容器 `minimaxM3-opt-20260921` 保持运行，但其性能型 8013 模型服务已依用户授权停下以释放 PPU；正式验收前需补齐 framework 前置回执、十题全对、有效的 88% 原生回执、性能与最终启动脚本验证。`framework.yml` 保留 `blocked` 以准确表达尚未完成的正式工作流，不否定本轮限定范围的重新适配结论。
