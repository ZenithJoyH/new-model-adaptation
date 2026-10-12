# 021：V4.1 稀疏 MLA backend 未声明 KV 缓存张量形状

## 元数据

- 状态：`root-cause-fix`（第十七轮真实 KV 张量分配已越过此接口；最小生成仍待验证）
- 首次出现及最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`
- 模式：TP8、DP1、eager、真实权重、前缀缓存启用、2048 token 上限

## 问题与原因

第十六轮真实权重启动约 03:05 越过上一轮的 64-token 索引器和 32-token SWA 块协商，随后全部 TP rank 在 Plugin `model_runner.py:_reshape_kv_cache_tensors` 调用 `attn_backend.get_kv_cache_shape()` 时触发锁定版 vLLM `AttentionBackend` 基类的 `NotImplementedError`。原始栈在 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log` 的 03:05:01 段；之后的 NCCL/TCPStore 断连是 EngineCore 退出的次生现象。服务尚未进入 API 就绪状态。

Plugin 自有的 `DeepseekV4SparseMLABackend` 直接继承 `AttentionBackend`，已有 64-token 能力和 metadata builder，却漏掉 KV 形状接口；同组的锁定版 SWA 与 indexer backend 均已实现该接口。V4.1 `MLAAttentionSpec` 为 `fp8_ds_mla` 计算每个压缩位置 584 字节，压缩比 1、2 分别采用 64、32 个压缩位置的物理页，页间 padding 由 spec 单独处理。需要 backend 返回未填充的页形状，不应把 alignment padding 算进每行。

## 受控修复与证据

仅在 Plugin `vllm_fl/models/deepseek_v4_1/sparse_mla.py` 补 `get_kv_cache_shape()`：对单 KV 头的 `fp8_ds_mla` 返回 `(num_blocks, storage_block_size, 584)`，普通行布局按传入 `head_size` 返回；没有改锁定版 vLLM 或公共 runner。源码 SHA-256 从 `1583facfafa7589b3dbe5898d514403845548a17231f361f4fc88e28d1a989a1` 变为 `abf742efb775059b4ea3dacdfbc5d9d8e1eada3e9ad60791288afdf82df3efa5`。补丁和测试保存在 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-mla-cache-shape-20260924/`；Ansible `--check --diff`、源码/补丁哈希守卫、`git apply --check` 和应用均通过，应用前确认本次推理服务已退出，容器未重启。

测试构造锁定版 `MLAAttentionSpec` 并调用其真实 `_reshape_attention_kv_cache`，在压缩比 1、2 下验证输出形状、584 字节行步长、带对齐 padding 的页步长和 dtype；普通行布局形状也通过。第十七轮真实权重 TP8 eager 于 03:14 左右重新启动，约 03:44 越过实际 KV 张量分配并进入稀疏 MLA 预热，后续失败见问题 022。这验证了形状修复在本次整模初始化的目标调用点生效，尚不代表生成成功。

## 限制与下一步

- 第十八轮继续验证稀疏 MLA 预热和最小生成；按最早失败 rank 定位后续问题，不把形状修复当作推理成功。
- `fp8_ds_mla` 的实际 FlashMLA 插入/读取及 Graph 尚未通过整模验证。
- 知识库处理状态：`needs-validation`；正式适配 diff 审查及 full graph 未完成。
