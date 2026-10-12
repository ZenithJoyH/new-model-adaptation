# 020：H100 V4.1 索引器和 SWA 的 KV 块能力声明不匹配

## 元数据

- 状态：`root-cause-fix`（第十六轮真实 KV 初始化已越过两组块协商；最小生成仍待验证）
- 首次出现及最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`
- 模式：TP8、DP1、eager、真实权重、前缀缓存启用、2048 token 上限

## 问题与根因

第十四轮真实权重 profile 已越过此前的 MoE 和索引 Q 量化，KV 缓存容量核算为 484248 token；随后全部 TP rank 在 `prepare_kernel_block_sizes` 报 `ValueError: No common block size for 64.`。原始首个栈在 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log` 约 13927—13944 行，发生于 KV 缓存初始化，尚未启动 API 服务。

锁定版 `DeepseekV4IndexerBackend.get_supported_kernel_block_sizes()` 返回 `[256]`，供其 DeepGEMM 路径使用；本次 H100 Plugin 实际选择 FlagGems-vllm FP8 索引器，`cache_config.block_size=64`，gather/logits 的缓存物理页也是 64。V4.1 其余 H100 稀疏 MLA backend 支持 64，因此旧索引 backend 的能力声明与真实实现及同组 backend 不匹配。第十五轮已越过这一 64-token 组，随后在 32-token SWA 组报 `ValueError: No common block size for 32.`。该组使用 Plugin `DeepseekV41SWACache` 的 32-token 物理页，但其 `DeepseekSparseSWAFlashMLABackend` 继承锁定版 V4 backend 的“64 的倍数”声明，同样与实际物理页不匹配。两次故障均发生在 KV 缓存初始化，服务尚未启动。项目故障库和既有适配问题未见完整匹配签名。

## 受控修复与证据

本轮仅修正 H100 Plugin 索引器 backend 的能力声明。`vllm_fl/models/deepseek_v4_1/nvidia/indexer.py` 增加 `DeepseekV41FlagGemsIndexerBackend`，继承锁定版的 metadata builder 与缓存形状，但声明独立名称和 `[64]` 支持；`attention.py` 的 `DeepseekV4IndexerCache.get_attn_backend` 只在 Hopper CUDA 返回该类，其他平台仍返回原 `DeepseekV4IndexerBackend`。不修改锁定版 vLLM 的公共块协商函数，也不改变 SWA 的 32-token 模型页或全局缓存参数。

`attention.py` SHA-256 从 `a389dee519a064171b25787e454555a28aa98981c971be6f254df57263085c7e` 变为 `83b3883671b9153bb3167c5a7bac91245ae4b43c597f94110ca4d544655611ea`；`nvidia/indexer.py` 从 `4a6affc961fac0fa6b7dee619356786eab35641ccfd46a85a0417b5d8895b11a` 变为 `5f9a6317b36626fb15f4f8f44ad78eff8002d517ba7504719953502dd82d3370`。补丁和最小协议测试在 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-indexer-blocksize-20260924/`。Ansible `--check --diff`、原文件/补丁哈希守卫、`git apply --check` 和实际应用均通过；应用前确认推理服务已退出，容器未重启。

定向测试调用锁定版 `select_common_block_size`：以旧 V4 indexer 和 H100 稀疏 MLA backend 输入 64 时复现 `No common block size`；换为 Plugin H100 indexer 后返回 64，且原 V4 backend 仍声明 256。第十五轮真实权重 TP8 eager 于 01:53 启动，约 02:28 越过 64-token 组，随后在 32-token SWA 组失败，详见同一服务日志的末尾异常。

第二次受控修复仅在 Plugin 的 `vllm_fl/models/deepseek_v4_1/nvidia/flashmla.py` 为 V4.1 FlashMLA SWA backend 声明 `[32]`，锁定版 V4 后端保持不变。源码 SHA-256 从 `18e934f6097827c181d10346bd179f2d4c2460d1c554d7123c25bac5f9620f11` 变为 `32bf58fb732451374724cb5fc3ea24270fbc9c346cc18c02012ea49aebaa6bea`。补丁及旧失败/新成功的定向测试位于 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-swa-blocksize-20260924/`；Ansible `--check --diff`、原源码/补丁哈希守卫、`git apply --check`、实际应用及定向测试均通过。第十六轮真实权重 TP8 eager 于 02:34 启动，并在约 03:05 越过 64、32 两组协商，后续在 Plugin 稀疏 MLA backend 缺少 KV 形状接口时失败，见问题 021。因此该缓存能力声明修正已通过真实初始化阶段对照，但实际 KV 分配和最小生成仍未验证。

## 限制与下一步

- 第十七轮继续核对实际 KV 缓存分配和最小生成；若后续 kernel 假定旧块尺寸，需按首个失败 rank 继续诊断，不能用能力声明掩盖真实不兼容。
- 非 H100 和原生 V4 路径保持原行为，但其他平台未经过硬件回归。
- 知识库处理状态：`needs-validation`；正式适配 diff 审查及 full graph 未完成。
