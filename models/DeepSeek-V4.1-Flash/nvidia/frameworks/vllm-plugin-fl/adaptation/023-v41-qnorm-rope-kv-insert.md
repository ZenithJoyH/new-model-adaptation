# 023：V4.1 SWA 融合 QNorm/RoPE/KV 缓存写入与锁定版扩展不兼容

## 元数据

- 状态：`root-cause-fix`（局部对照通过；第十九轮真实预热越过原调用）
- 首次出现及最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`
- 模式：TP8、DP1、eager、真实权重、前缀缓存启用、2048 token 上限

## 问题与原因

第十八轮于 04:28:14 进入真实模型预热，最早失败的 TP0 在 Plugin `DeepseekV4Attention` 的 SWA FP8 缓存写入调用报：`_C::fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert() expected at most 8 argument(s) but received 10 argument(s)`。锁定版注册的 `_C` schema 是八参数、原地更新 Q 与 KV cache、无返回值；Plugin V4.1 代码调用新接口，额外传入填充头数并期待返回填充后的 Q。容器内单独调用八参数 `_C` 又确认缺少 CUDA 实现。因此只调整参数仍不能执行。首个错误及栈见 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log` 约 17400—17485 行。

## 受控修复与证据

按既定算子优先级，先检查 FlagGems-vllm：其 `flaggems_vllm.ops.fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert` 提供八参数原地实现。对该库自带 PyTorch 参考测试，Q、KV、DP padding 和合并路径均通过；在 H100 上另测 V4.1 的 16 到 64 头填充、页布局和变输入 CUDA Graph 重放通过。诊断测试与补丁保存在 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-qnorm-cache-insert-20260924/`，测试不修改库源码。

仅在 Plugin `vllm_fl/models/deepseek_v4_1/attention.py` 的 H100 CUDA capability 9 分支调用 FlagGems-vllm 算子，再对 Q 显式做头维填充；其他设备路径保留原调用。应用前确认容器内无服务，源码和补丁 SHA 守卫、`git apply --check`、Ansible `--check --diff` 均通过。源码 SHA-256 从 `83b3883671b9153bb3167c5a7bac91245ae4b43c597f94110ca4d544655611ea` 变为 `9da289ab77886ad8713af403d2c15e3e79dad6a40751eac3cda4e97e832ce889`。第十九轮真实权重 TP8 eager 已进入八个 rank 的稀疏 MLA 预热，并越过原 10 参数调用；其后首错为 Plugin metadata 缺少预填充可见区间字段，见[问题 024](024-v41-prefill-visibility-metadata.md)。因此原接口阻塞在当前预热中已解除，但仍未完成最小推理。

## 限制与下一步

- 继续验证预热和最小文本推理；若失败，检查最早失败 rank。
- 2048 token 诊断不覆盖完整长上下文候选块；full graph 和正式验收仍未开始。
- 知识库处理状态：`needs-validation`。
