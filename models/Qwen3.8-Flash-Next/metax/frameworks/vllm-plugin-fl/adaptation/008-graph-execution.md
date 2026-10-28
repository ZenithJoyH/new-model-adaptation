# 008：整模型graph逐级验证（进行中）

仅mx-101/qwen3.8-flash、BF16文本TP8、配置max_len50000。先完成最终eager配置和真实前缀
命中回归，再按FULL → FULL_AND_PIECEWISE → FULL_DECODE_ONLY → PIECEWISE逐级执行；
每级保留原请求配置、实际解析模式、捕获/调度统计、失败与修复证据。自动降级不能当作
请求档位通过。当前尚无整模型graph通过结果；失败、诊断和修复记录如下。

已核对安装vLLM0.24 `CompilationConfig.resolve_cudagraph_mode_and_sizes`：mixed FULL
要求所有attention backend宣告ALWAYS；PLE与QSAMetadataBuilder均为UNIFORM_BATCH，
若splitting_ops实际包含attention，FULL会解析到FULL_AND_PIECEWISE；否则可能为FULL_DECODE_ONLY。attention_ops注册不等于splitting_ops已包含，须读取现场解析结果。
这只是源码预判，须由实际启动验证。当前实现仅支持decode full metadata；不把能力标志
改成ALWAYS来规避限制，不改只读vLLM。

模型运行中的原生ModelRunnerFL已生成CUDAGraphStat并传给ModelRunnerOutput；临时
`--cudagraph-metrics` 会输出实际runtime mode和调度次数，可用于核对至少两次真实重放。
GraphWrapper已有capture计数和原生捕获进度；不新增调试产品代码。最终启动脚本去除
这个观测开关。若OOM先保留资源/捕获阶段证据，再调整有依据的预算，不能直接跳档。

固定greedy短题及长前缀变尾部/独立salt探针保留完整输入、输出与logprob；相同输入要求
生成token完全一致，logprob绝对差不超过0.02作为本轮局部数值对照。
这是带明确范围的bring-up检查，不替代正式数据集精度和吞吐验收。

另准备 `02-issues/mixed-state-probe.py`：首请求流式逐行输出1至30，看到首个实际内容token后
插入第二条7×8短问，确认请求生命周期重叠、两条结果正确，并保留完整SSE与logprob。
先在最终eager配置冻结参考，再以graph同输入验证；原生图统计用于核实混合prefill/decode
和uniform decode的实际分派，不能仅凭两个客户端同时存在推断具体graph分支命中。

已冻结eager参考为model-eager-fgv-memorydb-20261024的smoke/prefix-state/mixed-state三份
真实JSON，均passed。图首档model-graph-full-20261024指定mode3/FULL/custom_ops=[all]，
保留eager的OOT算子选择以避免随编译默认值切换数学实现；临时开启原生cudagraph metrics。

## FULL第一轮：RoPE编译边界缺口

原生model-graph-full-20261024在profile的Dynamo全图追踪中失败：
logging.Logger method not supported，FGV apply_rotary_pos_emb的logger.debug经Plugin
rotary backend被直接内联；尚未到attention graph能力解析或capture，不能归为FULL本身不支持。
8卡已释放、容器仍running。原始server.log与配置均保留。

阶段2的环境回执已在容器内原生gate通过，run environment-mx101-memorydb-20261024，
receipt SHA256 8aa41ecd81ee3a9c16eb191c25d8d2c8265055be927a23f90bace249c67ab64d；
后续新增源码改动将重新采集/绑定，旧证据保留为原部署验证。

改前限定：只改Plugin以下两个既有文件，不改FGV数值kernel、不改vLLM，不删除日志、
不通过全局ignore_logger_methods屏蔽所有库的追踪。复用现有backend和torch.library边界，
与已采用的activation graph wrapper一致，正确表达in-place与out-of-place契约。

| 文件/符号 | 必要增量 | 证据与测试 |
| --- | --- | --- |
| dispatch/backends/flaggems/impl/rotary.py::rotary_embedding_flaggems及私有graph ops | 仅FGV被选中且torch正在编译时走opaque op；inplace显式声明query/key突变并返回None，外层保留原别名；out-of-place返回新Tensor并提供fake；eager及FGV关闭原路径不变 | 原真实logger负对照；CPU fake/别名和选择守卫；MetaX实际编译+两次变输入graph，partial-view尾部不变 |
| tests/unit_tests/ops/test_rotary_embedding.py | 追加上述回归，保留全部已有测试 | strided Q/K、两种旋转方式、BF16/FP16/FP32、in/out两侧及optional position IDs |

先最小复现旧路径，再实施；review新增两个schema的别名/返回Fake契约和全部增量diff。

原文件哈希：impl/rotary.py e6118d73ecd30fd8627b74e0ae99fe8a8de60195d82644cea6e7a5d716c6b200；
test_rotary_embedding.py 0a52099aac7445679f2d08428e61e644262055253dc6089474cad5c04303b3e5。
真实BF16 GPU+aot_eager/fullgraph负对照明确失败于相同logger.debug，rc2；
07-bugs/fgv-rope-compilation/reproduce.py及04-runs/fgv-rope-compilation/before.json/log保留。
已实施两个既有文件范围，正在跑完整rotary既有+新增回归。旧环境阶段回执保留但不再作为新源码的当前通过绑定。

修复仅新增impl70行和原测试160行，没有原行删除；原测试前缀完整字节哈希保持。
32项rotary完整测试28.09s全通过，含12组真实Inductor+CG两次变输入重放、共享QKV
backing和未旋转尾部；真实原复现aot_eager/fullgraph改后通过且最大误差0。
共享Qwen/worker/KV/Mamba/量化/平台/激活回归210项25.53s全通过，见
04-runs/fgv-rope-compilation/regression.log。Black/flake8及实现isort通过；
测试整文件isort仅有原第141行继承的多行导入折叠差异，原样保留，新增片段按项目分类通过。
model-graph-full-rope-fixed-20261024保持同一FULL/mode3/custom_ops all/原生统计配置，
config SHA256 73d02fd9b82dc3c898d87b3905fe0508f563e795c0adfa49ab2afb3c5f10a6c5，
API836660、PGID836660、start_ticks1108574392，继续首档验证；尚未下降任何档位。

## FULL第二轮：Torch 2.10编译产物接口变化

第二轮已越过RoPE追踪，在真实Inductor编译完成后失败于MetaX旧补丁返回
`CompiledArtifact(compiled_fn, artifacts)`；安装Torch2.10已将此类改为抽象基类，
其原生standalone_compile返回具体`CacheCompiledArtifact`。未到graph捕获，不下降档位。
原始失败保留在model-graph-full-rope-fixed-20261024/server.log，8卡已释放。

改前限定仅Plugin `dispatch/backends/vendor/metax/patches/fix_standalone_compile.py`
的编译产物类型选择/构造，以及新增专用回归测试。现有嵌套FX输出、autograd key和TF32
补丁保持；不复制Torch缓存序列化算法，不修改Torch/vLLM。新Torch复用原生具体类，
旧版没有此类时保留原CompiledArtifact构造，以覆盖补丁原先支持的版本。
原文件SHA256：e3f5f15b365079177c2a0eb73f1369c6f6752f5c10b95bebb35231434aa7e5cf。
先保留真实抽象类构造失败负对照，再测试实际CPU/MetaX编译数值、binary/unpacked保存
与原生加载，并用独立进程恢复binary缓存；最后重试整模型FULL。

已完成最小修复：新增原生具体类兼容导入8行，替换1行构造；保留旧类导入及返回类型。
新增compilation/test_metax_standalone_compile.py覆盖CPU/MetaX、binary/unpacked四组合，
两种设备均通过独立进程binary恢复并验证变输入数值。4 passed in316.38s，无skip；
04-runs/metax-compiled-artifact/pytest-module-import.log保留，before.json记录原抽象类失败。
首轮测试的from-import触发原模块级__getattr__签名问题，未到计算；改用与生产相同的
importlib模块加载，不扩大产品修复。旧版MetaX Torch兼容分支未在旧硬件/软件实际运行。
新测试Black(79)、isort、flake8通过；旧补丁仅审增量，不全文件格式化。

第三轮model-graph-full-artifact-fixed-20261024已启动，API/PGID874761、
start_ticks1108703795，config SHA256 d1fc9d5fc1a18e00312cc914b8dde2ddd65944620a15e575b24c74dc18fe5963。
当前源码身份e7d9ed6304e3db3cbc90daf467a7ef5e876242508ab936372dc14f8aa02cb6d8，
完整Plugin补丁4f69da23060ca225c61753b7c4c9bb5526e632a5ea3facd0d629eca270cb777e；
vLLM及FlagGems完整diff均保持初始哈希。继续验证FULL，尚无整模型graph通过结论。

第三轮在Inductor阶段设备trap randn_kernel，详见004追加诊断。尚未图捕获，未降档。
CPU小规模及GPU真实MoE量级独立随机输入均未复现，不以猜测添加randn排除。
下一轮仍FULL，仅增加同步错误定位和原生Inductor图日志，诊断设置不进入最终launcher。

同步诊断实例已启动：API/PGID904107、start_ticks1108779530，config SHA256
531405e9b8a007e86f8e572c5209c89a02e50bd8ffcb1bbb4d60ce054ee4a6b5。
启动保护先拒绝被失败实例残留API占用的8000；按旧owner核验后SIGTERM，15秒后仅对
仍存活的本任务API/资源跟踪进程SIGKILL，完整生命周期保留在第三轮stop-after-compile-failure.json。
确认/proc/net/tcp与tcp6无8000监听后启动，未改变保护逻辑，未触及其他服务。

原生Inductor日志留下最后单kernel12与组合kernel13及各自get_args实际形状，
在独立进程逐一get_args、同步、直接调用三次均无fault；这仅排除该独立条件的设备异常，
不代表数学对照或CUDA graph重放通过。见04-runs/randn-cpu-compile/generated-kernel-{12,13}.json/log。
未修改dump源码或产品，不把这两个负结果描述成原整模故障的成功复现。
已从现场libmcruntime.so确认开关MACA_LAUNCH_BLOCKING；CUDA_LAUNCH_BLOCKING那轮仍异步
未提供准确kernel调用栈。下一轮保持FULL，改用MACA原生同步开关定位，保留原生Inductor日志。

MACA原生同步轮model-graph-full-maca-sync-20261024仍在组合kernel13的编译期基准附近
触发相同randn_kernel设备trap；随机输入小例和脱离编译的单独kernel运行均正常，尚未确定
底层根因。run配置20e14fdcf9ed48f32df4452cd89de44e865f254b74038ddc4c92c2eae9b2336a，
API/PGID907724、start_ticks1108827291；保留原生日志及dump。

下一项单变量处置：通过原生inductor_compile_config将benchmark_combo_kernel设false，
保持combo_kernels=true、实际模型kernel、FULL及其余参数不变。现场Torch调度器6327行
确认此项只绕过编译期组合方案测速，组合代码仍可生成；不改Torch源码、不禁用全部编译或
模型算子，不加入未证实的randn黑名单。若能启动仍需真实数值、前缀状态、重放与后续性能
验证，不能把绕过候选benchmark称作底层randn缺陷已修复；该设置的性能影响尚未验收。

关闭组合测速轮model-graph-full-no-combo-bench-20261024仍失败于后续randn_kernel trap，
故benchmark_combo_kernel=false不是充分修复，后续配置撤销此项，不保留试验设置到交付。
config172716be1e53c460293309d8217817a36f801704350ea23ec51895efa6dbe027，
API/PGID911151、start_ticks1108863672。仍未降档。

现场preserve_rng_state在yield之后finally恢复设备RNG；当原编译体失败且设备context已坏，
恢复又抛异常，会掩盖需要定位的首次异常。新增仅过程目录02-issues/first_exception_diagnostics.py，
通过原生--worker-extension-cls导入，包装此上下文，在原生finally前记录异常及严格限定的
尺寸/设备元数据后原样raise。保留原上下文全部行为，不修改Torch/vLLM或模型数值，不记录
Tensor内容/权重，不使用PYTHONPATH。先用故意ValueError验证异常传播与CPU/GPU RNG恢复。
后续FULL恢复默认benchmark设置，删除大范围TORCH_LOGS，仅保留MACA同步和此临时扩展；
诊断结束后移除扩展开关，过程脚本不作为产品或最终launcher依赖。

model-graph-full-first-exception-20261024（API/PGID929882、start_ticks1108907373，
config9e500b2a493d05e1bb5cc98630087f0edb95878f2b14bc04fde93a7945a38666）
实际捕获8个rank首次异常，确认Gems randn编译期调用链；见004。元数据遍历仅检查顶层
traceback，未覆盖内部cause/context，故没有提取故障尺寸；完整异常链仍保留，不伪造形状。
后续优先通过已存在的算子排除配置做单变量整模对照，不把过程诊断脚本留在正常启动参数中。

model-graph-full-native-normal-20261024（API/PGID933219、start_ticks1108964470，
config a64d095dc7a370a56e618bcb44285a2590e81c58dbf87e76288f0857d39a0bc2）
仍失败，首trap变为编译器生成的triton_，随机入口排除不是充分修复，尚不能宣称已完成根因
处置。下一轮继续FULL，过程诊断遍历cause/context链提取实际size/stride/device，并保存
wrapper的原生tuning_code；仅metadata/代码，不保存Tensor值或权重，便于脱离335GB模型
独立复现。临时诊断module SHA绑定运行配置，正常启动仍须移除此依赖。

## 首次异常缩小：RoPE partial-view functionalization越界

native-normal-trace轮的原生autotune代码已保存至02-issues/native-normal-first-exception/
964680-autotune.py（其它rank同目录）。准确故障为triton_poi_fused_as_strided_clone_8。
生成的buf37仅按(6400,1,64)/(64,64,1)分配409600元素，却按原view跨度
256*6400-192=1638208元素clone；Q侧同类buf35仅1228800元素却计划4915008元素。
图节点明确来自本任务新增可变flaggems_vllm_rotary_embedding_的functionalization。
此前仅外部输入view的12项graph测试没有覆盖图内producer布局优化，不能外推此组合安全。
原随机kernel异常可能受同一缓冲越界上下文影响，尚不将其单独归为底层随机算法根因。

改前重新限定仍为Plugin impl/rotary.py及既有test_rotary_embedding.py：编译时统一调用
既有out-of-place opaque op，再用可追踪copy_回写原query/key以表达inplace/alias契约；
eager与FGV关闭路径保持。删除本任务自加、仅此入口调用的mutable私有op/fake，避免保留
失效试验实现。原CPU契约断言改为验证内部out-of-place调用，保留外部别名、突变和数值
断言；原上游测试字节前缀不改。追加图内producer→D256部分64视图→RoPE→后续消费者
回归，dynamic/Inductor compile-time autotune、三dtype、两次变输入CG重放。先独立进程
复现旧边界，再改动；不得删测试或放宽既有断言。修复后复核是否可撤销randn/normal_试验排除。

本次修复前文件哈希：impl/rotary.py 2154d1b968709ec29f00e15a903c3bb74ee28a90843cf9bcedbba74f9b8bc43d；
test_rotary_embedding.py fc045fa8ed3cee5f4f815ee31160eb11b54f86dcd7ccc022807a02d43030c119。
私有mutable op在全部安装源码Python文件中只由此backend调用，测试只有一个disabled-route
守卫引用；其删除不触及上游公开接口。新的out-of-place+copy边界保持公共inplace契约，
不再要求编译器对稀疏partial view按原存储跨度做opaque mutation functionalization。

修复后独立复现04-runs/rope-produced-partial-view/after.json通过。新增测试首轮仅因capture
调用漏传positions导致6项TypeError，未进入目标计算；修正调用后完整38项通过（26.67s，
无skip），见pytest-corrected.log。覆盖三dtype、inplace两侧、图内producer及两次变输入
重放；原上游测试前缀哈希保持0a52099aac7445679f2d08428e61e644262055253dc6089474cad5c04303b3e5。
下一轮整模使用clone单项排除，撤销尚未证实必要的randn/normal_试验设置；无诊断extension、
同步/图dump或benchmark开关。更换VLLM/Inductor缓存子命名空间绑定新完整Plugin补丁，
保留旧缓存，避免复用已删除mutable schema的旧图；eager与graph共享新命名空间。

当前共享回归216 passed in28.15s。源码快照01-environment/installed-identity-after-rope-functional.json
SHA25685fbbd4dc82526a5c8fb13c34d71315a151463abf49c6792192e289d14fba5c9；完整Plugin补丁
473aa021d1661c7dc74c06d9240fe2c9c24c62daf1b6f7e14ff5f79e523ae0af。已逐块重审RoPE两个
文件：只新增边界/compile分支和必要测试，不改原测试，不引入模型/主机分支，FGV关闭路径
守卫仍通过；无mutable残留。vLLM/FlagGems原完整diff保持初始值。eager新实例
model-eager-rope-functional-20261024（API/PGID1001068，start_ticks1111633404，config
c3232585b07fb4b7262de450927378bd7a4b90560523e856dbe1d2da8803409f）正在建立同源码基线。

新源码eager基线完整通过：04-runs/model-eager-rope-functional-20261024/ 下
smoke.json三问2/56/5；prefix-state.json五例56/56/5/56/56，实际cache hit增量
0/6400/6400/0/6400；mixed-state.json观察到流式1至30与7×8新请求实际重叠且均正确。
validation-progress.json passed；此结果与旧after-mamba参考分别保留，不替换历史身份。
本轮graph参考改为该新eager实例，比较工具02-issues/compare-eager-graph-current.py显式
接受reference-run/source-snapshot，逐例核对除cache_salt外相同输入、生成token/content、
有限logprob及预先沿用的绝对差阈值0.02；正式数据集精度不在此比较范围。

当前FULL实例model-graph-full-rope-functional-20261024：API/PGID1036213，start_ticks
1111676447，配置SHA256c0943c296a469ac38349cf883541a9af34b9e55bfeb21569f0ff8ef4baa1a932。
原eager按owner核验后停止，stop-before-full-graph.json保留；容器未停止。实际引擎配置
确认mode3、custom_ops all、默认combo benchmark开启、capture sizes1..64、包含PLE/QSA
的splitting_ops，无临时诊断扩展/同步开关；仍需等待实际解析和捕获，不把请求FULL当通过。

新源码clone-only FULL仍在编译期报randn_kernel trap，尚无graph捕获；保留原生server.log
和validation-progress.json失败，不将局部38/216测试外推整模通过。API leader已自行退出，
stop工具在leader缺失时拒绝发信号；核验原PGID无存活成员后保存exit-observation.json，
未重试kill、未停止容器。正在用相同Gems全局注册条件补充独立RoPE复现。
下一次诊断允许暂时恢复clone,randn,normal_排除并用既有first_exception扩展与MACA同步，
以区分尚存随机入口问题与实际model kernel越界；这是诊断配置，最终必须去除诊断扩展，
且额外排除是否必要仍待实验证据，不把此前未解决旧RoPE的尝试称为充分修复。

## FULL能力限制与下一档验证（2026-10-24）

生产注册独立RoPE复现production-dispatch.json通过。新诊断轮
model-graph-full-rope-functional-trace-20261024保持当前产品源码，临时恢复随机原生入口，
并使用既有只记录异常的worker extension与MACA同步；编译及initial profiling/warmup已通过。
10:15:01八个rank原生解析均明确：GDNAttentionBackend只支持AttentionCGSupport.UNIFORM_BATCH，
FULL不支持混合batch，自动转为FULL_AND_PIECEWISE。这是后端能力限制，不能通过将声明
伪改ALWAYS解决；保留真实GDN/PLE/QSA算子及默认调度/attention splitting，不替换后端或
为名称FULL改数值实现。本轮因此不构成FULL通过，原始配置和warning完整保留。

按顺序下一档为显式FULL_AND_PIECEWISE：保持TP8/BF16/50000/6400/prefix-align，先移除
临时extension、MACA同步，保留clone,randn,normal_作为待独立无诊断整模验证的进程级workaround。
该项不改FlagGems库默认值；若最终正常启动通过，才绑定其graph配置与eager数值比较。
仍需验证prefill piecewise、decode full实际捕获及多次变输入运行；不得仅凭自动调整标记通过。

诊断轮11个mixed PIECEWISE与7个decode FULL尺寸全部捕获，三类实际请求通过。
与同源码新eager逐例比较10例、105输出token全部相同、有限logprob最大差
0.008857404813170433，小于预先冻结0.02；eager-comparison.json保留原生输入/结果文件哈希。
诊断FULL配置已被原生调整，不能记作纯FULL通过。随后按owner停止诊断服务，停止记录passed；
端口保护在TIME_WAIT自然释放前拒绝启动，未改保护或kill其他服务。确认无监听/新owner后
启动显式无诊断FULL_AND_PIECEWISE，config SHA256
cbd4a0281a1cffb848946dd882b3a0625b1f5d4aad8ef8c8d375c49127fab76a。
当前源码与新增文件集合在切换前再次完整核对无变化。

## 本轮修复后的最终复验结论

显式FULL_AND_PIECEWISE、无临时同步/extension/TORCH_LOGS的实例
model-graph-mixed-rope-functional-20261024通过。API/PGID1264796，
start_ticks1111786964；配置cbd4a0281a1cffb848946dd882b3a0625b1f5d4aad8ef8c8d375c49127fab76a。
整模torch.compile 55.93s，mixed 11/11与decode 7/7捕获完成，无自动模式调整。
就绪后的原生运行窗口累计记录FULL101、PIECEWISE5、NONE11；mixed请求对应27→32
及34→40等真实piecewise运行，双请求decode也实际进入FULL，不以warmup代替重放。
大块prefill超过64捕获上限走编译NONE路径，未宣称8730-token全prefill均在CUDA graph内。

同源码eager参考与当前graph三类验证均通过。10例、105输出token逐项相同，全部logprob
有限，最大绝对差0.0051912786439061165＜预设0.02。8730-token五例三次各命中6400，
混合流式1至30与新7×8请求观察到实际重叠且正确。数值按此范围和容差一致，不是逐位一致，
也不代替正式数据集精度或吞吐测试。对照文件eager-comparison.json含全部输入/输出文件SHA；
最后原始日志冻结为server-verification-snapshot.log，避免运行中server.log后续增长改变绑定。

verification-summary.json SHA256
84cb515c65ecf52bc7011ac906d663097648e98dfe3f19389b46d587a9289d89，
位于04-runs/model-graph-mixed-rope-functional-20261024/，包含当前源码完整diff/新增文件
集合复核、PID/start_ticks/cmdline、健康检查、实际图统计及证据SHA。容器和当前graph服务
保持运行，未提交代码。汇总工具初次断言使用了本版本没有的通用“Graph capturing
finished”文字，核对后改为本版本实际两类100%完成行及真实重放统计，未放宽数值或图执行要求。

当前环境身份8993aab5...7b4d26已通过新的原生environment gate：
04-runs/environment-mx101-rope-functional-20261024/framework-check.json，
SHA256c62918d450e0d7eebfa49c19570f383497c04e7c01e5de0808e3cef200e183cd；
native-gate.log原生返回record-verification passed。控制快照只含13个必需控制/记录文件，
tar SHA256aa0820ff2e52ef800191b3d5e34a00713019b9929eb24652f6b8bf1535e663e3。

graph进程继续保留clone,randn,normal_原生入口workaround，eager参考为clone单项排除。
额外随机排除不修改模型的权重/输入/采样配置，也不修改库默认值，但不能宣称随机底层缺陷
根因已修复或无性能影响；未作正式性能测量。移除条件为新软件/修复后在全新编译缓存中，
clone-only完成相同整模编译、图捕获和数值/状态回归。原失败和负对照全部保留。
本轮用户要求的RoPE修复与整模graph/eager对照已完成；正式验收、最终launcher与镜像交付
属于仍未完成的整体适配事项，不以本轮bring-up结果标记optimized或完整验收。
