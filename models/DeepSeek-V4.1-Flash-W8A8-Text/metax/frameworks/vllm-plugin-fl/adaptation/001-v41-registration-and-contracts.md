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
# 整模型后续接入范围

整模型按已固定主线e77daef89e18语义接入实际Plugin，不复制数值kernel。新增模型`model.py`、
`attention.py`、`compressor.py`、`rope.py`及必要权重映射；补既有dispatch的薄公开算子桥和注册、
模型注册入口、独立权重映射/拓扑/前向编排测试。沿用已验证cache、V2 state、Engram、projections。
Attention通过FGV公开Q/KV fused insert、索引Q量化、paged MQA、候选选择/mask、TopK、FlashMLA与RoPE；
整数logical→physical映射保留Plugin。mHC通过已有公开pre_delayed/post/collapse；MoE复用原生V4模块，
num_hash_layers固定0，当前不启用EP/sequence parallel、speculation、vision或LoRA接口。

默认TP8×PP2、20/20层，确保KV共享owner留在stage内。每层独立SWA；仅2/8/14/20拥有main/index cache，
其他层依配置引用owner，indexer仅2/8/14/20/24/28/32/36生成新索引；stage1第20层开始候选池。
PP传BF16[N,4,5120]与FP32[N,4] pre_mix；Engram注入放在每块pre之前，包含stage第一本地层，
最终collapse后RMSNorm，无hc_head。ratio2 ring由ModelState request index管理，cache数值由FGV写。
CPU RoPE配置沿用原生get_rope构造，压缩层theta/YaRN与纯SWA区分，禁用mscale。

权重映射对指定checkpoint逐项处理INT8/FP32 scale、融合wqa/wkv、共享MLP w1/w3、路由expert与attn_sink TP切分；
只明确跳过vision/aligner/image及MTP，未知文本键或遗漏本地必需参数直接报错。必须先做完整key/shape
与本地参数映射检查，再真实加载；仅测试映射不代表769GB载荷加载通过。模型注册只在类/接口可导入后进行。
适用plugin:A1–A4/B1–B4/C1/D3/E1–E4/F1–F4/H1–H10及operator公开契约。
当前仍未完成注册/整模加载/PP调度、图级别选择及正式验收；后续逐步保留真实失败与证据。

102已安装未注册整模型切片11文件，完整48文件静态上下文通过适用hooks。
`04-runs/mx-102/model-slices-v1-20261104.log` 76项通过：权重namespace与完整fusion/expert覆盖、
公开算子capability/转发、模型类与PP/V2接口实际导入、TP分片/disable-TP融合加载、原生GateLinear
对象保留且FP32数值/新输入graph通过。没有分配整模型参数或运行PP服务。
原生mHC post读取comb[j,i]，与FGV默认TRANSPOSED一致；原生V4 RoPE类明确保留FP32 cache，
直接复用构造器，不在Plugin重写频率计算。inverse sin按RoPE族共享，避免逐层复制1M位置buffer。

后续限定MetaX general plugin hook新增惰性模型注册，保留已存在native entry；补metadata注册测试，
并在真实EngineArgs/ModelConfig中验证选择。Engram阶段缺失history输入应显式拒绝，防止ModelState
接线遗漏时静默跳过Engram。接着做真实cache/注意力链与模型构造/权重映射检查，再读取完整载荷。

102惰性注册及完整切片78项通过，`04-runs/mx-102/model-registration-v1-20261104.log`；
103同一切片78项独立通过，`04-runs/mx-103/model-peer-v25-20261104.log`。
102真实EngineArgs/ModelConfig探测选择本Plugin的DeepseekV41ForCausalLM，BF16/fl_w8a8_int8、
TP8×PP2/nnodes2/mp、logical block64/fp8_ds_mla、上下文50000、prefix on、async on、V2及FULL均解析通过；
Inspector判定text-only。证据`04-runs/mx-102/engine-config-probe-v1-20261104.json`，
仅配置/类解析，无模型构造、权重载荷、GPU整图或PP服务结论。
镜像支持原生multi-node MP参数，未安装Ray；不为本任务引入Ray依赖。

102注意力前向链4项通过，`04-runs/mx-102/attention-chain-v2-20261104.log`：
第2/20层、N=4/256，真实公开算子命中、独立CPU FP64注意力参考、缓存保护区和新输入图回放。
v1测试缺少原生CustomOp构造所需的current VllmConfig上下文，在进入计算前失败；
v2只修正测试fixture，未改变产品代码或数值容差。该检查隔离TP rank元数据，不证明collective或整模型。

下一步在两台实际适配容器内用原生分布式初始化建立TP8×PP2进程组，构造实际模型并核对
全部96085个safetensors文件头、明确排除项、本地参数、融合片及专家覆盖/形状/dtype。
只读取文件头，不读取权重载荷；结果逐rank保留。通过后再实际加载并验证原生MP服务及PP+async。

103相同注意力链4项独立通过，`04-runs/mx-103/attention-chain-peer-v27-20261104.log`。
构造探针v1的MCCL环境误配见002；v2已建立真实TP/PP communicator，16个rank均进入模型构造，
但诊断脚本直接调用initialize_model时漏掉原生BaseModelLoader的set_default_torch_dtype，
使GateLinear按FP32声明并被现有BF16权重契约显式拒绝。v3仅补齐该原生上下文，不修改产品或放宽检查。
v2逐rank失败和通信初始化/销毁日志保留于`04-runs/constructor-preflight-v2-20261104/`。

v3真实双机16 rank模型构造及全部96085个文件头映射通过，每rank结果`passed=true`、errors空。
102参数56.2175–56.2181 GiB/卡，103为32.6638 GiB/卡；真实TP/PP组、全部本地参数、融合片及384专家覆盖已核对。
结果`04-runs/constructor-preflight-v3-20261104/rank-<0..15>.json`；两端诊断退出并销毁通信组，容器保留。
该结果没有读取权重载荷或运行forward。随后使用原生MP CLI进行真实权重eager服务开发验证，
TP8×PP2/async/prefix on，50000上下文、2048批token、16序列，gpu_memory_utilization=0.95；
0.95用于为102实际56.22 GiB参数和运行缓冲区预留空间。此独立eager检查不是graph档位回退或正式验收。

eager-service-v1在原生worker显存预检失败：初始化通信后free=59.43/63.59 GiB，
0.95要求60.41 GiB，未读取权重。v2仅将gpu_memory_utilization降至0.92、重试使用独立端口与目录，
保留原失败日志，不修改worker、通信实现或调度开关。真实权重加载与推理仍待该轮结果。

eager-service-v2在102主体加载后失败：严格检查报两层Engram共12参数未加载。
全文件头原始顺序明确为93364个model键（无Engram）→head.weight→norm及12个Engram键。
原生AutoWeightsLoader按相邻前缀groupby，inner model的严格load_weights在第一个model分组末
提前要求全部参数，尚未迭代到后面的Engram。文件头单独映射检查没有覆盖此真实流式分组边界。
修复限定Plugin model.py顶层load_weights及权重测试：在完整映射流上统一调用既有严格加载器，
保留全部本地参数、每个融合片、每个专家片和未知/重复键检查；不修改vLLM或忽略Engram。
新增实际AutoWeightsLoader分组顺序的CPU回归，先复现原失败再修复，并重跑既有权重/模型切片。
保留v2原生日志；停止本任务对端尚在加载的服务后再安装修复。该问题与PP+async推理无已证实关系。

流式顺序回归在原产品上复现相同12个Engram缺失，`04-runs/mx-102/loader-stream-repro-v1-20261104.log`。
顶层完整流修复后102原切片及新回归79项通过，`loader-stream-fix-v1-20261104.log`；
103同切片加注意力链共83项通过，`04-runs/mx-103/loader-stream-peer-v29-20261104.log`。
完整性检查统一复用原严格loader，未移除遗漏/重复/未知键、融合片及专家片检查。
原生专家映射helper只扫描base_layer前缀，可用于顶层模型；vLLM保持只读。完整权重重新加载仍待完成。
构造v3汇总回执`04-runs/constructor-preflight-v3-20261104/review-v1.json`，SHA-256
`1d8b630796b51fb74988d64ea995b445bcb5b8f1618a2c84bac45d21a5825cbd`，作用范围仍仅构造与文件头。

## V4.1文本编码接入（改前范围）

指定权重目录缺少chat_template；镜像只有DeepSeek V4 tokenizer，其文字版thinking提示
不同于V4.1的numeric effort/System token，不能以V4替代。主线固定e77daef89e18
提供`vllm/tokenizers/deepseek_v41.py`（blob3a577172708ed391c8c2771288db63e029422994）
和`deepseek_v41_encoding.py`（blob841de385cb61a435c09997e151083d655cce4e87）；
同版renderer registry明确复用DeepseekV4Renderer。现场两项registry均提供公开register，
ModelConfig/EngineArgs的TokenizerMode均允许str；vLLM保持只读。

限定Plugin：新增`models/deepseek_v41/tokenizer.py`、`encoding.py`移植文本processor；
现有模型包`__init__.py`增加tokenizer/renderer双注册及失败回滚，已有`register_model`
在配置解析前调用；新增对应unit test。保留已有native deepseek_v41条目，幂等，
不覆盖V4/其他tokenizer；本次text profile的非文本content block在编码前明确拒绝。
验证numeric effort/none/thinking控制、System token、原始text parts分隔、不可变输入、
BOS/encode转发、真实tokenizer/token ID、公开renderer同步/异步和原生ChatCompletionRequest
参数传递，并在外部开发探针与只读V4.1 reference encoder对照。
新代码适用plugin:A2/C1/C2/C3/F1/F4/F7/G1；不是数值kernel，不涉及FGV增量。

文本processor v30精确52文件上下文适用hooks通过；102原生单测33项中30通过、3失败。
两项揭示renderer实例实际名为`RENDERER_REGISTRY`（`RendererRegistry`是dataclass类型），
产品双注册引用已纠正；一项测试golden遗漏参考格式中旧assistant的`</think>`，
修正预期而未改编码逻辑。失败日志`04-runs/mx-102/tokenizer-v30-20261104.log`保留。
当前模型同目录reference encoder SHA-256
`502bdaec8a3fd88ebc24c4721a7038fbe42f2063c664638127056107920035c1`
实际映射low50/high75/max100；e77旧映射low25/high50/xhigh75不适用于本权重，
移植时仅按当前参考调整numeric映射，明确拒绝额外xhigh。
V31复测后再同步103；非文本及工具调用前置拒绝，不声明相应服务支持。

V32两机原全部35项通过，52文件上下文静态hooks通过且未修改快照。
reference v2通过前24组后，在原生请求规范化修改历史reasoning字段时触发探针的
全链入参不变性断言；tokenizer自身深拷贝及prompt/token ID当时已通过。
V3仅让原生请求/renderer消费规范化副本，保留tokenizer输入不变与全部56组断言，
最终56/56通过真实tokenizer、公开registry及同步/异步renderer；原失败保留。
结果`02-issues/mx-102/tokenizer-reference-v3-20261104/result.json`，
日志`04-runs/mx-102/tokenizer-reference-v3-20261104.log`。

reasoning v2复用默认thinking parser处理thinking=false时不符合预期；只读对照
`serving.py:251`及`DeepSeekV4Parser.__init__`确认真实服务逐请求传入
`chat_template_kwargs`，该探针漏传，不能当作API问题。V3按真实构造传参重测，
产品与原生parser不变。这里只配置reasoning parser，不启用V4 DSML tool parser。

V31两机原全部33项通过。独立reference预检v1尚未执行容器测试，即被当前reference
的`Unknown role: developer`拒绝；这不是tokenizer数值或服务失败。主线旧实现允许
developer但本权重参考未定义，故V32在wrapper中前置拒绝developer/unknown，增加两项
负例；不猜测映射至system或user。V32 103原全部35项通过，102复测中。
参考对照v2保留7类有效文本（中英文、system、多段、历史reasoning、中途system、
空user、相邻user）×8组thinking/effort/drop控制，共56例；另用上述负例验证拒绝边界。
原生reasoning探针v1误用旧方法名`extract_reasoning_content`，已只读核实0.28接口为
`extract_reasoning`，仅修正外部探针v2，不修改原生parser；原失败结果保留。
