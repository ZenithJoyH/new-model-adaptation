# 009：锁定版 KernelConfig 没有可选 JIT 预热开关

- 状态：`resolved`（第四轮 TP8 越过该属性读取）
- 首次出现及最后验证：2026-09-23
- Host / 容器：`H100-149` / `deepseek-v41-plugin-adapt-20260923`
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、eager、前缀缓存启用、`max_model_len=2048`

第三轮整模启动通过 ViT 与 SWA 缓存构造后，8 个 worker 在 `attention.py`
读取 `vllm_config.kernel_config.enable_jit_warmup` 时一致报 `AttributeError`。
原始日志为 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`
中 18:15:07 的 traceback。锁定版 vLLM 的 `KernelConfig` 无该属性，且
vLLM 源码内没有此开关；V4.1 模型另在 `nvidia/model.py` 使用同一属性。

这两处仅控制 Triton kernel 提前注册/预热，不改变实际 forward 的计算分支。
本次只在 Plugin 的两个 V4.1 调用点把缺失属性明确视为未启用预热；新配置
如提供该属性，仍按其值执行原分支。变更前 `attention.py` SHA-256 为
`dae9b0c31f31e2560253121c19fc35207155a2dee84b807de21a3b35a1d82f7a`，
`nvidia/model.py` 为
`5189d68f1a8232e1847dc318841c68c91f046405be80cf8048ad0ad14ef7b8d0`；
补丁在远端 `02-issues/h100145-ring-20260923/v41-jit-warmup-h100149.patch`，
`git apply --check` 通过。第四轮服务已启动，除这两个属性读取点外未改变
模型、权重、启动参数或缓存路径。第四轮于 18:22:13 越过该属性读取，随后
因独立的 FP8 O 投影 recipe 签名错误退出（见 010）。eager 数值与 graph 尚未
验证；vLLM 保持锁定。

本项是框架配置接口差异，与算子缺失无关；知识库处理状态：`local-only`。
