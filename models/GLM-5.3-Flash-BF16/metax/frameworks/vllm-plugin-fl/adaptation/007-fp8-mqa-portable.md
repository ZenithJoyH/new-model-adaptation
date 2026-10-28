# 007：FP8 indexer prefill 在MetaX的dot lowering失败

## 基线和复现

2026-10-27，mx-102/C550，FGV `ddce1d66`，FlagGems已同步 `3eab0949`。
`tests/test_fp8_fp4_mqa_logits.py` 在收集时因vLLM0.24已无
`vllm.third_party.deep_gemm`而失败；保留原结果
`04-runs/glm-indexer-baseline-20261027/mx-102/`，没有删改或跳过后冒充通过。
其余不依赖该旧参考模块的分页MQA/cache/pack/unpack原生51项通过，结果
`04-runs/glm-indexer-portable-baseline-20261027/mx-102/`。

独立直接复现 `07-bugs/003-fp8-mqa-prefill/repro.py`：FP8 Q `[2,32,128]`、K `[70,128]`，
FP32 scales/weights，与CPU FP32数学参考。原始运行
`04-runs/fp8-mqa-prefill-baseline-20261027/mx-102/` rc1；编译首错是FlagTree
`GenericFMAVectorMultiplier::multiplyVectors` 断言 `aElem.getType() == tgtTy`，继而
`PassManager::run failed`，目标是FP8 `tl.dot`。尚未执行数值对照，不把它归为精度失败。

同步后的FlagGems `fused/fp8_fp4_mqa_logits.py:_fp8_fp4_mqa_logits_kernel` 同样直接FP8 dot，
无MetaX override；本次不重复在两个库叠加修复。实际FGV的 `ops/paged_mqa.py` 已采用
`fp8_storage.decode_e4m3fn` → BF16 dot 的可移植方案，并经本次分页数值和graph验证。
复用该既有解码实现，修复已有prefill kernel的MetaX路径，不新增计算回退或另建编译器。

## 编码前三张表

### 项目真相

| 字段 | 冻结内容 |
|---|---|
| Current op | 既有 `fp8_fp4_mqa_logits` 的FP8 Q分支，GLM indexer prefill |
| 可写 | FGV `ops/fp8_fp4_mqa_logits.py` 的标准FP8 kernel和对应host分支；新增 `tests/test_fp8_fp4_mqa_logits_portable.py` |
| 只读 | MXFP4/TLE kernel、旧参考测试、tune config、FlagGems/FlagTree/vLLM/SDK及通用libentry |
| 构建/验证 | 实际editable首次JIT；先同一07-bugs负对照，再独立CPU参考、stride/空输入/range和变输入graph |
| benchmark | 复核既有入口；固定M/N/H/D的latency及逐shape SpeedUp，失败基线无可比延迟；未测不宣称性能收益 |
| active set | Q/K E4M3FN、D128/H32，M1/2/17，N0/70/129，尾块、stride、clean range含空区间、graph两次变输入 |
| aggregation/timeout | 功能逐项通过、性能不以均值掩盖关键shape；独立run、首败停止，不增加服务超时 |
| profiler/autotune | profiler未验证；沿用既有BLOCK_M/N、HEAD_BLOCK及warps/stages候选，不盲调 |
| fallback | 生产无Torch计算/拷贝/cast，只有等字节dtype view；Triton内复用解码与BF16 dot |

### 数学与张量契约

| 字段 | 冻结内容 |
|---|---|
| 输入 | FP8 Q `[M,H,D]`、K `[N,D]`，feature stride1；FP32 key scales `[N]`、weights `[M,H]`，整型范围向量 `[M]`；同device |
| 输出 | 独立FP32 `[M,N]`；`sum_h(ReLU(dot(q,k)*k_scale)*weight)`，q scale已折入weights |
| dtype/累加 | 每个有限E4M3FN值可精确表示为BF16；软件解码后BF16乘、FP32累加，保持scale/ReLU/head reduction顺序 |
| 边界 | M/N为0沿用empty返回；clean模式范围外-inf、可含空区间；原校验和非连续stride协议保留 |
| unsupported | 不新增FP4训练/反向、其他D或NaN/Inf覆盖承诺；MXFP4路径保持原样，不声称MetaX FP4通过 |
| Torch参考 | 只在测试/07-bugs/benchmark，CPU计算，不导入生产路径 |

### 路径设计

| 路径 | 触发与实现 | 风险/验证 |
|---|---|---|
| empty/error | 原host分支 | 维度、dtype、device、空输出保持 |
| MetaX FP8 | host用uint8等字节view；同kernel的constexpr软件解码到BF16，再沿用dot/scale/ReLU/reduction；不选WGMMA TLE | 当前编译缺口的可移植路径；数值/stride/graph与模型D128验证 |
| 其他vendor FP8 | 原FP8输入和native/TLE选择 | 代码守卫未命中保持；无其他设备，不宣称跨设备实测 |
| MXFP4 | 原host/kernel | 不改变、不扩大支持声明 |

只修复实际FGV，不在Plugin、FlagGems重复叠加该兼容处理；公共导出/注册/签名不变，
无需新调优配置。新测试不依赖旧DeepGEMM模块。移除条件为当前MetaX原生FP8 dot路径
通过同矩阵数值/graph和同条件性能验证；不会凭capability数字提高就自动移除。

## 当前状态

`open`，以上边界在产品编辑前冻结；先102直接验证，再扩展回归及同步101。
无新增FlagTree/SDK修改，vLLM仍只读。知识库状态 `local-only`。

## 102 修复验证

`fp8-mqa-prefill-fixed-20261027/mx-102` 同一负对照输入通过，最大绝对误差
`9.5367431640625e-07`。新增维护测试在 `fp8-mqa-portable-regression-20261027/mx-102`
22项全通过（rc0）：守卫两侧、M/N空输入、feature-contiguous且外层strided、clean范围，
eager/capture及两次变Q/weight replay。102通过后已同步101，等待其相同矩阵结果。
这证明兼容路径的正确性，不代表性能优化或完整模型验收。

## 后续核实

101的相同22项亦全部通过、rc0，证据 `fp8-mqa-portable-regression-20261027/mx-101`。性能影响和最终source review待收尾，不作为完整模型验收。
