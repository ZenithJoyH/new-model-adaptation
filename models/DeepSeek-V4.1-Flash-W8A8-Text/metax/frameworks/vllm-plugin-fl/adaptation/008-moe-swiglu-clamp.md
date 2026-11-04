# 008：动态INT8 MoE的SwiGLU clamp

状态：2026-11-04，双机FGV与Plugin切片已验证，受控性能未通过。目标BF16、384专家top6、路由sqrtsoftplus、
scale=1.5、SwiGLU limit=10；主线V4.1明确num_hash_layers=0，原始配置未提供此项，
后续模型封装不能继承V4的hash-router默认值。

Plugin当前`dispatch/backends/flaggems/impl/w8a8_moe.py`明确拒绝正clamp，
但其`_flaggems_fused_experts_impl(**kwargs)`已委派FGV根公开API。
FGV根在MetaX绑定厂商`runtime/backend/_metax/ops/fused_moe.py`，目前core只允许silu，
不具备gemm1标量接口。FGV通用`ops/fused_moe.py`已公开支持
`swigluoai_uninterleave`：split gate/up，FP32 gate=min(gate,limit)、up=clamp(up,-limit,limit)，
输出gate*sigmoid(alpha*gate)*(up+beta)。alpha=1、beta=0、limit=10与目标clamp相同，
应复用该公开计算，不新增Plugin数值或复制激活kernel。

候选修改范围为MetaX MoE公开core、apply_moe_activation及inplace/outplace wrapper：
新枚举和keyword-only gemm1_alpha/beta/clamp_limit，沿用通用的同组件参数校验，
在所有GEMM/量化/状态写入之前拒绝无效参数；新激活不得进入plain-SiLU融合捷径。
默认silu及旧参数位置保持，先验证目标per-channel INT8范围，再决定公开支持边界。
Plugin只做clamp到该公开接口的映射、特性检查与既有dispatch编排；
实际计算开始后的错误直接传播，不依赖运行时异常切换后端。

先对未改库做小BF16/INT8 MoE基线，独立CPU两级INT8/INT32累加和BF16物化对照。
同时核对现有MetaX `_int8_quantize` 的per-token分支：源码目前除以已舍入scale，
与原生动态量化乘显式absmax倒数在half ties可能不同；先做实际边界诊断，证明后再限定修复，
不能从005中另一量化入口的通过推断此入口通过。
后续测试需覆盖原silu、新clamp触发、标量变化/非法值、routing权重、expert map、
原地/指定输出、空batch、实际graph新输入和受影响原调用方；基准沿用仓库框架。
具体改前文件hash/dirty、源码清单和可执行测试在确认基线后补齐，未确认前不编辑相关产品文件。

未改库的实际基线：half-tie输入4.625/2.3125得到127/63，原生参考为127/64，
确认与005不同入口的量化舍入问题。小BF16 MoE默认融合silu与两级BF16参考有40/192元素差异；
改为数学相同的identity expert_map以禁用已有plain-SiLU融合后，与相同独立参考逐位一致。
两轮source hash相同，证据`02-issues/v41-moe-clamp-20261104/mx-102/baseline-v{1,2}.json`。
故新clamp须走显式GEMM1物化/激活路径，不能沿用plain-SiLU融合。默认旧融合路径本身暂不改写，
也不把其差异宣称为已修复；新的half-tie修正限per-token INT8分支，复用既有根公开
`scaled_int8_quant`，保留block/static分支。当前厂商源SHA-256
`9de7b6eb0c366da625cb291b3be37d1fda01e8b9c346d10fb0924c12f0541746`。

第一批编辑限FGV该厂商`ops/fused_moe.py`、新增`tests/test_metax_w8a8_moe.py`及
`benchmark/test_metax_w8a8_moe.py`。不改generic激活kernel、不改其他厂商，不开始Plugin切片。
公开函数名已注册，新增的是既有API可选参数；无需增加op ID/导出。
新增clamp的fused路径先明确限制为BF16/per-channel INT8、无block/其他量化方案，
standalone激活与通用公开API保持同一签名和数学；原silu默认、旧位置参数和static/block量化保留。
库内允许复用同组件的私有标量校验；Plugin以后只访问公开API。全部scalar/capability检查在计算前，
默认SiLU融合枚举条件不得纳入新split-clamp激活。具体测试覆盖真实TP8 local形状H5120/I288/top6、
小shape/空N、clamp=0/10/参数变化、expert map、bias、routing位置、inplace/out、
根公开量化实际命中与half-tie、图回放新输入及非法参数前置拒绝；性能只准备原生Benchmark，资源受控后才测。

Plugin实际调用链补充：`FlagGemsW8A8Experts.apply` 的非Ascend分支直接调用根库并没有传clamp，
会绕过既有w8a8 provider及统一dispatch；此前只读provider中的拒绝并不能代表实际调用会被拦截。
库验证后须修改该else分支，通过resolve先选择既有w8a8 provider，再按clamp映射公开API，
补“旧代码曾忽略clamp”的真实回归和异常不重试；Ascend现有流程不顺带重写。
原selector已声明expects_unquantized_inputs，继续保持首次输入为浮点，不能重复量化。

第一轮安装控制变换在写入前因中间AST缺逗号被拦截，已修正控制脚本，产品未发生半安装。
实际首轮57项中55 passed、2 failed：所有目标local形状、clamp参数、根量化half-tie和graph均通过。
两项分别为新测试只传out而遗漏现有API强制配套的workspace13/workspace2，以及复用generic激活
默认min/max吞掉NaN，与独立Torch clamp参考不符。日志`04-runs/mx-102/moe-clamp-operators-v1-20261104.log`。
前者只改测试按既有契约传入双workspace，并保留错误组合的拒绝断言、新增out与workspace alias覆盖。
后者需扩一处已验证producer：`ops/fused_moe.py:_swigluoai_uninterleave_kernel`的三个min/max
显式设置propagate_nan=ALL；原计划不改generic kernel在此由已复现的NaN契约差异扩展，
只改该函数，不复制计算，不改普通SiLU或量化融合kernel，有限值数学保持。
generic源改前SHA-256 `00fc24faaf69540c1aa0103b0ae5c3732e9c971a1316a5eaa0063295c61f3f05`。
补跑原`tests/test_fused_moe.py`以覆盖该公开激活的通用调用方；不删除原失败case或放宽容限。

修正后新58项及原通用25项共83 passed，日志`04-runs/mx-102/moe-clamp-operators-v2-20261104.log`。
实际H5120/I288/top6、half-tie根量化命中、workspace配套/alias、NaN和新输入graph已覆盖。
目前仅102产品文件更新；逐hunk审阅、适用hooks、103独立验证与Plugin实际漏传clamp修正尚未完成。

下一批Plugin编辑限`quantization/w8a8/moe_experts.py:FlagGemsW8A8Experts.apply`的非Ascend分支、
`dispatch/backends/flaggems/impl/w8a8_moe.py`及相关测试。前者通过既有resolve_op选择provider，
后者仅验证有限标量、检查根公开API三个keyword能力并映射alpha=1/beta=0/limit；
非正limit沿用禁用clamp语义。Ascend分支、selector及既有原生fallback不改。
保留原专家契约测试的全部断言，新增provider能力/错误不重试、真实GPU专家apply独立INT64参考、
两级公开量化命中与新输入graph。FGV格式调整仅允许已改函数中的格式hunk。

102已完成实际Plugin接入：原专家/selector与新provider检查共43 passed、2个原硬件条件skip，
新真实GPU专家apply测试5 passed，覆盖H5120/I288/top6、强clamp对照、两级根公开量化实际命中、
新输入/scale/routes图回放。日志`04-runs/mx-102/moe-plugin-{unit,functional}-v2-20261104.log`。
先前格式检查拦截两处新测试编写问题（断言位置、分号），只修测试后复跑，产品计算未因此改写。
FGV及Plugin当前精确源码快照的全部适用hooks通过；逐hunk已审阅，FGV只改既定六处函数/枚举
及generic激活的NaN传播。103独立验证和原生benchmark仍待完成，整模型未加载。

103精确九文件切片复测完成：算子83 passed；Plugin单元43 passed、2个原硬件条件skip；
实际GPU专家调用5 passed。日志`04-runs/mx-103/moe-clamp-{library,unit,functional}-v13-20261104.log`。
切片manifest SHA-256 `ec72dc71ef298bae409aa6a54754954f0e179bbcb147b670fd1e4b09c4bbcbcc`。
两机均已验证clamp接线和根公开量化命中；仍不代表384专家完整权重加载或PP/async模型通过。

103原生kernel模式基准包含实际384专家表的H5120/I288/top6及小控制形状；
小控制形状M1/H64/E4/top2 speedup=0.7010，低于本轮保留的0.9门槛，故不判性能通过。
该轮同时发现scaled_mm性能回退，控制器在kernel模式门槛处结束，cudagraph模式未运行。
证据`04-runs/mx-103/components-controlled-benchmark-v13-20261104/{kernel.json,failure.json}`。
保留失败；原始kernel测量不构成整模吞吐或性能验收结论。
