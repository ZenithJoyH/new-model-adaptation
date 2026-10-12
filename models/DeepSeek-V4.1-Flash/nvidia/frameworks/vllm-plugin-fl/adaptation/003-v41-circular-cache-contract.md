# 003：锁定版 vLLM 缺少 V4.1 压缩器环形 KV 缓存契约

## 元数据与症状

- 状态：`open`（Plugin 环形状态已实现并通过局部测试；整模生命周期尚未验证）
- 首次出现及最后验证：2026-09-23
- 模型/Host/容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-145`，`xingchen4-flagos`
- Plugin / FlagGems / vLLM：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `7cd137ccaf09f25ce3012ba86438682072a69bc9` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式：模型仅到导入阶段；eager/graph 整模均未运行

前面几个导入缺口在 Plugin 内隔离处理后，真实目标容器的下一次导入报：
`ImportError: cannot import name 'CircularBufferSpec' from 'vllm.v1.kv_cache_interface'`。
报错源于 Plugin V4.1 `compressor.py`。该规格不是名称占位符：压缩比 2
的开放 token 组需要每请求一个可循环复用的状态块，元数据 builder 再把
token 位置映射到这一块；错误的分配或复用会污染后续 token 的 KV/score。

## 已验证接口和未验证假设

锁定 vLLM 有 `KVCacheSpecRegistry`，可注册自定义规格及 manager；但
`v1/core/kv_cache_utils.py` 的 DeepSeek V4 混合分组路径
`group_and_unify_kv_cache_specs` 只收集 `MLAAttentionSpec` 和
`SlidingWindowMLASpec`，忽略其他规格。目标 V4.1 attention 包含现成的
DeepSeek V4 SWA cache，返回 `SlidingWindowMLASpec`，因此该分组路径会触发；
仅添加 `CircularBufferSpec` 并向 registry 注册，不能证明环形缓存会进入
KV cache groups。锁定 GPU runner 还按 `max_model_len / block_size` 为每组
计算 block-table 宽度，没有新版对环形规格的专门分支。

参考 H100-149 NV-native V4.1 源码明确新增 `CircularBufferManager`，
覆写“只申请一个块、无前缀缓存命中、请求结束回收”等行为；其
`model_runner.py` 对环形规格关闭通用 slot mapping、调整 block-table
宽度。锁定版缺这些分支。以上是源码级的确定差异；尚未证明当前 Plugin
拥有覆盖完整分组和 runner 语义的现成可维护扩展点。用旧 V4 缓存或
注册同名空类只能推迟报错，不能视为推理适配。

## 受控尝试和边界

1. 原目标容器导入定位到 `CircularBufferSpec`；未加载权重、未占用模型显存。
2. 只读比较锁定版与 H100-149 参考版的 cache spec、manager、grouping
   和 GPU runner；没有改动任一 vLLM 源码或安装。
3. 独立算子已按 [002 号问题](002-v41-operator-contracts.md) 做 FlagGems
   复用与图测试；它们不替代 KV 生命周期验证。

以上是实现前的边界分析。当前用户锁定 vLLM，只允许 Plugin 产品源码修改，
因此不照搬参考版 vLLM 核心改动，也不以临时 monkeypatch 共享热路径
掩盖设计缺口。正式 PR base、整模数值、eager/full graph、精度和性能
均未确认。知识库处理状态：`local-only`。

## 2026-09-23 Plugin 实现与验证进展

已确认锁定版 `RequestState` 的索引在请求运行期间稳定，`InputBatch.idx_mapping`
把当前批次请求映射到这些索引。Plugin 的 `DeepseekV41ModelState` 现将映射复制到
固定地址 GPU 张量，沿模型、层、注意力链路传给压缩器。压缩器自行分配每层
`[max_num_reqs, capacity, 1024]` FP32 环，容量沿用原版的 speculative-token
公式；Plugin Triton 核利用 SWA 元数据的 token→请求映射和位置计算环槽。
因此不需要向锁定 vLLM 注入虚假的 `CircularBufferSpec`、cache manager 或
runner 分支。轮换请求索引后，位置零覆盖旧开放状态。

先检索 FlagGems `7cd137c` 和 FlagGems-vllm `3d73c8a`，未找到对应的
每请求环槽映射算子；压缩/归一化仍使用已有 Plugin fused Triton 实现。
目标 H100 上的独立数值复现覆盖跨 chunk、chunk 内配对、批次重排、索引复用、
17-token 长 chunk 和两次 CUDA Graph 重放，全部最大误差为 0；新增映射核
对 padding、无效 SWA 槽位、请求槽位变化及 Graph 重放也通过。
原始回执位于 `H100-145:/public/flagos/jinghao/deepseekV4.1/04-runs/h100145-ring-20260923/`
的 `prototype.json`、`mapping-test.json`；一次性过程脚本在同一根的
`02-issues/h100145-ring-20260923/`。Plugin 产品路径为
`/vllm-workspace/vllm-plugin-FL/vllm_fl/models/deepseek_v4_1/` 下的
`compressor.py`、`nvidia/model_state.py`、`nvidia/model.py`、`nvidia/vl_model.py`
和 `attention.py`。vLLM 原有 diff 哈希仍为
`2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`，
容器未停启。

这验证了环算法和稳定槽位映射，**尚未验证完整服务生命周期**。模型导入已越过
`CircularBufferSpec`，但随后缺少旧版 indexer 的 FP4 选择函数；Plugin 已增加
仅允许当前 H100 FP8 布局的显式选择。下一导入缺口是旧版 SWA 缺
`_LAYER_TYPE_C1A`/`_LAYER_TYPE_C2A`，见 [004 号问题](004-v41-swa-layer-types.md)。
需要在解决该独立问题后，测试真实调度下的前缀缓存命中、preemption、
spec decode、TP8 和 full graph，再把本问题标为 resolved。
