# 018：锁定版 vLLM 缺少 V4.1 MoE softplus-sqrt 路由算子

## 元数据

- 状态：`root-cause-fix`（整模已越过路由；最小生成仍待验证）
- 首次出现及最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`
- 模式：TP8、DP1、eager、前缀缓存启用、2048 token 上限

## 问题、根因和已有经验

第十二轮整模加载约 1627 秒，profile 越过 ViT 和 Engram 后，首次 MoE 路由在 Plugin `vllm_fl/ops/fused_moe/router.py:241` 委托锁定版 vLLM `fused_topk_bias_router.py`，报 `AttributeError: '_OpNamespace' '_moe_C' object has no attribute 'topk_softplus_sqrt'`。原始栈位于 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log` 约 10625—10669 行。锁定版 vLLM 具备 Python 参考实现和 CUDA 扩展调用点，但本容器扩展没有注册该 op。项目故障库和本模型既有问题未见完整匹配签名。

按用户指定的算子优先级，检查 FlagGems-vllm 与 FlagGems：前者已有 `flaggems_vllm.ops.topk_softplus_sqrt.topk_softplus_sqrt`，入参覆盖修正偏置、归一化、缩放、`input_ids` 和 hash 索引表；因此无需新写 Triton 算子。修改只在 Plugin `FusedTopKBiasRouterFL._compute_routing` 的 `sqrtsoftplus`、CUDA 且锁定扩展缺失分支，其他模型、已有扩展及非 CUDA 路径仍走原分发。输出张量按 vLLM 契约分配，缩放仅应用一次；FlagGems-vllm 依赖按需导入。

## 受控修复与验证

本轮唯一产品变量是 `vllm_fl/ops/fused_moe/router.py`；源码 SHA-256 从 `7d32bf00d6bcee6e453c59d9bd22ec10b0f6ee28e023853fc5c76e3d8c7a2d48` 变为 `dd5259435712f9b01bd5c79671a683c1046c8f959970f7b153aa5281c72c3461`。补丁、临时测试位于 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-topk-softplus-20260924/`。Ansible `--check --diff`、SHA 守卫、`git apply --check` 和实际应用均通过；应用前服务已退出，容器未重启。未修改锁定版 vLLM。

H100 上以 384 专家、top-k 6、偏置、renormalize 和 1.5 缩放对照锁定版 PyTorch 参考：专家 ID 完全相等，权重在 `1e-5` 容差内；含 hash 映射的路径及 CUDA Graph capture/replay 均通过。第十三轮 TP8 eager 于 00:11 启动、真实权重加载耗时 1702.13 秒，profile 已越过本 MoE 路由并进入稀疏索引器 Q 量化，随后因另一缺失 CuTe 包失败，见[问题 019](019-v41-indexer-q-cute-missing.md)。这验证了真实前向中的路由调用，但不代表整模 eager 或 full graph 已通过。

## 限制与下一步

- 继续完成稀疏索引器及后续层的整模 profile 和最小生成；不以越过 MoE 路由宣称功能完成。
- 其他平台和具备原生 `_moe_C` 扩展的 vLLM 未经实机验证；当前能力守卫应保持。
- 知识库处理状态：`needs-validation`。正式适配 diff 审查和图模式验证仍未完成。
