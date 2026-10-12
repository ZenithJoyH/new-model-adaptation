# 004：锁定版 SWA 只支持 V4 层类型

## 元数据与症状

- 状态：`resolved`（Plugin 元数据子类和 H100 局部验证已通过；整模推理仍待验证）
- 首次出现及最后验证：2026-09-23
- 模型/Host/容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-145`，`xingchen4-flagos`
- Plugin / FlagGems / vLLM：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `7cd137ccaf09f25ce3012ba86438682072a69bc9` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式：模块导入；未构造模型、加载权重或运行 eager/graph

Plugin 环形状态实现使导入越过 `CircularBufferSpec`。随后旧版 indexer 缺
`dsa_indexer_uses_fp4`：H100 所需的是 132-byte FP8 行，Plugin 已加入
显式 FP8 选择，并拒绝请求 FP4 的配置。再次导入后首个失败为：
`ImportError: cannot import name '_LAYER_TYPE_C1A' from
'vllm.v1.attention.backends.mla.sparse_swa'`。

锁定版 `sparse_swa.py` 只声明 `swaonly/c4a/c128a`，其 `_layer_type_for`
对 V4.1 的压缩比 2 抛 `ValueError`，tile scheduler 和 metadata 固定使用
`c4a/c128a` 字段；参考 V4.1 原生版增加 `c1a/c2a` 及对应 scheduler 字段。
因此只在 Plugin 定义两个同名常量可消除导入错误，却不能保证元数据构造
和解码调度正确。

## 诊断、责任边界与下一步

只读比对了锁定版与 H100-149 原生版的层类型、builder 初始化和
`build_tile_scheduler`。已验证的根因是锁定版 SWA 的 V4 专用层分类与
V4.1 `0/1/2` 压缩比不兼容。Plugin 的 `DeepseekV41SparseSWAMetadataBuilder`
现在按配置建立 `swaonly/c1a/c2a`，并在构造旧版基类 metadata 后增加
V4.1 专属的 tile scheduler 字段。压缩比 1 的 prefill 会保留全长压缩区域；
压缩比 0 不分配该区域。H100 局部测试确认三种层类型的 scheduler 均非空，
两请求 prefill 规划宽度分别为 `0/300/150`；原始回执在
`H100-145:/public/flagos/jinghao/deepseekV4.1/04-runs/h100145-swa-20260923/adapter-test.json`，
SHA-256 `ffa7d030b2054e7770de892973370720fc29b09e2309f812b9532519a93751be`。
此测试未覆盖完整调度生命周期或 TP8 数值。

本问题无权重修改或 FlagGems 缺陷。Plugin `git diff --check`
通过；vLLM 既有 diff 哈希未变。原始导入报错来自目标容器的受控
`python3 -c 'from vllm_fl.models.deepseek_v4_1.nvidia.model import DeepseekV41LLMForCausalLM'`
检查，缓存定向到批准工作根的 `06-cache/h100145-ring-20260923`。
知识库处理状态：`local-only`。
