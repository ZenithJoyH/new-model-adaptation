# 002：V4.1 算子复用与接口缺口

## 元数据

- 状态：`open`（局部算子已验证，整模未验证）
- 首次出现及最后验证：2026-09-23
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- 平台与 Host：NVIDIA H100 × 8，`H100-145`
- 容器与镜像：`xingchen4-flagos`，`sha256:d0af16489bc171d5434fc225c7afd89d32da7946af53655b9ad6dc7b50c745ca`
- Plugin / FlagGems / FlagGems-vllm / vLLM：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `7cd137ccaf09f25ce3012ba86438682072a69bc9` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式：单算子 eager 与 CUDA graph；整模尚未加载

## 库检索和根因

先检查已经同步的 FlagGems 和现有 FlagGems-vllm checkout，而后才决定
Plugin 中是否需要 Triton。两个库均有 `hc_split_sinkhorn`、
`fused_q_kv_rmsnorm`、`combine_topk_swa_indices`；但其 `mhc_pre`
是即时 pre-mix，没有 V4.1 delayed-pre 所需的 `pre_mix`、`x` 和
`norm_weight`。两库的 V4 索引合并均无 `out=`、`left_visible`、
`right_visible`、`max_image_tokens`，而 V4.1 FlashMLA 调用实际传
`out=`，图像还需要双向可见。签名相似不能当作兼容证据。

| 能力 | 处理和 Plugin 位置 | 已核实的结果 |
|---|---|---|
| mHC 系数 Sinkhorn | 复用 FlagGems `flag_gems.fused.mhc.hc_split_sinkhorn`，由 `vllm_fl/models/deepseek_v4_1/ops/mhc.py` 接入 | 1/8/257 token 对 Torch 参考最大绝对误差 ≤ `2.384e-7` |
| V4.1 delayed 残差折叠 | 两库无对应语义，仅在上述 Plugin 模块增加 `_collapse_residual` Triton kernel；HC4、BF16、eps `1e-6`、post multiplier 2，不符时显式拒绝 | 4 组 64/5120 hidden 数值通过；8×4×5120 两次不同输入的 CUDA graph 重放四个输出误差均为 0 |
| Q/KV RMSNorm | 复用 FlagGems `flag_gems.fused.deepseek_v4_attention_fused_q_kv_rmsnorm`，由模型专属 Plugin `common/ops/qkv_norm.py` 惰性选择；V4.1 attention 只调用该桥接点 | BF16 1/8/33 token；最大绝对误差 `0.00390625`；两次 graph 重放误差均为 0 |
| 压缩 top-k → 全局 KV slot | FlagGems `compute_global_topk_indices_and_lens` 的五参数接口与当前目标一致；删除 Plugin 复制的 kernel，由 `common/ops/cache_utils.py` 桥接 | 含无效 token、`-1` 哨兵和两个请求的 INT32 输出逐元素一致；FlagGems 本体及 Plugin 桥接各通过两次 graph 重放 |
| FP8 K-cache 解量化与收集 | H100 的 OCP E4M3 路径复用 FlagGems `dequantize_and_gather_k_cache`，由 Plugin `cache_utils.py` 分派；FNUZ 仍走模型局部 Triton | 576B/token、37440B/block 的两块布局；19/70 token、`gather_lens=None`、非零输出偏移均与原 Triton 实现逐元素一致；FlagGems 本体和 Plugin 路径分别两次 graph 重放误差为 0 |
| top-k/SWA 合并 | FlagGems 只满足无 `out`、无图像的 V4 子集；保留 `vllm_fl/models/deepseek_v4_1/common/ops/cache_utils.py` 中 V4.1 Triton kernel，去掉锁定版 vLLM 不存在的 JIT 预热包装 | 普通输出逐元素等于 FlagGems；预分配输出的两次 graph 重放使用新索引；图像有效长度 `[7,11,8]` |

以上 FP8 布局核对只覆盖 H100/OCP 编码；FNUZ 路径和多卡缓存更新
仍待专门验证，不把单算子结果外推为整模支持。

## 可追溯证据与界限

所有原始结果在 `H100-145:/public/flagos/jinghao/deepseekV4.1/04-runs/`：
`h100145-mhc-20260923/{flaggems-sinkhorn,delayed-mhc,delayed-mhc-graph}.json`，
`h100145-v4ops-20260923/{qkv-rmsnorm,qkv-rmsnorm-plugin-adapter,global-topk,global-topk-plugin-adapter,combine-topk,dequant-k-cache,dequant-k-contract,dequant-k-plugin-adapter}.json`。
一次性脚本在同根 `02-issues/` 对应子目录，缓存和临时文件分别在
`06-cache/`、`05-tmp/`。索引合并只覆盖单请求小张量；单算子 graph
不证明整模 full graph、TP8 或精度。

当前 Plugin HEAD 未提交，初始工作树干净；vLLM HEAD 及其 87 条
既存修改仍与环境基线相同，`git diff --binary` SHA-256 为
`2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`。
Plugin `git diff --check` 通过；PR base 和最终影响矩阵未确认。
未停启模型服务或容器。现有 Plugin 模型导入仍受锁定 vLLM 的
`CircularBufferSpec` 及后续调度接口阻塞，不能标为 functional。
知识库处理状态：`local-only`；完整跨模型/平台适用性未验证。
