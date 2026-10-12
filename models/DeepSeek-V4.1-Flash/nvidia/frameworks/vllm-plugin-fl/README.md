# DeepSeek-V4.1-Flash / NVIDIA H100 / FlagOS Plugin

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

当前目标是 `H100-149` 的 `deepseek-v41-plugin-adapt-20260923` 容器，使用锁定的
vLLM `0.24.1.dev0+gee0da84ab` 和 editable `vllm-plugin-FL`。按用户要求，
H100-145 原容器保持运行；其适配状态已通过镜像快照带到 H100-149，镜像身份、
8 张 H100、权重哈希、Plugin/vLLM/FlagGems 修订及 Host/容器工作根映射均已核实。
镜像转移和环境回执见[环境分析](environment/README.md)。

本轮只在 Plugin 增加 V4.1 配置、DSML tokenizer、模型实现及 NVIDIA 算子接入，
不修改锁定版 vLLM。算子优先复用 FlagGems-vllm/FlagGems：已有的 Sinkhorn、
Q/KV RMSNorm、全局 top-k 映射、H100 OCP 解量化及 FlashMLA 调用均在其现有库
中核对过；两库缺少的 delayed mHC 残差折叠与索引合并在 Plugin 保留针对性
Triton 实现。局部数值、请求环形状态、SWA 层分类及图重放测试已通过，详见
[算子契约](adaptation/002-v41-operator-contracts.md)、
[环形缓存](adaptation/003-v41-circular-cache-contract.md)、
[SWA 层类型](adaptation/004-v41-swa-layer-types.md)和
[FlashMLA](adaptation/005-v41-flashmla-extension.md)。

H100-145 的 TP8 首轮受 `/public` 上 Triton 缓存清理错误阻断；H100-149 已按
用户授权把本次编译缓存及临时文件放在容器本地
`/tmp/deepseek-v41-plugin-h100149`，日志保留在共享工作根 `04-runs/`。
整模启动进一步暴露锁定版与 V4.1 在 ViT 并行、SWA 缓存构造、可选预热、
FP8 配方、MoE 构造和稀疏索引器上的接口差异。针对这些差异的改动都在
Plugin；第八轮 TP8 eager 完成权重加载后，因多模态处理器缺少
`input_ids` 于 dummy batch 失败。Plugin 已补齐该接口；第九轮整模又暴露
带 processor cache 的图片-only 分支依赖 HF 私有 `_merge_kwargs`。
Plugin 已将此分支接回自有处理流程，并用与服务相同的带缓存 registry
诊断验证通过。另在独立 H100 合成输入中确认锁定版 FP8 O 投影的逆 RoPE
接口不兼容，并在 Plugin 接入 FlagGems-vllm W8A8 算子；逆 RoPE 与最终
投影的数值比对均通过。第十轮在视觉编码器 profile 时发现所选
FlashAttention callable 缺失；锁定版支持的 Torch SDPA 后端在第十一轮
越过该点，随后暴露 Engram 在前向读取临时配置上下文的错误，已在 Plugin
修复并通过局部回归。第十二轮整模 profile 已越过 Engram，随即发现锁定版
vLLM 缺少 V4.1 MoE `topk_softplus_sqrt` 扩展；Plugin 已在能力缺失时接入
FlagGems-vllm 的同契约算子，数值、hash 路由和 CUDA Graph 局部测试通过。
第十三轮 TP8 eager 已越过 MoE 路由，随后在稀疏索引 Q 量化命中缺失的
CuTe 包。Plugin 的 H100 索引器分支已改用 FlagGems-vllm 同接口算子，
FP8 数值和变输入 CUDA Graph 局部测试通过。第十四轮真实前向已越过该调用，
在 KV 缓存初始化时发现 H100 索引器沿用了 V4 的 256-token 块能力声明，
与实际 64-token 页不匹配；Plugin 已按 H100 后端真实能力修正并通过局部协商测试。
第十五轮越过该缓存组后，又发现 V4.1 的 32-token SWA 页继承了 V4 的 64-token
倍数声明；Plugin 已在 V4.1 FlashMLA SWA backend 修正声明并通过旧失败/新成功
局部测试。第十六轮真实权重已越过两组块协商，在实际 KV 张量 reshape
时发现 Plugin 稀疏 MLA backend 缺少形状接口；现已补齐并以锁定版 reshape
函数验证压缩比 1、2 的页布局。第十七轮实际 KV 分配已越过此接口，随后在
稀疏 MLA 预热中发现 Plugin builder 调用了锁定版缺失的请求索引方法；现已按
锁定版 SWA builder 的算法生成索引，定向测试通过。第十八轮已越过该方法，
随后发现 SWA 融合 QNorm/RoPE/KV 写入沿用 10 参数新接口，而锁定版只注册
8 参数接口且缺少 CUDA 实现。H100 Plugin 分支已改用 FlagGems-vllm 现有同语义
算子并显式填充 Q 头；PyTorch 参考对比和变输入 CUDA Graph 局部测试通过。
第十九轮真实权重 TP8 eager 已越过原算子调用，在稀疏 MLA prefill
读到 Plugin metadata 缺少图像可见区间字段时失败。Plugin 自有 metadata 已给
文本路径补齐空区间默认值并通过局部构造检查。第二十轮越过该字段后在
ratio-2 压缩器发现稳定请求槽缺失：锁定版 V1 runner 不调用 Plugin 已实现的
`DeepseekV41ModelState`。独立 V2 诊断确认 Plugin `WorkerFL` 仍创建 V1 风格
`ModelRunnerFL`，导致 V2 专用预热访问缺失的 `kv_connector`。Plugin 现已在
自身 runner 增设按模型声明的状态扩展，由 V4.1 自有状态按请求 ID 提供稳定
槽；重排、回收、容量与固定 GPU 地址定向测试通过。第二十二轮原 V1 eager
服务已完成真实权重 TP8 加载和 API 启动。同一条“1+1等于几？”请求在默认思考
模式下耗尽 256 token 并重复，不能算正确回答；使用模型 tokenizer 的
`chat_template_kwargs.reasoning_effort=none` 后返回 `2`，仅用 2 个生成 token
且以 `stop` 正常结束。响应证据为
`04-runs/h100149-eager-20260923/{text-smoke,chat-mode-smoke}.json`。这证明
短上下文、非思考模式的真实权重最小文本推理已可用，不证明默认思考模式的
长生成质量、并发、视觉或精度。
诊断命令正常启用
前缀缓存，日志为
`/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`。
见[缓存问题](adaptation/006-v41-triton-cache-filesystem.md)、
[ViT 接口](adaptation/007-v41-vit-dp-signature.md)、
[SWA 构造](adaptation/008-v41-swa-cache-constructor.md)、
[MoE 构造](adaptation/011-v41-moe-constructor.md)、
[候选块限制](adaptation/012-v41-candidate-indexer.md)、
[FlagGems-vllm 稀疏索引器](adaptation/013-v41-indexer-deepgemm-dependency.md)、
[多模态处理器](adaptation/014-v41-mm-processor-input-ids.md)、
[W8A8 O 投影](adaptation/015-v41-w8a8-o-projection.md)、
[视觉编码器后端](adaptation/016-v41-vit-flash-attn-unavailable.md)和
[Engram DP 上下文](adaptation/017-v41-engram-dp-context.md)和
[MoE 路由算子](adaptation/018-v41-moe-topk-softplus-sqrt.md)和
[索引 Q 量化](adaptation/019-v41-indexer-q-cute-missing.md)和
[索引缓存块协议](adaptation/020-v41-indexer-kv-block-size.md)和
[稀疏 MLA 缓存形状](adaptation/021-v41-sparse-mla-kv-shape.md)和
[请求索引](adaptation/022-v41-sparse-mla-request-ids.md)和
[融合 QNorm/RoPE/KV 写入](adaptation/023-v41-qnorm-rope-kv-insert.md)和
[预填充可见区间字段](adaptation/024-v41-prefill-visibility-metadata.md)和
[稳定请求槽](adaptation/025-v41-request-slots-v2-runner.md)。

已完成 eager 最小文本推理。首轮整模 full graph 于 2026-09-24 的稀疏索引解码
捕获中失败，首错是 FlagGems-vllm 公开算子的 GPU 长度 `.item()`；Plugin 包装
复用其底层 Triton 内核和静态长度上界，局部数值对照和变输入图重放通过。
第二次复试因上轮残留 worker 占显存而未加载权重；清理精确进程后第三次
复试完成权重加载，却在 FlagGems `linear` 首次编译时再次触发图捕获错误。
根因是原短上下文索引捷径让非捕获预热与捕获执行不同分支；Plugin 现按
配置的模型上限选择该捷径，并使 decode 预热与捕获复用同一 FlagGems-vllm
底层内核。见[分页 MQA 图问题](adaptation/026-v41-paged-indexer-full-graph-capture.md)
和[图预热路径问题](adaptation/027-v41-indexer-graph-warmup-divergence.md)。

FlagGems-vllm 和 FlagGems 当前 checkout 无 V4.1 候选块算子，Plugin 已新增
针对性 Triton 选择与掩码，并继续复用已有 logits/top-k；候选块 3 个、分页
MQA 1 个 CUDA 定向测试通过。18K eager 整模请求在约 190-token prompt
开始出现语义失真，换用不同前缀、普通词语或数字填充仍可复现；其出现范围
远低于 16K 候选预算。孤立 FlagGems-vllm 稀疏预填充 TLE 与普通 Triton
路径的 H100 数值对照接近 PyTorch 参考。18K 与 512-token 全覆盖索引
诊断服务在同样四个 160/256-token 中性提示上返回逐字相同的错误输出；
两项诊断服务验证后均已按精确 PID 停止。同机 NV 原生 vLLM 的
2048-token 对照服务用相同模型、TP8、FP8 KV、eager、前缀缓存和输入脚本，
四个提示全部正确且输入 token 数与 Plugin 一致；原生服务验证后也已停止，
所有容器保持运行。跨页 SWA 写入／gather、真实形状稀疏预填充、mHC、
INT8 矩阵乘和 MoE top-k 的孤立数值对照均未复现整模失真。
Plugin 另以相同的 2048-token 长度及批处理预算复测，四个提示仍与其
512-token 服务逐字相同且全部错误，排除了与原生服务的长度配置差异；
该 2048-token 诊断服务验证后已按精确 PID 停止，GPU 显存已释放。
另一次仅关闭混合 KV 缓存管理的诊断，在真实权重加载后因当前
Plugin/锁定版 vLLM 找不到共同的 64-token 内核块大小而未能启动 API；
服务已自行退出、GPU 显存已释放，该尝试不构成 HMA 精度对照。
因此不能单独归因于候选筛选或上述孤立算子，见
[候选块问题](adaptation/012-v41-candidate-indexer.md)和
[语义失真问题](adaptation/028-v41-short-context-semantic-regression.md)。
同机 2048-token 的逐层对照进一步确认：相同的 186 个完整 prompt token ID
序列，Plugin 返回 `1`、原生返回 `2`；第 0 层 position 63 的隐状态余弦已降至
约 `0.87`，而 position 0 约 `0.99995`。第 0 层仍是纯 SWA，因此 ratio-2
压缩器不是最早分叉点。真实请求第 0 层的 SWA 槽和窗口索引正确；
FlagGems-vllm 默认与同库 Triton FlashMLA 路径在相同 q/kv 上几乎一致，
均接近 PyTorch 参考。首层真实权重 mHC 预混合的 BF16 输出也与原生逐元素相同。
首层真实 Q/KV 进一步证明有效索引与注意力参数一致，而 Plugin 把 Q 额外做了
RMSNorm：八个有效 head 的 RMS 都约为 1，原生为 1.37–2.62；原生 V4.1
明确关闭这个归一化。Plugin 的 H100/FP8 SWA 分支已复用 FlagGems-vllm
融合算子完成 KV 写入，并用 FlagGems 通用 RoPE 旋转真实 Q，保持 V4.1 的
skip-QNorm 语义；无需新增 Triton 算子。五种长度的独立对照与原生 Q、KV
逐元素一致，6 项包含 CUDA Graph 重放的聚焦测试通过。相同 2048-token
TP8 eager 整模服务对修补前四个错误提示及扩展到 1024/1800 用户 token
的四个提示均严格输出 `2` 并正常结束，证明本轮短上下文回归已修复；
原始响应在 `04-runs/h100149-plugin-skip-qnorm-2048-20260924/`。该诊断服务
已按 PID `92242` 停止，8 卡显存归零，容器仍在运行。修补后的 18K
eager 服务（512-token 分块预算）对相同八个提示也全部严格通过；
17,037-prompt-token 的多样记录提示输出 `2` 且正常结束，原始回执在
`04-runs/h100149-plugin-skip-qnorm-18k-20260924/`。18K 服务 PID
`96049` 已在回执核对后停止，显存归零、容器仍运行。详见
[语义失真问题](adaptation/028-v41-short-context-semantic-regression.md)。
模型资料中的思考强度映射为 `low=50/high=75/max=100`，已在 Plugin
修正原先偏低的 `low/high`，并核对文本提示与模型编码参考一致；
另已补充 V4.1 reasoning parser 的 Plugin 注册及定向测试；尚未重启整模
服务验证前端效果。先前已结束的服务使用启动时载入的旧映射，
2048-token 服务启动于源码修正之后，但尚未单独验证前端 high 思考输出。
full graph、视觉、并发、正式精度和性能尚无整模通过证据；17K
只覆盖一个多样记录请求，不能推断任意长上下文的正确性，故尚不能标记
适配完成或 `functional`。正式验收未开始；当前已启动修补后的
`FULL` graph 诊断服务，锁定版 indexer backend 将其自动降为
`FULL_AND_PIECEWISE`，实测 prefill 使用 `PIECEWISE`、decode 使用
`FULL`，四个短上下文请求均严格通过。该结果不满足 profile 的 full graph
覆盖要求；该服务 PID `98850` 已在核对结果后停止，GPU 显存归零、容器仍运行。
显式 `FULL_DECODE_ONLY` 2048-token 服务于 9 月 24 日完成 decode `FULL`
图捕获并启动 API，但没有留下推理请求回执；9 月 28 日 EngineCore 意外退出，
日志缺少更早的 worker 异常，不能据此推断模型图算子故障或图模式推理通过。
同一 Plugin 源码已于 9 月 28 日启动新的 18K `FULL_DECODE_ONLY` 服务，
加入 V4.1 reasoning parser，待验证图级别、长短上下文、并发和图像请求。
共享根级 `start-model.sh` 属于
H100-149 既有 NV-native 服务，未覆盖，不能视为本 Plugin profile 的最终
启动脚本。
