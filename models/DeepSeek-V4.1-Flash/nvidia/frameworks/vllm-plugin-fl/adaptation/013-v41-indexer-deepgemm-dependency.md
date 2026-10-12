# 013：锁定版 CUDA 稀疏索引器强制依赖缺失的 DeepGEMM

## 元数据

- 状态：`open`（Plugin 替代实现已接入，整模验证进行中）
- 首次出现及最后验证：2026-09-23
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- 平台 / Host / 容器：NVIDIA H100 / `H100-149` / `deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `ee0da84ab9e04ac7610e28580af62c365e898389` /
  `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`
- 模式：TP8、eager、前缀缓存启用、`max_model_len=2048`

## 问题和证据

第七轮整模启动在八个 TP worker 的 `SparseAttnIndexer.__init__()` 中报
`Sparse Attention Indexer CUDA op requires DeepGEMM support in the current vLLM environment`，
发生于权重加载前。原始日志位于
`H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`
的 20:13:22 一轮。容器内 `deep_gemm` 不可导入；锁定版 vLLM 的索引器
构造无条件检查该依赖，且其 top-k 路径调用缺失的 `vllm._C`。因此即使
短上下文运行时会跳过 logits/top-k，构造阶段仍然失败。

`FlagGems-vllm` 当前 checkout 已有 `fp8_fp4_mqa_logits`、
`fp8_fp4_paged_mqa_logits`、`cp_gather_indexer_k_quant_cache`、
`bucket_sort_topk` 和 `persistent_topk`；`FlagGems` 也有部分相应
算子。根据优先级，在 Plugin 的 NVIDIA indexer 适配层调用
`FlagGems-vllm`，不复制现有算子，也不修改 vLLM 或依赖源码。
两库均未发现 V4.1 候选块过滤的完整实现；见问题 012。

## 受控处理

本轮唯一实质变量是 H100 FP8 稀疏索引器后端。Plugin 新增
`vllm_fl/models/deepseek_v4_1/nvidia/indexer.py`，复用锁定版 vLLM 的
metadata、workspace 和 K 缓存约定，以 `FlagGems-vllm` 算子完成
prefill/decode logits 与 top-k；`attention.py` 只在 Hopper CUDA
选择该后端，其他平台仍走原有 indexer。FP4、非 Hopper 以及当前候选预算
之外的上下文不在此实现支持范围内，须显式失败或另行验证。

变更前 `attention.py` SHA-256 为
`92b0d1e04feb118c197270f70675d0a1f74b4f9db4c53cd4d03f033d48c5bd2d`。
补丁存放于远端
`/public/flagos/jinghao/deepseekV4.1/02-issues/h100145-ring-20260923/v41-flaggems-indexer-h100149.patch`；
Ansible `--check --diff`、`git apply --check` 和实际应用均通过，Plugin
模块独立导入通过。第八轮 TP8 eager 整模启动在验证中。此处理尚不能证明
数值正确、graph 支持或完整长上下文推理。

知识库处理状态：`needs-validation`。
