# mx-101 环境核验（2026-10-23）

目标 `mx-101`，容器 `qwen3.8-flash`，ID `06b36c1d70e22ca68adef42e521d76f9b597f3fc6e8c0a9a8738ef03e1b85289`，host network。`/public-flash` 同路径 RW bind；批准过程根 `/public-flash/jinghao/qwen3.8-flash`。已通过维护入口 connectivity-check；容器保持 running，初查仅有原始 shell。

8张MetaX C550，每卡65536MiB，初查各858MiB且无设备进程。宿主机驱动3.8.1、MACA3.7.1.5；容器 `/opt/maca -> /opt/maca-3.8.2`，Torch `2.10.0+metax3.8.2.2`，解释器 `/opt/conda/bin/python`。原Triton `3.6.0+metax3.8.2.2`，没有FlagTree distribution或checkout；用户要求源码安装最新FlagTree。容器根盘初查剩余6.3GB，后查6.7GB；构建产物需核对容量，不删除其他任务数据。

实际editable安装：vLLM `/opt/vllm`，Plugin `/opt/vllm-plugin-FL`，FlagGems `/opt/FlagGems`，FlagGems-vllm `/opt/FlagGems-vllm`。均在容器内部，未被宿主机bind覆盖；未设置PYTHONPATH。精确版本、revision、原始dirty与diff保存于远端 `01-environment/baseline.json`，摘要见[001](../adaptation/001-pr455-flagtree-metax-bringup.md)。FlagGems与FlagGems-vllm远端分支查询分别等于现有HEAD `e510c6bb`、`c9003571`，无需更新源码；FlagGems继承权限位差异保留，未执行会丢弃改动的同步。

模型 `/public-flash/models/Qwen3.8-Flash-Next` 的config与index SHA256分别为 `889658f2508e8c61d409b02e70e0d78d8d4452ec65aaafbe129805d213d2e74b`、`99e815241ef03325536b0aaa4441deea45174c17fae31e10f0bb456410c590de`，与中文架构分析一致。配置文本最大上下文262144，按流程初始50000；BF16文本路径，TP8。整模进展单独在适配记录维护，此环境记录不构成推理通过。

PR455冻结 `65759c432cef847c311ccd0ab9dc077ab91454ed`，以共同祖先到PR差异三方应用到现有Plugin；原HEAD `f41b7de883ed71526716738a7e05d810f49ded58` 保持，不提交。原始证据均在已批准过程根。

源码安装已完成：官方FlagTree main `2f1229e51c03b345a1c72207854828eed7282de9`，安装
`flagtree 0.7.0+metax` / triton3.6.0。MetaX官方插件v0.6.2与pybind ABI11配对，固定
pybind11=3.0.1重编；实际JIT和graph回归通过。新wheel SHA256为
`2e2c32127e7de54f2f10dc630b45089229896cb50a1f53fdc51c55e1c736a7a5`。
原Triton distribution元数据并存，实际核心文件归属已按FlagTree RECORD核实，未借助路径覆盖；
详见[001](../adaptation/001-pr455-flagtree-metax-bringup.md)。

用户补充的FlagGems-vllm PR959冻结`22194f0b`，已应用且本机211/211测试通过，无跳过。
另在已复现的问题002修复短prefill状态同步，在问题003接入MetaX合法QSA M16 tile；分别
验证fusion37通过、QSA37通过/8项PPU专用skip，组合340通过/42跳过；新增受限selector后QSA51通过/8跳过，auto组件性能18项达标。
不将算子结果当作服务完成。

阶段性环境快照（含selector，尚不含后续异构Mamba兼容修复）为远端 `01-environment/installed-identity-after-qsa-auto.json`，SHA256
`478cce81c09f170bfe913099d0c8840409dab578294c13a0fc6b31dac6a3ae2c`；
完整补丁包含新增wrapper与benchmark文件。部署身份清单
`01-environment/deployment-identity-after-qsa-auto.json` 的SHA256
`ba1066b3bbaadd7b16a2f436628c05f430429e43750c381d8ca53b56aa435b4c`，绑定实际镜像
`sha256:a5d8d34d437eb3dfe45158078421792b9e2e5fc48a9d3d25431625110756dc96`、
容器/挂载、实际组件与库哈希、模型/tokenizer文件及分片大小、TP8和基础运行语义。
权重分片未逐文件计算完整内容哈希，实际加载验证另行记录；未将stat大小当作内容哈希。
vLLM完整diff仍为最初的`2a77f03f...361ec`，无任务新增改动。

2026-10-24：上述部署清单现在是历史快照，后续Plugin异构Mamba工厂与clone排除、prefix/align、
prefill预算调整均须重新采集并绑定。eager三问已正确；较短探针均未覆盖6400公共块；新预算6400用于让长输入首chunk落在公共边界，配置SHA256
`233605754eb2b4843e25352bf2cae63a0aef2881477000019c21622393ada868`，
run `model-eager-cache6400-20261024`（API594094，start_ticks1108163959），正在独立验证。
旧eager实例通过核对owner后SIGTERM正常结束，原生停止记录 `stop-cache6400.json` passed；
只剩PID1未回收的API zombie，不是运行中的服务，未停止容器。

## eager阶段已核实部署（历史，2026-10-24）

新增异构Mamba兼容后的源码身份快照 SHA256
f465566e0f73c176c2e4459e488e32ce9801c1db57b8dc0a491ca7f5d450b513，
01-environment/installed-identity-after-mamba-compat.json。源码diff及新增文件逐项重新验证；
实际FlagTree核心/MetaX插件二进制哈希保持前述值，vLLM完整diff仍原基线。
该阶段部署身份 01-environment/deployment-identity-after-memorydb.json SHA256
af8a3b2358767a38c7f64f9a88866c4b0d71c55040f7a684f47291ff4359277b；
deployment-observation-after-memorydb.json SHA256
5002a34e2f3b1a1f9f2dbbae26bb953d1346a5c544d85ea31e9d8fc40f319f75。
本轮重新Docker inspect确认原容器ID/镜像/mount及running，核对服务真实/proc环境、
PID/start_ticks/cmdline和配置哈希，未设置PYTHONPATH。基准运行语义为TP8、上下文50000、
max_seqs32、prefill6400、BF16文本、prefix开启/align、FGV开关1、clone追加排除及内存SQL。
图/eager控制独立绑定于执行记录；基准身份冻结共同语义。

最终eager候选model-eager-fgv-memorydb-20261024（API711132、start_ticks1108345575，
config SHA256 4fc53f3956ad13825f8d09687027273c2e99fc0d78cb1ce3121117225d9cae5e）
三问全对，8730-token五请求三次各命中6400、logprob差0；混合流式1至30与新7×8请求
重叠且均正确。内存SQL保留已有内核与派发，避免NFS调优SQL等待；跨进程调优结果不持久化，
Triton文件缓存仍在批准根。正式精度/吞吐及graph结果由对应阶段记录，不以本环境段落代替。

## graph修复后的当前源码与部署（2026-10-24）

RoPE编译边界和MetaX编译产物修复后，当前安装快照为
01-environment/installed-identity-after-rope-functional.json，SHA256
85fbbd4dc82526a5c8fb13c34d71315a151463abf49c6792192e289d14fba5c9。
旧memorydb环境回执在旧部署原生gate通过，但不能覆盖新源码；framework.yml已将environment
恢复in_progress并保留旧verification。新部署已按显式FULL_AND_PIECEWISE配置重新采集身份，新原生环境回执核验中。
最新FULL诊断见008，不能把组件级graph测试或历史eager结果改称当前整模型graph通过。

当前部署身份01-environment/deployment-identity-after-rope-functional.json SHA256
8993aab5b78ef20887d4a26773cf84ae48077ee1918fbe3b20757911dc7b4d26；
现场观测deployment-observation-after-rope-functional.json SHA256
280ac1d752cf0d425d0b044042fbc98d52655081ca6896be0abbe2a2434beaa0。
重新Docker inspect核实原容器/镜像/映射/running，逐组件校验HEAD、完整diff、新增文件集合
及内容哈希；实际服务/proc argv、start_ticks、配置SHA和全部指定环境变量匹配，无PYTHONPATH。
FlagTree libtriton与MetaX插件二进制SHA保持前述构建值。图开关/metrics从共同语义身份中
剥离，实际运行配置单独冻结；当前clone,randn,normal_排除限定此服务进程，未改库默认值，
未配置同步诊断或worker extension。eager参考使用同源码、相同TP/精度/输入与prefix语义，
随机入口额外排除仅图候选保留，差异已显式披露；对照不构成正式数据集精度验收。

## 100K正式验收运行语义（2026-10-24）

用户已选GPQA full198≥88%及九场景性能测量（不做业务达标判定）。历史60000生成上限仍有
截断，故本轮上下文100000，正式生成上限96000；使用qwen3 reasoning parser与显式思考xhigh。
eager/graph统一clone,randn,normal_原生入口，仍为TP8/BF16、max_seqs32、prefill6400、
prefix开启/align及内存SQL，未改产品源码、模型文件或库默认值。正式精度只在graph上运行。
当前eager已通过基础短问、前缀状态和混合请求，原生报告KV849403token、100K容量8.49x；
八并发长输入及思考模式另行验证，估算容量不代替实际测试。

当前部署身份01-environment/deployment-identity-acceptance100k.json SHA256
7d11fb14052581da5757d4ef52b71eda288d65a91a4daf1668a7a10a23b800ef，
现场观测deployment-observation-acceptance100k.json SHA256
428a7788ad5521ba8eab9677422a365f811afd4399d007740e1a5eddf065f569。
当前源代码快照仍installed-identity-after-rope-functional.json（85fbbd4d...4fba5c9），
所有HEAD/完整diff/新增文件集合及哈希经新采集器逐项核对无变化；编译器/插件二进制保持原值。
新运行基础身份显式剥离enforce-eager及graph控制，仅模式切换不改共同推理语义。
原50K环境及graph回执保留为历史，不移植为100K通过；新状态以framework.yml原生回执为准。

本任务评测容器qwen38-mx101-eval-20261024（7b0bb746...e4292b）独立运行，镜像
harbor.baai.ac.cn/flageval/flageval-llmeval:v1，实际ID/digest
sha256:1396e5d63553530425db81ebf9a724aa98dc2e11aaf2e677c908f991a9cb7ce3。
批准根同路径RW bind，host network，无GPU请求；响应SQLite使用批准根06-cache/
flageval-responses内2GiB tmpfs。镜像自带GPQA离线缓存落到本任务06-cache/flageval-datasets，
实测198题、fingerprint2ea5394e17e3ee1b；任务/评分/适配器和缓存文件哈希见
03-acceptance/gpqa-dataset-provenance-20261024.json，SHA256
94fdd9e44e80b2acf85f28a26ec9dfa74f34376c49039f98216ed1f82961190a。
未读取或修改其它既有容器，题目/答案不落本地记录。
