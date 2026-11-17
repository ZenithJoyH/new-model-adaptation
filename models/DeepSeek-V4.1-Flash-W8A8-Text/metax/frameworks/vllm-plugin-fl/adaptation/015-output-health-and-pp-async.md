# 015：真实生成异常与 PP 异步对照

状态：open，尚未归因。eager v8在TP8/PP2、async on、prefix on下已完成加载、cache和warmup，健康200；真实生成不健康，不能通过执行模式或sanity。

首个固定中文17×23请求返回200、stop，内容停在“根据你的问题，我需要输出。 我 需要计算 ”，没有结果。原始请求、响应与双机服务/源码绑定保留在 `04-runs/mx-102/eager-v8-first-request-20261104/`；该诊断脚本只检查HTTP/非空，不是正式sanity验收器。

后续顺序探针保留在 `04-runs/mx-102/eager-v8-output-probe-v1-20261104/`：复制“青山”只输出“根据你”，随后连续产生129280直到128 token长度上限；法国首都回答为unknown；英文17×23只重复题目；thinking请求content为空，reasoning开头“好的”后重复token35020直到1024上限。所有原始响应及token IDs保留，不作为通过证据。

真实HF配置展开词表129280，checkpoint EOS=1；真实rank15构造记录的LM head为BF16 `[16160,5120]`，TP8合计129280，没有尾部padding可解释129280这一越界ID。原生异步输出占位符相关源码使用-1，不能仅凭该ID声称泄漏了某个调度占位符。生成格式、KV/数值链与PP异步数据流仍需区分。

已完成的对照eager v9保留相同Plugin v32、FGV v41、FG clone v3、权重、20/20 PP切分、1024批token、16序列、512 MiB cache、50k上下文、prefix on及DEFAULT调优。只将异步调度显式设为off，另用新端口29599标识独立服务。首个请求与四项探针使用同一字节和顺序；源码绑定完全相同，命令差异仅异步开关与实例端口。首个中文乘法恢复391，但其余四项仍失败：复制错误、首都回答乱码且2个越界ID、英文乘法错误、thinking 817 tokens中51个越界ID且无最终答案。证据位于 `04-runs/mx-102/eager-v9-first-request-20261104/` 和 `04-runs/mx-102/eager-v9-output-probe-v1-20261104/`。因此不能把公共异常单独归因于async，也不能认定关闭async已修复模型。

2026-11-05进一步诊断：`04-runs/mx-102/logits-api-probe-v1-20261105/` 的返回概率项有限，但相同原始提示的首token与前次不同。`04-runs/mx-102/repeat-first-v1-20261105/` 12次完全相同的18-token提示、temperature=0、固定seed、max_tokens=1，在单请求顺序执行中得到多种首token（33、671、271、16）及不同概率；每次请求SHA-256均为591debb39a7f358b06612a837f5cebcbfab04db7e4d20b2825fe57495f2f402d。该现象发生于async off，仍需定位数值/状态/通信链，不进入正式精度评测。

下一轮eager v10沿用同一安装源码与async off配置，实例端口29601，仅增加原生worker extension诊断入口。观察器与CLI包装脚本均位于 `02-issues/<host>/eager-service-v10-20261105/`，不改变安装源码、不使用PYTHONPATH；进程初始化后通过原生collective RPC安装临时forward hooks，将选定层输入/输出复制到独立诊断buffer，再于请求完成后回传CPU摘要。复制会改变时序，故该轮仅用于定位，不替代无观察器的对照。v9两机本任务进程已按PID namespace、命令和starttime精确停止，两个适配容器均继续运行；停止回执在 `02-issues/<host>/eager-service-v9-cleanup-20261105/result.json`。

已确认的Plugin接入缺陷与修复边界（plugin:A3、C1、E1–E3、F2–F3）：原生 `InputBatch.make_dummy` 将共享 `is_padding` 全设True，而GPUModelRunner仅在 `VLLM_MOE_SKIP_PADDING` 生效时刷新它。V4.1 ModelState无条件读取该可选维护的buffer，导致实际Engram历史和compressor slot被屏蔽。v10真实18-token请求的slots/requests全为-1，query边界却为0、18，见 `04-runs/layer-observer-v1-20261105/layers/`。拟修改 `model_state.py` 的初始化和prepare_inputs，以原生 `num_tokens` 和 `num_tokens_after_padding` 构造本模型稳定padding buffer；不设置全局MoE开关、不改只读vLLM。

另确认CommonAttentionMetadata的token_to_req_indices在缓存命中时只返回旧buffer，不填新的调用方buffer。现有cache builder忽略返回值，会使同一group的第二builder在混合请求下映射错误。拟在 `cache.py::build` 将返回映射复制到本builder稳定buffer。

修改清单限定上述两个生产文件及现有三份functional tests（model_state、compressor_state、cache_metadata）：补原生dummy残留padding的负对照和修复回归，覆盖Engram和ring，补同一CommonAttentionMetadata多builder混合请求回归；已有metadata整数oracle、请求重排、状态复用、graph变输入replay继续执行。无新数值kernel，无FG、FGV或第三方组件改动。先停止本任务服务，在103复现旧源码失败，再修复、静态检查并核验后同步102。最终必须重启无观察器服务，重新检查生成、PP异步和正式验收。

103修复前负对照为4 failed、2 passed，分别复现stale padding的Engram/ring两项和缓存映射ratio1/2两项。原始日志为 `04-runs/mx-103/metadata-v33-negative-20261105.log`，失败保留。Plugin v33修复后同三份完整functional tests为92 passed，含原有metadata graph变输入replay与真实压缩状态组合；日志 `04-runs/mx-103/metadata-v33-positive-20261105.log`。静态检查绑定52文件上下文，七项适用Python hook返回0且内容不变。初次formatter修改两份测试的失败记录另存，修正后重新冻结。当前仅证明组件修复，整模型生成和异步调度尚待复验。

102同步相同五文件后亦92 passed，日志 `04-runs/mx-102/metadata-v33-positive-20261105.log`。两机均未修改vLLM、FG或FGV。v33的52文件manifest SHA-256为 `f8aba1d8181be037ca21c21838e2ffdf4294bed84c1adec9d5be2045c2af557c`；model_state.py为 `18770e9460845b34627ebdd76b9b77c5ed745c0602c0218ee7574b8265719805`，cache.py为 `564f1ca792e133f1bad4d5a5e4c2a15a1b0619ff2fec4b7047be01e5833c6a10`。v10本任务进程已停止，容器继续运行；后续eager v11移除观察器和dev RPC设置，以async off、端口29603恢复无观察器整模型验证。

v11在00:44:28完成引擎初始化，两机各8 ranks全部加载，健康200。无观察器的首个中文乘法准确输出391（1.43s）。原四项按同序复测均恢复：青山、Paris、391，以及thinking正确给出391并正常终止（45 tokens、10.90s）；四项均无越界ID。证据在 `04-runs/mx-102/eager-v11-first-request-20261105/` 与 `04-runs/mx-102/eager-v11-output-probe-v1-20261105/`。这支持padding接入修复消除了已复现的公共生成故障；并发/长提示、async on、FULL graph和正式精度性能仍待验证，不提升为完整验收。

v11扩展矩阵 `04-runs/mx-102/pp-matrix-v11-20261105/` 未通过：四并发中的加法、复制、首都均正确；两条未要求简短的乘法（含stream）生成分步解答，在128-token预算处被截断，不能按该探针宣称完成。1296-token重复背景请求则两次复述背景且没有回答末尾乘法。八项均无HTTP/运行错误，非stream响应无越界ID；不能据此通过长输入或完整矩阵，也尚不能归因于async（当前off）。后续明确简短答案要求并分档非重复背景，区分预算/提示影响与分页、chunked prefill问题，保留失败而不放宽旧断言。

长提示矩阵后，以原同字节18-token提示重测12次max_tokens=1，全部为Paris（51119），选择概率稳定接近1，未再出现旧轮的多种无关首token；证据 `04-runs/mx-102/repeat-first-v11-20261105/`。概率仍有微小浮点差异，不能声称逐bit确定性。该结果不替代长输入验证。

进一步的非重复背景分档 `04-runs/mx-102/long-prompt-v11-v1-20261105/` 中，134、446、862、1278、1694-token输入均复述背景、未答末尾乘法，因此不是仅1296-token重复背景或首次chunked prefill的问题。`04-runs/mx-102/prompt-boundary-v11-v1-20261105/` 明确只输出数值、max_tokens=1的分档结果为：30/43/56 tokens首选391，69 tokens首选171，82/95/108 tokens首选“根据”。该长度相关故障发生在async off，仍未归因；分页和批量计算路径需区分。v12 async on控制文件已准备但未启动，不能将其视作已验证。

原生API的逐请求cache_salt契约已只读核实。`04-runs/mx-102/prefill-split-v11-v1-20261105/` 用隔离salt比较同一69-token原始ID列表：整段prefill和预先缓存64-token前缀后均首选171；后者prefix_cache_hits_total确实从3904增至3968，且API返回的prompt IDs完全一致。不能据此只归咎于一次prefill的M大于64。下一轮v13沿用同一v33源码、async off及1024批token，只增加独立观察器，核对实际GPU input/metadata与PP0输出、PP1输入逐bit一致性。原生张量仅在批准04-runs保留，观察器仍不进入产品源码。

v11已停止本任务进程，容器保持运行；102停止回执沿用了预备async-on对照的reason措辞，实际后续改为上述v13故障诊断，v12仍未启动。原回执保留，不覆盖历史。

v13完成四组真实张量取证，记录在 `04-runs/layer-observer-v13-20261105/`，rank0/8原始CPU张量保留为pt，其余rank保存摘要。输入IDs与原始请求一致，已检查的slots/context lengths符合独立整数公式；短18-token仍为Paris，整段69-token为171，64+5分段本轮为391。CPU分析 `cpu-analysis-v1.json` 的直接rank0完整输出与rank8完整输入比对出现小差异，但原生GPUWorker实际使用TP切片发送/接收后all-gather；完整张量不能按直接一对一协议判错。该分析原始数值保留，后续按8个发送rank各自对应分片核对。Native源码路径与协议已只读确认。

新假设是TP复制计算的微小浮点差异影响路由。当前FG e584的MetaX FP32 mm在默认非确定性模式可选择atomic split-K，确定性模式已有two-step分支；mHC调用的是该公开ATen mm。v14仅在独立worker观察器中切换Torch确定性模式，并记录实际mm分支、FGV消费的topk_ids及TP分片hash，使用隔离cache salt进行同服务对照。未据假设修改FG/FGV/Plugin数值实现，不将该诊断开关当作已接受生产配置。


v14确定性对照完成：同一服务六个请求（18/69/134 tokens，各OFF/ON）按原生TP切片协议核对，hidden_states与pre_mix的全部对应分片均一致，没有观察到传输内容损坏。实际mHC投影在OFF命中MetaX atomic splitk_mm，ON命中splitk_mm_two_step；ON时三个输入的两PP阶段各80个实际路由调用键全部专家集合一致，PP出口TP复制张量也逐bit一致。OFF存在部分路由专家集合差异。原始证据与完整分析在 `04-runs/deterministic-observer-v14-20261105/`，`cpu-analysis-v1.json`。确定性模式前后69-token仍为171、134-token仍为“根据”，18-token仍为Paris，故它改善复制一致性但没有修复剩余质量故障。临时开关已恢复原False，观察器已禁用；没有将诊断设置或假设写入生产源码。

随后在同一v14服务内启动隔离的causal observer，以确定性ON比较整段69-token与缓存64+5的早期注意力/FFN接口，完成后恢复开关。该轮仍是定位实验，不是async ON、图执行或正式验收。


v14因果对照完成于 `04-runs/causal-observer-v14-20261105/`：确定性ON时整段69与单独64-token前缀的已观察attention/FFN/Engram输出以及decoder residual/pre_mix，在层0–3、14、19、20、39的共同前64位置逐bit相同。64+5尾段与整段69尾段有小数值差异，最早layer0 attention相对L2约0.00335，后续放大，但两种执行首选均171。`cpu-analysis-v1.json` 保留全部接口比较。不能据此认定缓存跨页写入正确，下一轮v15将捕获实际公开算子的输入、写后缓存页、attention输出，并用CPU独立数学核对；仅更换外置观察器，不修改生产源码。v14两机本任务进程已精确停止，容器继续运行。

v15真实算子取证在 `04-runs/actual-operators-v15-20261105/`：69/134-token、rank0层0/2及rank8层20，Q归一化和RoPE、SWA/压缩KV量化写入、index K闭合组RoPE、attention/LSE、输出逆RoPE均经CPU独立数学核对。`cpu-analysis-v2.json` 全部通过，KV FP8编码字节和E8M0缩放逐字节相同；未把未写入的压缩组和未使用的未初始化dummy K作为有效数值。该证据只覆盖所列真实算子输入，不证明全模型或所有算子。

首版 `cpu-analysis-v1.json` 失败保留：观察器用MetaX二维index_select提取非连续cache/cos view，该现有实现的2D快路径忽略行pitch。改为对原始trace中已经捕获的4D attention-entry缓存页和连续64列插入RoPE表做CPU核对，生产源码与服务输出均未改变。原始插入后2D gather副本不作数值判据，未删除失败或降低阈值。该取证错误尚未复现为V4.1生产路径的index_select调用缺陷，不据此扩大FG源码改动范围。

正在对v14已捕获的真实Q/KV及Q_B输入输出，与原checkpoint所选权重、独立CPU动态INT8量化/整数累加契约逐项核对；只通过CPU工具容器stdin传入临时权重片段，回执保存身份/hash，不持久化权重内容。

真实权重投影核对完成：rank0层0/2的fused Q/KV与Q_B，在69整段、64前缀、5尾段共12个接口输出与独立CPU整数累加及原checkpoint完全相同（max_abs=0）。回执 `04-runs/mx-102/actual-weight-projections-v14-v1-20261105.json`。v15额外检查 `cpu-selection-v1.json` 在六组层/输入上确认SWA可见窗口及短上下文的全部闭合压缩组均恰好选中一次，无遗漏、重复或额外索引。

长输入thinking探针 `04-runs/mx-102/long-thinking-v15-v2-20261105/` 仍失败：160 prompt tokens，1024个reasoning tokens持续复述/续写记录，content为空，length终止，249.30s，无越界ID。初次v1客户端因引用了不存在的thinking-request文件而未发请求，失败日志保留；v2使用已核实的math-thinking-request，不覆盖旧目录。

已只读核对固定主线e77的模型、attention、compressor和mHC源码。首层identity collapse与mHC post的转置组合布局均与现有契约相符，未据猜测更改。下一实验限定已有FGV MoE公开接口：非零权重、真实TP8局部H5120/I288、E384、top6、56/69/134 tokens，开启/关闭FG自动ATen替换与独立CPU双量化整数oracle比较。只在批准02-issues/04-runs执行诊断，无产品源码修改。v15两机本任务进程已精确停止，两个适配容器均继续运行。

MoE初轮numerics-v1和分段stages-v2失败保留。新诊断参考的`127./maximum`在Torch中执行倒数乘法，与原生直接除法在半整数舍入点不同，导致少量初次量化差异；不是已确认的产品缺陷。更正为`torch.div(127., maximum)`后，stages-v3的69-token两次量化、GEMM1、GEMM2及最终输出全部max_abs=0；numerics-v4原56/69/134三组、两个尝试的ATen上下文共六次均max_abs=0，未改变阈值、输入分布或生产代码。证据 `04-runs/mx-103/moe-batch-{numerics-v1,stages-v2,stages-v3,numerics-v4}-20261105/`。开启use_gems的三次有既有operator注册警告，不能把尝试开启标记当作全部ATen替换均激活的证据；FGV生产MoE/align/sum实际调用已记录。

真实历史核对 `04-runs/actual-operators-v15-20261105/raw-history-cpu-v1.json` 的69/134行与完整原始提示逐项一致。主线CPU tokenizer压缩映射、bucket布局、RNG乘子与Python任意精度整数oracle，对v14整69、前缀64、尾5两处Engram的全部实际hash逐项一致，含约9e18 rolling值；回执 `04-runs/causal-observer-v14-20261105/hash-native-cpu-v1.json`，map SHA-256仍为c60a86322ec17b4142bfef3c57a8d81fb428550cdf487f88a4320cb59fe46481。没有复现64位模运算或实际历史缺陷。

原checkpoint的layer1 Engram抽取bucket行、原Wkv/scale与q/k权重经CPU独立双量化/门控核对，整69、前64、尾5各最后token注入结果通过（前两项max_abs=0，尾5约9.54e-7）。回执 `04-runs/causal-observer-v14-20261105/engram-original-weight-cpu-v1.json`，权重片段仅通过stdin使用，不持久化；不外推为layer14或全模型通过。当前仍未归因、未通过完整推理。

最终隐藏状态与原输出层的171/199/391行独立乘法核对，整69及尾5的API概率差均精确对应最后一行的BF16 logits差，原始391分数确实低于171；`final-logits-original-head-cpu-v1.json` 不支持采样取错行的假设。layer2 compressor的原BF16权重FP32投影差约6e-6，观测scores的闭合组独立池化/RMSNorm与实际latent逐bit一致；`compressor-original-weight-cpu-v1.json` 仅覆盖整69、前64、尾5的该source层。

v16保持相同生产源码和async off、端口29613，仅更换外置worker extension，准备baseline/no-Engram/no-compressed-KV/两者跳过四种消融。每种用隔离prefix salt、确定性ON和相同69/134/18-token请求；NN hook仅在诊断时用输入residual替代Engram返回值，attention实例字典临时省略extra cache/indices。配置切换及结束时恢复原函数、hook和Torch开关，并核验16个ack。其结果用于定位，不可将跳过原模型功能的变体作为验收或最终配置。原生服务、源码绑定、消融脚本及结果均保存在批准02-issues/04-runs，不修改安装库。

v16四组消融全部完成，16 ranks的临时hook、attention字典与Torch确定性开关均已恢复。baseline的69/134/18-token首选为171/根据/Paris；no-Engram为好的/好的/Paris；no-compressed为EOS/。/Paris；同时跳过为根据/EOS/Paris。没有变体恢复目标391，不作为修复。证据 `04-runs/ablation-v16-20261105/result.json`。

更广的诊断 `04-runs/mx-102/diverse-quality-v16-20261105/result.json` 七项均未给出目标答案：英文自然背景乘法、英文记录乘法、短英文应用题及其thinking版、英文背景首都、中文背景接英文乘法、中文自然故事首都。部分复述输入至预算上限，部分正常stop但答错；thinking应用题512 tokens内仍重复问题。全部无越界ID。该证据说明剩余问题不限于中文或某一重复背景；预算用尽不单独证明算子错误，也不是正式GSM8K精度结果。

补充原始权重CPU核对均为诊断而非整模型通过：`causal-observer-v14-20261105/mhc-original-weight-cpu-v1.json` 检查层0/2的mHC组合、归一化输入和post残差，已检查接口在既定BF16复合阈值内；`ffn-original-weight-cpu-v1.json` 用真实层0最后token、六个实际专家与shared expert、全部八个TP分片，原gate/bias路由专家集合一致、权重差约3e-7，FFN输出与不同BF16归约次序的参考相对L2约0.003–0.004，未设置形式通过断言。`actual-operators-v15-20261105/rope-math-cpu-v1.json` 的实际RoPE表与独立plain/YaRN数学最大差约2e-6–6e-6。

完整层0注意力输出投影 `causal-observer-v14-20261105/global-attention-original-weight-cpu-v1.json` 使用原64个Q头、sink、全部分组WO_A与TP8的WO_B，CPU独立数学与实际接口比较：FP32归约参考相对L2约0.00561、max_abs=0.015625；首8头attention最大差0.0078125。尚未据该复合BF16偏差确认生产缺陷。`embedding-original-weight-cpu-v1.json` 的69行实际输入嵌入与原checkpoint对应行逐bit一致。

实际共享压缩缓存核对 `cache-consumers-v16-20261105/cache-consumer-cpu-v2.json` 覆盖69/134-token两种输入、source2→consumer3/7、source14→19、source20→21/24/39，共12组；所有可见有效slot的FP8数据与E8M0缩放字节逐字节一致，slot集合亦一致。只使用4D attention-entry快照，不使用已确认无效的2D gather取证副本。初版CPU脚本因第二请求无可选cache_layout记录触发StopIteration，失败保留；v2只修正可选布局摘要读取，未改数值判据。观察器已禁用，无生产源码变更。

v16 OFF与v17 ON完成同源码、同请求字节的TP8/PP2 eager对照，汇总 `04-runs/mx-102/pp-async-comparison-v1-20261105.json`。双机source-binding完全一致，启动命令只差async开关、实例目录和通信端口；8份请求逐字节及SHA-256核对一致。四并发短请求均正确输出391/Paris/青山/23并stop，两并发流式均正确结束且收到DONE；raw69和chunked1694均返回200、无越界ID，但仍分别错答171/记录。八项生成内容在ON/OFF一致，ON轮结束健康200。当前测试未复现PP+async额外的启动、挂起或流式故障；不外推为graph、长输出或正式精度通过，也不将共同质量故障归因于async。v16本任务进程已精确停止、适配容器保留运行；v17目前运行，worker extension未启用观察器。

`causal-observer-v14-20261105/qkvnorm-original-weight-cpu-v1.json` 补查实际fused Q/KV RMSNorm：层0/2、整69/前64/尾5的Q输入与整69的KV输入，共8个接口与原norm权重的FP64 CPU数学逐bit一致。真实FFN原权重核对另扩到层14/20/39的整69最后token，各自六个专家的路由集合一致；总FFN与FP32归约参考相对L2分别约0.00396/0.00383/0.00246，仍为组合BF16数值诊断，没有设置形式通过断言。回执为 `ffn-layer{14,20,39}-original-weight-cpu-v1.json`。

v17多步解码补查 `04-runs/mx-102/async-long-decode-v17-20261105/`：与v11相同四份chat请求均200并stop，青山/Paris/391正确；thinking乘法39 tokens、9.76s后给出391，无越界ID。生成文本和token长度不同于旧v11 thinking，不能声称逐bit确定性。该探针为顺序请求，不替代更长混合并发覆盖。

同机只读检查发现 `DeepSeek-V4.1-Flash-W8A8-BF16` 也为W8A8量化版本，含 `flagos_bf16_engram=true`，不能仅凭BF16目录名作为整模型高精度基线。两版tokenizer SHA相同；权重scale命名不同（Text为.scale，另一版为.weight_scale），部分indexer和Engram dtype不同。元数据和小片段比较 `04-runs/mx-102/checkpoint-compare-v1-20261105.json` 不代表完整张量身份。三个矩阵反量化后的FP64统计 `weight-relation-cpu-v5-20261105.json` 相对L2约0.0091–0.0138、余弦约0.99991–0.99996，没有据此确认目标权重损坏。v1/v2控制脚本的片段边界和scale命名错误保留；v4超长向量FP32范数导致非物理余弦值，统计改用FP64，生产计算不变。

按执行模式顺序，下一次从FULL开始；v17两机本任务进程已停止，容器均继续运行。准备的v18去掉dev RPC与外置worker extension，直接用vllm入口和 `cudagraph_mode=FULL`，保留TP8/PP2、async ON、prefix ON及原资源配置，不预设降级。当前仍为执行模式诊断，质量故障未解决，不启动正式精度或性能验收。启动前的空闲GPU窗口补查E384全部非零专家路由的独立数值，以覆盖先前只对8个分散专家赋非零权重的测试范围。

v18 FULL首轮两机16 ranks完成捕获并健康200，四并发短请求和两流式均正确，69/1694-token仍错答171/记录。证据 `04-runs/full-service-v18-20261105/` 与 `04-runs/mx-102/full-control-on-v18-20261105/`。此时没有更低graph档位阻塞证据，不回退；正式执行模式验收仍待质量修复及服务契约绑定。E384全非零专家、69 tokens、top6的独立两次量化CPU整数参考两次均max_abs=0；use_gems尝试仍有既有注册警告，不声称全部ATen替换激活。两处Engram扩展到整69/前64/尾5全部token，原权重CPU对照均在既定阈值内，见 `engram-layer{1,14}-all-original-weight-cpu-v2.json`。

**新确认的契约缺口及改前边界**：同机模型附带只读 `inference/model.py` SHA-256 `4e9ae23620edc8028ccc5d5fef552ab7fdc7dcd6f79608754fe9f67644056f65` 的Attention.forward只对Q做RoPE，没有head RMSNorm；其 `inference/kernel.py` sparse_attn也直接消费Q。固定vLLM e77的 `csrc/libtorch_stable/torch_bindings.cpp` 明确该融合API新增 `bool apply_q_norm=True`，V4.1 attention.py传False。当前FGV公开API与MetaX副本缺少该参数，V4.1接线因此额外归一化Q。此前逐头Qnorm CPU检查只证明该计算实现的数值，不证明它属于V4.1架构；不再用其作为完整语义正确证据。

拟修复范围（plugin:A1/A4/B1/B3/C1/E1/F1–F3/F7；operator:A1–A4/B1–B3/C1–C6/D2–D4/E1–E6/F1–F4/F6）：FGV既有 `ops/fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert.py` 及 `_metax/fused/` 同名wrapper/kernel增加向后兼容 `apply_q_norm=True`，False时保留Q NoPE字节、仅做Q RoPE，KV缓存数学/slots/pitch/写入规则不变。沿用已有固定generic/MetaX TPP阈值，不引入autotune或新性能参数，避免原地Q/cache在调优中污染；既有固定策略豁免需在交付披露。扩展同名tests及benchmark，覆盖False的非单位Q、0/1/69/512+tokens、零头KV-only、padding/负slot、pitch/offset保护、实际厂商分发、True默认回归、新输入真实graph重放及错误前无写入。

Plugin仅改 `models/deepseek_v41/attention.py` 的融合调用显式False、`dispatch/backends/flaggems/impl/deepseek_v41_attention.py` 的执行前能力签名，以及现有dispatch与真实attention-chain测试，独立核对投影后Q只旋转、参数实际传至公开库；不新增数值kernel或逐ATen适配。先完成FGV公开接口及数值/graph测试，再接入Plugin。其他厂商副本已盘点；本次只验证MetaX，未提供新flag的厂商入口由Plugin能力检查拒绝，原V4默认行为保持，不据未测硬件扩展声明。只写实际安装FGV/Plugin，FG和只读vLLM不改。完成后以相同失败请求重跑无观察器FULL及PP异步对照，尚不能预先宣布根因已修复。

FGV v42四文件实现后两机各113 passed，原8项native vLLM硬件对照明确未选、未计通过；日志 `04-runs/<host>/qnorm-v42-positive-20261105.log`。包含61项新公共/通用接口、边界保护、默认True及新输入graph等用例和52项原回归。原API负对照1 failed（不接受apply_q_norm）保留在 `mx-102/qnorm-v42-negative-20261105.log`。FGV静态51文件上下文七项配置hooks通过且字节不变；第一轮isort调整两份测试/benchmark的记录保留。注册ID和导出不变，参数语义在公开API文档中说明，现有metadata描述仍对应默认True路径。

Plugin v34在102的执行前能力、False参数传递、真实Q幅度与attention/cache/graph链共36 passed，日志 `04-runs/mx-102/qnorm-plugin-v34-positive-20261105.log`；52文件上下文七项适用hooks通过且字节不变，初次formatter调整两份测试的失败记录保留。103框架接线待同步；组件benchmark正在103执行，baseline为经独立CPU验证的FGV通用调度，target为MetaX调度，两侧都计相同Q输入复位。不将此比较称作native vLLM提速或整模型性能。

v42组件双模式完成但性能门槛失败，原0.9目标保留：kernel最小0.86087、cudagraph最小0.79110，36次资源观察、前后源码一致；12个形状的失败均为1024-token、zero-Q-head的KV-only分支，8头Q形状最小约0.971。完整证据 `04-runs/mx-103/qnorm-controlled-benchmark-v42-20261105/`。该分支没有Q归一化/旋转工作，原MetaX TPP8分块较通用调度慢。

下一轮v43只为新增False变体的zero-head输入在执行前选择已验证通用kernel，原True分派与数值kernel保持；不增加kernel或调优参数，不降低门槛。扩展同名dispatch spy测试覆盖False/zero-head和True/zero-head的实际kernel，benchmark补zero-head的1/512-token边界、共16形状。必要范围另加既有 `conf/operators.yaml` 对同一ID的描述，说明Q norm可选及False对应V4.1；不改注册ID、分类或导出。适用条款和写入边界沿用上述计划，重新检查完整51文件上下文和受影响数值/graph，再复测同条件双模式性能。

v43最终两机各115 passed（另8项native vLLM硬件对照未选）；配合相同Plugin v34，两机各36 passed，均含真实Q只旋转、NoPE幅度保留、缓存与新输入graph链。FGV 51文件和Plugin 52文件完整适用静态hooks通过且字节不变，manifest文件SHA分别为 `3c2749685a49dff766d9dd80d1da8582e7ee45fd0d5985033a6116bb6bd8aa73` 和 `ce201580ed4e8ea19eb001f1d22b178a2c43893ca6f757e2a151443637426828`。日志为 `04-runs/<host>/qnorm-v43-positive-20261105.log` 与 `qnorm-plugin-v34-fgv43-positive-20261105.log`。

v43组件双模式16形状通过原0.9门槛：kernel最小0.97468、cudagraph最小0.97213，36次资源观察、源码与环境前后一致。证据 `04-runs/mx-103/qnorm-controlled-benchmark-v43-20261105/result.json`。这里只证明MetaX选路相对所述通用FGV调度的该组性能，没有整模型或native vLLM提速结论。接下来v19以完全无观察器的vllm入口、FULL、TP8/PP2、async ON重验真实输出；原长输入失败是否恢复仍待结果，不能仅以组件测试宣布适配完成。

v19首次整模型复验通过此前故障请求：两台16 ranks均完成FULL捕获，健康200；四并发短请求、两并发流式全部正确，69-token与1694-token首选都恢复391。七组多样化请求均正常stop、无越界ID：两种英文背景乘法391、英文应用题及thinking版72、英文背景首都Paris、中文背景英文乘法391、中文自然背景首都巴黎。thinking版298个生成tokens（295 reasoning），29.40s后给出72；不是仅HTTP可用。证据 `04-runs/full-service-v19-20261105/`、`04-runs/mx-102/full-control-on-v19-20261105/` 和 `diverse-quality-v19-20261105/`。由同请求改前失败、改后恢复，确认额外head Q RMSNorm是已复现质量故障的修复点；不外推正式GSM8K通过。准备同v34/v43源码、相同FULL与TP8/PP2配置的v20 async OFF对照，除开关、实例目录和master端口不变。

统一启动入口已准备、尚未用于正式验收：ROOT/start-model.sh 与两机容器内部 `/opt/deepseek-v41-runtime/start-model.sh` 字节相同，SHA-256 `58583a1e64346d5e40ebfba0620f78706add35ce22cfc11ad662acc3ccaaee6d`。普通/精度prefix on，唯一 `--performance` 分支只换prefix off；未知参数/未分配Host IP拒绝，无诊断、安装、清理或磁盘缓存覆盖。V2 runner对应V4.1 metadata链，USE_FLAGTUNE=0固定该环境策略；网卡/HCA/GID/跨NIC沿用已验通信栈；TP8/PP2/mp绑定分片；dtype/量化/cache格式/block64绑定数值与页布局；KV512MiB/50k/batch1024/seq16绑定已测资源预算；tokenizer/parser/alias绑定文本协议与身份；async ON和FULL为当前已验证候选，master端口29621隔离实例。未保留冗余GPU利用率默认值。

两机私有provider按此前授权复制到该容器内部目录，SHA仍e2694779…，ldd无缺失，各枚举5个HCA（含4个已选活动HCA）。系统原库未改，legacy ABI警告仍保留。目录不在bind/volume内，原ROOT副本保留，回执 `02-issues/<host>/runtime-prepare-v1-20261105/result.json`。这是必要交付文件准备，未打包、发布或验证新推理镜像。

v19 ON/v20 OFF的15对请求逐字节一致，双机source-binding相同，启动命令仅async开关和master端口不同。两轮8项矩阵及7项多样化答案均正确、stop/DONE正常、无越界ID，OFF结束健康200；思考过程及解释性文本不要求完全相同。汇总 `04-runs/mx-102/pp-async-comparison-v2-20261105.json` SHA-256 `780a181ea37d635c2a6ac4e6d1bb55e13c57574c64e3a8be1a8a2d2de01857ef`。未复现这些场景内PP异步额外故障，不外推所有长时间压力或正式精度。时延为诊断记录，不作为公平性能比较。

改前文档范围（plugin:G1/G2/H10/F7）：只在实际安装Plugin的README支持模型表增加V4.1 Text W8A8、MetaX TP8/PP2及Merging状态，既有README补必要启动与格式边界，新增 `examples/deepseek_v41_client.py` 真实HTTP生成示例。使用参数化模型/通信地址和库路径，不硬编码个人路径、私有网络或凭据；明确固定公开依赖尚待交付。保持其余README内容，不新增过程报告。检查同仓格式hooks、链接、--help，并对最终服务实跑普通/思考两个入口；不改变模型数值和现有测试。正式源码审查仍不能把待发布依赖或H9基线缺失当作通过。

README首次typos检查仅报原有Ascend段落的正式术语CANN/cann-shmem，七项其余hooks通过且字节不变，失败记录保留。必要配置范围补 `pyproject.toml` 的typos精确术语字典，只认可cann，不修改既有Ascend使用说明、不扩大排除路径、不跳过typos；随后重跑八项适用hooks。

v21在相同真实量化权重和16 rank服务中完成三组eager/FULL对照：69-token乘法、六词颜色与八词数字复制均正确stop，生成IDs逐项相同；所生成token的logprob最大绝对差1.4305046533991117e-6，低于运行前冻结0.05。外置观察器只包装原生dispatch/run_fullgraph计数、使用原生 `_graphs_captured` 控制NONE/FULL，不修改Tensor或产品源码；每rank均有FULL捕获且实际成功重放至少两次，eager期间无重放并实际调用模型forward。16 rank观察器、捕获状态和方法均已恢复。完整原始请求/概率/计数在 `04-runs/execution-validation-v21-20261105/`；不把该eager参考当作高精度基线或全量logits误差证明。

Plugin v35只增加上述文档/客户端与精确typos词典，两机均已安装且--help成功；54文件上下文的八项适用hooks通过且字节不变，manifest SHA-256 `f346f089284a5683e293b3ea5a98e85410f29974a162c7b0794e730cc9274d40`。运行时Python数值文件与v34完全相同；无需因README和检查词典重跑所有GPU算子。最终候选v22已改用相同ROOT/start-model.sh启动，无dev RPC、worker extension或导入路径覆盖；服务完整就绪及正式评测尚待后续证据。

v22随后两机16 ranks完成FULL捕获（1/2/4/8/16/24/32七档），协调服务健康200。实际有效配置来自原生启动引擎行、`/metrics`缓存标签及`/v1/models`，没有伪造不存在的`/server_info`接口；冻结证据 `04-runs/service-runtime-v22-v3-20261105/effective-config.json` SHA-256 `611937d0632316fa145f5c2b0dfdfd3e532a418edf0e9bb2ebe34b11e820da76`。默认GPU利用率实际0.92，显式KV slab512MiB，277438 cache tokens；不沿用旧假设0.9。仅CPU元数据/进程和文件采集，不在服务运行期间新增GPU上下文。

两机原生API身份观察与PP进程树/owned socket分别以每次运行fresh nonce冻结，互相验证29621主端口、rank0/1、公共启动参数、组件/launcher哈希和跨机连接。最终服务契约SHA-256 `6e072a45831f15d29492c23d618c4d211d4017840e4fa426f0b76cd11df657ef`。sanity绑定 `04-runs/v41-sanity-v1-20261105/service-binding.json` SHA-256 `13b8a076ca59dc6b8c456c475115da9aaa4ade2a4346abc2a4c68a67349f82c7`；full测量另有独立绑定，不复用sanity nonce。

v22的8路文本sanity全部正常stop且内容经逐项独立审阅：中英自然解释、1697-token背景乘法391、Natalia思考72、结构化JSON、跨轮对话、另一思考应用题67和中文复制。62.763s完成，观测峰值running8、123次metrics采样、结束健康200。原生 `sanity-result.json` 的needs_review状态保留，独立 `sanity-review.json` SHA-256 `5180a5eaf195b5ea7017f90b84b78dfcfaf000bfe2a5a2f65d42931c9da6086a` 经原生validate_result检查通过。额外fresh cache_salt热运行8项也均正确；混合长prefill时短请求仍约14.77s、长thinking约44.64s，此为诊断数据，不作为公平吞吐或性能通过结论。

正式任务容量按原生task.fewshot_context与实际OpenAI renderer生成全部1319题，再经真实服务tokenize：输入63–226 tokens、均值99.689，最大输出预算32768，合计32994小于50000；8路按64-token页取整的保守容量264192小于277438。证据 `04-runs/gsm8k-capacity-profile-v2-20261105/result.json`。首版工具名profile.py遮蔽stdlib及未解包JsonChatStr的失败保留，v2只修工具文件/`.prompt`访问，没有改框架依赖或评分任务。

8题原生FlagEval试跑完成、0超时、退出0，flexible-extract为7/8。唯一漏分题正确算出160分钟后附“2 hours 40 minutes”，原过滤器取最后数字40；按原始评分计错，未改prompt、scorer或门槛。完整1319题于2026-11-04T21:27:07.979563+00:00启动，run_id `v41-gsm8k-full-v1-20261105`，C8、thinking/high、temperature0、top_p1、max_gen32768、seed20261104、timeout7200，每API一次尝试、无任务重试，最低0.95预先冻结。配置SHA-256 `222a38120af205e619314ef89e94aede0bab8cc5be4f9c0d91d19e538fa68b57`；输出根 `04-runs/flageval-native/deepseek-v41-text-gsm8k-c8-full/v41-gsm8k-full-v1-20261105/`，协调日志与durable watcher在 `04-runs/v41-gsm8k-full-v1-20261105/`。运行中尚无最终分数；没有用tqdm响应数冒充评分数。

源码补丁材料位于 `03-acceptance/source-materials-v35-20261105/`，Plugin/FGV/FG任务补丁分别53/45/3文件，SHA-256分别为 `cfe796822523ab31f572251326b4dc8cf159691919efda1df6e722c21576942a`、`6956da2ea0aece1391adcf71ff1ad45853cc78a006447c6626b0e33c6194800f`、`a43ba6fc892ee91e428e36ef279f5f053881c134b325d637d06f75a8ade345c9`。只执行reverse-check而未应用；继承Plugin dirty未混入任务补丁，实际导入根仍为/opt安装树、只读vLLM保持干净。最终逐块审查正在进行，公开固定依赖（plugin:D3）、高精度模型质量比较（plugin:H9）均未完成，框架状态不提升。英文部署指南仅草稿，不代表推理镜像打包、发布或新容器验证。

随后完整v1的额外原始API健康检查发现Q:停止词在reasoning内触发14条空最终答案；于742/1319响应时只终止客户端、保留原始失败证据和健康模型服务。该故障及同题C4对照见[017](017-reasoning-stop-condition.md)。仅移除冲突Q:的新完整v2已通过1319条提示/评分不变核对、原生预检及fresh两机服务身份绑定后启动；0.95门槛及其他生成设置不变。此更新覆盖前文v1“运行中”状态，不将部分响应作为有效完整分数。

最新结果：用户已要求将唯一未完成题计错，v2的1318份缓存经原生请求键核对并保留，独立汇总1171/1319=88.78%，未达原95%门槛。原生评测客户端已结束，保留退出143及原始证据；模型服务与容器继续运行。先前“仍在运行/无最终分数”描述为历史阶段，当前结论见[末题计错汇总](../acceptance/accuracy-cutoff-summary.md)。该自定义截止汇总不提升正式验收或证明PP覆盖之外的正确性。
