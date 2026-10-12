# 017：Engram 前向错误读取临时 vLLM 配置上下文

## 元数据

- 状态：`root-cause-fix`（整模已越过此处；最小生成仍待验证）
- 首次出现：2026-09-23；最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，
  `H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、DP1、eager、前缀缓存启用、2048 token 上限

## 问题现象和根因

第十一轮在 `--mm-encoder-attn-backend TORCH_SDPA` 下越过问题 016 的
视觉编码器报错，23:18:36 首次 profile 模型前向时，Plugin
`nvidia/model.py:615` 调用 `get_engram_dp_size()`。兼容函数当时执行
`get_current_vllm_config()`，而锁定版的当前配置仅在模型构造阶段设置，
forward 阶段已清除，因此 8 个 worker 报
`AssertionError: Current vLLM config is not set`。原始栈见
`H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`
约 9250—9299 行。已检索项目故障库与 V4/V4.1 相邻问题，没有完整匹配签名。

## 受控修复与证据

这轮只改变 Plugin `vllm_fl/models/deepseek_v4_1/compat.py`：
`get_engram_dp_size()` 从已初始化的 `get_dp_group().world_size` 读取
进程组大小，保留锁定版只支持 DP1 的显式 `NotImplementedError`。
`common/engram.py` 的构造和前向调用者继续复用同一兼容函数；不修改
vLLM 或分布式执行共享代码。源文件修复前 SHA-256 为
`7691351106a11b6d27c617e6a9050cd71b5d44ed0ad9f1c20ab9531745878bcb`，
修复后为 `a77893f07d8fc73635a7fcd2c0a47f63a54f1a952db3754481dde1d999485565`。
补丁和局部测试在远端
`/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-engram-dp-20260923/`。
Ansible `--check --diff`、原文件/补丁哈希守卫、`git apply --check`
及实际补丁应用均通过。应用前确认本次推理进程已退出；容器保持运行。

局部回归在没有 vLLM 配置上下文的进程中模拟已初始化 DP1/DP2 进程组：
DP1 返回 1 且无共享进程组，DP2 按预期明确拒绝。这个测试只覆盖接口契约；
第十二轮 TP8 eager 整模 profile 已越过 Engram 前向并到达 MoE 路由；
随后因另一缺失算子失败，见[问题 018](018-v41-moe-topk-softplus-sqrt.md)。
图和最小生成仍未通过，不把它记为功能完成。

## 限制与下一步

- 继续执行 TP8 整模 profile 与最小生成，确认后续层及请求路径。
- 当前适配只支持 DP1；若未来锁定版需要 DP>1，必须同时适配 Engram
  表分片、调度元数据与集合通信，不能仅移除拒绝检查。
- 知识库处理状态：`needs-validation`。
