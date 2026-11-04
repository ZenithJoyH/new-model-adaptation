# 007：最终mHC收拢公开接口

状态：2026-11-04修改前设计。目标FGV安装树`/opt/FlagGems-vllm`，HEAD f108ba81；
Plugin与vLLM暂不修改。主线V4.1最后一层FFN后的四路残差，须按最后的FP32 pre-mix收拢成BF16，
再执行最终RMSNorm。FGV已有延迟mHC数值kernel，但没有可供Plugin消费的独立公开collapse API。

按plugin:A4/operator:A4复用`ops/mhc_pre_delayed.py:_collapse_kernel`，仅补公开
`mhc_collapse(residual,pre_mix=None)` wrapper；不复制kernel，不增加tuning key或修改数学。
输入BF16 `[N,4,H]`、可选FP32 `[N,4]`，同GPU、连续、H>0，支持N=0及非零storage offset。
无pre-mix时系数为(1,0,0,0)，保留原kernel的IEEE乘加语义；四项按既有FP32顺序累加，
只在最终写出时转BF16。输出全新`[N,H]`，输入不变，不持有跨调用状态。

修改文件限既有`ops/mhc_pre_delayed.py`、`ops/__init__.py`、`conf/operators.yaml`、
`benchmark/test_mhc_pre_delayed.py`，新增`tests/test_mhc_collapse.py`。
复用既有`mhc_pre_delayed_collapse` tuning配置及libentry/libtuner；
用独立CPU顺序FP32参考覆盖dtype/shape/offset/空N、None/显式系数、非有限值和拒绝路径，
实际graph更新残差/系数并填输出sentinel。回归原延迟mHC与Engram/W8A8受影响公开入口。
基准沿用原Benchmark，比较同设备的独立FP32 ATen组合；不是原生厂商kernel对照。
受资源竞争影响的性能保持未通过；公开封装通过不等价于模型mHC链或整模通过。

首轮2 failed、257 passed：显式pre-mix、H=5120时N=7有1/35840、N=128有14/655360元素
与独立CPU顺序FP32→BF16的严格零容差不同；None/空N/graph/非法输入和原调用方均通过。
不先调整容限。保留`04-runs/mx-102/mhc-collapse-operators-v1-20261104.log`，
只读核对实际tuner/编译元数据，并记录公开BF16结果、FP32诊断输出、CPU顺序与FMA链的位模式，
以区分编译运算顺序、转换或参考问题。未证明前本接口和依赖整模链保持未通过。

诊断报告`02-issues/v41-mhc-collapse-20261104/mx-102/strict-rounding-repro-v1.json`，
SHA-256 `039e370e3b46d7cf211cf98a736151ce6d8302112dd9f206f21e35a57fc2d5a1`。
FP32诊断输出已与CPU顺序值不同，排除仅BF16 store转换差异；实际缓存虽记录
`enable_fp_fusion=false`，TTIR仍有math.fma，LLIR为llvm.mxc.pk.fma.f32。
例如首项CPU位模式1017151512、GPU 1017151470。当前编译路径提前融合乘加的事实已确认，
尚不把具体内部模块归因为第三方bug。下一次受控修复仅把既有kernel的一条复合表达式
写成显式tl.mul/tl.add三步，阻止表达式匹配的FMA融合；保留全部输入/输出/顺序及原严格断言，
不改编译器、公共tuner或容限。若仍融合则继续定位，不用未经证实的设置宣称解决。

v2显式tl.mul/tl.add仍为相同2 failed、257 passed，原断言保留；撤回这次无效表达式尝试。
下一步只对由现有runtime识别的MetaX选择libdevice公开mul_rn/add_rn，明确每项FP32 RN边界；
私有kernel新增默认False的constexpr参数，由原两个host wrapper推导传入，无用户开关，
其他后端保留原表达式和原参数选择。当前安装Triton公开列出了这两个API，设备实现仍需真实编译验证。
增加6项后端选择metadata检查，不能把它们计作其他芯片数值验证；原严格数值与graph场景不删减。

v3实际设备编译和原严格断言通过：最终collapse与延迟mHC共73项通过，
其中6项仅验证厂商选择metadata，其余为实际数值/graph/拒绝路径；未测其他厂商硬件。
日志`04-runs/mx-102/mhc-collapse-operators-v3-20261104.log`。
同样本FP32诊断复核、完整静态hooks、103独立复测及受控benchmark仍待完成。

同样本复核已完成：N=7/128的公开BF16及诊断FP32差异数均为0，报告SHA-256
`acd8bf7f67fa36a717b5eba8f0ec9a970f91a263742aa6d58daf52d679908225`。
当前FGV精确快照7项项目hooks通过。103按基线/依赖上下文同步五文件后，
最终collapse、原延迟mHC与原norm调用方共99项通过；日志
`04-runs/mx-103/mhc-collapse-operators-v12-20261104.log`。
切片manifest SHA-256 `1744d0215aa38494319b98bcdf321173d12aec106413f5c68f4f8e9955567a3c`。
受控benchmark、Plugin模型尾部调用和整模链仍未完成，原mHC性能只对旧切片有效。

103当前RN切片的受控benchmark已完成：kernel模式延迟mHC最小speedup=3.8997，
collapse=2.9552；cudagraph模式分别为3.3510、4.2481，原延迟mHC最低0.9门槛保持并通过。
每模式12个延迟mHC、4个collapse场景，独立同设备FP32 ATen组合基线，20ms warmup/50ms测量。
49次资源观察仅允许本轮精确命令和容器命名空间的benchmark进程，测量前后源码/环境记录一致。
结果`04-runs/mx-103/mhc-rn-controlled-benchmark-v4-20261104/result.json`，SHA-256
`8babc8ad211b972fbacf8f97f056a52f1bf515d439b0143e4af382131b4a418c`。
这是103的算子性能结果；102当前切片性能、Plugin模型尾部调用与整模验收仍未完成。
