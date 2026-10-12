# Qwen3.8-Flash-Next / ppu

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)


旧平台阶段记录按原位置保留（不作为新增执行入口）：
- [环境与设计](environment/README.md)。
- [问题台账](adaptation/README.md)。
- [验收记录](acceptance/README.md)。

## 整理前平台说明（历史原文）

2026-09-11 完成算子所有权与源码命名空间整理并推送：FlagGems
`support-qwen3.8-flash@4bce4f20fbd589299dc4ebf966b2748d2dff9144` 基于当前 upstream
`851ba60493692f5c84c5636f9117c53ab1f156ae`，以唯一一笔适配提交新增 QSA、PLE 状态、
packed GDN 和 common-slot mapping 共 10 个公开算子；Plugin
`support-qwen3.8-flash@939600b323c02c21916f1f76bfb4cd8c2b02578d` 先同步最新 upstream
`e2c6e2c`，再重放当日 HY4 PR `ff87b683ec9c6c1925dbedf12261914e45569b52` 的五笔提交，
最后以一笔 Qwen3.8 commit 收口。Plugin 只保留能力检测、既有 dispatch 注册和 vLLM
参数适配。公开 dispatch 名称按 QSA、PLE、GDN 和 slot mapping 语义命名，每个 FlagGems
符号独立检测可用性，不再绑定 Qwen3.8 模型名或要求十个符号同时存在。FlagGems 实现位于
`fused/qsa.py`、`ple_state.py`、`gdn_packed_decode.py`、`common_slot_mapping.py`；Qwen 模型专用
实现合并为单个 `vllm_fl/models/qwen3_8_flash_next.py`，文件内按 config、PLE、QSA、GDN、
cache metadata 和模型装载分段。Plugin 内原有
`dispatch/backends/triton/qwen38` 已移除，vLLM 仍保持
`ee0da84ab9e04ac7610e28580af62c365e898389` 未修改。

当前容器 `qwen3.8-flash` 持续运行。2026-09-18 正式轮次在 PPU 8–15:8038 和 PPU 0–7:8039 使用两个
相同参数的 TP8 graph 服务，并经 8040 轮询代理完成 full198、c64 GPQA：170/198（85.86%），
覆盖 198/198，7 个样本达到 60000-token 生成上限，低于 88% 阈值。全部请求 HTTP 200，服务无 RPC
timeout、OOM 或异步挂死；失败已归因到真实生成上限与仍待隔离的跨实例稳定数值分叉。详见
[正式精度回归](acceptance/gpqa-c64-auto-capture-dual-20260918.md)与
[问题 012](adaptation/012-a-b-accuracy-gap.md)。正式轮次结束后，8039 已切换为补齐正式 blacklist 的
eager 诊断服务；当前 8040 不能作为正式双 graph 入口复用。提交前在容器中通过 FlagGems
80 项 CPU/边界测试、Plugin 405 项模型与完整 dispatch 测试、目标模块内存编译及
`git diff --check`。当前精简记录位于远端
`/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/flaggems-ownership-organized-20260911.txt`，
SHA-256 为 `ae28fca9410ccae05cfb3fc3d4224ad3ac245c1f457b22e7714ac9094b9d5cf1`。
2026-09-10 的 `flaggems-for-day0@37716d41` 和对应记录保留为整理前历史证据。
测试时 PPU-01 的 16 张卡均被四组无关 TP4 服务占用，未运行新组合的 PPU eager/graph 和整模
回归，也未停止或干扰这些进程，因此适配阶段保持 `in_progress`。详见
[006：算子迁移至 FlagGems](adaptation/006-flaggems-qwen38-operator-ownership.md)。

以下 2026-09-07 的整模、精度与性能材料是迁移前 revision 的历史证据，不能替代新组合重验。

目录导航：[环境与设计](environment/README.md) · [问题台账](adaptation/README.md) ·
[验收轮次](acceptance/README.md) · [Plugin 设计审查准备](environment/plugin-change-review.md)。
全量评测与 22 题生成上限诊断分别保留；目录整理不代表重新验收。

平台历史状态：functional（迁移前 revision 的 graph 全模型冒烟通过，正式精度与性能仍待重跑）。
目标 PPU-01 容器 `qwen3.8-flash`；容器保持运行。

已完成架构/环境分析；FlagGems 已 fast-forward 到 clean
`dcd0cfeae8187dee691656c0616c1ed95899c2ae`。最终 Plugin revision
`a5c6f0ca373afa606b68d2daa4bb4a9dcc1833c5` 已推送至 `support-qwen3.8-flash`，集成 HY4/T-Head
基线并收窄 Qwen runner capability、保护未来上游注册所有权。最终 410 项结构/算子/调度回归全部
通过。vLLM `ee0da84ab9e04ac7610e28580af62c365e898389` 保持干净未修改。

整模第一次启动完成 131 分片权重加载并就绪，首次请求在调度元数据处理阶段触发 FlagGems slice 不支持 torch.bool，进程自动退出。已在容器 /bug/flaggems-slice-bool-20260904 独立复现 eager/graph；通过插件 thead.yaml 排除该算子，原生切片的 eager/graph 回归通过，修复后整模 eager 最小推理通过；首次请求130.283秒包含 PLE 卷积自动调优。

候选插件按文本路径运行（language-model-only）；视觉/MTP 等未验收。最终集成 revision 在连续卡
8–15 上以 TP8、FULL_DECODE_ONLY、`max-model-len=65536`、`max-num-seqs=32`、
`max-num-batched-tokens=4096` 完成全模型冒烟，请求返回 `2` 且服务继续健康。正式 GPQA 和性能尚未
在最终组合上重跑，不能标记适配完成。

见[架构](../architecture-and-inference.md)、[环境](environment/environment-analysis.md)、[计划](environment/platform-adaptation-plan.md)、[进度](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/history/progress.md)。

8并发长输入 sanity 曾发现 FlagGems 深度卷积按组通道填充16倍并产生7.79GiB临时张量；正式精度又发现默认300秒 TP RPC超时，以及 FlagGems `index` 多 rank 首次调优共享 SQLite 时的锁冲突。问题均有独立证据。最终运行配置以 `VLLM_FL_FLAGOS_BLACKLIST_APPEND=slice,conv1d,_conv_depthwise2d,index` 追加现场回退项，并将 `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS` 设为1800；不覆盖 tracked T-Head 平台策略。同步 FlagGems 后三项 PPU eager/graph 探针、410项回归及全模型冒烟通过；完整验收仍在继续。
