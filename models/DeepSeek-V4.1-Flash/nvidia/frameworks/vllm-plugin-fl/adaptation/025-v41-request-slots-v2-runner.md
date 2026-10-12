# 025：锁定版 V1 runner 不传递压缩器所需的稳定请求槽

## 元数据

- 状态：`resolved`（Plugin legacy runner 扩展通过真实权重 TP8 eager 最小文本推理；跨请求及 graph 仍待验证）
- 首次出现及最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 原模式：TP8、DP1、V1 runner、eager、真实权重、前缀缓存启用、2048 token 上限

## 问题与原因

第二十轮在 05:58:46 的真实稀疏 MLA 预热中越过此前的可见区间字段，随后 ratio-2 `DeepseekCompressor.forward` 报 `V4.1 compressor requires stable request slots`。日志见 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log` 约 19855—19873 行。压缩器的跨步环形状态不能安全地按临时批次序号复用，故此守卫是正确性要求，不宜删除。

锁定版旧 `v1/worker/gpu_model_runner.py` 的 V1 runner 仅通过 `_init_model_kwargs()` 构造模型参数，不使用模型的 `get_model_state_cls()`；其 DeepSeek V4 sparse MLA warmup 又直接走 V1 `_dummy_run`。Plugin 已实现的 `DeepseekV41ModelState` 会从 `RequestState.idx_mapping` 提供稳定槽，但只有锁定版 `v1/worker/gpu/model_runner.py` 的 V2 runner 调用 `init_model_state()` 和 `prepare_inputs()`。更关键的是当前 Plugin `WorkerFL` 无条件创建自有 V1 风格的 `ModelRunnerFL`，所以 vLLM 的 V2 开关不会替换实际 runner。

## 受控诊断与证据

保留原 V1 eager 启动脚本及日志，以独立的 `H100-149:/public/flagos/jinghao/deepseekV4.1/01-environment/h100149-plugin-20260923/start-diagnostic-v2-eager.sh` 仅增加 `VLLM_USE_V2_MODEL_RUNNER=1`，日志改用 `04-runs/h100149-v2-eager-20260924/service.log`。该开关被 vLLM 识别，但第二十一轮仍由 Plugin `WorkerFL` 创建 `ModelRunnerFL`；V2 专用预热在 06:41:01 访问其不存在的 `kv_connector` 而失败。首错见 V2 日志约 348—362 行，后续 TCPStore 断连是后果。故运行时开关不是适用修复。

在 Plugin `ModelRunnerFL._init_model_kwargs()` 增加按模型声明的 legacy state 扩展点，其他模型不声明则返回原有 kwargs。V4.1 文本和 VL model 均声明 `DeepseekV41LegacyModelState`：按请求 ID 分配稳定槽，保留被暂时移出批次但未完成的请求，只有从 runner 缓存状态中删除后才回收；固定地址 GPU buffer 支持预热与 CUDA Graph。超过声明的并发槽容量时显式报错，避免别名污染压缩器环形状态；DBO 路径显式不支持。补丁和测试保存在 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-legacy-state-20260924/`。源码/补丁 SHA 守卫、`git apply --check`、Ansible `--check --diff` 通过，应用前无服务。定向测试覆盖请求重排、完成后回收、dummy 与真实输入固定 GPU 地址、容量拒绝及未声明扩展的共享模型默认路径。相关源码 SHA-256：`ModelRunnerFL` `2f86c2fe5c6cbe2629f831b0ec32a69c71db84614cb6d42bc90ca96e653f0c27`→`d918aceae17ff0f02be87f51e88ea1250ce733ca5fdba3533509f161c5042386`，文本模型 `f3c078d8e01e922bbecf8a14a9e4bd694dc9c88d9721a2043d42a8865ad80748`→`1318f8a10a805c9e8fb60a533642c56b99a48295a0ce49aa965a16f1b3ea0fd8`，VL 模型 `d9e3b2f14f1ee4ece0a5e719f9e39c1dcbbbb308383ed7ceb3e8319e855a1d61`→`a458598d08f0be3d39cf16572a70f225b831338110c279addcdc1bcc11535bb8`，模型状态 `6713a82ece8cb3a467756e6ebd80f33b8dca861238438a9ef2c04916bc26ec79`→`69a8c0d890a90bc45b10246e504a50b1a47ba5b82944e118d539c1310ba51fa9`。

第二十二轮原 V1 eager 服务于 2026-09-24 07:27:17 完成真实权重 TP8 预热并启动 API。`04-runs/h100149-eager-20260923/text-smoke.json` 中默认思考模式请求生成 256 token 后以 `length` 结束，文本重复且未给出答案；这不能证明回答正确。改用 V4.1 tokenizer 的 `chat_template_kwargs.reasoning_effort=none` 后，`04-runs/h100149-eager-20260923/chat-mode-smoke.json` 记录相同问题“1+1等于几？”返回 `2`、`completion_tokens=2`、`finish_reason=stop`。因此稳定槽修复已在一次真实文本请求中越过原阻塞，完成最小推理；默认思考模式的长生成质量和跨请求槽生命周期仍未验证。转换到 full graph 前仅向经 PID/命令核对的本次 eager 服务发送 SIGTERM，确认 8012 空闲；容器保持运行。

## 限制与下一步

- 已验证单请求最小生成；仍需多请求重排、抢占、前缀缓存和 full graph 重放的真实生命周期验证。
- legacy 状态目前仅传递请求槽，V1 路径的 Engram 跨 chunk lookback 仍需正确性验证；DBO 和超过槽容量的并发请求未支持。
- 成功后仍需 full graph、候选块长上下文集成、视觉路径和正式验收；知识库处理状态：`needs-validation`。
