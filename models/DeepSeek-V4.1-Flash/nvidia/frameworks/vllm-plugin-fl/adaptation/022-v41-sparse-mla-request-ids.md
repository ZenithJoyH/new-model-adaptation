# 022：V4.1 稀疏 MLA 元数据调用锁定版缺失的请求索引方法

## 元数据

- 状态：`root-cause-fix`（局部请求索引测试及第十八轮真实预热越过原故障点）
- 首次出现及最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`
- 模式：TP8、DP1、eager、真实权重、前缀缓存启用、2048 token 上限

## 问题与原因

第十七轮于 03:44:31 完成真实 KV 缓存分配，进入锁定版 V4 sparse MLA 预热，八个 TP rank 在 Plugin `DeepseekV4SparseMLAMetadataBuilder.build()` 报 `AttributeError: 'CommonAttentionMetadata' object has no attribute 'token_to_req_indices'`。原始首个栈见 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log` 约 16410—16445 行；EngineCore 与其他 rank 的断连是后果。预热中断，API 未就绪。

锁定版 `CommonAttentionMetadata` 提供 `query_start_loc_cpu` 和 `num_reqs`，但没有此便利方法。锁定版 `DeepseekSparseSWAMetadataBuilder` 已在相同语义下通过每请求 query 长度 `repeat_interleave` 生成 token 到请求的索引，再写入稳定地址的 GPU 缓冲。Plugin V4.1 稀疏 MLA builder 原先引用了不存在的较新接口。

## 受控修复与证据

仅在 Plugin `vllm_fl/models/deepseek_v4_1/sparse_mla.py` 的该 builder 内复用锁定版 SWA 的算法：根据 `query_start_loc_cpu` 生成 pinned CPU 请求索引，以非阻塞复制写入既有 `req_id_per_token_buffer` 的切片，保留 CUDA Graph 所需的固定 GPU 地址。未修改 vLLM 的共享元数据或通用 runner。源码 SHA-256 从 `abf742efb775059b4ea3dacdfbc5d9d8e1eada3e9ad60791288afdf82df3efa5` 变为 `e1f2f56617ea76b87e014080826d9f86c32de9e5b66cec935f8a8dca72eb4576`。补丁及测试在 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-mla-req-index-20260924/`。Ansible `--check --diff`、源码/补丁哈希守卫、`git apply --check` 和源码应用通过；应用前服务已退出，容器未重启。

首次定向测试因构造的模拟 builder 漏设 `kv_cache_spec.block_size` 而失败，并非产品代码异常；补齐测试夹具后重跑通过。测试在两组不同 query 长度下分别得到 `[0,0,1,1,1]` 与 `[0,1,1,1,1]`，且目的 GPU 缓冲地址相同。第十八轮真实权重 TP8 eager 于 04:28:14 越过请求索引构建，进入 SWA 融合 QNorm/RoPE/KV 缓存写入，随即因另一接口差异失败，见[问题 023](023-v41-qnorm-rope-kv-insert.md)。这只证明当前预热阶段已越过原故障点，不代表最小推理或 CUDA Graph 通过。

## 限制与下一步

- 继续核对真实预热及最小生成；若出现新异常，按最早失败 rank 追踪。
- 长上下文候选块集成、full graph 和正式验收尚未完成。
- 知识库处理状态：`needs-validation`。
