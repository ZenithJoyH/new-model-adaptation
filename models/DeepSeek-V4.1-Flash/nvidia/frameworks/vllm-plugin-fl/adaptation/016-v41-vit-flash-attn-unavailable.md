# 016：视觉编码器自动选择了不可用的 FlashAttention

## 元数据

- 状态：`open`（替代后端越过原故障点，整模后续另见问题 017）
- 首次出现及最后验证：2026-09-23
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- 平台与 Host：NVIDIA H100 / `H100-149`
- 容器与镜像：`deepseek-v41-plugin-adapt-20260923` / `deepseek-v41-plugin-fl:h100145-20260923-r1`
- Plugin / FlagGems-vllm / vLLM：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、eager、前缀缓存启用、`max_model_len=2048`

## 问题现象

第十轮整模诊断在 22:35:45 完成 896 GiB 权重加载（1653.31 秒），
22:39:12 首次 profile 图像输入时 8 个 worker 报
`TypeError: 'NoneType' object is not callable`。首个 worker 栈从 Plugin
`common/vision.py:139` 的 `MMEncoderAttention` 进入锁定版 vLLM
`vit_attn_wrappers.py:51`，调用 `flash_attn_varlen_func` 时失败。
原始证据在 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`，
第十轮约 8039—8110 行。API 未就绪，因此不能判为最小推理通过。

## 诊断与假设

已检索 `docs/troubleshooting/` 和 DeepSeek V4/V4.1 相邻问题记录，
未找到相同的 FlashAttention callable 缺失签名可直接复用。
容器内导入 `vllm.v1.attention.backends.fa_utils` 后确认
`flash_attn_varlen_func is None`；同时
`torch.ops.vllm.torch_sdpa_wrapper` 已注册。锁定版 `MMEncoderAttention`
有公开的 `TORCH_SDPA` 后端选择路径，`--mm-encoder-attn-backend`
会经 `MultiModalConfig` 传入。FlagGems 当前 checkout 有通用
`flash_attn_varlen_func` 和 SDPA 算子，FlagGems-vllm 仅有该接口的
benchmark/兼容包装，未找到独立的 H100 视觉编码器算子。这里复用 vLLM
已有后端而不新增 Plugin 算子或修改锁定版源码。缺少原 FlashAttention callable 是已验证事实；
它是否为整模唯一阻塞点尚待复试。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 结果 |
|---|---|---|---|---|
| 十一 | 视觉编码器注意力后端 | 自动选择 FlashAttention | `--mm-encoder-attn-backend TORCH_SDPA` | 首次图像 profile 越过原故障点，继续执行至 Engram 前向；随后遇到独立问题 017 |

在目标容器用 `[1,64,8,64]` BF16 Q/K/V 调用锁定版
`vit_torch_sdpa_wrapper`，与直接 PyTorch SDPA 的最大绝对误差为 `0.0`。
诊断脚本为
`/public/flagos/jinghao/deepseekV4.1/01-environment/h100149-plugin-20260923/start-diagnostic-eager.sh`；
仅增加上述参数，Ansible `--check --diff` 核对过单行变化，服务于 2026-09-23
22:45 左右重启，容器保持运行。启动前检查了容器内没有原服务且端口 8012 空闲。

## 验证、限制与下一步

- 最小回归：替代后端小张量调用与数值通过；整模待验证。
- eager：第十一轮已越过 ViT 故障，但尚无完整 profile 或 API 响应。
- graph capture/replay：未测；本次诊断为 eager。
- 此配置是缺少 FlashAttention 库时的启动层 workaround；若后续安装并
  验证兼容的 FlashAttention，可移除此显式后端选择。
- vLLM、FlagGems-vllm 与 FlagGems 源码均未修改；Plugin 本次没有新增算子。
- 与已有问题 014、015 的症状顺序不同，首先失败于图像 profile，
  非多模态处理器构造，也非 W8A8 输出投影。
- 知识库处理状态：`needs-validation`。
