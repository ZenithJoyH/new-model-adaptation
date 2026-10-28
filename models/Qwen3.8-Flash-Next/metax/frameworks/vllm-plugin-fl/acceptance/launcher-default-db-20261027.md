# 2026-10-27 默认本地数据库启动与回归

已删除`export FLAGGEMS_DB_URL=sqlite:///:memory:`，未改到外层环境或其他变量。
mx-101 / qwen3.8-flash，容器ID`06b36c1d70e22ca68adef42e521d76f9b597f3fc6e8c0a9a8738ef03e1b85289`，
批准根`/public-flash/jinghao/qwen3.8-flash`同路径RW映射不变。
根脚本与容器内部`/opt/qwen3.8-flash-delivery/start-model.sh`均为
`c207cc11bfba76819ec04510cd34c8647ecc5fec92492dd48e8ba1eff6e3eda3`。仅保留FGV接入和clone,randn,normal_排除两项导出；
TP8、100K、max_num_seqs32、prefill6400、text-only、align、qwen3 parser和FULL_AND_PIECEWISE不变。
普通调用开启prefix；唯一`--performance`开关仅关闭prefix，未知参数退出2。

## 启动和默认数据库

旧PID3433953按owner/boot/start_ticks/cmdline精确核对并SIGTERM，未停止容器或其他服务。
新实例`launcher-default-db-normal-20261027`，PID4113542，start_ticks1140041619，
boot_id`d25f985f-9dbf-4aa8-ac92-e5437b2a76b4`，8000端口；从启动至health/model就绪约340.0秒。
实际参数和进程初始环境已取证，DB及此前缓存覆盖均不存在；mixed/decode图捕获完成。
默认数据库路径、真实worker文件描述符和独立进程SQLite读取见[环境补充](../environment/database-defaults-verified-20261027.md)。
没有清空、迁移或手动改写调优表；两库quick_check均为ok，未发现database is locked、OperationalError或引擎退出。
FlagTune缺少可选xgboost、使用既有default策略的警告保留，未通过新安装改变基线。

## 精度和延迟对照

明确选择仓库精度Skill的`service-sanity`，bundle SHA256为
`355bdf2946456710e0dbaaa9b331062f86be2ec4e5740f7be91ac57a6daa167d`。
冻结请求来自已核实100K eager参考：3个短算术案例和一个8730-token长前缀案例，
每项6轮、并发1、temperature0、seed20261023、关闭thinking，保留原请求生成上限与logprobs。
两组分别24/24完整文本匹配，错误/超时0；采用未修改原生sanity.execute/validate_result，
外部包装只记录墙钟时间并逐项保存原始结果，不重试或排除失败。
容量依据为同配置已通过的并发8小集，本次保守使用1。
额外smoke/prefix-state/mixed-state共10例、105个生成token与旧eager参考全部相同，
数值有限，最大生成token logprob差0.004307605326≤0.02。

下表单位秒；每格顺序为“内存DB / 默认本地DB”。首轮单列，后5轮用于暖请求统计。
新实例经历重启，旧实例已运行，因此首轮不作为严格同冷启动状态的因果比较。
固定cache_salt在每组内复用，普通服务prefix保持开启；这是延迟健康诊断，不是cache-off吞吐基准。

| 案例 | 首轮：内存 / 默认 | 暖中位数：内存 / 默认 | 默认暖最大值 | 暖中位数变化 |
| --- | --- | --- | --- | --- |
| smoke/add | 0.489 / 3.109 | 0.479 / 0.474 | 0.556 | -1.1% |
| smoke/multiply | 0.521 / 0.569 | 0.604 / 0.541 | 0.572 | -10.4% |
| smoke/subtract | 0.511 / 0.446 | 0.527 / 0.471 | 0.516 | -10.7% |
| prefix-state/cold | 19.227 / 32.528 | 6.227 / 6.162 | 6.316 | -1.1% |

各项暖中位数未触发预先冻结的1.5倍调查线，未重现历史NFS数据库短请求约25秒的反复停顿。
调查线只用于定位本次明显回归，不是业务性能达标线；不据5个暖样本推断P99或高并发吞吐。
此次检查范围通过，可采用默认本地数据库。全198题GPQA和九场景正式性能未重跑，
183/198（92.42%）及756请求等结果继续属于2026-10-25旧脚本/实例，未改写或重新绑定。

## 交付及证据

根脚本与内部副本相同，runtime、交付清单及恢复说明同步到
`03-acceptance/delivery-launcher-default-db-20261027/`和`/opt/qwen3.8-flash-delivery/`。
当前普通服务及适配容器保持运行。安装源码、完整Git diff、新增文件、模型输入和编译二进制
通过既有身份检查；没有修改产品代码、权重或挂载。镜像打包/新容器验证仍pending。
性能分支新脚本已做真实shell参数/环境展开；原EngineArgs证据只复用于未变化的argv，
未声称本次运行了性能服务或性能基准。final-recheck明确区分此范围。

以下路径相对批准根，原始结果未复制进本地模型目录：

| 证据路径 | SHA256 |
| --- | --- |
| 04-runs/launcher-default-db-normal-20261027/launcher-verification.json | 8ab5eb61568c040e06fc9ce8f19feabd3b3b205d9102aaa7bf7025d0e029da79 |
| 04-runs/launcher-default-db-normal-20261027/final-recheck.json | af74f521136589567f88c49d6503ea8d9c800a398ac18a28fc7c2a66b2eace25 |
| 04-runs/launcher-default-db-normal-20261027/eager-comparison.json | 5ce1fa0108a7cb1cd96183e157e8826eb255c7fb690b47b3cf78e82ec6b23d33 |
| 04-runs/launcher-default-db-normal-20261027/database-proof.json | b1b752a3be04e4f2f148d0686b4f67cf340c257573520beee9fb8f2baf696469 |
| 04-runs/launcher-default-db-normal-20261027/latency-comparison.json | 55b9514bfd8ae1538da4128b3366fa7bfbd5d2764b3d5dfbef1b6654be2e75c0 |
| 04-runs/db-default-memory-sanity-20261027/sanity-result.json | d5e3f947d32f5fbcac76b6848ac02e177776f4d3b26b6c57edc856cb34cd28e6 |
| 04-runs/db-default-local-sanity-20261027/sanity-result.json | 509553c61b100c2c7c2de614f5d408b14c8ccc8aee325cf5e4763196f8123c0b |
| 04-runs/db-default-memory-sanity-20261027/latency-result.json | 11f7aa29da8c25176a4af07d4388dd561550af1620616243895b8c6fa9211913 |
| 04-runs/db-default-local-sanity-20261027/latency-result.json | f4eb7c4c94212889db963ff31577d01746e5597412e737187e7279fcd72b8e44 |
| 03-acceptance/db-default-plan-20261027.json | 8bc75d0bcd9a13bf0a83cbde528b51b9b35f3abb72a2b7871f4aeb2998d7b50b |
| 03-acceptance/db-default-sanity-manifest-20261027.json | 8a4cb374a56bd9769a0a7a9b548277959bde956c0c0a87c7817fe81da2d28864 |
| 03-acceptance/db-default-skill-20261027.json | 57adfdc86d75e15fd818b2ed27db06e2bb6475652e21fd6350b689bf82369077 |
| 03-acceptance/db-default-native-sanity-20261027.py | 16cc7a1cfcb41ae3fee8581a2dca7550f7bdf07eddddc993c51dc8c7941f5cd4 |
| 03-acceptance/apply-default-db-launcher-20261027.py | 095887e1e6a4fbe4d63aaacd18b5d90024d32e5c64ff885cdc0d7673b1984a3f |
| 03-acceptance/db-default-postcheck-20261027.py | a7759b83fdcd05ca384e8b6a0464a4814ffaa532d5db73813e72219fde052ca0 |
| 01-environment/launcher-default-db-normal-20261027.json | 8ad772a8e2380cb15c63925b91a331ffbc7516905b9a8e22bb8f277110bd8e49 |
| 03-acceptance/delivery-launcher-default-db-20261027/delivery-manifest.json | 6c61feb4b5a00202bc69553c0c3c144402353ff897538f14f748edf6375d34b0 |

上版根脚本和内部文件备份于`04-runs/launcher-default-db-controller-20261027/previous-start-model.sh`
和`previous-internal/`；旧SHA1550bacb及回执保留为历史。
可恢复控制阶段记录为`04-runs/launcher-default-db-controller-20261027/state.json`，
执行包装为`03-acceptance/apply-default-db-launcher-20261027.py`，冻结计划为
`03-acceptance/db-default-plan-20261027.json`；本操作不支持正式journal完成映射，未借其他阶段回执替代。
