# 011：锁定版 V4 MoE 构造接口与 V4.1 路由参数不一致

- 状态：`resolved`（第六轮 TP8 已越过构造；MoE 前向与视觉路由待验证）
- 首次出现及最后验证：2026-09-23
- Host / 容器：`H100-149` / `deepseek-v41-plugin-adapt-20260923`
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、eager、前缀缓存启用、`max_model_len=2048`

第五轮整模启动在首层 MoE 构造时报
`TypeError: DeepseekV4MoE.__init__() got an unexpected keyword argument 'use_sequence_parallel'`，
8 个 worker 同样失败。原始日志为
`H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`
中 18:30:50 的 traceback，仍未进入权重加载。

锁定版 vLLM V4 MoE 只收配置和 prefix，直接读取 HF 配置的
`num_hash_layers`，没有 V4.1 新增的 sequence-parallel、draft 专家数、
视觉 sentinel 路由接口。当前 TP8 未启用 expert parallel，因此 Plugin 的
`_use_sequence_parallel()` 为假；本次只针对正常文本层，把 HF 配置的
`num_hash_layers` 在构造旧 MoE 时临时设为 0，再恢复原值。sequence-parallel
和 draft-layer 显式拒绝，避免静默误算。权重索引有 43 个 `gate.bias_vl` 项，
Plugin 对视觉模型注册该参数，使权重可加载；旧 MoE 的视觉 sentinel 路由
仍未实现，视觉推理不能据此声称正确。

改动只在 editable Plugin 的
`/vllm-workspace/vllm-plugin-FL/vllm_fl/models/deepseek_v4_1/nvidia/model.py`。
变更前 SHA-256
`92caf835a8409447796a1ddd69298787d488a9ed87e4093db117d16429b6e047`；
补丁在远端 `02-issues/h100145-ring-20260923/v41-moe-constructor-h100149.patch`，
根据原文件生成，`git apply --check` 通过。第六轮于 20:04:12 越过 MoE 构造，
随后因独立的稀疏索引器签名错误退出（见 012）；
实际 MoE 文本前向、视觉路由、graph 和精度都未验证。vLLM 未修改。

知识库处理状态：`local-only`。
