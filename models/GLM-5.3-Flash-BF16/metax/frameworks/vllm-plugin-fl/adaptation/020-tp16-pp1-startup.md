# TP16 / PP1 双机启动与推理检查

## 2026-11-03 恢复正常服务，精度暂停

用户将当前范围收敛为“先不进行精度评测，先能正常拉起服务”。本轮没有发起GPQA请求；已精确停止本任务eager对照客户端及两机eager服务，原有容器均保持运行。整模eager/graph数值对照、正式sanity、GPQA、性能与镜像验收继续未完成，不由本次启动检查推导通过。

两机继续使用原 `glm5.3-flash` 容器和批准根 `/public-flash/jinghao/glm5.3-flash`，以同一 `start-model.sh` 无参数启动：TP16、PP1、2节点各8卡、BF16、65536上下文、前缀缓存开启、`FULL_AND_PIECEWISE`、`VLLM_FL_USE_FLAGGEMS_VLLM=1`。本次恢复未修改产品源码和根启动脚本；脚本SHA仍为 `b4b959abacc49bb51a7984bd1bf2309db06a37239b69e63413a0d037be9ea2c8`。

当前服务运行ID为 `glm-execution-normal-gpqa-a1-20261103`（名称沿用已准备计划，不表示运行GPQA）。101 API PID为1754670、worker为1754992～1754999；102 headless PID为1123493、worker为1123766～1123773。各自 `01-environment/<run>/<host>/startup-manifest.json` SHA分别为 `ebbc1a2670b14eed2533b5cd146c4df631285271699e8869cc428e91a41c109b`、`90c42eb897be8783547bb0f68627e6e3ea88b6fd0bca501e58cb3e787fa59051`；完整日志为 `04-runs/<run>/<host>/stdout.log`。实际argv核实无enforce-eager/图统计参数，101日志记录PIECEWISE捕获5/5、decode FULL捕获4/4与Application startup complete。

101的18530端口 `/health` 返回200，`/v1/models`包含 `glm5.3-flash`。`glm-startup-only-a2-20261103` 只发出一次非GPQA算术请求，零API重试，最终文本为 `4`、finish_reason为stop、HTTP200、耗时27.486秒；这是启动后单次请求，不作为性能指标。回执 `01-environment/glm-startup-only-a2-20261103/mx-101/result.json` SHA为 `8b65451d4f93eb7f772e80fd40b3067b8fb8726f86ccdb00ff163acadb4ac2bc`，原始响应在 `04-runs/glm-startup-only-a2-20261103/mx-101/response.json`，SHA `0f16743fb44e3907f6dada5d89f5224e08411cd6cb9e372f7f707c00c9f63a75`。

保留启动日志中的算子注册警告与FlagTune缺少可选xgboost的默认策略选择记录，尚不声称这些警告已定位修复。最初CPU启动检查a1先于101状态文件创建而失败，没有发送生成请求；原失败保留。额外进程取证a1对worker继承环境的假设不成立，原失败也保留；a2区分launcher环境和worker exec-start环境，记录实际TileLang TVM路径，不改变服务环境或放宽正式验收规则。

两机 `01-environment/glm-normal-startup-observed-a2-20261103/<host>/verification.json` 均通过启动取证，分别核对实际8个worker、root PID/start_ticks、正常argv、前缀缓存和当前源哈希，保留当时日志快照；SHA：101 `8c7bd3aeb1277a522410b88303ab950dbce6a46c65f9290547e8e93cf5897d16`、102 `aefa89be817f08f782969cba38485d960bab0d272e22a352624e068558481878`。此回执仅为启动观察，不是正式framework执行模式或精度验收回执。

下文为此前各轮历史，当前运行进程以上述恢复实例为准。


2026-11-03当前结论：两机原 `glm5.3-flash` 容器的TP16/PP1服务已用最简共享脚本启动并保留运行，FULL_AND_PIECEWISE功能验证通过。诊断实例记录97次decode FULL、1次短prefill PIECEWISE；最终无诊断参数实例的2文本+1图像均正常结束、内容审阅通过。两机当前8文件来源各242项单元、16项GPU图回归通过，真实TP16通信图200次变输入重放通过。下列a1至a5失败及旧a6（20261102）均为保留的历史；最终a6（20261103）证据在本文末尾。

本轮新增4个产品文件改动、4个既有测试文件改动，无新增测试文件：按真实backend能力声明支持单token decode图，处理聚合KV spec；固定Kpool槽位metadata地址与padding刷新；撤销MetaX原地all-reduce覆盖，复用原生custom-op/PyNccl分发并补齐已有平台能力名单。完整增量diff SHA `67f43dfce8594816e9d2b5f5563f2f2127c2d2dae754b2b9f126d61998a459fb`。本轮未改FG/FGV数值实现、vLLM/Torch/SDK。capture上限仍为16 token，超限prefill按原生NONE路径；未宣称所有prefill进图。正式eager/graph数值验收、GPQA、性能和镜像交付保持未完成/暂停。

a4后续整模仍失败：原生统计确认3 token填充至4，成功记录FULL执行23+2次，之后停滞。四个抽样worker（两机各两个）的非阻塞Python栈均停在MLA builder的pageable CPU请求编号H2D copy；101输出线程等待GPU事件。该栈不能独立证明拷贝就是根因。约337.746秒后三个请求均HTTP500，vLLM执行响应队列超时，源码未变；两机原任务进程组最终均为空。原始响应与日志保留，25次执行不等于完整生成通过。后续原生栈采集时进程已退出，失败回执保留，不能声称取得有效原生栈。

下一诊断限定为配置单变量：保留a4所有源码与FULL_AND_PIECEWISE，仅在临时派生入口增加原生 `--no-async-scheduling`，保留图统计以核对成功decode；不加CUDA_LAUNCH_BLOCKING、不改根b4脚本、不同时重写请求编号算法。判断异步输入准备/输出回传与整图执行依赖是否有关。此前11-01关闭async的旧启动失败发生在不同阶段，不能支持或否决本次已修tail地址后的诊断。本轮若关闭async也失败，继续依据该轮首个证据定位，不把配置尝试包装为修复。适用plugin:E3/E4/F2/F3，正式验收保持未完成。

2026-11-02 固定tail槽位缓冲区组件验证完成：`glm-tail-graph-patch-a4-20261102` 两机均rc0；旧实现各2项CPU状态负对照、2项GPU图负对照按预期失败，修复后各226项单元、16项GPU图检查通过，无error/skip。覆盖固定capture下4→3→1→4请求、槽位地址与全padding刷新、独立CPU参考、显式公开ATen与自动替换路径以及NaN输出sentinel。原始XML/日志仍在同名 `04-runs/<run>/<host>/`；after-manifest在 `01-environment/<run>/<host>/`，SHA：101 `a1faf4d013757adb494a62cc1bc62167b29b5402f97ed053c1e53fb9bd4ad078`，102 `42419bfc5aa3e1c744de257fac3aab31837a32878014021d46c28fb955fccbfd`。

新增产品文件kpool.py SHA `a767ba206c9df5080075eb6d7788c5c8f60a17b47409fc8e4d48448e66e73ee7`；既有test_cache.py为 `d6b5411930a247c0964ff670368facbbf15f4ad8cee919a7811e9cb43b445543`，功能图测试为 `fb42600276052a28781e93dce80026c5f5eaf1d89aa3ccd81954f77b96177785`。本次图适配总计两个产品文件、三个既有测试文件，完整增量diff SHA `23075f944ce98e094f26b2d7455b20dbdf4eafd92c23eec77ac8ef80c45fc4fb`；全hunk复核及新增三文件Ruff检查通过，FlagGems/FGV数值源码与vLLM未改。

a3失败时scheduler记录三条cached请求、各1 token的纯decode batch，原生wrapper返回0不能作为功能通过；两机进程组已核实为空。新普通环境诊断服务 `glm-full-and-piecewise-metrics-a4-20261102` 已启动，取消CUDA_LAUNCH_BLOCKING，仅保留原生图统计观察参数。101 wrapper815819/API815825，102 wrapper208255/headless208261；startup-manifest SHA分别为 `c960ae1cd5fc8da06ad59a425832f650e7196234f57969a762661ddf39acf14b`、`13a5098248a7c3950f2e525b730f826f30cbe1c63d48c060ae3277ad862fd814`。目前仍在整模初始化，组件结果不能代替a4实际生成；最终将恢复无诊断参数的b4b959根脚本实例，精度/性能/镜像仍暂停。

2026-11-02 a2整模结果为失败：PIECEWISE 5/5、decode FULL 4/4捕获后API就绪；三路算术请求均在约69.515秒返回HTTP500，引擎退出。两机服务wrapper因原生关闭路径返回0而显示passed，这不代表功能通过。设备精确trap为MetaX `index_select_kernel` 非法访存；之后fill_/同步事件的Python栈为异步上报，不据此修改fill算子。原生图表只记录NONE batch23/47，尚无成功FULL运行统计，不能把失败归为已证实的FULL成功重放或断言完全未进入失败的FULL步骤。原始响应在 `04-runs/glm-graph-functional-metrics-a2-20261102/mx-101/`，原服务日志与来源保留。

独立102合法索引复现 `glm-index-select-graph-probe-a1-20261102` 通过：实际公开 `flag_gems.index_select` 来源为 `_metax.ops.index_select`，覆盖一维page table、三维strided tail和一维strided请求表，eager及自动替换后各3次变输入重放均正确。CUDA_LAUNCH_BLOCKING=1也可完成该图测试。没有据此修改FlagGems。新a3整模诊断只加同一同步报错环境和原生图统计，源码仍为a2，正在获取首次准确异常。

新增已确认的metadata缺陷：CPU独立复现 `glm-tail-metadata-address-cpu-a2-20261102` 中，两次实际 `KpoolTailMetadataBuilder.build` 返回不同地址，原持有的槽位仍为[12,21,-1,-1]，新构建为[30,39,-1,-1]，捕获地址内容未刷新。诊断进程隐藏全部GPU，只模拟导入时硬件能力；a1探针因导入查询GPU失败的原始记录保留。该结果证明地址/状态契约风险，但尚不能单独证明整模非法访存唯一根因。

修复前限定新增范围：Plugin `models/glm5/kpool.py::KpoolTailMetadataBuilder.__init__/build`、既有 `tests/unit_tests/glm5/test_cache.py`、既有 `tests/functional_tests/compilation/test_graph_capture.py`。builder预分配scheduler最大token容量的int64槽位缓冲，每次有positions时清空padding并拷贝循环槽位到同一地址，返回相应prefix view；独立compute函数和无positions时原始mapping的身份语义保持。增加旧实现负对照、固定capture下4→3→1→4状态刷新/地址/无效padding、独立CPU索引参考和GPU变输入重放；不新增文件或数值kernel，不改第三方。先102后101，在服务停止释放本任务显卡后执行GPU检查；运行中的a3源码不改写。适用plugin:A3/E1–E4/F1–F3、operator:E4，整模关系继续由新实例验证，不把局部缺陷修复冒称整模通过。

2026-11-02 聚合 spec 修复的两机组件结果：`glm-decode-group-patch-a3-20261102` 两机 wrapper均rc0，新增12例在旧实现各6项预期失败；修复后各144项单元、14项GPU图测试通过，无error/skip。两机最终 `mla.py` SHA为 `a91441461265b3ed674d806d7c2c8afd1419c3f6aafb8adcd2d47a12b0ace937`，`test_mla.py` 为 `b47a078f23d0ed20d428dda1103c80a7aa90f0207db0f657250f118263a89751`，功能测试仍为下文d88b4c。after-manifest位于授权根 `01-environment/glm-decode-group-patch-a3-20261102/<host>/`，SHA：101 `928fe2ee2e6c3a3d1915cbb5c81664b916ac1aa1c2798fd5cb278b1498dd3d65`，102 `a4317ccf9acf256eba050d2e5bb271eb51ac3f8b9efc0c66e34cf40e86f6d524`。除本次两个文件外，受保护源码及vLLM均未变化。当前完整三文件图增量diff SHA为 `8b78b92c0cb639b08d5e6813c5613b759b04db1640467da66f3c49dcfa5e1682`，仍未修改数值实现。

a1诊断服务已按PID/start_ticks/会话精确停止，两机 `01-environment/glm-graph-diagnostic-stop-a1-20261102/<host>/stop-result.json` 均remaining为空；停止后原始日志中的MCCL连接中断属于受控停机阶段，不混作新根因。新a2诊断实例为 `glm-full-and-piecewise-metrics-a2-20261102`：101 wrapper640910/API640916，102 wrapper35529/headless35535，仍使用b4b959根脚本加单一原生图统计参数的派生入口。对应startup-manifest SHA：101 `754a85fd75c63ff12e12565ae67740b6021fa897cc8916ccb0d72411fb8544a3`，102 `beda3da90d6dcc2d8dc7c347a8a94f61946159171a62633225d49c8efef6bcff`。目前权重加载在推进，尚无a2服务就绪或生成结论；以下a1和更早结果为按轮保留的历史。

2026-11-02 整模 a1 出现新的接口阻塞：八个101 rank报告 Sparse MLA 为 NEVER，并自动降为 PIECEWISE。当前 vLLM 的整模能力查询传入 `UniformTypeKVCacheSpecs` 聚合对象，它只有逐层 `kv_cache_specs`，没有单层 `head_size`；metadata builder 初始化时则收到拆出的单层对象。这解释了独立图测试通过而整模能力查询失败。a1自动降级日志保留，不算目标模式成功。

修改前追加限定：只改 Plugin `mla.py::FlagGemsSparseMLAMetadataBuilder.get_cudagraph_support` 及既有 `test_mla.py`。处理原生聚合类型，通过 `compilation_config.static_forward_context` 的已注册 backend/builder 身份筛选属于本后端的层；其他 indexer/cache 的头宽不能否决 Sparse MLA，但任何属于本后端的不支持头宽仍须拒绝。空聚合、缺失层映射、无目标层保持 NEVER。增加原生聚合规格、混合后端、混合头宽、无支持层和缺失映射回归，先保留负对照，再验证修复与既有单元/图测试。无数值 kernel、FGV 或 vLLM 修改。精确停止 a1 服务后在新 a2 run 验证，不覆盖旧来源和失败日志；适用 plugin:A3/B3/C1/C2/E1/F1–F3，整模图结论仍待实测。

2026-11-02 混合图组件结果：两机实际安装 Plugin 的 `dispatch/backends/flaggems/impl/mla.py` 已将已验证的 BF16 sparse pair 绑定标记为 graph-safe；backend 与 metadata builder 共同仅声明 `UNIFORM_SINGLE_TOKEN_DECODE`，支持512/576头宽，未知头宽仍为 NEVER。数值方法、cache writer、索引映射和 head padding 均未修改，未改 FG/FGV 或只读 vLLM。回归收敛在既有 `tests/unit_tests/glm5/test_mla.py` 与 `tests/functional_tests/compilation/test_graph_capture.py`，不新增测试文件。

两机各自保留3项旧声明预期失败的负对照、旧声明下12项完整计算链 GPU 通过；修正声明后各132项单元与14项GPU图检查通过，无失败或跳过。12项完整链测试覆盖512/576头宽、实际8/128头、topk80/2048、非连续cache及 FlagGems ATen 替换开/关，固定capture batch4下运行4→3→1→4，每轮更新Q/K/RoPE、索引、block table、slot mapping，独立CPU参考与eager对照、独立输出NaN sentinel、全cache与padding守卫和输入不变性均检查。另102公开 FGV sparse 算子8组形状、16轮变输入replay通过。释放本任务服务后未复现先前并发探针的queue失败；这不证明其驱动根因已解决。

原生组件证据：授权根下 `01-environment/glm-decode-graph-patch-a1-20261102/mx-102/` 与 `01-environment/glm-decode-graph-patch-a2-20261102/mx-101/`，相应XML/日志在同名 `04-runs/`。after-manifest SHA分别为 `8e8f6d67d62481e970c39a37cdfa40053673c90c7bf6061df0700df9e436374f`、`6d3da03c69838110e7c3424432d563f5ac8f0ef73e4073505ba2c74f1aa3e070`。102 wrapper在所有检查与manifest写完后因最终print的重复host参数退出1，原失败state保留；`independent-verification.json` 重新读取XML、三文件哈希及受保护源码后确认component_verified，不能把原wrapper改写为通过。101修正该诊断尾部后wrapper通过。

三个最终文件SHA：mla.py `28564989b46318f095b1b1dfad98a0887b31b0a5bceaae8e0b79cd6730e1586d`；test_mla.py `20d22e344827eed4d3ef3df74c1ffc17ef4f579aa04ef954d02e395787561011`；test_graph_capture.py `d88b4c6706571ba12c5f9e2fc1427a9b3c75a5783e05429924efc94d4d1ded14`，两机一致。两测试Ruff lint/format通过；mla.py原有两处F401在修改前后相同，未夹带无关清理。已复核增量hunk，但完整模型图执行、当前来源eager/graph精度比较和benchmark仍未完成，不据组件结果提升正式验收。

整模已启动新诊断run `glm-full-and-piecewise-metrics-a1-20261102`：102 wrapper19983/headless19989，101 wrapper625078/API625084，原容器保持运行。共享根脚本仍b4b959；临时派生入口只增加原生 `--cudagraph-metrics`，用于观察实际Runtime Mode，SHA `946fb12f9964c0ac1b4f8fc9d18d6b49fb3a41056295b87f932edc32cfaf7dbd`。这不是最终launcher或正式验收实例；待整模capture与请求验证后，以未改动根脚本重启并再次核对。当前只确认初始化在推进，尚未服务就绪/生成。GPQA、正式性能与镜像继续暂停。

2026-11-02 用户授权尝试 prefill PIECEWISE + decode FULL，即 FULL_AND_PIECEWISE。本轮选择当前 Plugin/FGV 上的图适配与双机服务验证，不恢复 GPQA、正式吞吐验收或镜像交付。当前 Sparse MLA 三处 NEVER/false 声明与已无 host scalar read 的实现不一致，但须先验证 cache writer、索引映射、head padding、sparse kernel 全链路真实 capture/变输入 replay 才能放开。候选产品范围限定 Plugin dispatch/backends/flaggems/impl/mla.py 的 sparse binding、graph support 和必要 metadata 地址/长度处理，已有 unit_tests/glm5/test_mla.py 及功能测试；只有复现需要时才修改已核实的 FGV 算子/测试。声明最多为 UNIFORM_SINGLE_TOKEN_DECODE、仅支持的 BF16/512或576头维度，不宣称 mixed/full-prefill 支持，不直接把 NEVER 改 ALWAYS。vLLM/Torch/SDK只读，现有厂商修复与上一轮八文件结构调整保留。

双机原 a6 API65987/headless3660448、原 wrapper 会话及每个后代 PID/start_ticks 已只读冻结；先102后101按精确身份停止本任务服务释放资源，原容器保持运行，不再与占卡服务并发运行101图探针。旧服务被停止属于本轮有意切换，不重写此前功能/失败记录。独立图探针及组件回归通过后，修改前备份实际安装文件、补齐守卫/失败/状态测试，先102再101同步；最终继续使用根级 b4b959 共享 launcher 正常prefix配置重新启动TP16/PP1，核对16rank实际模式/capture/replay及新输入推理。仅服务就绪、请求参数或自动降级不能当成目标模式通过。既有 FULL 受 MLA/indexer 能力限制的历史证据保留，本轮目标明确为用户指定混合模式。适用 plugin:A2/A3/B1/B3/C1-C4/E1-E4/F1-F4、operator:B3/C1-C6/D2-D5/E1-E6；所有未通过的 GPU/整模/性能门禁保持未完成。

2026-11-02 结构调整已落实并完成限定回归：102 试点通过后同步 101，同一八文件补丁已写入两机原容器的实际安装源树。Prefill 的平台准入集中于 MLA provider 的 supports_platform，backend 可用性复用同一 provider，GLM 在构造前通过现有 call_op(mla_prefill_backend) 选择类，移除了模型和 backend 中分散的 MetaX 判定。Sparse MLA 的候选参数已从公共算子移至 MetaX/NVIDIA 既有 YAML，由真实 ConfigLoader 加载；所有数值函数的参数与主体 AST 相等，候选 tile/warps/stages/num_ctas 逐项相等，原 autotune key/机制保留。

两机各自旧实现负对照为 14 项中 8 项预期失败、6 项通过，0 setup error/skip；新实现各 64 项 Plugin 单元/适配器契约回归、7 项 FGV 配置/ABI 检查通过，0 失败、0 跳过。覆盖按策略返回自定义 backend、原守卫不命中、无 vendor 属性、API 缺失/禁用、选择失败在构造前上抛、重复/异常回滚，以及独立 CPU oracle 的 padding、out 身份、LSE、new/context causal 语义和 output_scale 拒绝。FGV 检查同时证明 MetaX、NVIDIA、默认回落的配置和实际 autotuner 配置一致；这些检查不是 GPU 数值、capture/replay 或 benchmark 通过。

原生备份、计划、增量 diff、源码/测试哈希及最终回执位于授权根 /public-flash/jinghao/glm5.3-flash 的 01-environment/metax-dispatch-cleanup-a1-20261102/<host>/；XML、负对照和回归日志位于 04-runs/glm-metax-dispatch-cleanup-a1-20261102/<host>/。after-manifest SHA：102 66aca68311503d1f683bfd971d726b1371e99e496d8c05539ee760df82ed11ec，101 4589375ba1610e6679c518694de3aed4235c96383e91a3e732d9942ecfd33229。最终回执 SHA：102 035d92364f9efd658eb333c36af5569fdb58737696790f4b03bfcb98b282cf0e，101 afd59b0ee56fbeb0efee44c86e456941a5e4c583b715173de2f1f62f76883a7e。

终态复核两机原 CID、running/RW 映射、只读 vLLM HEAD/status/diff、其他受保护的 Plugin/FGV/FlagGems 源码均保持原样；原 API PID65987、headless PID3660448 的 start_ticks 不变，101 /health=200，共享 launcher 仍 b4b959。运行中的 a6 服务未重启，尚未按本次源码重新启动或验证整模推理。尤其普通 CUDA GLM 改走既有可移植 FGV provider 的真实 NVIDIA 数值验证仍缺，不能用 mock/CPU oracle 充当硬件通过；旧 a6 功能证据、历史 GPQA 和旧镜像也不覆盖本次源码。FULL_AND_PIECEWISE 的 NEVER/自动降级与此前 MACA queue 阻塞没有在本轮修复，formal_acceptance=false。Worker、MCCL、编译产物兼容、卷积/FP8/TLE 路径均保留，未重新运行用户选择保留未验证的 101 并发 GPU 图探针。

五个相关 Python 文件 Ruff lint/format 通过；完整增量 diff 逐块核对，Sparse MLA numerical AST 等价检查及最终文件哈希核对通过。本轮 scripts/syntax-check --offline 通过 341 项（19 skip）和 7 项运维回归、13 shell/3 playbook 检查；结构审计为 0 error/14 条历史 warning。git diff --check 通过。以上为本轮交付范围，下列计划及只读审查文字保留为历史，不表示仍未实施。

2026-11-02 用户已授权落实上一轮结构审查。改前限定：两机原 glm5.3-flash 容器、批准根 /public-flash/jinghao/glm5.3-flash、原 CID/RW 映射与 agent 控制模式重新核对；直接修改 Plugin 7094141e 与 FGV ddce1d66 的已安装源码，不更新版本、不切换导入副本。范围为 Plugin 的 attention/mla_prefill.py::is_available、dispatch/backends/flaggems/impl/mla_ops.py::supports_platform/is_available、models/glm5/model.py::Glm5NextMLAAttention 构造，以及既有 tests/unit_tests/glm5/test_runtime.py；FGV 的 ops/flashmla_sparse.py 调优装饰器、MetaX/NVIDIA 两个既有 tune_configs.yaml、既有 tests/test_flash_mla_sparse_fwd.py。总计八文件，不新增独立测试文件。

预期行为：平台准入集中在现有 MLA 分发 provider，prefill backend 的可用性复用它；GLM 在构造产生副作用前通过已有 call_op(mla_prefill_backend) 选择 backend，保留 NVIDIA reference/非目标平台守卫和临时 patch 回滚。普通 CUDA GLM 也采用该 provider 已提供的可移植 FGV backend，旧 legacy 类及其其他调用者不删；padding/out/LSE/chunked-context/output_scale 契约用独立 CPU oracle 验证，真实 CUDA 硬件尚未验证。MetaX 原本已使用此 portable backend。

FGV 开发前项目事实/契约/路径：已安装 editable /opt/FlagGems-vllm；本轮只是配置来源迁移，不写 kernel，不改变公开签名、输入/输出、dtype、mask、空行或 state 语义。保持 MetaX BK16/BH16/warps4/stages1 及默认 NVIDIA BK64/BH64/warps8/stages2或4，改用既有 runtime.get_tuned_config 和厂商/默认 YAML 优先级。保留原 triton.autotune 与原 key 作为本轮明确豁免，不同时切换为 libtuner，以免结构收敛夹带调优机制、cache 或测量行为变化；kernel 主体 AST 必须不变。无新 build、导出、注册或 benchmark 文件；本轮不比较性能，已有 GPU queue 阻塞及用户不跑 101 并发图探针的选择仍有效，数值/graph/benchmark 门禁保持未验证。目标缺少 optimization.md/deep_opt.md 已按固定 revision 的 tracked 清单复核，以现存 workflow 和本项目算子标准继续，不声称阅读缺失材料。

验证方案：先102备份八文件与只读vLLM身份，新增测试对旧实现留负对照；再验证新分发路径、策略禁用/API缺失、无vendor属性、构造前失败传播、重复/异常恢复、adapter的padding/out/LSE及chunked context。通过真实 ConfigLoader 验证两厂商和默认回落的全部候选参数，并验证实际 autotuner 引用该配置。测试不启动服务、不执行 GPU kernel/capture；失败则恢复本次八文件。102通过后101串行同步同字节补丁并重跑。适用 plugin:A2/A4/B1/B3/C1-C4/D4/F1/F2/F4、operator:A2/A4/B3/D3/D6/E1/E3/F3/F4；不改 Worker、MCCL、编译产物补丁、卷积/FP8/TLE 数值路径、FlagGems 或只读 vLLM。

2026-11-02 MetaX 特例专项源码审查：本轮只读核对实际安装的 Plugin 7094141e、FlagGems 3eab0949、FlagGems-vllm ddce1d66 相对 HEAD 的全部 15 个产品文件差异，没有修改产品代码、更新依赖、运行 GPU 探针或重启服务。以下是结构审查结论，不是新的数值/图/性能通过；既有验证及失败范围仍按下文保留。

| 位置与问题 | 判断与建议 |
| --- | --- |
| Plugin models/glm5/model.py 构造期按 vendor 选择两个 prefill backend；attention/mla_prefill.py 与 dispatch/backends/flaggems/impl/mla_ops.py 又分别判断同一能力 | 优先收敛。模型应通过已有 backend 注册/dispatch 入口选择实现，可用性判断应复用统一来源，保留构造事务的限域与回滚。两个 backend 的 padding、out、LSE、chunked context 和策略契约需先对齐，不能仅因同名就直接合并，也不能把 MetaX 判断直接扩大成所有 OOT CUDA 平台。 |
| FGV ops/flashmla_sparse.py::_sparse_mla_configs 在公共文件按 MetaX 固定 C550 的 BK16/BH16/stages1 | 应调整配置归属。复用现有厂商调优配置机制，避免把一款卡的参数写成整个厂商的永久策略；保持原参数与选择范围，迁移后验证实际配置命中、数值与性能。不能为此在模块导入阶段新增 GPU 能力探测，重复引入选卡前初始化问题。 |
| FGV conv 的 STATIC_HISTORY、FP8 的 SOFTWARE_FP8、Sparse MLA 的 TLE 排除条件 | 有真实 SDK/编译器兼容依据，应保留可移植 kernel 变体，将选择策略收敛到已有能力入口或厂商入口。现有 utils/tle_capabilities.py::supports_sparse_mla_tle 仅检查 Python API，尚不足以证明目标 compiler/MMA layout 支持；未建立可靠特性判断前，不能机械删除 MetaX 守卫或以 device_type=cuda 替代。 |
| Plugin worker/worker.py 的 MetaX GLM 延迟激活 | 保留现有必要时序：绑定 rank-local device 后、collective 和模型构造前激活。已有双机前后对照支持该修复；统一所有平台时机或新增平台钩子需另证生命周期等价，不为隐藏一次 vendor 判断增设抽象。 |
| Plugin vendor/metax 下的 MCCL Abort 与 standalone concrete artifact 兼容 | 保留。职责位置正确，分别对应厂商通信 ABI 和当前 Torch 产物接口；不是应移入通用模型的逻辑。 |

FlagGems clone 使用真实 dispatch key，FGV MHC reduction extent 与 TopK canonical_output 也是通用契约修复，均未新增 MetaX 名称判断，无需再次拆成厂商副本。审查依据为 plugin:A2/A4/B1/B3/C1-C4/D4/F1-F4、operator:A2/A4/B3/D3/D5/D6/E1-E4；上述建议尚未实施，当前 GPU stream/queue 阻塞及用户保留 101 图探针未验证的选择不变，不能声称结构调整或对应硬件回归已完成。

2026-11-02 本轮测试收敛终态：先 mx-102 验证，再同步 mx-101，均在原 glm5.3-flash 容器的实际安装源树中完成。9 个本任务新增测试文件并入 8 个既有模块，104 项新增参数化用例的收集身份保持一致；两机各 69 项单元、注册和分发选择回归通过，0 失败、0 跳过。这不代表 104 项全部 GPU 数值/图测试执行通过。

| 组件 | 新增文件 → 既有模块 | 保留新增用例 | 本轮回归通过（每机） |
| --- | --- | --- | --- |
| Plugin | 4 → 3 | 23 | 59 |
| FlagGems | 1 → 1 | 9 | 2 |
| FlagGems-vllm | 4 → 4 | 72 | 8 |

测试落点如下，路径相对于各组件已核实的安装根：

- Plugin：tests/unit_tests/glm5/test_runtime.py、tests/functional_tests/compilation/test_graph_capture.py、tests/unit_tests/distributed/test_collective_compile.py。
- FlagGems：tests/test_clone.py。
- FlagGems-vllm：tests/test_causal_conv1d.py、tests/test_fp8_fp4_mqa_logits.py、tests/test_mhc_with_norm.py、tests/test_flash_mla_sparse_fwd.py。

原有函数定义及移动测试的断言、参数、容差均保留。五个图回归额外加入 replay 前的独立输出 NaN 哨兵；conv 输出与状态不共用存储，Sparse MLA 三个输出均覆盖。FP8 原模块在当前 vLLM 下存在未受保护的可选 DeepGEMM math 导入，已纳入原有 availability 守卫，旧 Hopper 条件和测试函数不变，新增 portable 测试未套上 Hopper 守卫。八个目标文件 Ruff lint 通过；FP8 整文件格式建议在改前已存在，未进行无关整理，未声称全仓 pre-commit 通过。

原生计划、改前备份、运行时/测试哈希和终态回执保存在授权工作根 /public-flash/jinghao/glm5.3-flash 下的 01-environment/test-layout-final-a3-20261102/<host>/，回归 XML/日志在 04-runs/glm-test-layout-final-a3-20261102/<host>/。102 引用 a2 同字节计划的成功收集记录及哈希，a3 重跑修正后的回归；101 重新收集。after-manifest SHA：102 7401edb0b708a1ac26f97dd1934a432376457446554517011a8df3193e75188d，101 79cd1daab1d18d0cb0d96fd9ac0e350c005e6bfad1d83882eac8a613e24a2fda。final-verification SHA：102 e8da12e1f3f5607ebb2d58a6c0945a1ae4ce6b4c83cd99428b37cdd982013003，101 fec203c4484cfbce298ccd86de26d0e45a40daebc581fab4e5c297cfb67170d0。

终态核对：两机原 CID、running/RW 映射、三个组件产品源码哈希均未变；原 API PID65987 和 headless PID3660448 继续运行，101 /health=200，共享 launcher 仍为 b4b959。旧 a6 全来源清单包含旧测试布局，保留为历史证据，不将其当作当前测试布局指纹；本轮没有产品运行时代码修改、模型重启、提交、推送或镜像封装。

算子开关实测：102 的 04-runs/glm-sparse-route-graph-{0,1}-a1-20261102/mx-102/result/route.json 确认，开关 0/1 下 Sparse MLA 都解析到已安装 FlagGems-vllm 的公开 flash_mla_sparse_fwd，实际路径 /opt/FlagGems-vllm/src/flaggems_vllm/ops/flashmla_sparse.py；concat_and_cache_mla 也核对公开对象身份。变化的是旧 dense flash_mla 导入，当前 GLM sparse 解析不依赖此开关。两机原服务进程的开关本来就是 1，因此未为重复设置而重启服务。

图验证仍未通过。Plugin sparse binding 图能力为 false，builder/backend 明确返回 AttentionCGSupport.NEVER，服务请求的 FULL_AND_PIECEWISE 仍自动落到 PIECEWISE。独立 FGV 探针在首组 eager 数值断言后卡在 PyTorch 创建捕获用 stream，180 秒超时，未完成 capture/replay。仅导入 Torch、尚未导入 Plugin/FG/FGV 的 90 秒基线也卡在首次 torch.cuda.Stream，MACA 原生日志反复报 ioctl create queue block timeout；证据在 04-runs/glm-stream-baseline-a1-20261102/mx-102/。这是底层 stream/queue 创建阻塞的证据，不能据此断言 FGV kernel 不支持图，也不能宣称图问题已经解决。停滞测试子进程已精确结束，父任务回滚后再完成最终收敛，未停止模型服务或容器。

用户引用的 prefill 分支是为当前 vLLM 的 MetaX OOT 平台补接入口：其 is_cuda() 为 false，需要额外 vendor 判断。MetaX 选择已有 attention.mla_prefill backend，经统一分发调用 FGV 的 flash_attn_varlen_func；CUDA 保留旧 backend，NVIDIA reference 配置保留原路径。选择器及 stock indexer 的 DeepGEMM 构造守卫均限定于 temporary_patches 构造事务，结束/异常时还原；后者适配已替换的 portable indexer 构造入口，不代表安装了 DeepGEMM。vLLM 源文件未改；prefill 接线与 sparse decode/图能力声明分别管理。

101 并发 GPU 图探针被自动审批以可能干扰在跑 TP16 服务为由拒绝，用户随后明确选择保留未验证，未执行或绕过。GPQA、性能、镜像交付继续暂停，formal_acceptance=false。先前收集器解析、可选导入及执行器漏建 pytest 临时父目录的失败均保留；最后一项的 17 个 fixture setup 错误由执行器修正，没有删减断言或跳过用例。本地 git diff --check 通过；全仓审计有两个无关的 XingChen4 README 断链和 14 条历史 warning，未修改其他模型。下文保留计划与历史轮次，以本段终态范围为准。

测试收敛补充范围：FlagGems 的 clone 注册测试并入既有 `tests/test_clone.py`（9项）；FlagGems-vllm 的 conv1d、FP8 MQA、MHC norm、Sparse MLA 四个新增文件分别并入既有对应算子模块（72项）。原有测试函数AST与移动测试函数体已比较等价，无容差/断言削弱；GPU限定仅施于原先限定的移动用例。FP8模块Ruff格式建议在合并前后都存在，保持原主体以避免无关整理；5个目标模块lint通过。先102再101验证全部81项新增用例，不以未运行的大矩阵声称全库回归。当前尚待远端结果。

11-02用户要求的测试收敛与算子开关验证——改前范围：Plugin仍为7094141e、6个产品文件+4个本任务新测试dirty，两机原CID/RW映射及实际安装路径复核。读取当前tests/README.md和pyproject测试约定，tracked/root搜索未提供AGENTS/CONTRIBUTING，按现有测试结构及本项目标准实施。仅调整本任务测试落点：prefill11项及worker4项并入既有 `tests/unit_tests/glm5/test_runtime.py`；MetaX standalone编译/保存/恢复的CPU/CUDA×两格式4项移入既有 `tests/functional_tests/compilation/test_graph_capture.py`，按MetaX vendor限定，支持场景仍须四项全执行；MCCL4项并入既有 `tests/unit_tests/distributed/test_collective_compile.py`，adapter采用按测试fixture延迟导入以保留原CPU隔离编译子进程。合并前冻结7文件原字节，核对所有旧断言与参数化覆盖等价后只删除本任务4个独立文件，禁止降低断言/容差或改生产代码；先102复核用例/回归通过再101。适用plugin:A2/A4/C1/F1/F2/F4/F7及贡献标准0，测试读取已授权算子接口但此步骤不修改算子。

后续只验证用户指定开关与图行为，不以修改能力声明制造通过：服务当前VLLM_FL_USE_FLAGGEMS_VLLM=1；GLM SparseMLA的 `_resolve_sparse_mla_kernels` 通过 `_load_flaggems_op → get_flaggems_vllm_operator` 实际总是读取FGV公开API。将用独立进程核对0/1的真实函数来源和backend图声明，并对真实FGV sparse算子做独立参考数值/capture/变输入replay检查（operator:C1/D2/D3/E1/E3/E4、plugin:F1/F2/F3），记录失败与未覆盖项，不重跑GPQA/正式性能，不改只读vLLM或停原容器。现有完整模型服务已是开关1且自动PIECEWISE，不能将重复设置1包装为新的后端切换成功。

本次最终功能结果（2026-11-02）：原双机 `glm5.3-flash` 容器通过同一b4b959脚本以TP16/PP1启动，101 API18530健康、102 headless运行；两文本/一图像均无错误、finish_reason=stop，原生内容校验及独立审阅通过。算术返回391；两句月亮回答说明反射太阳光和白天处于地平线上方；图像准确回答左红色正方形/右蓝色圆形，与已目视核实的PNG一致。服务保持运行，本轮未新增产品源码修改。

明确限制：实际后端报告AttentionCGSupport.NEVER，FULL_AND_PIECEWISE自动调整为PIECEWISE；只完成该实际运行模式下的功能检查，不是FULL_AND_PIECEWISE、执行模式或完整sanity验收。三请求用时235.158/288.863/162.824秒（completion_tokens89/416/90，含reasoning；temperature0/max_tokens2048/c1/timeout600），时延明显较长，不判性能通过、不声称optimized；这些样本不替代正式benchmark。冷NFS权重加载约32分钟、引擎profile/KV/warmup359.20秒（编译42.84秒）如实保留。GPQA、完整性能、镜像交付继续暂停，历史87.8788%不覆盖当前代码。

原始报告保持needs_review原字节：`04-runs/glm-tp16-functional-sanity-a6-20261102/mx-101/sanity-result.json` SHA `fe0c79f53751fafb3e40df75f945dfd77c204722e19a5fd39c194d8a7d457f01`。独立 `sanity-review.json` SHA `f0ea6c2b83207e276b491e1eb91add1f1ebc5d6956a2db433c4b6023c52db8b5`，原生校验后的 `content-verification.json` SHA `41cd1a35d72374d60fa516851983a79b06541197d7755da373a1827c8a66ae80`。恰为共享的3请求，不按双机计为6。独立审阅同时披露月亮回答的满月前后举例较宽泛，不把它当成最佳观测时段结论。

两机当前十文件源码/完整patch、PID寿命/命令哈希、原容器/RW映射及共享脚本均复核，vLLM/FlagGems/FlagGems-vllm与启动前HEAD/status/diff一致。a6 `source-manifest.json` 两机同SHA `23230b94059d2d5d494e7633e3b4599c7a6ea7e7a4054061fe0be39819869f01`。最终作用域回执与不可变服务日志快照位于 `04-runs/glm-tp16-functional-final-a6-20261102/<host>/`，formal_acceptance=false；101回执SHA `e7ed930caf708959e664d681b601798a0dc83996d0ece5ffab63b8ab44000134`、102 `fc29dc828b419f1e238c76cc204023217e86458b1619d9bc25e09d39ec0ec913`。这不创建正式部署指纹或提升整体阶段。既有失败、无效探针和工具错误均保留。 本轮最终 `./scripts/syntax-check --offline` 通过，结构审计0error/14条其他历史warning；作用域YAML断言及 `git diff --check` 通过，本地检查不替代上述远端证据。下文为按轮保留的定位、计划与中间状态，以本段最终功能范围为准。

a6服务就绪：120分片加载完成，实际EngineCore初始化（profile/KV/warmup）359.20s、编译42.84s，KV容量386560 tokens；17:03:37 API application startup complete，后续 `/health` 和模型别名/当前源码/prefix检查通过。原生三请求已运行，尚待全部原始响应。另核实17:00:24两机后端报告 `FlagGemsSparseMLABackend / AttentionCGSupport.NEVER`，框架把请求的FULL_AND_PIECEWISE自动调整为PIECEWISE，只观测到mixed prefill/decode PIECEWISE的5/5捕获；不能把当前服务就绪当作FULL_AND_PIECEWISE或正式执行模式通过。a6 binding里的graph_mode记录的是启动请求值，实际模式在本段与终态观察单独披露，不修改已运行的冻结请求或binding来伪装一致。

11-02恢复后的实测：a3两端wrapper均rc0/passed，逐rank原生记录完整覆盖0–15、两周期stream、all-reduce独立期望136/272、每周期2次原生Abort完成及再次建组，未见Abort异常。冻结 `04-runs/glm-mccl-reinit-stream-a3-20261102/verification.json` SHA `5efc493051cd10a98a421c8064501bab3df95ecadcef82c89264711888cdfaf4`，不是整模验收。两机当前10文件与冻结清单/完整patch一致、启动脚本仍b4b959，未新增产品修改。a6已实际启动：102 wrapper3660436/headless3660448，101 wrapper65975/API65987；使用同一正常prefix脚本，尚待完整就绪与推理。

a6权重加载定位：两机rank0的非阻塞Python栈均位于真实 `load_weights`；102在 `_load_w13 → flag_gems.copy_ → torch redispatch` 读取/拷贝路径，`read_bytes` 从6587207680增长到17272016896，后次wchan为 `wait_on_page_bit_common`，且16:29:35预读进度报告1/7。当前存在NFS文件页等待但读取在推进，不能概括为GPU stream阻塞。 随后同一a6已实际推进至93/120分片（加载约23分33秒），继续运行，未重启或更改加载参数。原始Python栈及身份在各run的 `rank-local0-weights-a6*`。进一步原生栈采集因py-spy不支持 `--native --nonblocking` 组合而失败，失败及I/O/wchan均保留在102的 `rank-local0-weights-native-a6*`；该失败不是模型错误，也未据此修改代码或停止服务。


当前a6请求离线预检通过，3cases/concurrency1；路径 `03-acceptance/tp16-startup-check-a6-20261102/`，manifest仍88907cd0，binding SHA `a5d14a9550f778f1905291d5d9219182bf9f9a3e29451ce3c843b11d94742a59`，工具与Skill bundle不变。绑定本轮10文件、双机a6、TP16/PP1、FULL_AND_PIECEWISE与prefix开启，尚未发送请求。此前a5绑定不复用。

11-02连接恢复复核：严格hostname核对通过，原双机CID/RW映射与b4b959脚本一致，两容器docker top均仅PID1 bash、GPU空闲。主机及容器内均不存在a2 run目录，102的 `reinit-resource-free-spec.json` 也不存在，故更正前轮“102已启动并核实运行”结论：前轮堡垒机回包不能支持实际执行，a2未执行；历史文字保留以说明更正来源。现改用唯一a3 run、同一双周期测试、同一安装源码，增加显式原生启动标记并按真实state/PID校验。没有停止或重启原容器；a6仍待通信结果。

2026-11-02恢复验证：用户告知显卡已释放并授权继续。只读核实原双机容器ID、RW映射、真实Plugin导入路径和b4b959共享脚本未变，control.mode仍agent；GPU原生状态回到每卡约858 MiB，未停止其他任务。沿用已冻结的6个产品文件/4个测试，不更新组件或添加启动开关。先复跑全8卡stream/算术，再复跑双机真实TP16两轮建立/计算/Abort/重建，通过后以同一共享脚本运行a6并发送冻结的两文本/一图像请求。原精度、性能、镜像交付继续暂停，以下11-01资源阻塞记录保留为历史；本轮结果待实际核验后填写。

11-02已验证结果：`glm-torch-eight-resource-free-a1-20261102` 两机均rc0、无超时，完整覆盖每机GPU0–7的默认计算、显式stream、新stream算术与同步结果；同一脚本SHA `553cd11e7dceabd3f2718c817b6a19bf7f5b38d6f448932a023b249be7329241`，stdout SHA：101 `d6aaa09a0a037abcf0c38cc8a9b60ba84109efe84a98e23c61985144a2f52a0d`、102 `cf8cffbb38035acc23e36077e002b57becfa1666a6e2adb583a1cdfba395543b`。与11-01占用期间的GPU0失败区分，当前不能再沿用“GPU仍被外部容器占用”为阻塞。未停止任何外部容器。

通信探针使用新run `glm-mccl-reinit-stream-a2-20261102` 和原字节不变的两周期诊断，102准备/启动/运行状态已核实，240秒上限；101端首次连接前认证失败，重试的Ansible仅给出空回包/缺stdout，不能作为实际启动或通过依据。随后严格 `connectivity-check` 发现101返回 `match asset failed: Core API 发生错误`（SSH rc0但不是远端hostname），102认证失败；另一次只读SSH返回“必须是唯一的资产”，同样不是远端执行证据。末次102只读原生状态采集同样返回 `match asset failed: Core API 发生错误`，严格sentinel/JSON检查拒绝该rc0回包。当前通信终态与精确清理回执尚不可读，不能认定MCCL通过/失败或声称全部探针已退出。恢复SSH后必须先核验现场和原生state/cleanup，再决定是否需要新run，禁止盲目重放。

a6完整服务尚未启动，十文件当前来源复核及新的功能绑定离线预检尚未完成；准备预检的101命令亦在远端执行前认证失败。没有发出生成请求。原容器在恢复初始核查时均为原ID运行、仅PID1 bash，后续堡垒机故障不能支持新的现场状态断言。共享脚本字节未由本任务改动，产品代码本轮无新增修改。恢复连接后按原计划继续，不需停止其他服务或重启设备。

本轮本地 `./scripts/syntax-check --offline` 通过，audit 0error/14条其他历史warning；精度Skill bundle仍为 `a1c3dce2e0dde6304b95d5a7ee0d54bf436dd4fab94ed4719c377737122fe6a2`，当前原生sanity.py仍为 `7d92c2bcf3625a65265229f11d92b19d23e9c3434073cdcc6597f8f0b0086ccd`。这不是服务通过证据。


当前结论（2026-11-01 13时续查）：原先GLM激活早于选卡导致的stream等待已修复，a4完整服务两机均越过原阻塞并加载完120个权重分片；随后编译产物接口错误已修复并完成两机独立测试。当前无法继续整模验证：两机全部16卡正由其他任务的 `mx8_0`～`mx8_7` 容器占用，模型为 `DeepSeek-R1-0528-Qwen3-8B`，每卡该进程约57330 MiB、总占用约58191/65536 MiB，剩余容量不足以加载本模型（a4每卡权重约41 GiB）。尚无服务就绪或实际生成，不能宣称修复闭环。

占用归属由host GPU PID、cgroup、容器ID和模型命令交叉核实；原生记录在 `01-environment/stream-fix-20261101/<host>/resource-contention-evidence/`，2026-11-01T04:59Z冻结。ownership.json SHA：101 `97efb9d89f9604f3dc10ad9bee5c20ef15a918b16dc84c6031683f9a5fa12cfd`、102 `754ae8290d8ee46912bef8a7ed6eb135d688bc27d0f19a80c538391cca73120d`。没有停止这些外部服务、reset GPU或重启主机。继续验证需外部负载结束，或用户明确批准暂时停止这16个DeepSeek容器；待批准的操作只按已冻结身份复核后停止精确CID，102试点核实后再101，保留数据及原GLM容器。尚未执行该操作。

MCCL Abort补齐结果：102旧实现负对照4项失败，修复后两机各4项通过，覆盖ctypes签名、原生转发、错误传播及缺符号失败。`pynccl_wrapper.py` 修复后SHA `8baeef8aad857daac93253d8777e220ed81e80a0441b4481897b701b3250ce45`，测试 `test_metax_mccl_abort.py` SHA `6873116399ad6f1faa5d97a19cf8a1cce92e8cee6e38642ed662f1b9e5bdcea0`。真实16rank两轮重建探针 `glm-mccl-reinit-stream-a1-20261101` 在第一轮初始化即阻塞，两机240秒有界退出并精确清理，未到达Abort，不能声称真实清理/重建通过，也不能认定缺少Abort造成SDK队列超时。

后续独立Torch探针 `glm-torch-eight-after-queue-timeout-a1-20261101` 在两机均只测到GPU0：默认stream计算通过，显式新建stream等待至90秒后终止；因遇首错即停，其他7卡未测。内核队列超时日志保留，但在上述外部负载占用期间，不能据此判定永久驱动故障或把队列异常直接归因为资源竞争。已确认的是资源不足，停止追加GPU测试及大模型重试。

本轮最终Plugin共6个产品文件、4个回归测试，两机源码一致，完整patch SHA `7ca8a1f4bb7996e78b7dbbf0356f145d16c15950eb45e53788e44a83ece48628`；封存在 `01-environment/stream-fix-20261101/<host>/final-source-resource-blocked/`。manifest SHA：101 `bd95876f0abf0e7c0719e7647366486e87278a546045e6f448c1e5a44d86bef5`、102 `b6f7487d7a56b1817c9f170048ca22ebe6206bff31e3216bfaf356801391b1f2`。vLLM、FlagGems、FlagGems-vllm的HEAD/status/diff哈希与a5启动前完全相同；未改Torch/SDK。根脚本仍为b4b959、TP16/PP1、FULL_AND_PIECEWISE、正常async及prefix开启。a4/a5及所有失败证据保留，a5功能请求绑定在新增Abort修改后已过时，不能沿用为当前服务验收。

两机原 `glm5.3-flash` 容器均保持原ID运行，最终docker top仅有PID1 bash；本任务服务/诊断进程均退出，API18530未监听，生成请求为0。新的作用域诊断回执在 `04-runs/glm-tp16-diagnosis-resource-blocked-20261101/<host>/verification.json`，状态blocked_external_gpu_capacity，非正式模型验收。诊断回执SHA：101 `7c15ecb75e2822c3e0196d902d6d7100ac93695ffbdc838711937d3aba165aa6`、102 `29f5bc8f532bd2c77849722d343216baa0590302bbe118ad788d8388364fa812`。精度、性能和镜像交付继续暂停，历史GPQA不覆盖本轮源码。本次收尾YAML解析、blocked/暂停/请求0的作用域断言及 `git diff --check` 通过；末次全库audit仍报根README和models/README指向缺失XingChen4模型的2条范围外断链错误及14条历史warning，未修改这些文件，不能声称末次全库审计通过。下文是按轮保留的调查、修改前范围及失败记录，“当前/最终”须结合相应轮次解读；此前审批环境冲突现已解除。

a5及第三处限定计划（2026-11-01）：编译类型修复后两机CPU/CUDA×binary/unpacked各4项全通过（102127.07s、101147.00s），两机独立新进程空缓存各4产物/8组新输入均rc0通过；具体修复SHA `6346ccbf6c831555df37512ce16697603b420461c6bf2fcffb334997f26009f6`、格式化测试SHA `18b2a1b93e737de496c84ab7daf413abcdae40e24fa964ae454816b14d031bde`。a5完整服务在模型加载之前出现另一阻塞：两机 `ncclCommInitRank` 中SDK `mxkwCreateQueueBlock` ioctl队列创建超时。已保存双机Python/native栈、初始/停止前身份并精确停止本run；原容器均保留。未降图、未改Torch/SDK、未重启主机或设备，仍无API/生成请求。a5冻结来源与a4均保留，不覆盖。

只读核实两机实际MCCL均为 `libmccl.so` 2.16.5，原生导出 `mcclCommAbort`，头文件声明其释放通信器并中止未完成设备操作；当前Plugin `pynccl_wrapper.py` SHA `977a9c37e7bd1335301eda53dbe031f24c04d8e952a9917535bffb82e41d4491` 没有 `ncclCommAbort` 方法。当前只读vLLM `PyNcclCommunicator.destroy` 明确在daemon线程调用该方法，解释此前销毁阶段AttributeError。两机共享内存各仅占1%，未见容量耗尽；不能据此推断缺失Abort必然造成这轮SDK队列超时。

扩大范围前限定：只新增Plugin MetaX `pynccl_wrapper.py` 的原生 `mcclCommAbort` 必需符号/ctypes签名和同名上游兼容薄方法，经既有NCCL_CHECK传播错误；不以collective Destroy或no-op代替Abort，不吞异常，不改分发/all_reduce/其他厂商。增加 `tests/unit_tests/distributed/test_metax_mccl_abort.py` 验证公开方法转发、签名、错误传播及缺少原生符号时在创建通信器前失败；保留旧实现负对照。随后以真实GLM激活、TP16组、stream与变输入all-reduce做两轮建立/销毁/再建立，检查实际清理回调与后台异常；先证明基础通信健康再重启大模型。若SDK队列问题仍存在，继续只读驱动/资源诊断，不擅自reset GPU、重启主机/容器或删共享资源。适用plugin:A2/B2/B3/B4/B5/C1/C2/E3/E4/F1/F2/F4/F7；无算子数值实现修改。

a4后续结果与第二处修复计划：原stream等待已由实际完整权重加载证实越过，但warmup于12:09:46在MetaX `fix_standalone_compile.py:127` 失败，`CompiledArtifact` 已是抽象基类（缺__call__/save），当前Torch2.10原生standalone_compile返回具体 `CacheCompiledArtifact(compiled_fn, artifacts)`。101随后失败退出；102仅按初始PID/start_ticks/命令哈希停止本run的10个残留进程，controlled-stop.json保留且all_exited=true，容器不重启。无API、推理请求仍为0，不把原stream修复等同于完整启动通过。

这是013中已验证过、主线更新后旧补丁归档未重放的同一接口差异，当前适配器SHA仍为 `e3f5f15b365079177c2a0eb73f1369c6f6752f5c10b95bebb35231434aa7e5cf`。扩大范围前限定：只增加Plugin `dispatch/backends/vendor/metax/patches/fix_standalone_compile.py` 的具体类能力导入/返回构造类型，缺失具体类时保留旧版CompiledArtifact构造路径；不改变嵌套节点遍历、cache key、TF32旧hook、签名或缓存算法，不改Torch/vLLM/SDK。从更新前归档单独复用 `tests/unit_tests/compilation/test_metax_standalone_artifact.py`（原SHA `9665f1cfb8e7b1c673cdd674b0e9cdd9fe507e4371dc8607d9b999e1fc7322d1`），先在当前未修适配器保存CPU编译负对照，再验证两机CPU/CUDA×binary/unpacked真实编译、调用、保存/原生加载及变输入数值；独立进程恢复新产物。当前接口已只读核对，旧Torch缺少实机仍须披露；不把旧通过直接改称本轮通过。适用plugin:C1–C4/F1/F2/F4/F7，复用既有厂商patch入口，不扩展数值算子修改。后续完整服务使用新a5来源/绑定，a4失败和冻结来源保留。

续查第二次恢复（2026-11-01）：审批环境恢复可用，重新核实两机原CID、running/RW映射、agent模式及既有4文件状态，之前未启动的组合复现现已执行。`glm-activation-group-late-a1-20261101` 在无权重场景重现：16rank完成distributed初始化，两机local_rank0停于Stream创建，其他14rank创建成功；两机Python/native栈均指向 `mcStreamCreateWithPriority → HostQueue::start → Semaphore::timedWait`，到180秒上限精确清理本探针组，原始失败保留。`glm-activation-group-early-a1-20261101` 仅先选卡，16rank数值检查均通过、两机wrapper均rc0。进一步 `glm-activation-group-bound-a1-20261101` 保持模块导入时序，仅在实际 `initialize_glm5_worker` 前选卡，16rank同样报告stream/all-reduce136/complete通过（wrapper终态待核对）。两种通过路径均有既有MCCL销毁线程缺 `ncclCommAbort` 的异常，单独披露，不据此宣称清理库契约无缺陷。

产品修改前限定范围：Plugin安装基线7094141e2、3产品文件+1测试的既有prefill修复保留；新增仅 `vllm_fl/worker/worker.py::WorkerFL.__init__/init_device` 与 `tests/unit_tests/glm5/test_metax_worker_startup.py`。MetaX且真实GLM架构的激活移到现有assigned→visible映射/set_device之后、distributed和ModelRunner/CustomOp构造之前，避免选卡前的GLM能力探测在所有rank默认GPU0执行；复用现有模型匹配、激活和选卡逻辑，不复制设备映射、不新增环境开关。其余平台/模型保留原构造期路径，实际初始化失败直接上抛。单元测试覆盖visible设备映射与顺序、非目标平台/非GLM守卫、失败在collective前停止；先保留旧实现负对照，再改实际安装文件并验证。随后以相同TP16/PP1共享launcher完整启动、文本/图像功能检查；仍不恢复GPQA、性能、镜像。适用plugin:A2/A3/A4/B3/B4/C1/C2/D4/E3/E4/F1/F4/F7；无数值kernel或第三方源码修改。

实现与已完成验证：102旧实现负对照2失败/2通过；相同4项测试在两机修复后各4通过，既有GLM激活/策略/异常回归102另16项通过。Worker原文件SHA `659c928b04d7ae841be72693e3061fa424c3b1e0a331e0e5365b0d2bbdd07de6`、修复后 `b65a42dd904a74847ec7db506bf4da98be6401304538ac55088eb1c93f0ff578`，新增测试SHA `690c260d17293b924bacb7a0655cfed50729456be54637451ea915f71e505abe`；原文件及manifest保存在 `01-environment/stream-fix-20261101/<host>/worker-patch/`。新测试ruff0.14.0 lint/format通过；显式检查worker整文件在修改前后均有相同2处继承的I001导入排序问题、整文件format建议也均存在，未夹带全文件整理。新增两处hunk已按模型/平台守卫、实际设备映射、激活在collective前执行及异常传播逐项复核。其他硬件仅接线验证，未声称硬件通过或完整PR门禁完成。

`glm-activation-group-bound-a1-20261101` 两机最终wrapper均rc0。完整服务a4 `04-runs/glm-plugin-tp16-startup-a4-20261101/<host>/` 已通过原共享脚本启动；101 API27169、102 headless3620535，原容器不重启。两机本地rank0分别27426/3620736的12:01非阻塞栈均实际进入 `load_weights`，原stream等待在完整服务中已越过；栈、进程身份保存在本run的 `rank-local0-progress-a1*`。当前仍处于权重加载，尚不声称就绪或推理通过。

完整当前来源封存在 `01-environment/stream-fix-20261101/<host>/final-source-a4/`：4个tracked产品文件+2个untracked测试，完整patch SHA `4314b32885cd0e0625ab0758d44e281e57cb590efaad302434d015b114d57b21`，manifest SHA分别101 `fe0e3ecab95f9fab371c7c373ea6027ad1b34831c238001cfb3881771fb88368`、102 `8da1f73c13424190916d2559b66a82fe3de0b232c46eeab2774db9de59048960`。相同6文件哈希已核实；未提交、推送或封装镜像。

a4功能请求单独绑定在 `03-acceptance/tp16-startup-check-a4-20261101/`，原生离线预检为planned、3cases、concurrency1，尚未发请求。manifest SHA `88907cd0e27483f56bdd5701779e09ab4f7b06703db76830629b412f5f5f9e5d`，binding SHA `dadde0ed812082c97e20a646d15591957ab8d37e6c5c463dc5aa6de83ba01062`，实际sanity.py SHA `7d92c2bcf3625a65265229f11d92b19d23e9c3434073cdcc6597f8f0b0086ccd`，Skill bundle SHA仍为 `a1c3dce2e0dde6304b95d5a7ee0d54bf436dd4fab94ed4719c377737122fe6a2`。这仅用于用户请求的功能修复验证，不冒充重新完成执行模式或正式service-sanity验收。

本轮12:00前本地 `./scripts/syntax-check --offline` 通过341项（19skip）+7项运维回归、13shell/3playbook，结构审计0error/14历史warning。前轮末次出现的其他模型断链本轮已不再报错，未由本任务修改，不沿用旧审计失败结论。

2026-11-01 后续定位已获用户授权恢复，范围仍为双机TP16/PP1功能修复与文本/图像推理；精度、性能、镜像交付继续暂停。重新核对两机原容器、RW映射、agent控制模式、共享launcher及既有4文件dirty状态，无其他任务进程，卡空闲。先以8进程GLM实际激活入口、选卡时序和stream测试隔离完整模型初始化差异，不加载权重；未证实前不改产品代码。后文“最终”均指此前一轮冻结结果，后续新增证据使用新run保留。

续查结果：102的 `glm-activation-stream-late-a1-20261101` 有界8进程探针通过，8个rank均完整执行实际 `initialize_glm5_worker`、选卡、显式stream创建与新输入计算，rc0，随后全部退出。每个进程在GLM模块导入后CUDA已初始化，激活完成时设备均为0；rank0创建stream约3.3秒，其余rank约0.02秒，但本测试没有distributed组，不能证明GPU0上下文是完整服务阻塞根因。未运行early对照，无必要把单次等待归结为故障。原生产物位于批准根 `04-runs/glm-activation-stream-late-a1-20261101/mx-102/`；state.json SHA `95ba66da6207d3654bb852c626378d68f0a6cf547bdfbf5106f417b88d30c418`，stdout.log SHA `68df07ceb3f26d8cbffaa3c8af83cca24d8b14a7a4bd5733aa53c2a7147b89a7`。本轮没有新增产品修改，launcher仍b4b959，服务未就绪、请求0；原容器保持running。

只读核实当前Plugin注册入口在未显式设置时已把 `VLLM_WORKER_MULTIPROC_METHOD` 设为spawn，因此不能直接用“fork继承CUDA上下文”作为已确认原因，也未叠加重复spawn开关。

已准备下一步判别实验：保留真实16rank初始化/stream/all-reduce（期望136）流程，增加GLM实际激活，并比较选卡前后激活两种次序；不加载权重，180秒上限只清理诊断自身进程组。本地临时playbook为 `/private/tmp/glm53-stream-fix-20261101/probe-activation-group-{late,early}.json`，嵌入Python及JSON结构校验通过，尚未执行。执行late的102试点被工具拒绝：`approval required by policy, but AskForApproval is set to Never`。来源是 `.codex/rules/ansible.rules` 对通用 `./scripts/playbook` 的 `decision = "prompt"` 与当前环境 `approval_policy=never` 冲突；不是用户撤销任务授权。未修改审批规则、未改用其他路径绕过。需恢复可按命令审批的执行环境后，先运行102并核实已准备/运行状态，再运行101；不能因这一拦截声称技术修复失败或根因已定位。

当前结论：TP16/PP1配置已生效并完成三轮双机启动尝试，但完整服务仍未就绪、推理请求为0，验证未通过。两机本地rank0在创建MACA stream时等待，根因尚未定位；关闭异步调度只使等待点移到MoE辅助stream，已撤回该无效诊断开关。独立Torch测试、真实16rank stream与all-reduce小测均通过，不能把该阻塞归结为TP16通信不支持。两机原 `glm5.3-flash` 容器保持running，任务服务进程已精确清理，API18530未监听。

2026-11-01，用户明确要求将共享配置改成 TP16、PP1，在 mx-101、mx-102 的原 `glm5.3-flash` 容器中重新启动并检查实际推理。沿用批准根 `/public-flash/jinghao/glm5.3-flash`。本轮只做功能启动及就绪后的代表性文本/图像推理检查，不重跑 GPQA、性能或镜像交付。

修改前两机容器均 running、未 paused，无 GLM 推理进程，8卡均空闲；实际 Plugin 同为干净主线 `7094141e28a2680644fc41073aa9dfdfbf1f0044`，版本 `0.3.0rc2.post1+g7094141e2`。vLLM 与算子库保持上轮身份及既有改动。控制模式仍为 agent，保留此前完整验收的暂停状态。

首轮变更范围仅为根 `start-model.sh` 的 `--tensor-parallel-size 8 --pipeline-parallel-size 2` → `16 / 1`。先保存原脚本及 SHA，再在102通过已验证映射修改共享文件、核实101读取同一新字节。模型、BF16、上下文65536、双节点mp、网络接口、端口、FULL_AND_PIECEWISE及正常prefix cache保持原配置。先启动102 headless，再启动101 API；只操作本任务进程，容器不重启。

验证范围：实际安装路径与参数、进程/两机通信、完整就绪、代表性文本的非空且切题输出、finish_reason及异常日志。使用本地精度Skill的 service-sanity 工具保存请求和响应并逐项审阅，作为本轮功能检查，不提升为完整模型验收。若遇新的真实依赖或运行时阻塞，先记录根因与最小必要范围，再作已授权组件内的修复；不修改只读vLLM或第三方依赖源码，不以旧GLM注册覆盖主线。

原生产物留在批准远端根，最终结果与封存回执见本文首段及末段。

首轮 `glm-plugin-tp16-startup-a1-20261101`：两机16个rank均完成TP组建立、PP均为0，随后模型构造失败，尚未加载权重。根因：`Glm5NextMLAAttention.__init__` 用 `current_platform.is_cuda()` 限定便携prefill hook，而实测MetaX `PlatformFL` 是OOT、`is_cuda() == False`、`device_type == cuda`；原生MLA选择器只候选不可用的FlashAttention。两机原始state/stdout及进程所有权快照保存在 `04-runs/<run>/<host>/`，禁止覆盖。

首次产品修复前限定范围（Plugin基线7094141e2、原始clean；FG/FGV/vLLM身份沿用019）：

- `vllm_fl/models/glm5/model.py::Glm5NextMLAAttention.__init__`：将已存在的构造期事务扩展到已核实MetaX；MetaX复用现有 `attention.mla_prefill.FlagGemsMLAPrefillBackend`，其算子经现有统一分发调用FGV公开API。原CUDA路径及NVIDIA reference保持原选择；不恢复旧模型注册。
- `vllm_fl/dispatch/backends/flaggems/impl/mla_ops.py::is_available`、`vllm_fl/attention/mla_prefill.py::is_available`：仅为MetaX的varlen attention和prefill backend开放已有能力探测，保留API可调用与黑白名单条件，不开放其他MLA算子。实测FGV已导出 `flaggems_vllm.ops.attention.flash_attn_varlen_func`，目前统一分发被平台守卫拒绝。
- 在现有GLM测试目录增加上述接线、非目标守卫、事务恢复和失败传播回归；真实MetaX以独立Torch参考检查BF16/head256的变长因果prefill数值，随后相同共享launcher双机重试。若后续再阻塞，记录新证据，不扩大到只读vLLM/第三方源码。

本次不新增数值kernel、不改cache/workspace所有权；适用plugin:A1–A4/B1/B3/B4/C1–C4/D4/F1/F2/F4/F7，算子实现未改。非MetaX硬件仅接线回归，不能宣称硬件数值已验证；图执行需由实际服务捕获/推理继续验证。完整GPQA、性能、镜像交付仍暂停。模型具备图像能力，服务就绪后同时做代表性文本和图像功能检查。

修复验证：102新增 `test_metax_prefill.py` 11项全通过（20.16s），覆盖MetaX/CUDA portable/CUDA reference/其他平台、两次构造、异常传播及事务恢复、缺失API与黑白名单。两机真实公开FGV prefill通过：BF16、head8×256、变长[1,17,33]、两组新随机输入，CPU独立FP32因果attention参考，max_abs_error为0.0083852/0.0080566（rtol/atol各0.02），显式out同址、无NaN、LSE有限。该检查未验证图捕获或LSE数值，不能替代完整算子验收。证据 `04-runs/glm-plugin-tp16-prefill-{tests,numeric}-a1-20261101/<host>/`（单测先在102执行）。

第二轮 `glm-plugin-tp16-startup-a2-20261101` 已由同一根级脚本启动：102 headless PID3595055，101 API PID4368、EngineCore4570；16rank通过模型构造并开始读取120个safetensors分片。尚未服务就绪，推理待测。原始进程归属快照留在各run目录。新增回归测试按ruff0.14.0排序/格式化，两机相同，另存 `prefill-patch/test-format.json`；运行中3个产品文件未因格式检查改写。上游pyproject默认排除vllm_fl，显式lint三个产品文件通过，额外format检查mla_ops守卫提示换行风格，暂保留本轮冻结运行字节；其余两个产品文件及新测试format通过。未运行完整pre-commit（容器无该工具），不声称PR交付检查已全部完成。

文本与图像请求已冻结在 `03-acceptance/tp16-startup-check-20261101/`，原生sanity离线预检通过，仅用于本次功能诊断；尚未发请求、不声称formal service-sanity通过。

a2进一步诊断：两机本地rank0尚未进入权重加载，而同机其他rank已加载/预读。两次非阻塞py-spy Python栈均停在 `worker/model_runner.py:803` 异步调度输出stream的 `Stream()`；102原生栈进入 `mcStreamCreateWithPriority → mcr::Stream::Create → mxr::HostQueue::start → Semaphore::timedWait`。cgroup pids.max629145、current约2450、events.max=0，未见线程数限额耗尽。不能将所有rank的状态概括为权重读取慢，也不能据此声称TP16 collective数值已通过。

下一次仅调整必要启动配置：增加原生 `--no-async-scheduling`，绕开当前等待点，保持TP16/PP1、图模式与其他参数。先保存a2线程栈、日志及精确所有权，再停止本任务API/headless及其后代，保留原容器和其他进程；保存b4 launcher备份及新SHA后运行a3。此项是受控诊断，尚不证明SDK问题根因已修复；若下一处仍发生stream等待，需要独立小型复现，不继续堆叠开关。

a2已受控停止，容器保持运行；原始日志及rank0 Python/原生栈、停止前精确PID/启动时间/命令哈希和 `controlled-stop.json` 全部保留。容器Python缺少 `os.pidfd_open`，首个停止脚本在发送任何信号前报错；随后逐PID复核启动时间和状态执行TERM/必要KILL，仅操作本run后代，结果已核实退出。没有重启Docker或容器。

两机独立Torch复现均通过：默认stream计算、显式 `torch.cuda.Stream()`、新stream计算与同步结果正确，rc0、未超时；证明不能把a2等待点归结为无条件的单进程stream故障。复现 `07-bugs/tp16-stream-20261101/torch-stream-gpu0.py`，SHA `aa155bd4e7bf5b5eaec95c0ea588ce6721097fe570d3a187f9cccf99d297d826`，证据 `04-runs/glm-torch-stream-probe-a1-20261101/<host>/`。

第三轮 `glm-plugin-tp16-startup-a3-20261101` 使用新增 `--no-async-scheduling` 的同一共享脚本，SHA `552bd6d1abdc5f8e7186328cbf42757b374045efad6a22506e28ca7d8ac73e2b`。只读核实vLLM原生arg_utils使用BooleanOptionalAction，否定开关合法；图模式保持FULL_AND_PIECEWISE、prefix保持开启。当前待实际启动和推理结果。

a3在两机本地rank0再次等待：101 PID8570（TP0）、102 PID3600042（TP8），py-spy非阻塞栈均为 `torch.cuda.Stream.__new__ → vllm.utils.torch_utils.aux_stream:753 → shared_experts.py:70 → moe_runner.py:280 → FusedMoEFL → GLM模型构造`。关闭async仅让等待点后移，不能作为解决方案；服务依旧未就绪、没有推理结果。不再追加禁用MoE或禁用图等开关。先保留现场、停止本run，再以小型双机通信/stream初始化复现区分触发条件，待证据支持后才改产品层。

小型复现：以真实 `init_worker_distributed_environment` 建TP16/PP1组，不加载权重，测试group初始化后创建显式stream和16rank all-reduce（独立期望136）。首版 `glm-tp16-group-stream-after-a1-20261101` 遗漏 `ParallelConfig.master_addr/master_port`，vLLM将env rendezvous改写为默认127.0.0.1:29501，两机均有界超时rc124；该无效配置不能支持产品故障结论。保留首版原始记录，v2补齐已验证双机master与inbond1地址，在 `glm-tp16-group-stream-after-a2-20261101` 重测，每机driver180秒上限，仅清理本诊断自身进程组。

v2探针也未建立有效组：torchrun继承 `TORCHELASTIC_USE_AGENT_STORE=True`，vLLM切换到29655后，所有rank（含0）按代理store客户端等待，没有进程创建该store；两机直连29655返回ECONNREFUSED，rank0栈位于 `_create_c10d_store`。按180秒上限退出rc124，不能作为产品/网络故障证据。v3仅在诊断子进程移除该代理标志，使用独立29654代理与29655原生store，并新增逐rank JSONL原生进展；前/后stream对照只移动同一个创建点相对于初始化的位置，import/config保持相同。原始v1/v2保留，不覆盖、不放宽产品验证条件。

v3正确握手后，16rank均报告 `distributed_initialized`、`create_stream_done`、`all_reduce_passed(expected=136)`、`complete/passed`，逐rank JSONL完整覆盖0–15；说明TP16组与通信初始化后创建stream的最小路径可以工作，不能把完整服务等待归结为TP16通信不支持。当前继续比较GLM初始化额外路径，尚不改worker顺序或SDK。候选检查是 `runtime._concat_handles_zero_rope`：若原生_C_cache_ops入口存在，会在worker选卡之前向默认CUDA设备分配小张量做ABI探测；先做独立复现，未证实前不修改该逻辑。

最终核验与封存：v3双机小型复现均rc0，16rank阶段与all-reduce值136完整，root wrapper状态passed。102独立零RoPE能力探测后创建stream的测试也rc0，未复现等待；该假设未证实，未据此修改runtime或worker。保留仅已验证必要的3个Plugin产品文件及1个接线测试，逐hunk已复核；vLLM、FlagGems、FlagGems-vllm和SDK均无本轮修改。

最终共享launcher恢复正常async默认值，仍是TP16/PP1、FULL_AND_PIECEWISE、prefix开启，SHA `b4b959abacc49bb51a7984bd1bf2309db06a37239b69e63413a0d037be9ea2c8`。两机最终来源、容器ID/映射、脚本、4文件哈希、终止进程身份与无API均已重新核实。完整补丁、4文件tar和manifest分别在 `01-environment/tp16-pp1-20261101/<host>/final-source/`，原始失败及所有无效诊断均保留。没有镜像封装、提交、推送或新精度/性能评测。

最终功能检查回执 `04-runs/glm-tp16-functional-final-20261101/<host>/verification.json` 明确status=failed、service_ready=false、inference_verified=false、generation_requests_sent=0，不是正式模型验收回执：

| Host | verification.json SHA-256 | final-source/manifest.json SHA-256 |
|---|---|---|
| mx-101 | `75ac444c75ab792b599e2c16f2f5d1fe2d84e0f20d6350a6df12fba2963f12f3` | `1347aa8cd71669b825a7b90d30ecd0e55a083d8cfe413dc68b28620f58fb7a1c` |
| mx-102 | `0f9d30bff049bd177cdb08e80c5c29626efa753b518361b270825d08af272874` | `8eb4b88f5d1a20185b37a9801bf48fa0703a4baed0396b8abafc821dac1702af` |

本地 `./scripts/syntax-check --offline` 通过341项工作流回归（19skip）、7项运维回归、13个shell/3个playbook；audit为0error、14条其他历史工作区待复核。完整适配、原GPQA离线计分和性能/镜像验收继续保持用户先前的暂停状态，本轮不更新为functional或optimized。后续若恢复修复，应从已保存完整GLM worker初始化现场继续缩小复现，不重复无依据的图降级、async禁用或大权重重启。

收尾时单独运行 `./scripts/audit-workspace --json`，出现2条本轮范围外错误：根README及models/README指向缺失的 `XingChen4-29B-A4B/README.md`，另有上述14条历史warning。本轮GLM/MetaX记录没有审计错误；未修改这些其他模型或全局链接。该末次全库审计不算通过，与此前完整syntax-check的通过时间和范围区分。作用域结果结构断言、TP/PP配置、blocked状态及暂停状态校验通过，所改工作区 `git diff --check` 通过。


2026-11-03通信定位与修改前范围：a2/a3小型探针在graph前的eager校验失败，已核实不是BF16类型枚举错误。a3逐rank真实输出显示第一次sum=136且输入被修改，第二次2176；实际MetaX `pynccl_wrapper.py::_compile_friendly_all_reduce` 在模块导入末尾全局替换 `CudaCommunicator.all_reduce` 为原地Torch ProcessGroup调用，违反GroupCoordinator公开的非原地/no-alias契约。虽存在可用PyNccl对象，之前据此认定实际使用其all_reduce的判断不成立，现予更正；该缺陷与整模型FULL中途卡住的因果关系仍待验证。

范围限Plugin7094141e2的上述文件：删除原地override及其独有imports，保留MCCLLibrary替换、Abort和全部其他符号；原生GroupCoordinator custom-op已隔离ctypes，不需要该编译绕行。复用既有 `tests/unit_tests/distributed/test_collective_compile.py` 增加4项输入/输出alias、PyNccl/禁用回退、错误不重试契约；现有真实Dynamo编译测试保持。先保存旧实现4项负对照，再验证新实现9项测试及双机真实TP16 eager/变输入graph80collectives×200replays，显式记录实际方法来源、输入不变和独立136参考。产品不新增数值实现，不改FG/FGV/vLLM/Torch/SDK，不设置MCCL_GRAPH_MIXING_SUPPORT。MetaX补丁导入范围保持原厂商入口，其他平台路径不改；无其他硬件通过声明。适用plugin:A2/A4/B3/B4/C1/C2/E1/E3/E4/F1/F2/F3/F4/F7。之后重新加载大模型验证完整响应，组件通过不等于整模型通过。

配套范围补充：实际 `PlatformFL.use_custom_op_collectives()` 仅列NVIDIA/AMD/Hygon/THead/Iluvatar，MetaX返回false，直接删除旧override尚不能证明真实模型Dynamo边界。限定再修改现有vendor能力名单一项，将MetaX ctypes通信经原生custom-op，保留其余平台/配置条件；在同一个既有测试文件加7项能力守卫，负对照仅MetaX失败。a1修复试跑因测试stub遗漏world_size而4项失败，已自动回滚，属于测试设置错误，回执保留；补齐字段不放宽输入/alias/异常断言。a2验证与a3配套变更分别冻结，最终产品共pynccl_wrapper/platform两文件，无其他通信实现重写。

通信修复a3两机结果：每机7项能力负对照仅MetaX失败1项，修复后16项全通过（含真实Dynamo custom-op编译、输入/alias、禁用回退、异常不重试和Abort）。after-manifest SHA为101 `c3d76cd104eacf1f7ce40ea4d39c7aea8e4475ffebf99f654945a2806a06f7a8`、102 `73defea44f327757cd1c3264cacee9b0635966dfa9b709824ca54abd03d716b3`；原生产物 `01-environment/glm-collective-contract-patch-a3-20261103/<host>/`。通信增量diff SHA `7f0212e89a3a0b8f4b5b3b29ffacfbb6ca3fe13858ecfe84276f97b6a1ce4fa5`。新增用例lint/format通过；产品全文件显式lint存在继承项（platform改前后均6；pynccl改前4、改后2），未夹带清理；非本次修改行缺陷不宣称已修复。双机TP16真实graph探针仍待结果，不据CPU/接线回归宣称模型通过。

真实双机通信图a4已通过：16rank全部报告原生 `CudaCommunicator.all_reduce`、custom_op=true、PyNccl enabled；3次BF16 eager为136且输入不变，80次all-reduce组成同一图，100次纯图和100次图后eager all-gather变输入重放数值全部正确。独立输出sentinel重置、输出非alias，两机driver rc0且无超时。源码SHA `5292a2ffa83934ba554b2e477f235b9d1314a1915a554b94e7aa35dc7e2c27df`；`04-runs/glm-tp16-collective-graph-default-a4-20261103/<host>/driver-result.json` SHA分别101 `8565d1dca65553177813c017abf4506bf3248da727ac48877fbc55280d15c472`、102 `6029465667b9be03cf8cd84b1c77d63614985b6b20ccb5ddfd7bcaf28849a823`。MCCL_GRAPH_MIXING_SUPPORT未设置；不能据此反推旧TorchPG路径卡住的机制已被完全解释。

新整模型验证a6（20261103）冻结本轮8文件（4产品、4个既有测试文件）、前述组件和通信证据。共享b4 launcher不改，派生诊断仅增加原生cudagraph-metrics；先102后101启动，完整回答及实际FULL计数待验。此前a4异步25次FULL后超时、a5无异步12次FULL后超时仍保留，不列入成功结果。

2026-11-03 a6整模型诊断已通过内容检查：mixed PIECEWISE 5/5、decode FULL 4/4捕获成功，API于00:54:37就绪，无自动降级。102权重加载454.15秒，其间mmap I/O持续推进，未添加超时或缓存开关。三并发算术分别输出391/551/527，全部finish_reason=stop，约50.135/51.851/46.664秒。原始needs_review报告SHA `35f4ed561556ece50e83bddb70da7bbcee4b9f0035efe940be6a97a16aa2bd6c`，单独内容审阅SHA `fd657b09bd8a93f5084386e778d3281e49c506f11a4854632248bf56046f076e`，原生validate_result通过。native Runtime FULL合计97次，覆盖3、2、1请求及3填充到4，完整结束，已越过此前25/12次后卡住的位置。该对照支持通信修复有效，不将MCCL内部机制推测写成已证实事实。

另在 `04-runs/glm-piecewise-short-prefill-a6-20261103/mx-101/` 以4-token原始prompt `1+1=`、max_tokens=1验证实际prefill PIECEWISE 1次，输出2；这是有意单token长度截断的调度诊断，不是完整回答sanity。verification SHA `37b4b99439d4080a9361be60aa322bb008a1b79c17bbe8e2f477886ca53cc46b`。较长23/47-token首轮prefill超过当前capture上限16，实际NONE；不能声称所有prefill都进图，也不虚增每rank重放次数。随后移除metrics，用同一根级b4最简脚本重启并做最终文本/图像检查；正式执行模式数值对比、GPQA、性能和镜像仍未恢复。

最终合并来源统一回归 `glm-graph-regressions-a6-20261103`：两机各242项单元、16项GPU真实图测试全通过，无失败、错误或跳过；8文件及其他组件来源不变。after-manifest SHA分别为101 `4838327819b631017c0fbec781c9fac54e8e95c58ccf6309cbe3eb83a0fddab4`、102 `e2818800f1203e9ad48b40504e56660b6d39e2f85bdc817666db2725a68b5b98`。测试期间101无模型服务，没有在运行的101服务旁共享GPU做探针。测试文件默认lint与format通过；额外I规则检查发现既有编译helper的1项I001，改前后相同，未借机改写或宣称完整pre-commit通过。

最简正式脚本复测 `glm-full-and-piecewise-normal-a6-20261103` 于01:18:11就绪，原根级 `start-model.sh` SHA仍为 `b4b959abacc49bb51a7984bd1bf2309db06a37239b69e63413a0d037be9ea2c8`，prefix开启，无metrics/no-async/enforce-eager开关。101 API PID1374728（wrapper1374722），102 headless PID766881（wrapper766875），同一双机TP16/PP1服务；不重启或替换容器。两条文本及一条图像均正常stop：527；两句话正确解释水滴折射、内部反射与色散；准确描述左红色正方形、右蓝色圆形。耗时分别26.267/101.520/31.063秒，仅记录功能样本，不作为正式性能通过或速度提升结论。

最终原始报告 `04-runs/glm-graph-functional-normal-a6-20261103/mx-101/sanity-result.json` SHA `bfab0b444fcd8c86e99952e21de4ea305bc58a24ad25af3190db8ddcf1812e91`，原始needs_review不改写；单独内容审阅SHA `b6fdd5d8cd4ea706de501dcb1919256830e7c3ad0a14e7947eb5b556883b2a14`，原生validate_result通过，content-verification SHA `b0f6190580d6e19253eaef1836d5c268ecf3ea38a0d867d2ce9c82d5e5f375ab`。本轮图功能通过不替代当前源码的eager/graph logprob正式对比、GPQA、性能或镜像验收。

最终服务取证 `04-runs/glm-graph-service-frozen-normal-a6-20261103/<host>/verification.json` 核实实际TP16/PP1/双节点、各8个worker、prefix开启、无诊断开关、来源未变和服务运行；SHA为101 `3ca42350e6a4296a4a59a128544f5c128834a95f712aa9150261d77c1cfb9f25`、102 `44d74b6af460efbdb890971471f7d7660354b1ccd2c73fd2a8db215c9450aa66`。当前启动来源manifest SHA为101 `38c50da11671f85a21d276496fe28ae67e546936a1adad23cab2a5e57e0b0d02`、102 `c43f4205e13a309ab16bd838b66e7ef48b596500abf573620040d2173dc0b7b8`。

源码冻结位于 `01-environment/glm-graph-final-source-a6-20261103/<host>/`，包括Plugin/FlagGems/FGV相对各自HEAD的完整补丁及修改文件、8文件本轮增量、最简脚本和容器身份；manifest SHA为101 `cef7cf38ee378c97e4268c50c69ef987441ae5aa43bda6b1ac4cc5b13b162339`、102 `8766c27e4e20e5d224aa89293196bb7a1809b83d5ffc3fab829c0c017669d95a`。这不是镜像封装：101实际基础镜像为 `local/qwen3.8-flash:snapshot-20261027-093440`（d4bf8593），102为 `local/glm5.3-flash:mainline-20261027`（a6f6bad1），不声称两机基础镜像相同或新补丁已进入交付镜像。两机原CID与/public-flash的RW映射保持，未提交或推送代码。

最终增量设计审查（相对本轮改前安装字节，完整相对HEAD补丁另存上述目录）：

| 已有文件（Plugin根下） | 增/删行 | 职责与必要性 |
|---|---:|---|
| `vllm_fl/dispatch/backends/flaggems/impl/mla.py` | +39/-18 | 公共算子图能力与单token decode范围一致；按实际builder归属处理聚合KV spec，未知范围保守NEVER，未改数值forward。 |
| `vllm_fl/models/glm5/kpool.py` | +14/-0 | builder持有固定metadata槽位缓冲，容量拒绝、padding重置；无positions时原mapping身份保持。 |
| `vllm_fl/dispatch/backends/vendor/metax/patches/pynccl_wrapper.py` | +2/-18 | 移除违反非原地契约的通信覆盖，保留MCCL库及Abort适配，恢复原生分发。 |
| `vllm_fl/platform.py` | +9/-2 | 在既有ctypes平台能力名单加入MetaX；其他平台原条件保持，无GLM专用通信分支。 |
| `tests/unit_tests/glm5/test_mla.py` | +93/-4 | 解码能力、聚合spec及非目标守卫；旧实现负对照与当前回归。 |
| `tests/unit_tests/glm5/test_cache.py` | +31/-3 | 固定地址/状态/padding、容量边界与原身份语义。 |
| `tests/functional_tests/compilation/test_graph_capture.py` | +283/-0 | 独立CPU参考、公开ATen与自动分发、变输入真实capture/replay及输出sentinel。 |
| `tests/unit_tests/distributed/test_collective_compile.py` | +67/-0 | 原生编译边界、通信输入/alias、失败不重试、平台名单与未命中路径。 |

所有新增/删除hunk均对应已复现问题或其回归，没有新数值kernel、平行分发或额外后端重试。相关主机实测与负对照已列明；其他平台硬件、旧Torch兼容和完整pre-commit未验证，继承lint项仍披露，不宣称完整PR门禁就绪。适用plugin:A2/A3/A4/B3/B4/C1/C2/E1–E4/F1–F4/F7；operator规范用于独立数值、状态与graph验证，本轮没有算子库产品修改。

2026-11-03 01:32 CST最后只读复核：101 API1374728健康200、模型alias正确，102 headless766881运行；两机各8个冻结worker身份及当前源码/HEAD/diff均匹配。PYTHONPATH、CUDA_LAUNCH_BLOCKING、MCCL_GRAPH_MIXING_SUPPORT、额外启动超时变量均未设置，未留下诊断配置。原容器和服务保持运行。

本地作用域记录/来源/服务绑定断言及 `git diff --check` 通过。全库audit另有2个范围外错误（根README与models/README指向缺失的XingChen4-29B-A4B记录）及14条历史warning，本GLM/MetaX工作区无审计问题；未修改其他模型或据此声称全库审计通过。既有341项离线工作流回归、7项运维回归的通过记录保留，控制工具未修改，不将它们冒充本轮模型验证。
