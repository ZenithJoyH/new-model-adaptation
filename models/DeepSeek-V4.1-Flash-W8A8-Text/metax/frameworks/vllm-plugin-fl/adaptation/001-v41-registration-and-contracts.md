# 001：V4.1 注册与主线契约接入

状态：open。2026-11-03，Host与基线见[环境分析](../environment/environment-analysis.md)。尚未加载模型。

## 已验证问题

实际 `get_config` 报 `KeyError: deepseek_v41` / Transformers不识别该模型。
Plugin无V4.1注册，vLLM无 `models/deepseek_v41`、`sparse_mqa_indexer`。
0.28 sparse_swa仅有SWA/C4A/C128A，不能直接承载V4.1 C1A/C2A。
参考固定为用户同意的主线 `43067f6df60e2eafba5797908484cc1c12e4a48b`；
旧NVIDIA的QNorm/RoPE、跨层缓存和消息编码问题仅作待复验假设，不沿用旧私有kernel包装或结果。

## 变更前范围与测试

当前只计划独立配置切片，不把它称为整模支持：

| 组件 | 文件/符号 | 变化与理由 | 验证 |
|---|---|---|---|
| Plugin | `vllm_fl/models/deepseek_v41/__init__.py` | 新增轻量包，不导入数值后端 | 无GPU分配的导入 |
| Plugin | `vllm_fl/models/deepseek_v41/config.py` / 配置类、注册函数 | 基于pinned主线配置类展开嵌套参数，通过公开AutoConfig注册 | 真实配置解析、输入不变、序列化、重复注册、已有注册保留 |
| Plugin | `vllm_fl/__init__.py:register_model` | 使用现有general-plugin入口，在EngineArgs解析前注册 | 真实入口、fresh/spawn加载、非目标配置回归 |
| Plugin | `tests/unit_tests/models/deepseek_v41/test_config.py` | 新增聚焦配置契约测试 | pytest、formatter/linter、diff-check |

不删除既有函数/注册/测试，不改vLLM、Transformers、FlagGems或FlagGems-vllm。
首次修改前保存Plugin继承diff、入口原文件与哈希；修改实际 `/opt/vllm-plugin-FL`。
配置属于模型metadata，适用 `plugin:A2/A3/A4/C1/C2/D1/F1/F4/F7`；保留已有native注册，不导入厂商依赖。
该切片无数值kernel，后续算子范围和规范条款在同一问题补充，不绕过算子库公开API。

后续缺口：专用文本编码、模型/权重映射及W8A8、Engram lookback/INT8表、CED共享KV/index、
C1A/C2A metadata与注意力。先核查同步后的FlagGems ATen及FlagGems-vllm公开API，再确定必要修改。

## 后续契约核对

主线 `43067f6.../common/grouped_wo_a.py` 构造函数使用 `divide(n_groups, self.tp_size)`；
实际配置仅8个输出分组，因此初始TP16候选不能直接承载此路径。
下一候选为每机TP8、双机PP2，需要重新核算两阶段Engram及MoE分布、cache、激活与图池，
并补齐实际容器内Send/Recv前置；该前置后续已通过，见004。16rank三项通信只证明对应collective范围。
当前环境快照中的TP16明确是未启动的历史候选，不作为后续有效服务配置。

V4.1使用上一子层携带的pre-mix折叠residual，并返回下一pre-mix。
已安装FGV `mhc_pre` / `mhc_pre_with_norm` 使用本次pre-mix且只返回三项，
现有实现还将fn转BF16；不能仅改Plugin参数包装来满足V4.1的FP32投影和延迟混合契约。
已核对主线首次支持 `e77daef89e18e08321ae7b8b24827eedd5fe8673` 的
`mhc_pre_delayed_tilelang` 签名、四项输出、首层独立x与BF16折叠后RMSNorm边界。
算子范围已在下节限定；102已开始该切片实现及验证，103尚未同步。

## 下一数值切片：延迟mHC（修改前范围）

只拟修改已核实的FGV安装树，不扩展其他第三方依赖。现有mhc_pre及所有V4调用保持原行为。

| 文件/符号 | 增改内容及理由 | 验证 |
|---|---|---|
| `ops/mhc_pre_delayed.py:mhc_pre_delayed` | 新公开四输出API；FP32投影、上一pre-mix折叠、下一pre-mix返回 | 独立FP64/FP32 oracle、真实公开入口、dtype/布局/空输入/异常 |
| `ops/__init__.py`、顶层现有导出机制、`conf/operators.yaml` | 在既有导出/后端机制接入新API | import、公开导出、实际kernel命中 |
| `_nvidia/tune_configs.yaml` 及实际需要的现有后端配置 | 新kernel的仓库libtuner配置；不改其他算子配置 | 配置key与constexpr对应、两次新输入graph replay |
| `tests/test_mhc_pre_delayed.py` | 前向数值/状态和graph测试，参考不调用生产helper | hidden5120、非2次幂、tokens0/1/多token、首层x、可选norm、非法组合 |
| `benchmark/test_mhc_pre_delayed.py` | 按现有Benchmark类比较独立模型参考与公开API | 同卡、同步、warmup、同graph口径，key shapes SpeedUp≥0.9；未达标继续受控优化 |

接口沿用pinned主线参数顺序和默认值，名称去除实现后缀。首版声明HC=4、前向推理；
residual BF16 `[N,4,H]`，fn FP32 `[24,K]`，scale/base FP32 `[3]/[24]`，
pre_mix可选FP32 `[N,4]`，x可选BF16 `[N,K]`（省略时为展开residual，K=4H），
norm_weight可选BF16 `[H]`。输出依次为FP32 `[N,4,1]`、FP32 `[N,4,4]`、
BF16 `[N,H]`、FP32 `[N,4]`；不修改输入或持有跨调用workspace。
先校验全部输入再分配/发射；不支持的HC/device组合显式失败。维度、dtype和设备不符报错。
支持连续张量及连续非零offset；上游明确要求连续的输入仍检查连续，其他合法stride由copy准备。
空N返回正确空shape；正H/K及正Sinkhorn次数，所有epsilon及post multiplier实际生效。

host路径先校验与空输入处理，再用公开FlagGems FP32矩阵乘及FGV库内kernel完成系数和折叠，
保留折叠BF16物化后RMSNorm顺序；不使用Torch计算fallback，不将参考函数引入生产路径。
数值极值/NaN/Inf按独立oracle对照，不通过clamp或删样本掩盖偏差。
autotune仅写当次独立输出，输入和状态不可被调优污染；graph replay更新输入并覆盖sentinel输出。
NVIDIA硬件尚未验证，不能据此声称跨厂商通过。Profiler与benchmark active set在比较前冻结，
缺失优化指南继续按已记录替代依据执行。

适用 `operator:A1–A4/B1–B3/C1–C7/D1–D5/E1–E6/F1–F4`，
`plugin:A1/A3/A4/B1/C1/D3/E1–E3/F1–F4/F7`；Plugin dispatch接入待公开API数值切片完成后单独限定。

### 单机实施与失败保留

102在实际FGV安装树新增上述三份Python文件，修改公开导出、operator metadata和两个后端tuning配置，
共7个文件；顶层沿用现有star-import与替换机制，无需另改顶层初始化。
pytest.ini已有marker处理约定，本轮不修改。改前干净树身份及原4份注册/配置文件在
`02-issues/v41-mhc-delayed-20261103/mx-102/` 保存。
Black24.8.0、isort5.12.0、flake8 7.1.0已按目标仓库固定版本在隔离工具环境检查三个新文件，
服务解释器及第三方依赖源码未修改。

首轮 `04-runs/mx-102/mhc-delayed-tests-v1-20261103.log`：20 failed、9 passed。
实际错误为libtuner/FlagTree调优配置与launch同时传入 `BLOCK_K`，最终JIT调用重复关键字；
尚未形成完整数值或graph通过结论。修复限定为新算子的确定性归约范围在JIT函数内部推导，
不修改第三方调参器或公共libtuner，不改变数值断言。
直接公开API复现器和原始失败源文件/组件diff保留在
`07-bugs/mhc-delayed-launch-20261103/`；修复前先执行复现，修复后用同一复现器和完整原测试复核。
后续诊断的FlagGems及Triton缓存显式位于任务 `06-cache/`；这些仅为开发诊断设置，不进入最终服务脚本。

第一处修复后直接公开API复现器通过，固定结果SHA-256为
`40a21508d1a3b1f835caea00cb5fef5f5c1ec0c0633cce3052bc1a08367e3b38`，
源文件SHA-256 `ea47f319bc90c1f919fe47edb7f2ed52f0794caf2b175c533070f0e644e526bc`。
第二轮原测试（v2日志）16 failed、13 passed：不带norm的数值路径已通过；
剩余失败为既有直接callee `ops/mhc_with_norm.py:_norm_kernel` 同样同时从launch和调优配置接收 `BLOCK`。

必要范围扩展仅增加第8份文件 `ops/mhc_with_norm.py`：语义归约宽度改在JIT内部由D推导，
移除对应launch重复关键字；不改归一化数学、dtype/stride支持、可选norm行为或调参器。
先在 `07-bugs/mhc-rmsnorm-launch-20261103/` 直接调用公开 `gems.mhc_rms_norm` 独立复现并保存原文件。
复测本轮29项原断言，以及既有 `test_mhc_with_norm.py` 中RMSNorm相关dtype、layout、空输入和graph覆盖。
若影响到其他mHC调用方，按相同源审查核对；不把该修复扩大为公共libtuner或第三方库改写。

两处启动参数修复后，v3日志42项通过（29项新API + 13项既有RMSNorm），
另 `mhc-legacy-callers-v1-20261103.log` 的其余13项旧调用方检查通过，累计覆盖55个不同用例。
直接RMSNorm复现器修复结果SHA-256为 `7697ef2510873f7c9cac9abbb2f7416b18d7f46f4fc4707a8828cb6ffc14266f`。
冻结benchmark覆盖6个N/H形状、两种投影/混合变体，kernel/cudagraph各12案例，全部通过0.9门槛；
最小参考加速比分别4.0808、3.6225。参考是独立FP32模型组合，不是厂商原生V4.1 kernel，更不是整模吞吐。
两份原生JSON SHA-256为 `30dcd411e4f7cb917089091b25d2c63e2537e6c1b1c76a51cd35517c93cfb0e8`、
`ab9ef9ca24e2fc81aad5eb0e83481d8b30b3ca70d710bbeed50e0bba3f4582f0`。
已逐案例核对完整性、正有限延迟、比例和源码未变化，测量审阅回执在
`02-issues/v41-mhc-delayed-20261103/mx-102/measurement-review-v3.json`，SHA-256
`e60e2566bd254ed3976a1372d29cf1d484d3194af50bacbc0d81f15db98d38ae`。
8文件切片manifest `tested-slice-v3.json` 的SHA-256为
`e827ad00b1b35c9771d3a8969862a453d186be31861fb22d674828e1d5fe6da8`；103已按原5文件哈希守卫应用相同8文件，55项数值/调用方/graph测试通过。
103基准v1受外部资源竞争、graph未完成；v2资源检查再次失败，见003，未形成受控性能通过结论。
未发现设备profiler命令；保留实际dispatch/graph、调参配置及无profiler基准，未进行多轮性能优化。

FGV配置的Gitcode hook源下载遭代理CONNECT 500，保留原始失败；使用原配置注释所列官方GitHub源，
固定相同版本、参数和7个hook，在8文件字节相同的静态快照及实际包边界context上全部通过。
目标仓库配置未修改；不是全仓hook通过，镜像源内容未独立取得。结果和逐文件哈希在
`04-runs/mx-102/mhc-static-hooks-v3-20261103/official-source-checks.json`，SHA-256
`a4b8e69a9d07229f58adf9cf957ec45d336b44bf514fb034598eccbd9a2a3dc9`。

## 当前边界

配置切片已在两机实际安装的Plugin实施：新增配置包和5个测试，general-plugin入口新增4行；
原有厂商修改均保留。两机各20/20单测通过（5个新增、9个ARM注册、6个GDN回归），
新文件Ruff检查及格式通过。原生日志为 `04-runs/<Host>/config-regression-20261103.log`。

共享证据 `02-issues/v41-config-20261103/tested-config-files.json` 记录逐文件哈希；
测试切片archive SHA-256为 `a14ba53bbf8be984e3893df56bcaf2d2b5623d56dfca6bce54a1f75fcc4eca10`。
原始入口、继承diff和未跟踪文件备份位于该目录的Host子目录。
完整pre-commit受NFS构建错误及本地ShellCheck下载中断影响，未声称完整命令通过；
在字节相同的静态快照上按仓库配置运行7个适用hook通过，证据为
`04-runs/mx-102/config-applicable-hooks-20261103.{json,log}`。
typos按原配置排除本切片，ShellCheck无Shell文件，不将其计为已执行检查。

FlagGems已在原安装树同步至 `e584bded1ddb0ea2a638653043ef0d48931119a3`，两机干净；
FlagGems-vllm基线为 `f108ba81bf6799ccfe48c86f77cbb3ce117c4179`，现有上述8文件修改；
环境阶段原生回执绑定的是实施前观察快照，后续服务验证前须重新冻结实际组件身份，不能沿用旧部署指纹。
该FGV版本引用的 `optimization.md` / `deep_opt.md` 经目标树搜索及Git文件清单核实缺失，
后续采用本项目算子规范和目标AGENTS/现有测试与benchmark流程，不声称读过缺失文件。

双机RDMA前置另见002。vLLM当前HEAD及干净状态与初始一致，保持只读。
配置解析通过也不能代表模型推理、graph或正式验收通过。

后续007对mHC收拢增加了MetaX逐项RN边界，原102两组12-case速度比只适用于原冻结v3切片，
不能用于当前RN版本性能放行。现行版本需重新受控测量，103既有受竞争测量仍不可采信。
