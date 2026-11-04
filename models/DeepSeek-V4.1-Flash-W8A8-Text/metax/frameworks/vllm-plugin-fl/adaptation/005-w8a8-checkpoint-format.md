# 005：动态W8A8权重格式接入

2026-11-04性能诊断补充：103受控原生kernel模式中scaled_mm的M1/8/128、K5120/N1792及
M1/8、K6144/N25600低于0.9门槛，最小speedup=0.2737。
`04-runs/mx-103/components-controlled-benchmark-v13-20261104/{kernel.json,failure.json}`保留；
控制器在该模式门槛结束，未形成整个测量通过，cudagraph尚未执行。
后续先用公开API的显式tile参数诊断，不增加数值实现或放宽门槛。

公开参数受控诊断已完成，25组均通过披露的抽样CPU INT64→BF16对照，
连续资源观察及前后源码/环境一致；仅为选型诊断，不代替完整数值或原生性能验收。
`04-runs/mx-103/w8a8-tiles-diagnostic-v1-20261104/`保存源、命令、tiles和资源观察。
窄N1792的M1/8用(16,32,256)从约1.8ms降至0.061/0.062ms；M128用(32,64,128)
从约1.51ms降至0.108ms；宽N25600的M1/8用(32,64,128)约0.39ms，原约10.5ms。
据此下一批编辑限新增MetaX `ops/triton_scaled_mm.py`薄wrapper、厂商ops导出及现有同名测试。
wrapper仅通过现有公开tile参数选择已测区域，调用原公开通用API，不复制或修改kernel；
未覆盖区域、FP8/BF16输入、显式use_heuristic=False和不对齐输入保留原路径。
新路径先限定INT8且K/N为32倍数、M<=128、K/N>=1024；窄N的M<=8用第一tile，
其他窄N及宽N的M<=8用第二tile，宽N的M>8维持原路径。
验证实际根API厂商命中、原数值/graph和显式参数、metadata边界，以及完整CPU整数参考；
再以原生Benchmark验证性能。无需改Plugin或NVIDIA实现。

102三文件厂商选择切片已通过188项（含新增14项metadata、6项完整CPU整数参考及1项graph），
保留48项原vLLM原生对照未运行，未删除原测试。日志
`04-runs/mx-102/w8a8-metax-tiles-operators-v1-20261104.log`。
新路径在根公开API实际绑定到MetaX wrapper，调用原通用kernel；通用文件未修改。
Plugin实际Linear/Engram调用方回归命令已完成成功，最终计数待读取。
完整项目hooks、103独立复测和正式性能复测仍待完成；抽样tile诊断不代替这些门槛。

上述Plugin实际调用方最终50 passed，覆盖真实W8A8加载、Linear及Engram WKV和graph；
FGV v16/v17完整适用hooks通过，所有新变更逐hunk审阅。103九文件联合切片复测正在执行。

103独立复测已完成，188项算子及联合Plugin102项功能检查通过。v17受控复测两个模式都完成，
原0.9门槛保留：scaled_mm最小speedup kernel=1.2743、cudagraph=1.2721；
动态量化最小分别2.3383、1.9926，原7个MM/10个量化形状均达标。
证据`04-runs/mx-103/components-controlled-benchmark-v17-20261104/`；前后源码/环境一致，44次资源观察。
该联合run整体仍为gate_failed，因为另一个MoE小控制形状kernel模式未达标；
不得把各已达标组件结论改写为整套组件或整模型性能通过。

状态：修改前计划，2026-11-03。目标配置的 `quant_method=w8a8_int8`、`is_dynamic=true`，
权重INT8 per-channel、scale为FP32 `[out,1]`，activation为per-token动态对称INT8。
当前102实际 `get_quantization_config("w8a8_int8")` 报ValueError，原方法不在支持列表；
不能把带offset参数的ModelSlim格式直接套用到本权重。

## 已核对扩展点

当前Plugin `register_quant_linear` 安装已有FL W8A8 Linear和MoE selector；
本切片复用上游公开 `CompressedTensorsW8A8Int8`、`CompressedTensorsLinearMethod`、
`CompressedTensorsW8A8Int8MoEMethod` 及已存在的FL后端，不增加数值kernel。
动态输入的input_scale/zero-point应为None；不生成ModelSlim weight_offset。

上游 `initialize_model` 在构造模型前调用 `configure_quant_config`，先应用模型的unstacked
`hf_to_vllm_mapper`，再传入packed_modules_mapping。因此ignore名单的HF命名与实际native模块命名
应通过模型公开mapper对齐，无需在量化配置中硬编码DeepSeek路径改写。
复用 `is_layer_skipped` 的exact模式及fused shard一致性检查。
wo_a INT8→BF16及Engram INT8表加载属于后续模型加载器切片，不在此处伪装成一般Linear。

## 变更前边界

只修改实际安装的Plugin，保留现有四行V4.1配置注册和镜像继承修改；不改vLLM、FG或FGV。

| 文件/符号 | 必要变化 | 验证 |
|---|---|---|
| `quantization/w8a8_int8.py:DynamicW8A8Int8Config`、注册函数 | 注册独立FL alias，仅识别该动态格式，复用现有对称W8A8标准schemes；映射ignore，拒绝不支持的混合/静态格式 | 输入不变、标准量化参数、mapper/fused规则、已有native注册保留、重复注册 |
| `vllm_fl/__init__.py:register_model` | 在现有ARM早返回之后注册metadata，保留既有GPU quant kernel安装顺序 | fresh general-plugin入口；ARM和GDN原回归 |
| `tests/unit_tests/quantization/test_w8a8_int8.py` | 新增配置、公开mapper/packed层选择、异常及注册守卫单测 | 不用mock宣称数值正确；ModelSlim原单测回归 |
| `tests/functional_tests/ops/test_dynamic_w8a8_checkpoint.py` | 沿用实际仓库functional/ops目录，真实小Linear加载INT8+FP32 scale并走现有FL后端；独立动态量化参考及新输入graph replay | 实际kernel命中、eager/graph、通道scale与舍入；仅声称实测dtype/shape |

声明范围为对称8-bit、per-channel权重、per-token动态activation；目标实际BF16路径优先验证，
不支持静态、zero-point或逐expert混合精度时在分配/计算前明确失败。
新的metadata模块不在导入/注册时加载数值kernel或分配GPU张量；实际method选择时才导入标准层。
不覆盖已有同名native实现，不改变其他HF quant_method；显式冲突的用户quant选择仍由上游拒绝。
适用 `plugin:A2/A3/A4/B1/B3/B4/C1/C2/D3/E1/F1/F2/F3/F4/F7`。
此切片通过不代表完整权重映射、MoE整层、Engram或模型推理已通过。

源码核对发现新的直接依赖风险：当前FG公开 `scaled_mm` 对齐ATen `_scaled_mm`，仅接收FP8；
既有Plugin W8A8 Linear仍把INT8传给它。FGV公开 `triton_scaled_mm` 则接收INT8、FP32 token/channel scale，
与该Linear所需布局相容。先通过实际格式测试/最小复现确认失败，再限定必要接线修复；
不为INT8扩展ATen FP8语义，也不把新数值计算放入Plugin。FGV既有API的bias为输出dtype转换后相加，
该细节及空batch、实际分发、异常不重试需在接入前明确，不能仅因接口名称相近便替换。

102新增格式12项和原配置/ARM/GDN 20项共32项单测实际通过，
日志 `04-runs/mx-102/w8a8-format-unit-v1-20261104.log`；新3文件按固定Ruff0.14检查和格式化。
首次functional入口收集到8项，但因镜像未装pytest-xdist、既有conftest无条件声明其专用
`pytest_configure_node` hook而发生PluginValidationError，实际没有测试运行。
必要范围增加 `tests/functional_tests/conftest.py:pytest_configure_node` 一行
`@pytest.hookimpl(optionalhook=True)`，保持有xdist时的原分卡行为，允许原本支持的串行pytest入口。
保留原文件和失败日志；用同一真实functional入口重新验证，未安装/修改pytest或其他第三方库。

第二轮实际选中 `FLW8A8DynamicLinearKernel`，通过真实权重创建/加载、动态量化后，在FG公开
`scaled_mm` 明确报 `mat1 and mat2 must be Float8 matrices`。日志为
`04-runs/mx-102/w8a8-functional-v2-20261104.log`；既有FG ATen接口行为正确，问题属于Plugin接线。

修复范围增加4个Plugin文件：`quantization/w8a8/linear.py` 将动态量化及scaled-mm通过
`resolve_op` 先选实现再执行，计算异常直接传播；`dispatch/backends/flaggems/register_ops.py` 按既有
W8A8 MoE注册方式增加 `w8a8_scaled_mm`；新增 `impl/w8a8_linear.py` 为FGV公开
`triton_scaled_mm` 提供仅校验/布局及空输出分配的薄适配；原 `test_w8a8_linear.py`
保留数值/布局断言，将旧mock接线改为真实新分发点，并补参数转发、能力缺失与异常不重试检查。
不改全局dispatch重试机制、不新增参考后端、不修改FG/FGV数值kernel。

新op契约为A[M,K]/B[K,N] INT8、FP32 scale_a[M,1]/scale_b[N]，同设备连续存储，
K/N正数，M可为0；out为BF16/FP16/FP32全新[M,N]，不修改/alias输入。
bias可选、连续[N]且dtype等于输出；遵循所复用的FGV及上游Triton scaled-mm顺序，
先将缩放累加转为输出dtype，再加bias。目标模型Linear无bias；额外biased用例需据此独立核对，
不能把ATen FP8的中间精度约定直接套到此vLLM INT8融合算子。
以实际功能用例覆盖两个activation dtype、通道scale、ties-even、零行与graph新输入，
性能仍不在共享资源受干扰时宣称通过。已有动态量化可选fallback保留在原体系，
本Linear明确只执行resolve选定的实现，量化或matmul发射后的错误不切换重试。

桥接修复后相邻量化单测51 passed、2 skipped（原Ascend硬件限定项），原断言保留。
真实functional v3为7 passed、1 failed：失败是 `[M,K,N]=[8,5120,1792]` BF16。
同seed=812的分项复现表明：GPU INT8量化与CPU FP32逆尺度乘法、FP64比值参考均0个差异；
与测试原先“先舍入scale再除”相比有4个差异。例如x=2.3125、absmax=4.625，原参考得到
63.499996→63，原生顺序和FP64得到63.5→64。用实际INT8及scale独立做CPU整数乘积，
最终BF16输出逐元素相同，scale误差也为0。分项报告在
`07-bugs/w8a8-bf16-rounding-20261104/diagnosis-v1.json`，复现器SHA-256
`4eb85e31009e9208e7761095de18e1aa973529d7285accdac4993a53ae09239b`。

固定只读vLLM revision的 `csrc/libtorch_stable/quantization/w8a8/int8/scaled_quant.cu:171`
明确为 `inv_s=127.f/absmax`，然后FP32输入乘inv_s再round-to-nearest-even；该文件SHA-256
`e6fc36b6ddc925e40e0a7a84543dd29da456c19672e0daf28f8287d2e3645243`。
因此仅修正新增独立CPU参考的浮点顺序，不改数值kernel、不放宽任何阈值。
补实际半整数回归、BF16/FP16两个shape的graph新输入、FP32输出、bias、非零storage offset、
K/N tail和空batch，并观察实际注册的FGV公开API命中；旧失败测试源码及日志保留。

扩展v4为17 passed、8 failed。6项K=70/N=35的真实公开FGV matmul均报MetaX私有内存
9KB/thread超过现场4KB/thread；不采纳错误信息中修改驱动模块参数的建议。
FP16大形状另有1个量化INT8与CPU FP32源码顺序不同（2.03515625/4.0703125的半比值），
造成14个最终输出超过原阈值；当前Triton `/` 是近似除法，源代码写法相同不证明运算精度相同。
该GPU结果恰为数学FP64的64，而CPU规定FP32逆尺度乘法为63；后续修复明确固定FP32点运算，
不声称已在NVIDIA硬件证明逐bit等同。FGV原量化测试允许INT8误差1，新增精确用例会更严格。
还有1项新增halfway用例的手写expected漏乘activation scale，属于测试错误，须依完整量化公式修正，
不改既有严格相等断言。直接公开API复现与原hash保存在
`07-bugs/w8a8-public-contract-20261104/{reproduce.py,before.json}`。

必要数值修复转入实际FGV安装树，revision仍为f108ba8，保留前8文件mHC修改：

| 文件/符号 | 限定变化 | 验证 |
|---|---|---|
| `ops/scaled_int8_quant.py` 三个dynamic symmetric kernel | 用显式FP32 round-to-nearest除法形成scale及inverse，保留zero行、nearest-even和原调优配置；不动static/asymmetric分支 | 直接公开API、CPU独立FP32点参考、三个归约形状族、dtype及graph新输入；原回归 |
| `ops/triton_scaled_mm.py` wrapper及两处masked load | 非32对齐K在发射前选小tile；明确masked乘积补0；修正既有manual配置时未初始化tile_shape，使原参数可用；保留对齐K默认路径和bias顺序 | 原公开失败、INT64 CPU独立参考、tail/storage offset/bias/scalar与vector scale、手动32tile及graph；原回归 |
| `tests/test_w8a8_boundaries.py` | 独立公开API数值/输入不变/graph回归；不以Plugin或mock证明数学 | 实际MetaX；NVIDIA未验证需披露 |
| `benchmark/test_w8a8_boundaries.py` | 固定目标5120与边界case的独立组合baseline，kernel和cudagraph，使用原Benchmark入口 | 资源稳定后原生测量，当前不得宣称性能准入通过 |

同时仅修正Plugin新增halfway测试的完整缩放expected。适用算子标准A1–A3、B1–B3/B5、
C1–C3、D1–D6、E1–E7、F1–F6中的本切片要求；无新增第三方依赖、workspace或持久缓存。
新kernel未引入；原libentry/autotune和后端配置保留。源码归属、公开API、独立测试与性能门槛仍逐项审阅，
未测或失败项不能用于整个适配/PR就绪结论。

首轮算子回归v1为50 failed、27 passed：小K tail及手动32tile已通过；大K非零storage offset
还会请求7KB/thread。18项量化及6项量化graph实际未计算，因为根命名空间已被MetaX替换为
`runtime/backend/_metax/ops/scaled_int8_quant.py`，其4个参数原本均无默认值。
这与Plugin原先直接导入通用public模块的路径不同，必须分别识别，不能把两者混作同一实现。

修复收敛调整：撤回未验证且现在不再需要的通用量化文件修改，保留失败快照；将精确FP32除法
限定到实际MetaX公开入口的两个dynamic symmetric分支，并对齐公开默认参数及空batch返回。
新增对该入口的空batch用例，不改static/asymmetric数学或原block选择。
Plugin `dispatch/backends/flaggems/impl/quantization.py` 仅把导入改为根公开API，继续显式传
scale=None/azp=None/symmetric=True，让库选择真实MetaX实现；原fallback及其他平台代码保留。
这也使新root API测试与实际Plugin路径一致。厂商源改前SHA-256为
`9e490b9949a0f4e9386cc3f94ec103c905cd7b7145e48fa6b8cdf610eef49051`。
scaled-mm的小tile条件另覆盖operand byte storage offset非16对齐的已复现情况；
不修改对齐输入的大K默认路径。下一轮仍运行原77项，并增加空batch，不删除失败参数组合。

v2实测53项矩阵乘/graph通过；26项量化被本次rows并行赋值中使用未初始化变量的错误挡住。
该错误已拆为两条顺序赋值。v3量化10 passed、16 failed，其中又定位到独立参考的第二处精度问题：
PyTorch `Tensor.__rtruediv__` 实现为 `self.reciprocal()*other`，所以Python写法 `127 / maximum`
并非C++源码中的单次除法。对于maximum=4.0703125，前者inverse bits为1106877630，
显式 `torch.div(127.0, maximum)` 为1106877631；半幅乘积分别为63.499996、63.5。
因此先前诊断JSON中的 `native_fp32_order` 字段实际上是当时错误参考，不能作为原生数值差异证据。

当前修正仅将新增CPU/benchmark参考改为显式torch.div，并撤回MetaX两个kernel的div_rn尝试，
以原始数值数学重新运行严格断言。保留公开默认参数、空batch初始化及Plugin根入口接线；
不以不必要的数值改动去迁就参考错误。上述各失败日志和源快照均保留。

v4在原始量化kernel数学下26项全部通过；连同v2的53项矩阵乘及graph，79个不同公开API用例已覆盖。
未保留通用或MetaX量化kernel精度改动。新保留改动仅为MetaX公开默认参数/空batch/日志，
以及scaled-mm的边界tile、masked零填充、manual参数与日志。
直接数值与graph通过仍不代表受控性能或整模适配通过。
下一步对Plugin根API导入调整同步原 `tests/unit_tests/dispatch/test_flaggems_quantization.py`
mock目标，保留原参数/失败传播/注册及fallback断言；补真实空Linear和双公开API命中观察，复测原整套。

Plugin v5最终56 passed、2 skipped（原Ascend限定项），真实27项eager/graph/空Linear通过。
原FGV量化quick与原matmul独立reference回归57 passed；vLLM对照组因旧import路径不适用，
本轮按明确选择排除48项，不将其计为通过。v5精确切片已冻结：11个Plugin文件、4个FGV文件，
manifest SHA-256 `d8d5749a28767ab53adae37dfcf218eeed901def1fb60f5d834c7340e134b215`。

交付前再收窄FGV小tile选择：只对实际 `runtime.device.vendor_name=metax` 生效，
保留其他后端的原启发式参数，避免把C550资源修复推广成未经测量的NVIDIA调优。
新增6项参数选择单测只证明分支元数据，不声称其他厂商硬件数值通过；复测当前完整85项公开API。
此修改不改变数值kernel或MetaX选择结果，v5归档作为历史保留，后续冻结新版本。

当前v6完整算子85项在102通过；冻结manifest SHA-256
`74d779d6953b805a76364f39c843fbef9eb3464a39a3a7d21f44d36782ef70af`，FGV归档SHA-256
`1b63657ae04441ebe93f66bb3e02af46908e3d8e7567bb91bce90cb11703a2cd`。
103已按原文件hash/HEAD和归档hash校验同步15文件，独立复测85项算子、76项Plugin单测（另2项原Ascend限定skip）
和27项真实量化加载/graph均通过。日志位于`04-runs/mx-103/w8a8-*-v6-20261104.log`。
当前没有量化kernel数学改动；受控性能、完整权重加载与整模验收仍未完成。
Engram实际wkv为N=25600/K=6144，后续还需覆盖该宽N真实路径，不能从较小Linear样例推断通过。

v7扩展实际Engram WKV 6144→25600和q_b 1280→4096，修正M=1原先仅有全零输入的覆盖不足；
非零输入原路径及q_b通过。WKV eager/graph BF16/FP16共4项失败、其余29项通过，
明确为默认wide-N tile `(64,128,256)`请求98304字节shared memory，C550上限65536。
不是精度失败，也不通过改驱动/第三方编译器处理。下一步仅在FGV既有MetaX启发式中，
把small-M/wide-N选成已支持small-N的`(64,64,256)`，保留其余厂商/shape路径；
补边界分支测试并重跑原公开API、实际33项Plugin用例，benchmark补充该真实WKV形状。
日志`04-runs/mx-102/w8a8-functional-wide-v7-20261104.log`保留，不以v6小形状通过替代此门槛。

上述MetaX wide-N tile修正后，102实际33项加载/graph通过，W8A8与Engram合计192项通过；
103 v9独立复测221项FGV（含原mHC29项）、85项Plugin单测（另2 skip）、62项W8A8/V2功能检查通过。
适用项目静态hooks在精确源码快照通过；曾由临时isort未用black profile产生的导出文件排版已恢复，
最终导出diff只增加三项Engram接口，不保留无关格式改动。
这仍未覆盖完整MoE clamp、整模权重加载、受控性能或正式验收。
