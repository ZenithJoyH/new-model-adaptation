# 006：mHC RMSNorm 的语义BLOCK与自动调优冲突

## 问题与原始证据

2026-10-27，mx-102 / `glm5.3-flash`，实际FGV `/opt/FlagGems-vllm@ddce1d66`。
真实worker初始化后，8项GLM基础、40项KDA bounded、68项KPool全部通过；随后mHC首个
RMSNorm用例D127/FP32报 `JITFunction.run() got multiple values for keyword argument 'BLOCK'`。
回执为批准根 `04-runs/glm-worker-primitives-fp32ref-20261027/mx-102/`，116通过1失败、rc1。
该失败不是模型加载、OOM或数值误差。

实际 `mhc_rms_norm` 调优候选META均为空，仅4/8warps；源码配置本身没有重复BLOCK。
安装的FlagTree `Autotuner._bench` 在AABS路径调用 `auto_adjust_block_sizes`，会将运行时
BLOCK加入候选/缓存配置。现场缓存D127配置含BLOCK128，而当前声明候选不含BLOCK。
FGV LibTuner最终将调用kwargs与config.all_kwargs分开展开，造成重复关键字。
不凭该错误修改通用调优器、删除缓存或重写NVIDIA配置。

## 编码前三张表

### 项目真相

| 字段 | 冻结内容 |
|---|---|
| API | 既有 `mhc_rms_norm(x, weight, eps)`，mHC pre/post-pre的恰好一次RMSNorm；当前Torch2.10公式参考 |
| 可写 | `src/flaggems_vllm/ops/mhc_with_norm.py:_norm_kernel/mhc_rms_norm`；新增 `tests/test_mhc_norm_model.py` |
| 只读 | 原有全部mHC测试、参考及tune config；libentry、FlagTree、vLLM、其他算子 |
| 构建 | 实际editable解释器首次JIT，无安装或导入覆盖 |
| validation | 原有 `tests/test_mhc_with_norm.py` 全量，加D4096独立CPU参考及两次变输入graph |
| benchmark | 先复核现有mHC基准入口；latency越低越好，SpeedUp逐shape评估；失败基线无有效延迟，不伪造收益 |
| active set | FP32/FP16/BF16；D127/128/257/1280及模型4096；stride、空/identity、非法输入、pre/post-pre顺序 |
| aggregation/timeout | 功能逐项通过，性能不以平均掩盖关键shape；独立run和实际进展记录，不延长服务超时 |
| profiler/autotune | 未验证profiler；沿用当前4/8warps调优，仅将不可调的语义extent移入kernel由D导出，配置不变 |
| fallback | 无Torch生产计算回退；metadata、empty分配和已有Triton copy保留 |

### 数值与布局契约

| 字段 | 冻结内容 |
|---|---|
| 输入 | 任意前导维度、末维D，FP32/FP16/BF16；weight `[D]`同device；允许stride，已有连续化保留 |
| 输出 | shape/dtype/device与x一致；weight=None返回原对象；无in-place/out新承诺 |
| 计算 | FP32 `x * rsqrt(mean(x²)+eps) * weight` 后转输出dtype；BLOCK必须覆盖完整D，禁止调优截断reduction |
| 边界 | 原空输入、非法shape/device、NaN/Inf传播行为不变，不扩展整数/复数；forward-only，不承诺autograd |
| Torch参考 | 只用于测试/benchmark，生产helper不引用参考 |

### 路径与改动

| 路径 | 选择/实现 | 验证与风险 |
|---|---|---|
| identity/empty/error | 现有metadata和返回分支 | 既有测试保持 |
| 正常RMSNorm | 从私有kernel签名及host调用移除BLOCK参数；kernel内部 `BLOCK: tl.constexpr = triton.next_power_of_2(D)` | 完整数值、dtype、stride、D4096、graph；计算tile与原意相同 |
| autotune | 只调warps，semantic extent不暴露为参数 | 新JIT hash隔离旧配置，不删除或篡改旧缓存；多D连续调用验证 |
| 其他vendor | 同一语义修复、无厂商SDK新依赖 | MetaX实机；其他硬件未提供，不宣称实机通过 |

无需新导出、注册或调优配置：公共API不变；私有kernel只有本文件host调用。
`optimization.md`/`deep_opt.md`在当前FGV主线缺失。此次为兼容性修复，不进行盲调或性能优化声明。
先102验证，再同步101；最终逐块审查与问题003的卷积差异分别绑定。

## 当前结论

mx-102已实施局部修复，未改libentry、配置或缓存数据。原有mHC完整26项加新增模型4096维
FP32/BF16 CPU参考、两次变输入graph回放共28项通过、rc0，原生结果位于
`04-runs/mhc-semantic-block-fixed-20261027/mx-102/`。
相同修复和测试已同步101并正在验证。状态 `in_progress`，最终source review和性能影响仍待收尾。
原失败保留，不能用116项其他算子通过代替mHC通过。知识库状态 `local-only`。

## 后续核实

101相同路径亦28项通过、rc0；两机正确性回归已验证。性能影响和最终source review待收尾，不作为完整模型验收。
