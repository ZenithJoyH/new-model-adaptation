# Qwen3.6-35B / metax

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)

当前 framework 记录：
- [vllm-plugin-fl](frameworks/vllm-plugin-fl/README.md)（v2；历史结论不自动成为新门禁通过）。

旧平台阶段记录按原位置保留（不作为新增执行入口）：
- [环境与设计](environment)。
- [问题台账](adaptation/README.md)。

## 整理前平台说明（历史原文）

目标为 `mx-104` 上持续运行的容器 `qwen3.6-35B`，模型
`/data/Qwen3.6-35B-A3B-nomtp`。已完成模型架构、运行环境、远端根映射和现有调用链核实；
适配阶段已把 Plugin 的 GDN prefill/decode 接到 FlagGems-vLLM，并把 MetaX、无 LoRA、
无 expert-map 的 fused MoE 接到其专用 `outplace_fused_experts`。路由契约、GDN 数值、Qwen
目标 shape MoE 数值和 Plugin 真实入口集成测试均通过；LoRA/expert-map 使用的分阶段
align/GEMM/sum 保持由 `default.flagos` dispatch，内部已改为 FlagGems-vLLM MetaX 算子，
并通过 E=256 恒等 expert-map 数值测试。
整模 eager/graph 尚未执行，因此状态仍为进行中。没有修改既有 dirty vLLM/FlagGems，也没有
停止、重启或移除容器或当前占卡的外部 VLLM 服务。

导航：[模型架构](../architecture-and-inference.md) ·
[环境与调用链](environment/environment-analysis.md) ·
[适配问题台账](adaptation/README.md)。验收阶段尚未选择、尚未执行。
