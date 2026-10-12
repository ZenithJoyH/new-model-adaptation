# Qwen3.6-35B / MetaX / vllm-plugin-fl

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `not_started` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

2026-10-10，在用户指定的 mx-59 现有容器 `qwen3.6-35B` 中完成 MetaX 非量化 MoE
接入已安装 FlagGems-vLLM，并优化完整 MoE 的 tile/workspace、GDN 页缓存路径和
prefill metadata 转发。实际安装回归 196 项通过，缓存位置修正后再次通过；三个大
prefill 回归也通过。已重启本任务服务，两个 TP rank 的实际 trace 确认新路径命中。

用户指定的三个场景完成无 profiler、前缀缓存关闭的原生对照：输入 4096/16384/65536、
输出 1024、并发 64、请求 128；基线和最终测试均各三轮，剔除第一轮。
输出总吞吐依次为 560.05→679.54、239.44→395.51、72.00→107.29 tok/s，
提高 21.3%、65.2%、49.0%，所有轮次均 128 成功/0 失败，原生 validator 零错误。
最终采用 batch8192、显存预算0.9、FULL_AND_PIECEWISE/capture64；收益包含算子与调度。
平均 TTFT/TPOT 改善，但4K/64K的 P99 ITL 上升，不能声称所有时延指标改善。
详细修改、原生证据、失败与限制见[003：端到端优化](adaptation/003-e2e-optimization.md)，
职责与兼容性见[代码设计审查](environment/003-optimization-code-review.md)。
最终脚本 `/public-flash/jinghao/qwen3.6-35B/start-model.sh` 与容器内部
`/opt/flagos/qwen3.6-35b/start-model.sh` 一致，实际由内部副本启动 API PID532870。
正常服务显式开启 prefix/mamba align；30个长输入请求与2次prefix重复检查通过，
命中3168 tokens，健康检查HTTP200。8个短例均HTTP成功，其中2个达到128-token上限；
首都问题以512-token预算补查完成，不将原截断结果改写为完整通过。

历史记录：[001：MoE 迁移](adaptation/001-mx59-moe-flaggems-vllm.md)、
[002：完整入口与分阶段对照](adaptation/002-full-vs-staged-moe.md)。完整入口仍包含多个
GPU kernel，性能依赖 shape/config；本轮不宣称它在所有场景必然更快。

vLLM 与 FlagGems 保持原源码状态，保留所有既有 dirty 工作；没有提交或 PR。
本轮是局部优化诊断，正式整模精度和镜像新容器验收未执行，框架五阶段状态仍为
`not_started`，不设置 `functional/optimized`。旧 mx-104 的上级 legacy 记录不证明
本次 mx-59 通过。
