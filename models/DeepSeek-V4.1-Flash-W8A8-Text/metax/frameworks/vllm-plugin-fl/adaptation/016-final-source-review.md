# 最终源码审查（候选，尚未通过）

## 本轮PR整理范围（2026-11-05，执行前冻结）

用户要求先按Plugin PR规范整理当前代码，ERQA任务因图文模态不匹配待澄清，本轮不启动任何评测。仅操作已授权mx-102、mx-103的实际安装源码；当前64序列服务保持运行，不提交、推送、创建PR或改写Git历史。

已重新核对两机HEAD、tracked diff和全部untracked文件内容一致、index为空，vLLM干净。Plugin为detached HEAD，恰对应本地`origin/0.4.0-dev`；FlagGems-vllm为main/origin/main，FlagGems为master/origin/master。现有remote refs不是实时远端或用户确认的PR目标；材料以精确安装HEAD生成可审阅补丁，将建议目标分支与已确认base分开，不假称完成对最新上游的重基。

本轮仅拟修正下列3文件；沿用下文既有53/45/3文件审查，不扩大数值实现或公共API：

| 组件 / 文件 | 修改及必要性 | 验证 |
| --- | --- | --- |
| Plugin `tests/functional_tests/ops/test_dynamic_w8a8_checkpoint.py::test_real_graph_replay_with_new_input` | 使用参数化dtype构造输入，避免FP16用例实际仍测BF16；rtol按原有eager测试的`2*finfo(dtype).eps`，BF16比原0.016略严，FP16为0.001953125，不放宽容差 | 实际已安装树上执行6项真实capture、两次新输入replay、独立CPU INT64 oracle及sentinel检查；计划仅在有足够空余显存的103执行，102不冒充已补测 |
| Plugin `vllm_fl/dispatch/backends/flaggems/impl/quantization.py` | 仅修正docstring：运行时错误直接传播，不再描述不存在的执行后fallback | 去除docstring后的可执行AST与当前版本完全相同；原生格式/lint钩子及现有异常传播测试证据 |
| FGV `conf/operators.yaml::dequantize_int8_weight.description` | 仅修正登记描述，明确当前为FGV融合实现；不改ID、导出、调度或kernel | YAML除该description外语义相同；适用配置/lint钩子，完整任务清单前后哈希核对 |

先102应用并验证哈希及服务健康，再103同样应用；所有变更带原文件哈希守卫和批准根内备份。现有服务运行时代码逻辑不变，不重启服务、不借此宣称其历史精度覆盖新数值代码。适用`plugin:F2/F3/F4/F5/F7/G2`、`operator:F3/F4/F6`；FGV文档已读取同HEAD的AGENTS及workflow，既有缺失optimization/deep_opt处理记录继续有效。重新导出三个组件的任务补丁、逐块覆盖索引、继承改动清单和PR模板正文，公开固定依赖与高精度质量证据仍须如实列为未完成。

补充范围（首次全补丁敏感路径检查后、修改前冻结）：发现Plugin两个新增真实checkpoint集成测试硬编码本机`/public-flash/models/...`路径，分别为 `tests/functional_tests/models/test_deepseek_v41_attention_chain.py::setup` 与 `test_deepseek_v41_engram.py::test_hasher_actual_tokenizer_frozen_map_and_public_dispatch`。本轮再限定修改这两文件：通过明确的 `DEEPSEEK_V41_MODEL_PATH` 测试环境变量读取外部资产，未设置时明确失败，保留配置/词表指纹和所有数值断言，不改为自动skip或删除测试。使用同一实际权重目录补跑两文件的相关真实集成测试；PR正文说明资产参数，源码与补丁不携带个人主机路径。此变更仅改善测试可复现性，不改生产代码、测试场景或门槛。

验证隔离调整（执行前记录）：服务占用GPU时，首轮图测试600秒超时，outer docker客户端返回124，遗留测试进程已按命令/命名空间/起始时间清理，失败证据保留。限制测试CPU线程后的v3通过完整13项收集（6 dtype图、6 attention、1 tokenizer），faulthandler仍定位首项阻塞于`torch.cuda.Stream.__new__`，尚未进入graph/数值断言，故CPU线程并未解决问题；v2只是控制脚本预期项数错误，收集后即终止，没有执行硬件测试。下一步短暂停止两机本任务推理进程，严格按原64契约的PID/start/cmd身份限定范围，容器保留；隔离GPU完成真实回归后，用原SHA `364d18c989f8ce0e5e1406e714eb79cd8586af95487512b6c39aaf9845f9bce9`脚本与相同参数恢复服务并重新记录身份。当前仅将“活跃模型GPU上下文影响新stream创建”列为待验证假设，不修改第三方runtime/驱动，不重启主机或容器。

## 本轮整理结果

本轮5文件收尾已在两机实际安装树完成：Plugin v37（数值运行时代码仍v34，本轮仅测试及docstring）、FGV v44（数值仍v43，仅description）、FG clone v3不变。未暂存、提交、推送、创建PR、切换分支或改写历史；vLLM仍为只读干净树。相对原逐块审查，仅Plugin4文件及FGV1文件有变化，其余96文件的补丁块逐字相同；新增/删除均已按上面的限定范围复核，没有删测试、加skip或放宽误差。

| 组件 | 任务文件 / 块 | 最终任务补丁SHA-256 |
| --- | --- | --- |
| Plugin | 53 / 70 | `72d614f59d72731e8451a4b1d0b6742d4f94d62edf58f1419d2ba3a72b5e8b5a` |
| FlagGems-vllm | 45 / 106 | `b7872796ce75b7b76387d2bb2e5bcfcb1f459c85f31b441f32f01cb28a5507eb` |
| FlagGems | 3 / 4 | `a43ba6fc892ee91e428e36ef279f5f053881c134b325d637d06f75a8ade345c9` |

完整材料位于批准根 `03-acceptance/pr-materials-v2-20261105/`，source-review-materials.json SHA-256 `079cd3e272e82f3ed2379eb4887a35792beb65f87eae7da33f1a5edcc70a1869`，三个补丁均通过实际安装树的反向apply检查（只check，没有实际反向应用）。继承的8项Plugin变更仍单独保留并排除。本地[候选交付目录](../../../../../../deliveries/DeepSeek-V4.1-Flash-W8A8-Text/metax/vllm-plugin-fl/README.md)包含三个源码补丁、按各仓原模板写的英文PR正文、101文件/180块索引、依赖顺序与限制，不包含权重、密钥、原始日志或缓存。

验证：Plugin精确54文件上下文的8项适用hooks通过，FGV精确51文件上下文的7项适用hooks通过，formatter未改字节；不是全仓CI通过声明。103 GPU0在隔离当前模型进程后，**13项全部通过**：6项真实FP16/BF16图、6项attention/cache、1项实际tokenizer/hash/public dispatch，0 skip。包含两次新输入重放、NaN sentinel和独立CPU参考，指纹与断言未削弱。日志 `04-runs/pr-cleanup-v4-20261105/tests-mx-103.log` SHA-256 `f6059fc0d1ac524f72ca53db025827493ee54309d7a753908407eaa83bba0e88`，native退出0。102未补跑这13项，不声称双机均补测。

原共享GPU尝试仍保留：v1在600秒外层超时124，v3在明确stream堆栈后主动结束143；v2只是收集项数预期错误，没有硬件执行。隔离模型后同一GPU mask/源码的stream预检及13项通过，证明隔离条件有效；驱动内部原因未定，不能记成已修复共享GPU stream问题，亦未改第三方依赖。未将这些失败删除或计入通过数。

两机服务已用**同一64脚本字节**恢复，FULL、TP8/PP2、V2 runner、async ON、prefix ON及原生生效配置与此前64完全相同；FULL19个捕获尺寸完成。恢复后8项文本原生sanity与逐项内容审阅通过（包含thinking），health200、running/waiting均0；容器始终运行。新服务ID `v41-pr-cleanup-restored-v1-20261105`，启动/输出/最终记录根 `04-runs/pr-cleanup-service-restored-v1-20261105/`：

- 当前服务契约 `service-contract.json` SHA-256 `4e06dfc698829fe57792d7860805ac5021f800cbf8fe3edfb90d3dceb00e20a0`；精确候选部署身份 `c8e5374193de3c0a4641e64a579323b1f8a06cbcd0f9ff0fae5e8c3e7e23bf27`。旧服务PID身份不再复用。
- 原生恢复响应 `sanity.json` SHA-256 `128ed43c97e15ea77ec4bbac63f897d2aebabde5ab8b91de4c1bbea569e8caf0`；独立 `sanity-review.json` SHA-256 `777e367e321707ad9d520855ad2ae452809fd5802c4ccf0ef72e4ee81fc2024d`，通过原生validate_result。
- 最终 `pr-cleanup-final.json` SHA-256 `8a1fa6292627fbddbb6ca97276bed1889967f407605a2fdb3f01a40f928a5aa4`，status=`cleanup_validated_delivery_gates_pending`，ready_for_submission=false。
- 归档 `03-acceptance/pr-handoff-v2-20261105/pr-candidates.tar.gz` SHA-256 `94772fe6032913553d8e9440b121981dee4dd4b2c9cb009fcb72cd96a5745418`。因大小超过单条命令参数上限，使用受守卫的Ansible copy传输；未改变源码、校验规则或服务。

结论：本轮代码整理与候选材料准备完成；三个原待修项和两处私有路径已解决。Plugin、FGV仍因`plugin:D3`公开固定依赖、`plugin:H9`高精度质量对照及最终目标集成/适用构建CI未完成，保持“候选、交付门禁未通过”；FG clone维持独立PR候选范围，仍待维护者/目标CI。整体source_review不提升。未重跑GPQA/GSM8K、启动ERQA或进行正式性能；历史16配置精度不迁移为当前64完整精度通过。

## 历史v35/v43审查依据（保留原始状态）

以下为本轮整理前的逐文件/逐diff块审查，绑定Plugin v35、FGV v43、FG clone v3；完整清单及可逆检查在批准根 `03-acceptance/source-materials-v35-20261105/`。其中当时的“待修/仍在评测”状态以上述本轮结果为准，原始失败与未完成门禁不删除。此处是设计判断与限制，不以服务HTTP成功、单测数或文档完整替代正式门禁。

| 组件 | 安装根 / HEAD | 任务范围 | 任务补丁SHA-256 |
| --- | --- | --- | --- |
| Plugin | `/opt/vllm-plugin-FL` / `37f2127367cfbc24349a1f28cb37c4c629b9ed6c` | 53文件、70块 | `cfe796822523ab31f572251326b4dc8cf159691919efda1df6e722c21576942a` |
| FlagGems-vllm | `/opt/FlagGems-vllm` / `f108ba81bf6799ccfe48c86f77cbb3ce117c4179` | 45文件、106块 | `6956da2ea0aece1391adcf71ff1ad45853cc78a006447c6626b0e33c6194800f` |
| FlagGems | `/opt/FlagGems` / `e584bded1ddb0ea2a638653043ef0d48931119a3` | 3文件、4块 | `a43ba6fc892ee91e428e36ef279f5f053881c134b325d637d06f75a8ade345c9` |

上述HEAD是任务基线，不是已确认PR目标分支。Plugin原有四项tracked及四项untracked的standalone/MCCL相关改动单独列于source-review-materials.json，未混入任务补丁；没有删除、恢复或提交它们。FG/FGV没有任务清单外dirty。只读vLLM仍为 `2cf0a6915ce544dc493a0990f2ea38d81601128a`、干净。对三个任务补丁只做`git apply --reverse --check`，未真正反向应用。editable安装metadata可能滞后，复现身份同时记录实际HEAD、dirty文件哈希和真实`/opt`导入根。

## 必要性与职责

| 变更组 | 核对结论与影响边界 |
| --- | --- |
| Plugin注册、config、tokenizer/encoding与单测 | 镜像缺V4.1实现，需要懒注册和文本协议；保留未来native注册，重复初始化与失败回滚有测试。编码保留pinned vLLM来源与模型数值effort定义；拒绝图像/tools/不支持role，未假称多模态。`plugin:A1/A4/C1–C3/G1/G2`。 |
| Plugin模型、weights、projections、Engram、compressor、attention | 仅模型编排、加载生命周期与薄调用；原生V4 MoE、Linear与allocator可复用部分保持。完整流式权重覆盖、TP/PP局部权重分片与BF16/FP32边界均有独立测试。WO_A只做一次INT8×scale到BF16，不宣称在线重载。Q只旋转而无额外head norm。`plugin:A1/A4/H1–H6`。 |
| Plugin model_state/compressor_metadata/attention_metadata/cache | 只读写raw ids、请求/slot/block映射与地址，不含KV数值运算，属于`plugin:A3`。保持独立稳定buffer；按actual/padded token数防止native dummy padding污染，拷贝其他builder拥有的cached token map；真实native对象与CPU整数oracle覆盖故障。PP划分不得跨KV共享组，speculation/CP/DBO明确拒绝。 |
| Plugin dispatch/register、W8A8配置与调用桥 | 通过既有统一分发和public FGV root接入。能力/签名在执行前验证；新增动态线性和MoE实际计算错误直接传播，无执行后换后端重试。保持原无clamp/非正limit语义、ignore/packed映射、原生工厂对象引用。`resolve_op`真实返回已选择函数，模型构造期冻结的handle归各模型实例所有；未验证捕获后动态修改policy，不能声称支持热切换。`plugin:B1/B3/B4/C1/H3/H4`。 |
| FGV Engram、mHC、compress_norm、candidates、indexer与dequantize API | 数值归FGV，包含独立INT64/FP32/FP64 oracle、真实public分发与新输入graph。caller拥有请求metadata/ring/cache持久buffer；显式值域/contiguous契约，不同步GPU数据做隐式能力探测。ring的R2只聚合相邻两token，偶数prefix块起点清ring正确，未误当四token重叠窗口修改。`operator:A1–A4/C1–C6/D2/E1–E6`。 |
| FGV既有FP8 cache/attention、scaled_mm、MetaX量化/MoE | 修正独立数值发现的空输入、半整数RNE、尾K零填充与空稀疏块；新增split对自然LSE与sink只合并一次。MetaX只调整明确shape/资源边界内调度，其他分支保持通用选择。原V4默认Qnorm=True不变，新False/zero-head选择通用schedule修复已测回归。没有复制数值kernel到Plugin。 |
| FGV exports/operators/tune/selector | 新public API与ID齐备；原native测试保留、另加独立测试。NVIDIA tune文件只补shared generic所需默认配置，原有条目不变，不能据此声称NVIDIA硬件验证。MetaX厂商入口日志按`operator:F6`核对；旧private helper日志不冒充公开入口命中。 |
| FlagGems clone注册与测试 | 原flattened Autograd tuple修成单元素规则tuple，并限制Autograd后端，不再误拦CPU clone/RNG；device kernel不改。CPU Autograd、真实device kernel命中、Inductor、新输入graph和原layout回归两机各64项。新增operators ID只补登记。`operator:A1/B1/C1/E1/F1–F4`。 |
| 文档、example与测试基础设施 | README仅必要支持表和已验证边界；真实stdlib客户端普通/思考均生成391。typos仅增CANN精确词典，未扩大排除；functional conftest optionalhook解决未装xdist时pytest hook校验，空行变化来自同仓formatter。删除/替换均对应上述实际调用或测试，未发现无关重构。`plugin:G1/G2/F7`。 |

## 验证与限制

最终v43 Qnorm接口/旧回归两机各115通过，另8项原native vLLM硬件对照明确未选择，不能计通过；Plugin v34/v35同运行时代码两机各36项接线测试通过。v35 Plugin54文件上下文八项hooks、FGV51文件上下文七项hooks通过且字节不变。FG clone64项/机与适用Python/YAML/metadata hooks通过；本地macOS CPU不支持clang-format13的跳过不表示C++检查通过，本次没有C++改动。

组件受控kernel/graph数据见各编号记录。Qnorm v43相对独立CPU验证的通用FGV schedule，16形状的最小比值分别0.97468/0.97213，原0.9门槛不变；旧v42失败保留。MoE原小控制形状修复后相同组件套件双模式通过。Engram lookup仅65536-row驻留工作集，不代表完整实际大表带宽。clone kernel/graph门槛通过，额外高层operator模式存在较大Python调度开销，未宣称所有模式提速；数值kernel未修改。其他厂商仅有契约/选择隔离检查，无实际硬件通过结论。

完整1319题候选测量正在运行，期间不改产品或测试。审查发现三个待修项：

1. Plugin `test_real_graph_replay_with_new_input`虽参数化dtype，实际输入固定BF16，不能用其声称FP16图通过；应使用所选dtype并补跑六个shape/dtype图用例。
2. Plugin动态量化provider沿用的docstring仍描述执行失败fallback，与新的直接传播错误调用不符；只修文字。
3. FGV `dequantize_int8_weight`登记描述仍称public FlagGems组合，实际已为FGV融合kernel；只修描述。

三项修正后须重新绑定源码材料、审查受影响块并补适用检查。当前各组件设计结论：Plugin **需修改**（测试/描述与交付门禁）；FGV **需修改**（描述及公开固定依赖交付）；FG clone **可作为独立PR候选的代码范围**，不等于跨仓库交付或适配已通过。整体`source_review`保持未通过。

`plugin:D3`的公开可获取固定依赖与`plugin:H9`的同设置高精度模型质量比较尚未完成，继续阻塞对应源码审查结论。相似命名W8A8-BF16仍含INT8专家/线性，不能当成全高精度基线；公开README的其他框架/预算结果不能替代。本地反向检查、toy算子性能、同量化eager对照和最终任务分数均不能豁免这两项要求。此前误写的`plugin:H11`在当前规范中不存在，现纠正：高精度端到端性能比较属于H10末尾的【应该】，不是额外硬门禁。本任务没有已核实可用的高精度权重/同条件性能基线，先完成请求的W8A8首次测量并披露无法比较的限制，不声称量化提速或显存收益。没有提交、推送或创建PR。

补充只读上游核对：当前公开FGV main为 `f4c16203083f3cbc712867fbc7d68e2ebb9d75a8`（2026-11-04），其[融合Qnorm入口](https://github.com/flagos-ai/FlagGems-vllm/blob/f4c16203083f3cbc712867fbc7d68e2ebb9d75a8/src/flaggems_vllm/ops/fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert.py)仍没有 `apply_q_norm`；本次新增Engram与compress_norm路径在该固定提交返回404。因此不能用未经验证的整体升级替代所需接口交付。Plugin公开 `0.4.0-dev` 已到 `ed8c4801dc1f62b2fc7c5bf01a125a2bd52d2c1b`，其中继承的Torch artifact/MCCL修复已发布；这不表示本任务模型接入已公开，也没有将其自动设为已批准PR base。FlagGems旧组织地址重定向至[flagos-ai/FlagGems](https://github.com/flagos-ai/FlagGems)，公开master为 `a4e2556d572fc8dfbd38bb28764faae29c51d035`。上述发现未触发当前安装树、Git HEAD或运行服务变更。

最新结果：用户已要求将唯一未完成题计错，v2的1318份缓存经原生请求键核对并保留，独立汇总1171/1319=88.78%，未达原95%门槛。原生评测客户端已结束，保留退出143及原始证据；模型服务与容器继续运行。先前“仍在运行/无最终分数”描述为历史阶段，当前结论见[末题计错汇总](../acceptance/accuracy-cutoff-summary.md)。该自定义截止汇总不提升正式验收或证明PP覆盖之外的正确性。
