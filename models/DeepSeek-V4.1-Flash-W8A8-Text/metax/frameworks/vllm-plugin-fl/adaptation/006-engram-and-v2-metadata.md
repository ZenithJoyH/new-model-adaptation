# 006：Engram数值与V2请求元数据边界

状态：2026-11-04，纯CPU元数据在102验证通过；GPU数值部分仍为修改前设计。目标仍为mx-102/103实际适配容器；
FGV安装树 `/opt/FlagGems-vllm`，Plugin安装树 `/opt/vllm-plugin-FL`；vLLM只读。
保持原mHC和005切片，不引入另一份源码导入路径，不顺带移植V1 runner或视觉/MTP功能。

## 已确认契约与复用边界

本机只读参考 `DeepSeek-V4.1-Flash-W8A8-BF16/inference/model.py:Engram` 与
主线初次支持提交 `e77daef89e18e08321ae7b8b24827eedd5fe8673` 的
`vllm/models/deepseek_v4_1/common/engram.py` 给出相同门控数学：逐HC分支FP32 RMS、
q/k权重乘积、归一化点积、带符号sqrt(clamp(abs(dot),1e-6))后sigmoid，最后将完整残差和门控值转BF16。
不能替换成会在归一化后先物化BF16的PLE gate。FGV全树未发现Engram/ngram公开等价实现；
已检查qwen4 PLE邻近实现，语义/状态不同，不复用其计算。

目标权重头信息与主线FP8表不同：第1层表 `[384006168,256]` INT8、scale `[384006168,1]` FP32；
第14层分别为384016682行。两层wkv均为 `[25600,6144]` INT8、scale `[25600,1]` FP32；
q_weight/k_weight均BF16 `[4,5120]`。因此使用005的量化Linear处理wkv，表查找需专门的INT8逐行反量化。
表按完整hash head的连续桶区间做TP8分片，每rank24/8=3个head；不能把主线FP8/UE8M0直接套用。
读取的只是safetensors header，未声称本轮读取或校验了大权重payload。

V2 `init_model_state` 已有模型公开 `get_model_state_cls` 扩展点，当前WorkerFL可选原生V2 runner。
沿用主线的GPU token history获取chunk之前3个token，再结合当前chunk的input_ids；
不能从异步调度下包含placeholder的CPU token表推导已生成token历史。
当前vLLM没有CircularBufferSpec；这不影响无slot cache的V2 Engram哈希。
注意力compressor状态的spec兼容属于后续独立切片，不把Engram成功当作缓存接入通过。

## 修改前清单与调用链

| 组件/文件 | 计划符号与必要性 | 验证边界 |
|---|---|---|
| FGV `ops/engram.py`（新增） | `engram_ngram_hash`：消费框架构造的原始token history，完成compressed-id映射、INT64乘法/XOR/mod及全局桶offset | 独立Python整数oracle；缺失历史、负ID、padding、int64范围、多个layer、空N及新输入graph |
| 同文件 | `engram_embedding_int8`：读本rank连续INT8表及FP32逐行scale，返回全新BF16局部head结果 | 独立CPU逐行反量化；invalid/非本rank ID写0；strided hash view、offset、tail、空N、输入不变及graph sentinel |
| 同文件 | `engram_gated_add`：逐分支FP32门控与BF16残差输出 | 独立CPU高精度参考及BF16边界，零输入/负点积/近零、mask、shape/dtype拒绝、graph新输入 |
| FGV公开导出、operators.yaml及既有nvidia/metax tuning配置 | 在原机制注册3个API；无第二套dispatcher；采用原libentry/libtuner | 导入/实际命中、原调用方、静态hook；NVIDIA硬件未验证须披露 |
| FGV `tests/test_engram.py`、`benchmark/test_engram.py`（新增） | 数值、实际graph、固定模型shape与边界case的原生测量 | 显式调用库公开API；独立reference；不得用mock或受竞争性能作通过 |
| Plugin `models/deepseek_v41/engram_metadata.py`、对应unit test（新增） | 先独立提供纯CPU tokenizer归一化、prime桶/TP8 shard及确定性乘数元数据，保存不可变tuple，避免模型初始化的默认CUDA上下文影响 | 实际表行数精确一致、TP区间无重叠/遗漏、Unicode/UTF8 byte token、全局RNG不变；实际tokenizer压缩词表应为99092 |
| Plugin `models/deepseek_v41/engram.py`（新增） | tokenizer压缩映射/prime桶布局、INT8表及scale权重加载、TP gather、staging所有权与Linear编排 | 配置/权重mapper/TP边界单测；真实小表加载；进程内不假装已证明TP8通信 |
| Plugin `models/deepseek_v41/model_state.py`（新增） | V2 lookback及history复制元数据，按真实请求/位置区分chunk；原生ModelState公开扩展 | 请求重排、不同chunk起点、padding、prefix命中与decode历史、PP+async整模回归 |
| Plugin既有dispatch中的contract/注册/薄调用桥及相关测试 | 接入FGV公开3 API，计算前选实现、执行异常直接传播 | 命中/不命中、能力缺失、参数与out mutation、异常不重试 |

数值API输入必须同设备；shape/dtype/layout不符合在launch前明确失败。
原始history为 `[N,4]` INT32/INT64，shift0为当前token，向过去排列，负ID为缺失；
token_map为INT32；multipliers、prime及offset为模型初始化验证过的INT64布局。
按原参考，一旦越过序列开始或遇到无效token，后续更早项统一使用compressed pad id。
乘法使用INT64，布局初始化保证非负乘积不溢出；hash结果为INT32 `[N,L,24]`。
GPU数据定义域和invalid-id行为必须在实现及测试中明确，不能通过未屏蔽的地址访问处理padding。

表lookup读取 `[N,24]` 的strided hash view，输出为BF16 `[N,local_heads,256]`；
初始API返回新结果，避免引入自定义out alias契约；所有非法/非拥有位置写0。
Plugin通过普通ATen copy_写入自己预分配的稳定staging，遵循FlagGems自动替换约定，
并在模型集成检查实际dispatch与捕获行为。这里不新增Plugin数值kernel或逐算子ATen adapter。
算子不持有跨调用状态，不自行创建stream或持久workspace；Plugin管理分片参数、
hash/history和lookup staging生命周期，复用当前计算/capture stream。

门控输入为BF16 hidden `[N,4,H]`、kv `[N,5H]`、q/k权重 `[4,H]`；可选BOOL token_mask `[N]`。
门控为false时保留有限值原残差。已在实际容器CPU/CUDA核对：单元素负零乘积经Torch sum后为正零，
本机copysign参考输出为+0.000499725341796875；GPU实现按该reduction边界处理零值，再执行带符号sqrt，
增加H=1回归，不能直接保留乘积负零并当作参考点积符号。输出全新BF16 `[N,4,H]`。

## 仍需完成的门槛

实现前冻结各被改注册/配置文件原hash和当前dirty集合；确认当前主线相关正确性修复，保留来源版权。
每个数值API完成独立、真实分发及graph测试后才接模型。必要FP32投影、BF16物化、
TP gather和Engram注入顺序均需与参考逐项对齐；PP首个本地层若为Engram层也必须执行注入。
主线初次实现的该分支不能未经验证照搬。最终默认20/20分层仍需实际显存及KV共享边界验证。

适用plugin:A1–A4/B1–B4/C1/C2/D3/E1–E4/F1–F4/F7及operator对应实现/分发/数值/graph/benchmark条款。
缺失的FGV optimization.md/deep_opt.md按001已记录替代依据处理。
资源竞争尚未解除时继续独立实现/诊断，受影响的性能准入、TP8×PP2整模、精度及交付保持未完成。

另已读取主线固定提交 `43067f6df60e2eafba5797908484cc1c12e4a48b` 的新路径
`vllm/models/deepseek_v41/common/engram.py`（Git blob b88293037ea20d1e9b3d6aa4fcbfa9cbf7f0d0de）。
与初次提交逐函数比较，token-map、乘数、hash kernel和gate kernel文本完全一致；
新增DP共享/offload/预取路径不属于本次DP=1、HBM表的初始范围。不能据此声称整个当前主线都无正确性变化。

102纯CPU元数据9项通过，真实tokenizer/bucket核对通过。报告
`02-issues/v41-engram-metadata-20261104/mx-102/metadata-review-v1.json`，SHA-256
`63c5d7f65838323d897ade0c694af737515f2e492d9ed1f6d803f782bf5cea64`；
129280→99092的INT32映射SHA-256为
`c60a86322ec17b4142bfef3c57a8d81fb428550cdf487f88a4320cb59fe46481`。
此结果只证明processor/桶布局，尚未加载表payload或执行数值Engram。

102新增FGV三API首轮72 passed、1 failed：组合测试误按两项解包原有三返回值量化API，
未发生Engram数值失败。修正测试解包并显式断言azp=None后，原全部73项在实际硬件通过，
包括超过2^31元素的INT8表寻址、H=1负零乘积边界、三API新输入graph以及
hash→lookup→原有W8A8投影→gate的独立CPU整链对照。
日志`04-runs/mx-102/engram-operators-v2-20261104.log`。当前尚未做受控性能或103验证。
新增`benchmark/test_engram.py`沿用原Benchmark；lookup仅用65536行工作集，
基线先gather INT8再反量化，不转换整表，也不能把该微基准当成真实12GB/rank表吞吐。

V2元数据实现前细化：当前镜像的InputBatch公开query_start_loc、idx_mapping、is_padding，
RequestState公开GPU all_token_ids和num_computed_tokens，与主线lookback来源相同。
因此可在Plugin `DeepseekV41ModelState.prepare_inputs` 一次构建稳定INT32 `[padded_tokens,4]` raw history；
当前chunk优先复制input_ids，跨chunk从对应request的GPU committed history复制，
padding、非法request索引或历史位置写-1。该kernel仅复制token元数据，按plugin:A3保留Plugin，
不合并compressed map/hash数值计算，不另行维护lookback副本，不读取CPU占位token。
文件限`models/deepseek_v41/model_state.py`及对应functional测试，暂不注册整模型。
验证多请求重排、chunk/prefix边界、已生成token、未commit当前chunk、重复padding边界、
非法映射、容量、dummy准备和新输入图回放；准备阶段更新稳定buffer，模型图消费该buffer。

102 V2元数据29项通过，日志`04-runs/mx-102/v41-model-state-v1-20261104.log`。
WKV资源修正后W8A8与Engram合计192项通过；实际量化加载/graph扩展33项通过。
两组件精确源码快照的适用hooks通过，FGV用已核实的相同版本官方源替代不可访问Gitcode镜像，
不修改安装树hooks配置；Plugin typos排除全部本轮Python路径，ShellCheck无适用文件。
静态快照不代表全仓检查或完整适配通过。peer v9切片manifest SHA-256
`840a029bdc619f4ec831064ce1392c0216aca2607f04dbf5f7868043bec3c0ee`，103独立复测中。

模型编排切片改前细化：新增`models/deepseek_v41/engram.py`，只含token-map常量、完整head桶
INT8/FP32参数加载、框架稳定staging、既有TP gather和ReplicatedLinear编排；
新增`dispatch/backends/flaggems/impl/engram.py`及既有`register_ops.py`中的三个可选注册。
公开契约位于薄adapter的显式签名/docstring，沿用既有可选op注册与resolve机制，
不新增dispatcher，也不扩展抽象backend接口来影响无此能力的其他后端。
增加`unit_tests/dispatch/test_engram.py`及`functional_tests/models/test_deepseek_v41_engram.py`。
先resolve lookup/gate，再lookup及ATen copy_写staging；执行错误不重试。先支持TP、HBM、BF16，
SP入口分配前显式拒绝；无本任务支持证据的V1 slot cache/CPU offload/预取不接入。
验证严格dtype/full-shape和TP8桶区间加载、真实小表+W8A8+gate独立CPU对照、三个公开API实际命中、
实际tokenizer冻结映射、新hash/hidden/scale/mask图回放及容量/能力缺失前置拒绝。
单进程TP rank隔离的加载测试不等价于TP8 collective；整模与真实TP8通信仍需后续证据。

103 v9复测完成：221项FGV算子（包含原mHC29项）、85项Plugin单测（另2项原Ascend skip）、
62项真实W8A8/V2 metadata功能检查均通过；日志`04-runs/mx-103/engram-*-v9-20261104.log`。
此切片尚不包含正在102验证的Engram模型编排模块。
102新编排首轮：35项新/受影响单测通过；15项功能检查中10项通过，5项在构造LinearBase前
因测试仅隔离parameter模块而遗漏linear模块导入的TP rank别名报错，尚未进入数值计算。
仅补齐测试的rank别名隔离并重跑原全部用例；不改产品数学、容限或跳过失败参数。

102编排v2：35项单测、原全部15项真实功能检查通过；实际tokenizer映射指纹和两层整数hash对照通过。
新五文件连同前述Plugin修改的精确快照通过7项适用项目hooks，非全仓检查。
另补v3测试单独验证FlagGems ATen归属：直接`flag_gems.copy_`做数值检查，
再使用既有`use_gems(include=['copy_'])`自动替换普通Tensor.copy_，
观察真实copy内核路径处理本层staging，并覆盖新输入graph replay；退出恢复注册上下文。
这不替代最终服务Worker中实际自动启用状态的取证，不新增Plugin逐ATen适配器。

v3原全部加自动替换两项共17项通过，含真实FlagGems copy_计算、普通ATen staging实际命中与新输入graph。
当前Plugin切片适用hooks再次通过，源码快照未被hook修改；尚待103同步该五文件模型编排增量。

103五文件增量已同步，manifest SHA-256
`9196802e08f6495b23cbcdbafa770e9585e2a803b1302ce172fa750159f962e3`。
独立复测95项单测通过（另2项原Ascend skip），79项真实功能检查通过，
包含17项Engram编排/ATen自动命中、29项V2 metadata及33项W8A8加载/graph。
日志`04-runs/mx-103/engram-plugin-*-v11-20261104.log`；整体模型、真实TP8 gather和PP+async仍未验证。
