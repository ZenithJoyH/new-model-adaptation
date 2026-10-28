# 005：KDA prefill 对照在 state stage 首次分歧

## 基线与现象

2026-10-27，mx-102 / `glm5.3-flash`，FGV `ddce1d66`，KDA产品文件未修改。
原生 `tests/test_kda_bounded.py` 的首个prefill用例 FP16/T1/H2/K64/V32 与只读vLLM
64-token core 的bitwise对照失败。`tests/test_glm5_numerics.py` 的8项以及gate-cumsum的
6项均已通过；此轮合计14通过、1失败，`-x`首败退出，后续KPool/mHC未执行，不宣称通过。

原生证据：批准根 `04-runs/glm-primitives-fp32ref-20261027/mx-102/`。
参考计算已明确关闭TF32，原断言完全保留。

## 诊断与当前假设

进程内观察相同kernel，未写vLLM源码。`04-runs/kda-stage-trace-20261027/mx-102/result.json`
显示 inter/intra、inverse、recompute 的共同tensor逐元素相等；首次分歧发生于
`chunk_gated_delta_rule_fwd_kernel_h_blockdim64` 的h、ht、v_new，最终output最大绝对差
0.000869751。该诊断本身正常退出，不等于KDA数值通过。

加入显式连续化的后续进程中，相同kernel逐stage以及最终output/state均bitwise相等
（最终最大绝对差0），结果位于 `04-runs/kda-stage-contiguous-20261027/mx-102/`。
但日志随后确认原initial已连续，stride `(4096,2048,64,1)`，因此该控制不足以证明布局根因；
已撤回先前的布局根因判断。进程初始化时序、autotune及真实MetaX backend初始化尚需核实。
两边实际FLA_CHUNK_SIZE和默认chunk_size均64，已排除猜测的chunk大小差异。

## 边界和后续

不放宽bitwise断言，不把generic recurrent的CPU对照通过等同于prefill通过。
撤回尚未执行的参考测试连续化修改计划；没有根据这个不足的控制改写测试或产品。
下一步记录每个输入的stride、所有scalar launch参数和真实kernel提供者，在同一进程验证
重复运行与真实MetaX初始化前后行为。只有证明参考前置条件或产品缺口后才限定新变更。
vLLM、FlagTree、SDK继续只读。
仅继续直接算子和元数据诊断，尚无模型服务或正式精度证据。
知识库状态：`needs-validation`。

## 已验证的真实worker缺口：USE_EXP2被忽略

真实worker调用 `current_platform.import_kernels()` 后，state kernel 从只读vLLM切换为
Plugin `dispatch/backends/vendor/metax/patches/chunk_delta_h.py`。该实现明确接收
`USE_EXP2`，但注释为unused，六处gate衰减始终调用自然指数exp。
这与KDA累计gate的log2输入协议不一致。它是独立验证的真实服务缺口，不能未经证明就当作
此前未初始化worker的原生测试偶发差异的根因。

负对照：`07-bugs/002-metax-kda-exp2/repro.py`，原始结果
`04-runs/kda-exp2-baseline-20261027/mx-102/`（rc1）。同一进程、相同常量输入、相同
4warps/1stage启动，分别直接比较实际Plugin和只读vLLM的原始JIT kernel，禁用autotune影响。
USE_EXP2=False时history/state/value逐位相同；True时history/value相同，final state
最大绝对差0.0330301374。该证据确认指数基数协议缺口，不涉及参考布局猜测。

### 修复边界（产品编辑前）

| 组件/文件/符号 | 动作与职责 | 验证 |
|---|---|---|
| Plugin `dispatch/backends/vendor/metax/patches/chunk_delta_h.py` | 仅导入既有FLA exp2，并在六处gate衰减按已有USE_EXP2 constexpr选择exp2/exp；不改调优参数、kernel注册、state/cache布局或其他平台 | 原负对照True修复、False逐位保持；G/GK两分支、K64/128、FP16/BF16，eager/graph变输入回放 |
| Plugin `tests/unit_tests/patches/test_metax_kda_exp2.py` | 新增可维护数值测试；真实设备路径、独立常量/CPU数学参考，显式初始化实际MetaX backend | USE_EXP2守卫两侧、其他vendor/无设备导入隔离；旧GDN false行为与KDA true行为 |

基线 Plugin `/opt/vllm-plugin-FL@4e23ae8f` 工作树在修改前干净；此修复落在既有vendor扩展点，
不改变通用worker/dispatch。False保持原表达式，用于既有GDN调用；True遵循vLLM已有协议，
用于KDA。纯Python/Triton直接JIT；无新torch生产计算，无新kernel导出和调优配置。
先mx-102负对照和针对性回归，再同步mx-101。另行重跑实际worker初始化后的KDA完整测试。
保留初始未初始化worker测试失败，未证明根因前不删除或放宽。vLLM/FlagTree/SDK不修改。

mx-102局部修复后的同一负对照已通过：
`04-runs/kda-exp2-fixed-20261027/mx-102/` rc0，True/False的history、state、value均逐位相同、
最大绝对差0。实现仅增加Triton内联 `_gate_exp(value, USE_EXP2)`，复用现有exp/exp2，
替换六处衰减调用并移除unused注释。
针对性维护回归 `04-runs/kda-exp2-regression-20261027/mx-102/` 已24项通过、rc0：
G/GK、True/False、FP16/BF16和K64/128/256，真实eager/一次capture/两次变输入replay，
独立数学参考，无mock目标计算。相同产品修复和测试已同步到101，其同一回归正在运行。
未初始化worker的先前数值差异仍保留为未定根因；正在按实际worker初始化重跑完整算子组合。

结果更新：101同一24项全部通过、rc0，路径 `04-runs/kda-exp2-regression-20261027/mx-101/`。
实际worker初始化后的FGV测试中，完整40项KDA bounded已通过（包括模型128维、varlen、
prefill/decode、padded state stride及拒绝路径），另68项KPool、8项基础GLM通过。
组合测试随后在独立mHC配置问题处停止，见006；KDA通过不替代后续整模精度。
初始未初始化worker的cold路径差异尚未定根因，记录保留，不将其描述为布局修复。
