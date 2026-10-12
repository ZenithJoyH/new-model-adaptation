# 010：FP8 O 投影 recipe 函数在锁定版不接受参数

- 状态：`resolved`（第五轮 TP8 已越过该函数调用）
- 首次出现及最后验证：2026-09-23
- Host / 容器：`H100-149` / `deepseek-v41-plugin-adapt-20260923`
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、eager、前缀缓存启用、`max_model_len=2048`

第四轮整模启动在 FlashMLA attention 初始化时报
`TypeError: compute_fp8_einsum_recipe() takes 0 positional arguments but 1 was given`，
8 个 worker 同样失败，尚未加载权重。原始日志为
`H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`
中 18:22:13 的 traceback。

锁定版 vLLM 的 `vllm.models.deepseek_v4.nvidia.ops.o_proj.compute_fp8_einsum_recipe()`
只根据 GPU capability 生成 recipe。H100 为 SM90，返回 `(1, 128, 128)` 和
`tma_aligned_scales=False`。新参考版的函数可接收 `block_size`，但仅在 SM100+
分支使用该值，因此 H100 上去掉实参不改变 recipe。Plugin V4.1 的 FlashMLA
及两个 FlashInfer 类均有带参调用，本次统一改为零参；高于 SM90 的语义
未验证，不据此宣称跨平台支持。

变更前 `flashmla.py` SHA-256 为
`73657340352d4a4b9ce8806b4ace89cc541d43877e7ac8eebbd8d7f8d8a29c38`，
`flashinfer_sparse.py` 为
`6b04d9f3fff52807df814e8ece7dfe5f6b4b2e81fac21bf24441779c13bd3e02`；
补丁在远端 `02-issues/h100145-ring-20260923/v41-einsum-recipe-h100149.patch`。
哈希守卫与 `git apply --unidiff-zero --check` 通过，修改后检查三处调用均为
零参。第五轮于 18:30:50 越过该函数调用，随后因独立的 MoE 构造参数错误退出
（见 011）。实际前向/数值和 graph 尚未验证。vLLM 未修改。

知识库处理状态：`local-only`。
