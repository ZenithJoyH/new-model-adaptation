# DeepSeek-V4-Flash / metax

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)

当前 framework 记录：
- [vllm-plugin-fl](frameworks/vllm-plugin-fl/README.md)（v2；历史结论不自动成为新门禁通过）。

## 整理前平台说明（历史原文）

- Inventory group: `metax`
- Hardware query: `mx-smi`

当前任务：[V4 / vllm-plugin-fl / PR 427](frameworks/vllm-plugin-fl/README.md)，`mx-59/deepseek` 已通过 eager 与 decode FULL graph 的真实请求。最终脚本为 `/public-flash/jinghao/deepseekV4/start-model.sh`（SHA-256 `68ec107dd20e812e1e16faca384f381c06af55f696cd0f3f7097cb6dccc50cb0`）。结构化状态仍为 `blocked`，原因是标准 torch.compile 语义根因和正式 profile 回执/accuracy/performance 尚未完成，而不是模型当前无法服务。

平台根目录保留本索引、`platform.yml` 和显式 `frameworks/` 工作区。新任务使用
`scripts/new-framework <model> metax <framework-id>` 创建独立环境、适配和验收记录；平台
根目录已有的三个同名目录只作为历史隐式 `vllm-plugin-fl` 记录保留。
