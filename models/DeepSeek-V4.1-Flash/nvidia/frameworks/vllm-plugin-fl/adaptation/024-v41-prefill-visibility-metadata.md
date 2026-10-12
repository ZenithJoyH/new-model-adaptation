# 024：V4.1 稀疏 SWA metadata 缺少预填充可见区间字段

## 元数据

- 状态：`root-cause-fix`（局部构造检查及第二十轮真实预热越过原读取）
- 首次出现及最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、DP1、eager、真实权重、前缀缓存启用、2048 token 上限

## 问题与原因

第十九轮八个 TP rank 于 05:19:13 进入稀疏 MLA 真实预热；最早失败的 Plugin FlashMLA prefill 路径在读取 `DeepseekV41SparseSWAMetadata.prefill_left_visible` 时报告 `AttributeError`。锁定版 `DeepseekSparseSWAMetadata` 基类不含 `prefill_left_visible` / `prefill_right_visible`，Plugin V4.1 FlashMLA 和 FlashInfer 路径却按较新 V4.1 接口读取它们。日志见 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log` 约 19120—19150 行。后续 NCCL TCPStore 断连是 worker 异常的连锁反应。

## 受控修复与证据

在 Plugin 自有 `vllm_fl/models/deepseek_v4_1/sparse_mla.py` 的 V4.1 metadata 子类新增两个可选字段，默认 `None` 表示文本路径没有图像可见区间；不修改锁定版 vLLM 基类。应用前服务已退出；补丁哈希、源码 SHA、`git apply --check`、Ansible `--check --diff` 均核实。文本路径实例化检查通过，源码 SHA-256 从 `e1f2f56617ea76b87e014080826d9f86c32de9e5b66cec935f8a8dca72eb4576` 变为 `df55389c337effacc98631c444716cf063fd986ee1581ab12285f1aa74520d05`。补丁保存在 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-prefill-visibility-20260924/`。第二十轮真实权重 TP8 eager 已越过字段读取，随后在 ratio-2 压缩器因缺少稳定请求槽失败，见[问题 025](025-v41-request-slots-v2-runner.md)。因此原字段阻塞解除，但仍未完成最小推理。

## 限制与下一步

- 当前修复仅给出无图像区间的文本路径默认值；视觉输入所需的实际可见区间生成尚未验证，不能据此声称图像推理正确。
- 继续核对真实预热和最小文本生成；随后仍需 full graph、长上下文和正式验收。
- 知识库处理状态：`needs-validation`。
