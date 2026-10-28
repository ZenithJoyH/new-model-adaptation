# 002：PLE 短 prefill 原位状态更新不确定

## 用户提供的上游修复 #959（先行同步）

用户补充 [FlagGems-vllm #959](https://github.com/flagos-ai/FlagGems-vllm/pull/959/)。
实取 head `22194f0b2ee0cebb51f945a20a157b82c4e19c65`，与容器 HEAD 的共同基线
`fa78ddee4c3e78ce5047213ff0ef02acff34b2d5`；该 PR 尚未包含于当前安装版本。
PR 补丁已保存在远端 `02-issues/pr959.patch`，仅修改
`src/flaggems_vllm/ops/qwen4/ple_conv.py` 与 `tests/test_ple_conv.py`（373增/3删）。
先将完整上游修复三方应用至当前安装树，保留当前 main 的后续内容，不提交。

改前新增范围：`_ple_conv_state_kernel` 在乘行stride前提升int64、state store前CTA同步，
以及原测试文件中的边界/大stride/变输入graph回归。Plugin已核对在decode、spec与prefill
回退调用此通用入口；这与下述短prefill fusion是两个实际入口，不把通用入口修复当作fusion已修。
原核心测试及参考断言不变；无新fallback、dispatch、调优参数或外部依赖。
验证计划：上游完整PLE conv测试在本C550执行，并重跑原短prefill失败，确认剩余问题边界。
PR的PPU结果仅作来源说明，不作为沐曦验证；本机结果尚待执行。

三方应用无冲突，当前HEAD不变。应用后ple_conv.py SHA256为
`2f273afafdfd1a991dd0138b0d330d001cf0cd17bdcb96b83a22a5f3929140c0`、
test_ple_conv.py为`6b987f18310465870ed19c2360cc9dceff578dad03c3bf84e7ebc57c302a6ad5`，
均与PR声明的已验证文件一致。本机完整回归 `04-runs/pr959-metax/pytest.log`：
**211 passed in 159.35s，无skip**。实际graph与大stride测试包含在此轮，未将PPU结果替代本机结果。

## 现象与身份

2026-10-23，mx-101 / qwen3.8-flash，批准根同宿主机、容器路径
`/public-flash/jinghao/qwen3.8-flash`。FlagGems-vllm实际editable安装树
`/opt/FlagGems-vllm@c9003571a6bd06bdc94ca3dbfad4cc606a8d82f8`，修改前工作树干净。
Torch2.10.0+metax3.8.2.2，C550，FlagTree main `2f1229e5`、pybind11 3.0.1。
原算子文件SHA256 `8cbf93a7904a67671d0d401ec225aa3412ca78ec21176dbd339b7625e77e3dd6`。

六组Qwen算子quick测试收集165项，执行35通过后首个失败：
`tests/test_ple_fusion.py::test_ple_prefill_conv_boundaries_state_and_determinism[lengths0-dtype0]`，
BF16、lengths=[1]、channels65、kernel4、dilation3、state_len9、非连续state。
初次数值对照通过，重复相同输入10次时state不再逐元素相等。
原始结果 `04-runs/qwen-kernels-abi11/pytest.log`；状态为待修复，不将其当成整模通过。

## 契约与代码阅读

已读组件AGENTS、workflow.md及相关实现、调用方、测试和benchmark；其链接的
optimization.md/deep_opt.md在实际checkout搜索未找到，记录此缺项，不宣称完成性能优化协议。
已核对[PyTorch2.10 conv1d](https://docs.pytorch.org/docs/2.10/generated/torch.nn.functional.conv1d.html)：
本算子是有历史状态的causal depthwise dilation卷积再SiLU，状态更新是额外的原位协议，
不把cuDNN卷积可非确定性的说明解释成状态移位可以不确定。

## 项目真相表（改前冻结）

| 字段 | 内容 |
| --- | --- |
| Current op | FlagGems-vllm `ple_prefill_short_conv_`，问题来自本模型已有算子回归 |
| Editable files | `src/flaggems_vllm/ops/qwen4/ple_fusion.py`内`_ple_prefill_state_update_kernel`；新增`tests/test_ple_fusion_state_alias.py` |
| Read-only files | 原tests/test_ple_fusion.py、benchmark/test_ple_fusion.py及参考入口、Plugin与vLLM；不放宽原断言 |
| Build | Python/Triton源码直接生效；新进程与独立JIT缓存，禁止PYTHONPATH |
| Validation | 先07-bugs独立状态复现；原失败测试、原PLE全测、新eager/graph状态测试、六组算子回归 |
| Benchmark | 既有benchmark/test_ple_fusion.py::test_ple_prefill_conv_perf；µs越低越好，SpeedUp=Torch参考耗时/算子耗时 |
| Active set | BF16/FP16/FP32，qlen1/8/9/10及long/mixed候选，channels65/2560，连续/非连续state，保留null/empty守卫 |
| Aggregation | 分dtype/shape报告，不以均值隐藏失败或回归；不代替服务性能验收 |
| Timeout | 最小复现120秒、功能600秒、组件benchmark600秒；到期先查进程而非重复启动 |
| Profiler | 暂未核实MetaX profiler；先保留dispatch、kernel数、条件分支与原生耗时，不冒称NVIDIA profiler可用 |
| Autotune | 不新增性能参数或改动既有block/warps配置；仅修正线程同步，现有调度完整保留；本轮无新tune配置 |
| Fallback | NO_TORCH_COMPUTE_FALLBACK；不增加Torch计算、复制或类型转换fallback |

## 对齐契约表

| 字段 | 内容 |
| --- | --- |
| Torch/API | conv1d groups=C、kernel4、dilation3，SiLU；额外维护最近9个输入的历史 |
| Device | 实际C550/MetaX CUDA dispatch，其他设备未实测 |
| Input | x[T,C]与weight[C,4]连续；state[slots,C,S>=9]支持实际strides；request offsets与state索引保持既有类型 |
| Output/alias | 输出[T,C]；state有效行前9步原位更新，padding和未选中/null行不变；必须从写前状态读取 |
| Dtype | 现有支持BF16、FP16、FP32；本轮不扩展dtype支持 |
| Accumulate | 卷积FP32累加、按源dtype存储；状态是精确复制/移位，不放宽容差 |
| Semantics | 短query新state=tail(old_history+new_x,9)；empty/null保留原守卫；NaN/Inf复制语义不变 |
| Autograd | 推理forward/state更新；不新增训练或backward承诺 |
| Unsupported | 原host gate与NotImplementedError保持；不缩小原支持范围 |
| Reference Torch | 仅测试/benchmark用Torch构造独立参考；产品路径不得调用 |

## 实现路径表与假设

| 路径 | 条件 | 拟改动 | 验证与风险 |
| --- | --- | --- | --- |
| early/unsupported | 原empty/null或非法参数 | 保留现有行为 | 原守卫测试 |
| long prefill | query_len>=state_len | 保留现有两kernel与调度 | 原长query数值/graph与组件benchmark |
| short prefill | query_len<state_len | 候选：读取旧state完成后、写state前加入CTA同步；不改dispatch或新增workspace | 精确移位、重复执行、跨warp非连续布局、eager/graph |
| external | 无 | 无新外部库或Torch fallback | 静态审计 |

当前假设：状态更新kernel原位读取偏移后的历史，再写回前端；没有CTA同步，另一个warp可能
提前覆盖尚未读取的旧state。现有输出kernel与state kernel已经分离，不应重复新增第三条算子链。
每个CTA负责一个request/channel tile，同一request的query_len为CTA一致条件；
候选同步只作用短query路径，需受控复现和前后对照验证后才能认定根因。

## 变更与验证状态

该fusion路径尚未修改产品代码（通用PLE另按#959同步）。最小复现保存在 `07-bugs/ple-prefill-state-race/`，在该容器路径原地执行，
不另建/bug。不改Plugin、FlagGems、vLLM，不调整正式精度阈值或跳过失败用例。
设计审查、设备数值、graph和性能影响均待验证；知识状态local-only。

## 改前受控复现

已在同容器 `07-bugs/ple-prefill-state-race/reproduce.py` 独立调用公共库API，seed457，24组dtype/channel/length组合，各30次。结果 `04-runs/ple-prefill-state-race/baseline.json` 为失败；例如FP32/C65/qlen1在30/30次均有128个状态元素错误（首批位置time3/7），qlen8/9/10控制通过。实际模型宽度C2560的所测组合未复现，不将其推广为该宽度已出现同一故障。完整各组结果留在原生JSON。

候选改动限定为 `_ple_prefill_state_update_kernel` 中 `next_state`读取完成后，`query_len < state_len` 的CTA一致条件内增加 `tl.debug_barrier()`，再执行既有store。既有两次kernel发射、原block/warps、long路径、导出/注册和unsupported行为不变；不使用Torch计算或新增workspace。

原 `test_ple_fusions_capture_and_replay` 的query_len65大于state_len9，不覆盖此次短历史原位移位；新增 `tests/test_ple_fusion_state_alias.py`，覆盖BF16/FP16/FP32、qlen1/8/9/10、C65/2560、非连续state、eager/graph固定地址重复更新，精确比较状态及未选行/padding。原功能测试、参考实现与benchmark文件均只读保留。

先验证长prefill基线原测试（lengths=[15,16,17]，BF16/FP32），再运行既有long-only组件benchmark（tokens33/1024/4096，hidden129/2560，三dtype）作为改前对照；不对当前错误的短状态路径声称性能达标。

改前清单细化：复用既有 `tests/test_ple_fusion.py` 与 `_prefill_conv_reference`，仅在文件末尾
追加短状态eager/graph回归，不另建前文拟议的test_ple_fusion_state_alias.py。
原参考函数、原测试函数与断言及benchmark全部保持原样。追加测试24组合、每组3次eager和
3次变输入/索引/初始标记replay，精确检查整个state（含未选行和padding）。在改kernel前先跑
FP32/C65/qlen1负对照。Plugin融合阈值1024按整batch token计，混合prefill即使总长超过1024
也可能包含短query，因此不以单请求token阈值排除此入口风险。

追加回归改kernel前负对照 `alias-test-before.log`：FP32/C65/qlen1失败，128/2145元素不同，
最大绝对差14。已包含#959的此轮仍失败，确认两入口分别需要处理。
实施fusion候选：仅`next_state`后增加query_len<state_len的CTA一致同步（3行），无其它产品修改。
`after-fix.json`：24组合×30次精确状态全通过；`fusion-after.log`：**37 passed in 9.53s**，
包括新增24组合、72次变输入/索引/flag graph replay及原测试。不存在单独新增测试文件。
原长prefill基线测试2通过；改前组件benchmark18 SUCCESS。完整Qwen组合与改后benchmark正在运行。
