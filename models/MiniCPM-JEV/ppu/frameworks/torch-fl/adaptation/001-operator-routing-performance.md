# 001：Transformers / Torch-FL 算子路由性能优化

2026-10-26，用户授权在 PPU-01 的 `minicpm-jev` 容器优化此前 12 个 value-head 样例的推理耗时。选择 experimental Torch-FL profile，仅执行适配阶段的局部诊断、配置/实现尝试与回归，不启动正式性能验收。

## 身份、基线与边界

- 容器 ID：`0ee63bbcec91264acfef52636b7a2983d53bf31ccb976c808fe827646673e069`，运行中，`/mnt:/mnt` RW。远端工作根为 `/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt`，Host/容器同路径，现场 stat 均为 dev41 / inode18374857198。此根沿用既有 Transformers/Torch-FL 运行区，与子目录 `vllm-plugin-fl` 的工作区分开。
- 实际可写产品组件仅 `/workspace/PyTorch-Plugin-FL`，HEAD `ac2ca673d8ee56b28719ab0bcc38d5c40baf6d82`；初始 tracked clean，仅 `torch_fl/lib_ppu/` 为既有 untracked 运行库，保留原状。实际导入 `/workspace/PyTorch-Plugin-FL/torch_fl/__init__.py`。厂商 libtorch、Transformers、模型 demo/权重只读。
- Transformers 5.10.4、官方 torch 2.10.0+cpu，经 Torch-FL CUDA facade 执行 PPU；物理 PPU3 → `cuda:0`，BF16、SDPA、batch size1、原生双图预算。无 PYTHONPATH 覆盖。PPU0/1/2 已有服务保持原状。
- 原始预热基线：工作根 `04-runs/transformers-warm-timing-12-20261026-1/timing.json`，SHA-256 `ca140c2dd6364f24d507f6bad512cfbb90d5c229dc4a94d32e4e90e66b8d8926`。完整 12 例预热后测一轮，合计1.836138秒、循环墙钟1.836735秒，平均153.012毫秒；最大参考误差0.003685066 < 0.005。后续比较应在同一新运行内重测多轮基线，不将 profiler 开销计入性能。

## 改前计划与验证

1. 首先不修改产品代码：使用原 demo 的真实 load/score；拆分预处理、传输及前向的诊断计时，读取 Torch-FL 既有 profiler/dispatch 工具，确认真实热算子及路由。完整预热 12 例后记录至少三轮无 profiler 顺序耗时，并保留每例分数/token 数。
2. 优先使用既有 `FLAGOS_OP_<name>` 单算子后端开关做受控 A/B，每次一个关键变量。候选仅限 profile 允许的运行配置及 Torch-FL 扩展点，不改模型、权重、厂商运行库或依赖版本，不全局禁用 FlagGems 来代替定位。
3. 若确需源码修改，先补本记录的文件/符号、前后哈希、必要性、调用方及测试清单，再编辑实际安装源码。沿现有 codegen/路由入口，禁止在模型层 monkey patch 热路径、复制模型实现或新增版本覆盖。
4. 验证保持12个输入文件哈希、顺序、BF16/SDPA及图像预算一致；预热和测量分数对照、参考误差≤0.005、token数一致。产品公共路由修改另做所涉 dtype/shape/layout/边界与 guard 未命中测试。整轮测量仅报告相同配置的局部结果，不声称正式性能、全量精度或 optimized。
5. 容器和其他服务保持运行；测试进程自行退出。仅保留有稳定收益且精度通过的最小变更，不提交、推送或创建 PR。

## 经验复用与待验证假设

已阅读 Qwen-Image-2.1 / PPU / Torch-FL 的001记录。共同点为官方CPU wheel与PPU CUDA boxing/FlagGems共存；其 complex slice、unsafe_view 和全有效 attention mask 的故障签名与本任务不完全相同，不直接套用。当前“部分小算子 Python/Triton 路由开销超过厂商 boxing”及“CPU fallback 或同步”为假设，必须由本机实测确认。

## 当前结论

诊断证据为工作根 `04-runs/torch-fl-op-routing-20261026-1/`，脚本位于 `02-issues/torch-fl-op-routing-20261026-1/`。三轮默认基线中位数1.903093秒，最短1.896025秒，分数与此前完全相同。带逐算子同步的 TorchDispatchMode 只用于定位，不能用其耗时替代无 profiler 结果。另有 cProfile 和输入/输出哈希。

已发现并更正运行身份：`cuda:0` Tensor 的 key 为 CUDA，`flagos:0` 才是 PrivateUse1；PPU 有真实 CUDA-ABI 运行库时 Torch-FL 不安装 cuda→flagos 别名。此前描述“CUDA facade”不准确，已有耗时和样例结果仍然有效。默认模型不产生 Torch-FL dispatch 日志；CPU fallback 日志为空也不能据此声称所有算子通过了 Torch-FL 路由验证。

较长样例 cProfile 中，18 次 `torch_chunk_gated_delta_rule` 累计0.133秒、模型前向0.187秒；原生分块实现包含64次三角矩阵行递推及大量 clone/小归约，是首要候选。诊断两例共 clone4536、sum.dim_IntList2342。普通读图/预处理约0.135秒/12例，优先级低于模型前向。

## 融合算子候选计划补充

当前 FlagGems `/workspace/FlagGems` 为 `367d19367880eaf8843449abe11db4cfb7d47e03`，clean，仅作为只读依赖使用。已有 `flag_gems.fused.chunk_gated_delta_rule`，不安装 FLA、不修改其源码。先在一次性数值探针中比较64/242/782长度及状态输出；HF原生的L2定义为 `x * rsqrt(sum(x*x)+1e-6)`，与该融合算子可选L2的clamp范数定义不同，必须保留HF归一化。其公开包装要求q/k/v/beta/g同dtype，而HF的g/state为FP32，候选优先FP32输入、输出恢复原dtype，并明确验证性能和数值。

若数值及整模型通过，候选接入点是GDN实例已有的 `chunk_gated_delta_rule` 可调用属性；这是原生构造为FLA/torch选择保留的边界，不替换模型forward或全局Transformers函数。先只在一次性诊断进程显式选择，产品化前再列出Torch-FL适配文件/符号、guard/恢复与幂等测试。原计划“不在模型层monkey patch热路径”仍禁止全局替换/模型文件改写；显式实例适配须在此接口边界内，并保留原函数用于未支持的dtype/layout/state条件。无已验证收益时不保留产品变更。

诊断进行中，尚无本轮产品修改或性能提升结论。原始证据仅留批准远端根；本地仅记录精简结论与定位。

## 受控实验与拟保留实现

- `flagos-default`：仅从 `cuda:0` 改为 `flagos:0`，三轮12例中位数7.043335秒，最大参考误差0.006077671 > 0.005，不保留。测试退出码0只表示执行完毕，结果字段passed=false，不能按退出码宣称通过。
- `gdn-probe`：保留HF的BF16 L2归一化后转FP32调用已安装的公开FlagGems wrapper，输出恢复BF16。64/242/782长度逐元素对照通过，输出最大差0.00048828125，状态最大差0.000540525；GDN本体由4.67–7.45毫秒降为0.229–0.519毫秒。以上只是局部诊断，输出状态与正常整模型分别验证。
- `gdn-fused`：实例callable边界仅替换18个GDN；三轮总耗时0.791337/0.774442/0.791636秒，中位数0.791337秒，较1.903093秒约2.40倍。最大参考误差0.004621146 < 0.005，较原CUDA结果最大差0.000936080，所有token数一致；864次融合调用与1预热+3测量×12例×18层吻合。

拟保留产品变更限Torch-FL两个新增文件：`torch_fl/compat/qwen3_5_gdn.py`提供显式启用/恢复的PPU推理适配，在现有实例callable边界调用FlagGems公开算子，不改全局注册、模型forward、厂商配置或默认调用；`tests/integration/test_qwen3_5_gdn.py`覆盖实际融合数值/状态、重复启用/恢复、CPU/grad/unsupported守卫及保留用户自定义callable。原生dtype归一化、FP32中间计算和最终dtype保持当前候选语义。未命中条件执行原HF函数；不捕获异常后重试。启用函数不覆盖已有FLA/用户实现，默认不自动启用。

安装源码编辑前保存新文件不存在证明、初始HEAD/status和相关依赖哈希到本轮原始证据；测试进入正常pytest入口。最终同一协议完整预热后测5轮，按用户要求计算60次单样例延迟的中位数/p90，使用线性插值分位数并披露统计口径。保留同时期5轮原CUDA基线用于比较。未完成这些验证前不宣称最终交付完成，不刷新正式验收状态。

## 最终结果与逐块审查

两文件新增，合计325行：适配144行、测试181行。没有任何既有tracked源码修改/删除，原untracked运行库保持原状。HEAD未变，未暂存、提交或推送；PR base尚未选择，本轮是对当前安装HEAD的局部源码审查。

| 文件/代码块 | 必要性与兼容边界 | 验证 |
| --- | --- | --- |
| `compat/qwen3_5_gdn.py`：`_ChunkGatedDeltaRule`构造和适用条件 | 保存原实现、HF L2和已安装融合kernel；仅无梯度、PPU CUDA入口的BF16/FP32、q/k/v同形、head_dim128、有效batch/seq、FP32 g/state、BT64且无packed kwargs时选新路径。原模型/CPU/训练/FP16/其他chunk/packed路径保持原行为。 | 真实设备BF16/FP32数值、初始状态、非连续layout、63/64/65/242长度；5个guard测试；异常不重试。 |
| 同文件：未命中分支与融合调用 | 完整透传原参数；HF BF16 L2保留，转FP32统一包装契约，输出恢复原dtype、状态保持FP32。没有复制GDN算法、宽泛异常fallback或新kernel。 | 原函数独立对照，输出atol0.002/rtol0.02，状态同界；数值用例令reference分支直接报错以证明实际命中融合；整模型另以0.005阈值对照。 |
| 同文件：`enable_qwen3_5_gdn` | 显式opt-in、仅PPU构建、仅原生Qwen3.5 dense GDN且原callable未被替换、参数已在CUDA；无候选时不导入FlagGems。通过现有实例callable接口，不改global/module forward。 | CPU、其他平台守卫、幂等、已有custom callable保留。其他平台实机未执行，仅测试选择隔离。 |
| 同文件：`disable_qwen3_5_gdn` | 只恢复本适配器持有的callable，不覆盖用户后续实现；支持重复调用。 | 重复启用/禁用及原函数身份还原。 |
| `test_qwen3_5_gdn.py`：测试fixture/数值与选择 | 正常integration测试入口，最小真实GDN实例，非mock计算；状态输入不被修改，None状态、guard/错误行为均明确断言。 | 18 passed，36.77秒；没有skip/xfail以掩盖本机失败。 |

`python -B -m pytest -q -p no:cacheprovider --basetemp <本轮05-tmp>/pytest tests/integration/test_qwen3_5_gdn.py`在实际源码根、CUDA_VISIBLE_DEVICES=3执行。首次Ruff E731指出新增测试lambda赋值，已改为普通def；失败日志保留。最终Ruff0.15.12 `check`和`format --check`均通过。pytest7.2与Python3.12的AST弃用警告保留，不作为失败或跳过结果。

最终两个文件SHA-256：适配`a8ae075e006e69b25f5c134282bd3a3bdaa3f12cdcaf716b57d02ecb3bf7137d`，测试`421c065abbc23c7a4f651818979cd5d767dba0de58b03bc654e3cc0e07a8752e`。原生`product-after.json`绑定当前源码，FlagGems仍为上述HEAD且clean；没有新增依赖版本覆盖。设计审查结论：可保留为本次已验证范围内的显式适配候选；无需C++重编译，直接导入实际editable源码。

## 用户表格口径的最终测量

两路径各新进程加载一次，相同输入哈希、顺序、PPU3、BF16/SDPA/bs1。先完整12例预热，再无profiler测5轮，共60次逐例延迟；每例前后设备同步，计入读图、OCR文本读取、预处理、传输、前向和softmax/CPU回传；排除加载、预热及测量后的调用验证。p90按排序后`(n-1)*0.9`线性插值。

| 指标 | 原CUDA路径 | 显式GDN融合 |
| --- | ---: | ---: |
| 单样例延迟中位数 | 148.208758ms | 56.310442ms |
| 单样例延迟p90 | 195.362851ms | 89.281440ms |
| 单样例平均值 | 157.124145ms | 63.557369ms |
| 12例整轮总耗时中位数 | 1.887819s | 0.765616s |
| 最大参考误差 | 0.003685066 | 0.004621146 |

优化整轮五次为0.765616/0.771657/0.754759/0.754843/0.766702秒。整轮中位加速约2.47倍；60次token数全部一致、分数参考误差均≤0.005，较旧原路径分数最大差0.000936080。额外测量后的cProfile独立验证单例恰有18次调用真实`flag_gems.fused.chunk_gated_delta_rule`，不将该诊断耗时加入统计。

原始结果：本轮`final-baseline.json` SHA-256 `98dd867b623f23503d6ff46ffe3483636d7d357391c00d6a6804d1572242ff86`，`final-optimized.json` SHA-256 `d97235f2cecb7500aa4dcba3452581c18271c99bbcc1b3199b53320139b9d465`。最终脚本`02-issues/torch-fl-op-routing-20261026-1/benchmark_final.py`，准确命令存本轮`final-commands.json`。

调用方须在原demo load后显式调用`enable_qwen3_5_gdn(model)`，返回18；普通demo未自动改写。`disable_qwen3_5_gdn(model)`可恢复。其适用范围为当前dense Qwen3.5、PPU CUDA eager、对应dtype/head结构；MoE、训练、其他硬件、packed输入、长上下文与正式全量准确率未验证。仅12个短样例不能证明这些场景。当前experimental profile没有正式performance runner，本次不标记optimized，不生成服务launcher或验收通过回执。

知识库状态`local-only`：局部融合收益及全量路由变慢只在本次精确软件/模型条件验证，尚不提升为跨模型/平台经验。
