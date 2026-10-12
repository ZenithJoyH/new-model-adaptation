# 019：锁定版 vLLM 错选缺失的 CuTe 稀疏索引 Q 量化路径

## 元数据

- 状态：`root-cause-fix`（整模已越过 Q 量化；最小生成仍待验证）
- 首次出现及最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`
- 模式：TP8、DP1、eager、前缀缓存启用、2048 token 上限

## 问题现象与根因

第十三轮真实权重加载耗时 1702.13 秒，profile 已越过问题 018 的 MoE 路由。00:44:34 首个失败 worker 为 TP0，Plugin `attention.py:1282` 调用锁定版 `fused_indexer_q_rope_quant`，其 `has_cutedsl()` 返回 true 后导入 `vllm.models.deepseek_v4.nvidia.ops.fused_indexer_q_cutedsl`，而该模块又要求不存在的 `vllm.vllm_flash_attn.cute` 包，报 `ModuleNotFoundError: No module named 'vllm.vllm_flash_attn.cute'; 'vllm.vllm_flash_attn' is not a package`。原始栈在 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log` 约 13408—13434 行。问题是锁定版的可用性判断与实际包内容不一致；未修改 vLLM 安装。

检索 FlagGems-vllm 和 FlagGems 后，前者已有同签名 `flaggems_vllm.ops.fused_indexer_q_rope_quant.fused_indexer_q_rope_quant`，支持 H100 所需 FP8 Q 和权重缩放；因此无需写新 Triton 算子。项目故障库和当前模型既有记录中未见完整匹配签名。H100 已在 Plugin `DeepseekV41FlagGemsIndexer` 下处理稀疏索引 logits/top-k，故在同一个 H100 能力选择分支绑定 FlagGems-vllm Q 量化函数；其他平台保留锁定版路径，可选依赖只在 H100 分支导入。

## 受控修复和证据

本轮唯一产品变量是 Plugin `vllm_fl/models/deepseek_v4_1/attention.py`，SHA-256 从 `6ee8f9028ff32a14ee2d11875c9be3be9456a8bc82d603e490076b930b3379ee` 变为 `a389dee519a064171b25787e454555a28aa98981c971be6f254df57263085c7e`。补丁和局部测试保存在 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-indexer-q-20260924/`，缓存使用已批准的容器本地 `/tmp/deepseek-v41-plugin-h100149`。第一次补丁预检发现补丁头行数错误，源码未改；修正后 `git apply --stat`、Ansible `--check --diff`、原源码/补丁哈希守卫、`git apply --check` 和实际应用通过，应用前确认本次服务已退出；容器保持运行。

定向 H100 测试以 BF16、4 token、8 head、128 head dim 的输入对照锁定版 vLLM 的 Triton fallback（只在测试进程内令 `has_cutedsl=False`）：FP8 字节完全相等，缩放后权重在 `1e-6` 容差内；更换输入后的两次 CUDA Graph replay 与重新计算一致。此测试验证算子契约和图重放，不代替整模 profile、生成或 full graph。

为缩短后续接口排查，用相同 TP8 命令但 `--load-format dummy` 于 00:54 启动单独诊断，日志在 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-dummy-20260924/service.log`。约 01:10 首次前向在 Plugin `nvidia/model.py:321` 断言 `hc_attn_fn_broadcast is not None` 失败。真实模型的 `load_weights` 会填入该张量，而锁定版 dummy loader 跳过模型专有装载路径，因此本次失败属于合成权重模式的限制，不能用于判定 Q 量化接入是否成功；没有为 dummy 修改产品逻辑。

真实权重第十四轮于 01:12 启动，加载耗时 1642.43 秒，profile 已越过索引 Q 量化，进入 KV 缓存分配并报告容量 484248 token；之后在块大小协商失败，见[问题 020](020-v41-indexer-kv-block-size.md)。真实前向验证了本问题的 H100 路径已命中且不再触发 CuTe 导入错误，但最小生成仍未完成。

## 限制与下一步

- 继续修复 KV 缓存块大小协议并完成最小生成，不能以 profile 通过宣称功能完成。
- 非 H100 原路径保留，但其他平台实机未验证；后续设计审查需核对共享调用方和未命中守卫。
- 知识库处理状态：`needs-validation`；正式适配 diff 审查尚未完成。
