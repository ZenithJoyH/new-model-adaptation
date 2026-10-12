# 适配问题索引

- [001：目标 vLLM 缺少 DeepSeek V4.1 基础模型与 tokenizer](001-v41-engine-baseline.md)：
  已在 Plugin 验证配置与 tokenizer；模型导入继续受锁定版 SWA
  层类型与调度接口阻塞，尚未完成推理适配。
- [002：V4.1 算子复用与接口缺口](002-v41-operator-contracts.md)：
  核对 FlagGems/FlagGems-vllm，复用已有 Sinkhorn、Q/KV RMSNorm、全局 top-k 映射及 H100 OCP 缓存解量化；
  对两库缺失的 delayed 残差折叠和索引扩展保留 Plugin Triton 实现。
- [003：锁定版 vLLM 缺少 V4.1 压缩器环形 KV 缓存契约](003-v41-circular-cache-contract.md)：
  Plugin 自有每请求环形缓存和映射核已通过局部数值与 Graph 检查，
  整模生命周期仍待验证。
- [004：锁定版 SWA 只支持 V4 层类型](004-v41-swa-layer-types.md)：
  Plugin 补齐 `c1a/c2a` 元数据；H100 局部 scheduler/prefill 检查已通过。
- [005：锁定版 FlashMLA 扩展不可用](005-v41-flashmla-extension.md)：
  优先复用 FlagGems-vllm 的 Triton prefill/decode 算子，整模结果待验证。
- [006：Parastor 上 Triton 多进程编译缓存清理失败](006-v41-triton-cache-filesystem.md)：
  H100-145 的同参数对照确认容器本地缓存越过此错误；H100-149 获独立路径授权。
- [007：V4.1 视觉塔调用锁定版 ViT 并行接口失败](007-v41-vit-dp-signature.md)：
  H100-145 TP8 模型构造首错；Plugin 已在迁移后的 H100-149 容器对齐四处接口，
  第二轮成功越过视觉塔。
- [008：锁定版 V4 SWA 缓存缺少 V4.1 页大小与 backend 参数](008-v41-swa-cache-constructor.md)：
  Plugin 内新增 V4.1 缓存适配层，第三轮 TP8 已越过此构造阶段。
- [009：锁定版 KernelConfig 没有可选 JIT 预热开关](009-v41-optional-jit-warmup.md)：
  Plugin 内对缺失开关跳过可选预热，第四轮 TP8 已越过此阻塞。
- [010：FP8 O 投影 recipe 函数在锁定版不接受参数](010-v41-fp8-recipe-signature.md)：
  H100 recipe 语义已核对；Plugin 三处调用对齐锁定版，第五轮 TP8 已越过此阻塞。
- [011：锁定版 V4 MoE 构造接口与 V4.1 路由参数不一致](011-v41-moe-constructor.md)：
  Plugin 复用旧 MoE 的当前文本路径，显式限定未适配模式，第六轮 TP8 已越过构造。
- [012：锁定版稀疏索引器缺少 V4.1 压缩比与候选块协议](012-v41-candidate-indexer.md)：
  Plugin 候选块 Triton 实现与 3 个定向 CUDA 测试已通过；18K 整模 eager 请求待验证。
- [013：H100 索引器依赖镜像缺少的 DeepGEMM](013-v41-indexer-deepgemm-dependency.md)：
  Plugin 接入 FlagGems-vllm 的 H100 稀疏索引实现；整模生成待验证。
- [014：多模态 dummy batch 的 input_ids 接口](014-v41-mm-processor-input-ids.md)：
  Plugin 处理器已补齐；后续真实 profile 越过该接口。
- [015：W8A8 O 投影逆 RoPE 接口](015-v41-w8a8-o-projection.md)：
  Plugin 接入 FlagGems-vllm 算子，局部数值回归通过。
- [016：视觉编码器 FlashAttention callable 缺失](016-v41-vit-flash-attn-unavailable.md)：
  诊断服务使用锁定版支持的 Torch SDPA，并已越过视觉 profile。
- [017：Engram 前向读取临时 DP 配置上下文](017-v41-engram-dp-context.md)：
  Plugin 对齐调用上下文，真实 profile 已越过该点。
- [018：V4.1 MoE 路由缺少 topk_softplus_sqrt 扩展](018-v41-moe-topk-softplus-sqrt.md)：
  Plugin 复用 FlagGems-vllm 同契约实现，局部数值和图重放通过。
- [019：索引 Q 量化缺少锁定版 CuTe 包](019-v41-indexer-q-cute-missing.md)：
  H100 Plugin 分支复用 FlagGems-vllm FP8 算子，真实 profile 已越过调用。
- [020：V4.1 索引器和 SWA 缓存块能力声明不匹配](020-v41-indexer-kv-block-size.md)：
  64-token 索引器和 32-token SWA 组均在第十六轮真实初始化中通过；后续失败见问题 021。
- [021：V4.1 稀疏 MLA backend 缺少 KV 缓存形状](021-v41-sparse-mla-kv-shape.md)：
  Plugin 已补齐接口并通过压缩比 1、2 的真实页 reshape 测试；第十七轮整模已越过 KV 分配。
- [022：稀疏 MLA 元数据调用锁定版缺失的请求索引方法](022-v41-sparse-mla-request-ids.md)：
  Plugin 对齐锁定版 SWA builder 算法，GPU 地址稳定性定向测试通过；第十八轮真实预热已越过原故障点。
- [023：SWA 融合 QNorm/RoPE/KV 缓存写入与锁定版扩展不兼容](023-v41-qnorm-rope-kv-insert.md)：
  H100 Plugin 分支接入 FlagGems-vllm 现有算子；PyTorch 参考对比和 CUDA Graph 局部测试通过，第十九轮真实预热越过原调用。
- [024：稀疏 SWA metadata 缺少预填充可见区间字段](024-v41-prefill-visibility-metadata.md)：
  Plugin 自有 metadata 补齐文本路径的空区间默认值，局部构造检查通过；第二十轮真实预热已越过原读取。
- [025：V1 runner 不传递稳定请求槽](025-v41-request-slots-v2-runner.md)：
  V2 开关不能替换 Plugin 自有 runner；Plugin legacy 状态扩展已通过第二十二轮真实权重 eager 最小文本推理。
- [026：FlagGems-vllm 分页索引打分无法 full graph 捕获](026-v41-paged-indexer-full-graph-capture.md)：
  GPU `context_lens.max().item()` 是第二十三轮图捕获首错；Plugin 包装已通过数值及图重放，第三轮整模先被问题 027 阻断。
- [027：索引器预热与 CUDA Graph 捕获走不同分支](027-v41-indexer-graph-warmup-divergence.md)：
  第三轮首错为 FlagGems `linear` 在捕获内首次编译；Plugin 已统一预热/捕获路径，整模复验待完成。
- [028：超过约 160 token 后整模回答失真](028-v41-short-context-semantic-regression.md)：
  18K eager 服务在约 156-token 提示正确、190-token 起失真；512-token 全覆盖索引配置得到同样四个错误输出。
- [029：V4.1 思考强度与输出解析不一致](029-v41-reasoning-frontend.md)：
  Plugin 前端映射已对齐模型资料，并补齐锁定 vLLM 的思考解析注册；定向测试通过，整模待复验。
