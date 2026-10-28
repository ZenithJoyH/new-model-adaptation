# 014 整模型图模式验证

批准范围mx-101/mx-102、glm5.3-flash容器，TP8/PP2、BF16、65536上下文、seq8、
2048批token、Mamba align、prefix开启。冻结最大logprob绝对差0.05，不调整容差。
按FULL→FULL_AND_PIECEWISE→FULL_DECODE_ONLY→PIECEWISE顺序；没有下档通过声明。

首个实际FULL `glm-full-graph-diagnostic-v9-20261028` 在capture前失败，根因为mHC的
CachedOp/FGV Python边界被Dynamo追踪，见012。修复mHC及相邻SwiGLU后，两机71项
回归和v11整模型eager通过。013又在独立真实编译负对照确认Torch产物抽象类API变化，
最小修复经两机各四例及独立恢复验证通过；没有为推测中的后续错误预先修改缓存或编译参数。

当前重试 `04-runs/glm-full-graph-diagnostic-v12-20261028/<host>/`：源集合33文件、
共同部署指纹d69d7bf666be5ae7331ec764f296c5c82355e7b8af4ec32ea3e9a3281187e5eb，
环境原生gate已通过。102先启动并核实实际子进程，再启动101。102使用当前根级
start-model.sh；101离线LLM driver使用相同基础引擎参数和FULL，执行四请求对照。
实际模型仍在加载/编译，尚无整模型图模式通过结论。

driver临时测量16 rank的实际cudagraph_mode、原生compilation_counter和CUDAGraph.replay
计数，要求每rank确有capture、每个变输入请求后replay增长。输出逐token logprob与原
v11 eager两短请求、两长前缀冷/热请求比较；参考复用边界见013。计数hook仅用于诊断，
健康路径还原，不进入产品或交付脚本。离线RPC函数传输要求两端设置原生
VLLM_ALLOW_INSECURE_SERIALIZATION=1；这是本轮过程环境，不进入最终API启动脚本。
原生自动调整图档位必须保留为FULL未通过证据，不能以请求配置代替实际档位。

最终API sanity、GPQA198和性能必须由同一最小start-model.sh启动，再绑定实际服务实例。
当前没有formal acceptance或最终镜像验证声明。容器保持运行，原始失败与日志留在远端。

v12实际FULL在profile_run编译阶段失败：最早rank7报Unsupported hasattr call，
SymNodeVariable的__class__检查来自FGV libentry.run；调用链为GLM
_indexer_forward_nope→INDEXER_OPS.rotate_indexer_query→provider→hadamard128。
尚无capture/请求。102随后Broken pipe是主节点退出后的通信后果，不能当首因。
101 runner已rc1退出；102仅按本次任务的精确headless PID/父子关系SIGTERM并记录停止。

扩大修复前清单：仅Plugin模型glm5next.py和既有PP测试文件，沿用已有
direct_register_custom_op。为GLM indexer的Hadamard旋转及相邻FP8 query准备建立有真实
CachedOp实现和纯元数据fake的局部边界，保留SparseIndexerOps接口、dispatch选择、
FP8 dtype/group/scale参数及原数学库；既有kpool/MLA和KDA重算处已位于注册op内部，
不批量包装或修改FGV libentry。先对两处实际调用分别执行严格动态Inductor负对照；
只有证实失败的路径才改。测试追加实际32头×128维、BF16/FP32、1/3 token、layout、
schema/fake、独立CPU参考和两次变输入graph。原71项/断言保留，不修改Torch/vLLM，
不禁编译或降档。两机局部与受影响eager/FULL都须重跑。

`glm-indexer-compile-baseline-v13-20261028/mx-102`两例真实eager均通过、严格动态
Inductor均失败：旋转为上述SymNode hasattr，量化为实际MetaX provider中的logger.debug。
据此仅修复这两处已证实边界。新增十例（旋转两dtype，量化两dtype×scale布局×UE8模式），
包含Hadamard独立CPU矩阵参考、FP8 absmax scale/量化误差界、schema/fake、动态编译
及两次变输入replay。FP8原始字节与原CachedOp对照，避免只看近似重构掩盖接口改变。

v13首轮37项通过，新增旋转BF16的CPU参考、空/1/3 token、动态编译、schema/fake及
两次变输入replay已全部执行成功；随后新测试把底层FGV的ValueError误作CachedOp接口错误。
实际CachedOp会将失败实现标记并转为RuntimeError，这是既有行为，不能据此改产品或
让无效输入污染后续用例的dispatch全局状态。只把本次新增的无效shape检查改为直接验证
fake元数据边界；真实计算/编译/两次重放断言全部保留，原71项不变，不宣称无效输入的
真实CachedOp错误路径被修复。失败日志保留，以新run ID重跑完整81项。

102 `indexer-compile-fixed-v13b-20261028/mx-102` 完整81项通过（164.48s、runner rc0）。
模型SHA f3bdadcff159ecc66ccb51cf5f7eefcbb752881987dffb1e170cba12c83ba48b，
原PP测试追加后SHA 643c1ce020ed9226d197b48f7c139d80abc037dd249347bdb0c3bb4dc7664ea0。
原71项测试字节前缀保留，未改FGV/FG/编译产物补丁；完整源仍33文件，仅两文件增量。
101按完整旧源集合与原FULL进程退出守卫同步，同样81项通过（337.00s、runner rc0）。
v13模型13文件归档SHA为0a9e617d2a82cb4858dde7433fb8ed72104930c46c2551ac2483bbbd866ce9e7。
另保留下发过程中的两次换行转义解析失败（未执行任何文件写入）；整段staging增加本地
compile校验后才成功执行。此过程错误不属于模型或算子故障。

v13同源双机eager随后通过六请求、idle和四chat参考：4、Paris、mixed Paris/yellow、
repeat yellow及chat **4**；其余chat参考为**5**、**56**、Paris。idle四组输出均为yellow，
最大logprob差依次0.0047664568、0.0106430873、0.0257107615、0.0103012174，均≤冻结0.05。
本轮不为0，不沿用v11的0差结论；两个hot请求各命中3456 token。原始结果位于
`04-runs/glm-eager-model-probe-v13-20261028/mx-101`、`glm-prefix-idle-v13-20261028/mx-101`
和`glm-eager-chat-references-v13-20261028/mx-101`。API PID943306，core943571；三个
请求任务state均passed。随后按精确owner停止此eager实例重试FULL，不停止容器。

当前实际FULL重试为 `glm-full-graph-diagnostic-v13-20261028`：102 root PID1149076，
101离线driver7 PID963237，runner963231。两个旧eager进程树已核实退出；16 rank已进入
初始化，新FULL正在加载/编译，尚无capture/replay或通过结论。driver7仅增加诊断耗时
字段，数值阈值和实际mode/capture/replay要求不变。两端离线RPC序列化flag只在任务
环境设置，根级启动脚本SHA仍3679d87a8c1c000e1b99294f1a48d10fd9275a75e72f9c15c41b03520bf10c37。

07:39两个PP代表rank已完成compile range(1,2048)，各保存原生AOT产物，torch.compile
总计38.41s/39.16s；其后首次profiling/warmup分别72.20s/73.15s。此前mHC/SwiGLU/indexer
追踪阻塞已越过，但尚不能视为capture、replay或有效FULL通过。FlagTune缺少可选xgboost
沿用既有AUTO→default行为，没有安装额外依赖或修改其策略。

FULL13最终未通过：07:40:46，全部16 rank的原生解析明确指出MetaXGlm5NextMLABackend
或Glm5IndexerBackend只支持UNIFORM_BATCH，将FULL改为FULL_AND_PIECEWISE。
前者继承只读vLLM FlashMLASparseMetadataBuilder的能力（flashmla_sparse.py:232），后者继承
DeepseekV32IndexerMetadataBuilder.get_cudagraph_support（indexer.py:241）；KpoolTail存储
builder的ALWAYS不能替代实际MLA/indexer能力。没有把这些声明改成ALWAYS冒充支持。
代码追踪与产物兼容已先修复并通过真实整模型编译；剩余是当前元数据/后端支持范围，
不能通过更名模式或改一个能力枚举解决混合batch的全图支持。

实际混合prefill/decode PIECEWISE五档、decode FULL四档完成capture。worker-initial.json
显示16 rank全部effective_mode=FULL_AND_PIECEWISE、各num_cudagraph_captured=4，replay=0。
driver据此正确拒绝FULL请求并rc1退出，未发四个数值请求；没有result.json，不记graph通过。
worker-restored和退出状态须结合原始文件核对，不以capture代替变输入replay。
保留其configuration、两个stdout、worker-initial、原生能力代码和source快照作为FULL阻塞证据。

下一档按序显式FULL_AND_PIECEWISE，保持全部33文件、权重、TP8/PP2和基础参数不变；
只把根级launcher的cudagraph_mode从FULL改为FULL_AND_PIECEWISE，先102后101同步核验。
新run必须确认有效档位一致、真实capture、四请求变输入replay及≤0.05对照。
限制为mixed部分走piecewise、decode走full；恢复纯FULL的条件是相应MLA/indexer构建器
取得并实测混合batch ALWAYS支持，再从FULL重验。未因此跳过任何档位或降低精度要求。

已核对FULL13的worker-restored存在、全部16 rank的capture最小/最大均4；主driver退出，
从节点完整stop-request进程树也无残留。显式下一档run为
`glm-full-and-piecewise-diagnostic-v13-20261028`。launcher只改变一个模式值，新SHA
a9ccaa4159df8790dd8c7c1833913e239d3f55ba347a65976cf6be29ba6b6626；prefix默认开启、
仅--performance关闭的分支和其他字节保持不变。102已启动并验证，101按同流程启动。
此时仍无四请求变输入数值/replay通过声明。

显式下一档随后实际通过：`glm-full-and-piecewise-diagnostic-v13-20261028/mx-101`
state passed/rc0、result passed，16 rank实际均FULL_AND_PIECEWISE，初始capture119～124。
四请求文本依次4、Paris、yellow、yellow，与v13 eager一致；logprob最大绝对差依次
0.0050130067、0.0141989067、0.0191135481、0.0323140994，均≤冻结0.05。
每请求后的worker-after记录均通过所有rank的replay增长断言，不能用旧自动降级capture
代替本轮变输入验证。记录的诊断耗时为220.46/37.75/133.89/12.00s，包含首次通信/形状
预热等影响，不能据此宣称正式吞吐或优化达标；最终服务仍须性能sanity与正式测量。

主driver主动shutdown后native executor曾发送SIGTERM/SIGKILL回收本任务worker，并提示
semaphore/shared-memory resource_tracker残留；主任务最终rc0。102 headless在主节点结束后
仍存活并持续报TCPStore Broken pipe，已按精确owner停止，不隐藏此生命周期限制。
容器保持运行；下一步用同一最小launcher、移除仅诊断调用方的序列化flag，启动API候选
并完成最终运行身份、正式execution-mode/sanity/GPQA绑定。当前不是完整适配验收通过。
