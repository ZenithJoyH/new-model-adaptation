# 008：MetaX sparse MLA 候选共享内存超限

## 问题与边界

102上 `sparse-mla-padded-baseline-20261027/mx-102`（只读产品代码的组合probe）失败。
现有FG/FGV两库的标准kernel只有BK64/BH64、8warps、stages2/4候选，实际加载要求
163840字节共享内存，而C550硬件限制65536。尚未运行到数值断言，与补头本身无关。
不改FlagTree/SDK，也不在Plugin复制attention kernel。

| 项目真相 | 冻结内容 |
|---|---|
| 算子/所属 | FGV现有 `flash_mla_sparse_fwd`，标准Triton BF16分支 |
| 版本/可写 | ddce1d66，`ops/flashmla_sparse.py` 的候选选择，及新 `tests/test_sparse_mla_metax.py` |
| 不改 | TLE路径、数学循环、公共签名、FG和vLLM，只修一处实际被选FGV |
| active set | D512/576，HQ64/128，部分/全部无效索引，topk_length，eager和两次变输入graph |
| 验证 | 首先07-bugs固定tile诊断确认资源/数值；再正式候选守卫和真实CPU对照；逐shape报告不以平均值掩盖失败 |
| tuning/profiler | 先验证数学和资源上限；BK16/BH16、4warps、stage1是受64KiB约束的诊断候选，未测不称性能最优 |
| fallback/timeout | 不增加Torch计算回退、不增加超时、不禁图，其他vendor保留原候选 |

| 数学契约 | 内容 |
|---|---|
| 输入/输出 | BF16 Q `[SQ,HQ,D]`、KV `[SKV,1,D]`，INT32 indices `[SQ,1,TOPK]`；BF16输出512维，FP32max/lse |
| invalid | 索引<0或>=SKV屏蔽，topk_length限制；全部无效输出0，max=-inf、lse=+inf（现有kernel约定） |
| 累加 | 原分块在线softmax、FP32分数和累加，概率转BF16的数学顺序保持 |
| alias/layout | 不改现有contiguous和shape校验，独立输出；补头属于Plugin adapter而非修改此数学契约 |

| 路径 | 实现/验证 |
|---|---|
| MetaX | 根据FGV runtime vendor选择满足共享内存上限的候选，先实测固定tile后才进入产品；守卫命中实际GPU验证 |
| 其他vendor | 原候选和TLE能力选择；无其他硬件，只声明选择隔离测试 |

当前open；资源失败和所有实验结果保留。若固定tile仍失败，先诊断完整错误，不盲增候选。

## 后续核实

固定BK16/BH16、4warps/stage1的组合probe在102通过head4/8/64数值/变输入graph。正式FGV候选修复后，两机各10项通过、rc0，涵盖HQ64/128、D512/576、无效索引、topk_length、两次变Q/K replay；证据 `sparse-mla-resource-fixed-20261027/<host>`。没有修改数学循环或TLE分支。性能影响和最终source review待收尾，不作为完整模型验收。

## 真实服务新增触发条件与计划（2026-10-28）

第五轮真实请求TOPK进入128倍数域，FGV仅检测TLE Python属性及cuda兼容device，误选
NVIDIA MMA shared encoding；MetaX compiler builder不存在`make_nv_mma_shared_encoding_attr`。
旧10项测试TOPK80不满足TLE资格，不能证明服务默认选择安全。当前diff f3e2c82仍只有候选
修复，尚未包含该新增问题。v5服务与probe已按精确PID登记停止，容器保持运行。

必要增量仍限定 `ops/flashmla_sparse.py:_can_use_tle_flash_mla_sparse_fwd` 和已有本任务
`tests/test_sparse_mla_metax.py`：MetaX真实vendor在入口拒绝不兼容TLE，复用已经数值验证
的标准Triton实现；其他vendor与环境开关原行为保留，不改TLE kernel/SDK/FlagTree。
先增加vendor守卫两侧测试，并将实际数值/graph矩阵加入TOPK128和2048以覆盖服务触发域；
原80、边界、dtype、topk_length及两次变输入replay均保留。负对照须在新守卫前复现编译
失败，修复后走默认公共入口，不通过环境禁用开关绕过选择。该选择变更的性能待整模测量。

`sparse-mla-tle-baseline-20261028/mx-102` 真实TOPK128负对照复现相同NV MMA shared API缺失。
新增3行MetaX selector守卫后 `sparse-mla-tle-fixed-20261028/mx-102` 28项通过，保留原80并
覆盖128/2048、HQ64/128、D512/576、bounds、无效token及两次变输入graph；NVIDIA选择
隔离仍原结果。source SHA `575890059485fa9c9c2e5d21fac307b8a298b8da072a78e5899c28548f5a1243`，
FGV完整tracked diff SHA更新为 `16e4ef6d5d3fa2ebde6d9578403e1be477eca04be0e3c565a7b0dfe3de0f65f4`。
101同步后同组验证进行中，整体性能及跨厂商实际设备仍未验证。
