# Qwen3.8-Flash-Next 模型结构与推理路径

核实日期：2026-09-04。对象是 PPU-01 `/mnt/cpfs/models/Qwen3.8-Flash-Next` 的原始 BF16 快照。
配置 SHA256：`889658f2508e8c61d409b02e70e0d78d8d4452ec65aaafbe129805d213d2e74b`。权重索引 SHA256：`99e815241ef03325536b0aaa4441deea45174c17fae31e10f0bb456410c590de`。
131 个权重分片，1658 个索引条目，索引总字节数 359999963128；未复制权重。
模型上游提交号未随目录提供，使用配置及索引摘要标识本次快照，不臆造权重 revision。

## 证据与边界

- 配置和模型卡来自给定模型目录，采集证据在 `ppu/environment/container-baseline.json`。
- 逐项核对的推理实现为 `ZenithJoyH/vllm-plugin-FL` 的 `support-qwen3.8-flash@2b2fe95e2e4a92b9d0f94f0ed9c0104b7e591025`，尤其 `vllm_fl/models/qwen3_8_flash_next/{config.py,gpu/model.py,gpu/gdn.py,gpu/qsa.py,gpu/indexer_qsa.py,gpu/ple_layer.py,common/hyperconnection.py,common/qsa_cache.py}` 与 `patches/qwen3_8_flash_next.py`。
- 这是候选插件实现的已核实静态语义，不等于当前设备数值、整模或性能验收已通过。
- 已安装 vLLM 0.24、Transformers 5.8.1 和原 GLM 插件没有 qwen4_exp/Qwen4Exp 模型实现；需要插件注册，不能直接改模型名称冒充 Qwen3.5。
- 候选分支当前验收边界为 BF16 文本路径；视觉分支、MTP、EP、量化和 PLE CPU offload 尚未验证。视觉不能依据文本验收宣称通过。

## 完整结构

配置外层 `Qwen4ExpForConditionalGeneration` / `qwen4_exp` 包含 text_config 与 vision_config。
文本隐藏维度 2560，词表 248320，输入 embedding 与 LM head 不共享权重。模型卡为主干 125B、每 token 激活约 6B，额外约 51B N-gram 表及 4B MTP；这些参数量是模型卡描述。

48 层依次组成 12 组 `[GDN, GDN, GDN, QSA]`，每层都有 MoE 与两次 Gated Residual。
因此线性注意力 36 层、稀疏全注意力 12 层；不能将 `full_attention` 字符串解释成普通 dense attention。
MoE 每层 512 routed experts，top-10 路由，另有一个 gated shared expert；expert 中间维度 640，激活 SiLU。

残差有 4 分支，低秩门控维度 320。层间张量为 `[tokens,4*2560]`，分支视图 `[tokens,4,2560]`。
`GatedResidualSimple.mix` 对各分支执行 Gemma RMSNorm（权重为 1+weight），经 low-rank Linear/SiLU/Linear/Sigmoid 生成逐元素读门，再对分支 gated mean 得到 `[tokens,2560]`。`combine` 使用归一化残差的线性投影及 `2*sigmoid` 写门注入 attention/MLP 输出；这不是 GLM mHC 的 Sinkhorn mixing，不能复用同名概念替换数值公式。

GDN：16 Q/K heads、48 V heads，K/V head_dim 都是128；卷积宽度4，FP32 SSM state。
沿用 vLLM QwenGatedDeltaNetAttention 的投影、prefill、causal conv、metadata；专用子类仅覆盖 non-spec decode，用 packed QKV dispatch 更新状态。a/dt_bias/A_log 生成衰减，beta 必须保持 FP32 sigmoid 语义；Q/K L2 normalization 和索引原位 SSM 更新是关键数值边界。

QSA：Q24 heads、KV2 heads、head_dim256；RoPE维度64（partial_rotary_factor=.25），theta=10000000。
Indexer 是 replicated projection：Q4 heads/K1 head，dim128。原始 K 按4 token 微块压缩，归一化后使用块首位置 RoPE，MQA 打分选块；预算2048 tokens=512完整块，并处理至多3个未满尾块 token。返回固定宽度2048+3的选择空间，分页映射必须尊重实际 strides 和padding。
主 K/V 与 raw/compressed indexer side caches 分开管理；选出的 token 进入稀疏 GQA、稳定 softmax、V加权、sigmoid输出门和输出投影。

第2层（0起算）含 PLE：ngram_size3，即 bigram/trigram 各8个头，合计16头，每头输出160维，拼为2560。
每头词表基于20,000,000附近的不同素数，按128对齐；持久化 multipliers/vocab_sizes/offsets 从checkpoint加载。
哈希是有符号整数乘法/位操作/取模，不能用浮点替代；EOS边界填充防止跨段历史污染。
128份checkpoint embedding分片按各TP词表区间交集加载。VocabParallelEmbedding查表后经归一化、门控和宽度4的短卷积注入；runner必须提供原始token历史，续写、chunked prefill和请求行重用均须更新。

视觉配置：27层、hidden1152、16heads、MLP4304，3通道，空间patch16、temporal patch2、spatial merge2，输出2560，位置表2304，无deepstack索引。需要patch投影、位置嵌入、attention/softmax、tanh近似GELU、patch合并及跨模态embedding替换。候选分支继承Qwen3视觉组件但没有本模型视觉验收，首轮文本启动显式language-model-only。
MTP配置为1个full_attention层；本轮不启用speculative_config，分支会明确拒绝，而不是把它当普通下一token路径。

## 端到端数据流

1. tokenizer/chat_template将用户内容转为token；默认thinking，可用enable_thinking=false生成简短sanity答案。max_length=262144，不能从商业API的1M推断当前checkpoint默认上限。
2. API/调度器构造token、位置、每请求已计算token数、block tables和状态索引；PLE runner准备n-gram历史及公共slot metadata。
3. Embedding扩展为四分支残差。每层先读混合，执行GDN或QSA，再写回；之后读混合、MoE routing/expert/shared计算和写回。第2层注入PLE。
4. 最后hyperconnection mixer压缩到2560，归一化、LM head得到248320维logits，经采样和qwen3 reasoning解析返回答案。
5. prefill写入QSA缓存并初始化/更新GDN与PLE卷积状态；decode只处理新增token；graph replay必须随调度刷新地址映射和状态索引，不能复用上个请求的metadata。

## 按组件的算子与通信清单

| 组件/阶段 | 从配置或实现核实的关键运算 | 接入/风险 |
|---|---|---|
| 输入与PLE | integer hash/XOR/remainder、embedding gather、TP shard copy、EOS masking、cummax、state gather/scatter、短卷积 | 高风险是边界、非连续布局、重复state行和graph新请求 |
| Gated Residual | FP32 square/mean/rsqrt、1+weight缩放、低秩矩阵乘、SiLU、Sigmoid、分支mean与残差加法 | 保持HC外/hidden内布局及BF16舍入 |
| GDN | fused projection、causal conv1d/update、QK L2 norm、softplus/exp衰减、FP32 beta sigmoid、chunk/recurrent gated delta、gate norm、输出GEMM | packed decode ABI与SSM布局；prefill/decode一致性 |
| QSA indexer | replicated GEMM、GemmaRMSNorm、partial RoPE、4-token pooling、paged MQA scores、topk块展开 | 因果尾块、block table、物理stride |
| QSA attention | QKV GEMM、norm/RoPE、KV write、sparse QK dot、softmax、AV、sigmoid输出gate、输出GEMM | BF16限制，graph形状固定，禁止部分写入后fallback |
| MoE | router GEMM、topk/归一化、dispatch/permutation、expert gate/up GEMM、SiLU multiply、down GEMM、weighted combine、shared expert sigmoid gate | 512专家、10激活，不能把已有GLM配置直接套入 |
| 末端 | mixer、RMSNorm、LM-head GEMM、logits处理、采样、detokenize | 模板thinking与最终答案正确分离 |
| 多模态/MTP | 视觉conv/attention/GELU/merge；MTP额外full_attention层 | 架构已列举，设备实现/验收仍不在已验证范围 |
| TP通信 | column/row/vocab parallel、all-reduce及logits gather等框架collectives | TP8：24个Q头可整除，KV头复制；TP16不满足Q头整除。PP=1，EP/DBO/spec禁止 |

## 执行限制与待验证事项

原生支持262144，初始服务max-model-len=min(262144,50000)=50000。候选QSA构造直接使用config.max_position_embeddings建立RoPE，和配置上限一致。
TP8选空闲PPU8–15，每卡96GiB；约335.28GiB BF16总权重意味着平均约41.91GiB/卡，但实际embedding分片、缓存和graph额外内存需实测，不能仅依均值宣称能启动。
候选分支记录的是旧FlagGems revision上的组件测试；本次必须先快进同步当前FlagGems，再检查是否已有兼容算子，按dispatch接入并重新验证。
保留 vLLM 0.24 源码与原GLM插件，独立候选插件安装。视觉/视频、MTP、量化、PP/EP、最大上下文请求以及完整准确率仍待实测或明确后续范围。

## 2026-09-06 复核

复核标识：`architecture-review-20260906-maxlen65536`。远端只读复核确认模型 `config.json`
SHA256 仍为 `889658f2508e8c61d409b02e70e0d78d8d4452ec65aaafbe129805d213d2e74b`，
`text_config.max_position_embeddings=262144` 的原结论未变化。为诊断 GPQA 中达到30000-token生成
上限的样本，65536上下文试验处于模型声明范围内；这项复核不等于最大上下文正确性或性能已验收。
