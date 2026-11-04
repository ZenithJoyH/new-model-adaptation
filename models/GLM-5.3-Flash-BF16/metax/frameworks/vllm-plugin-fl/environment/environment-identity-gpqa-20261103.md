# GPQA前置环境复核（2026-11-03）

用户要求全量GPQA后，明确选择先补齐前置验证再运行。范围为mx-101/mx-102原glm5.3-flash容器、既有批准根 `/public-flash/jinghao/glm5.3-flash`；环境、适配审查、执行模式及sanity按序补齐，未授权恢复正式性能或镜像交付。当前accuracy前置检查明确返回environment未完成，不把先前图功能检查改称正式验收。

已只读复核：原服务与冻结来源一致，101 API1374728、102 headless766881，各8个worker，TP16/PP1、FULL_AND_PIECEWISE、prefix开启。当前KV容量388096 tokens，最大上下文65536；既有198题提示审计最大2901，四路各最多60000生成共251604 tokens，容量可容纳。计划GPQA保持temperature1、top_p0.95、并发4、零API/eval重试及完整198题，strict-match门槛0.85；前置通过前不发GPQA请求，原结果和缓存保留。

通信预检先固定官方MetaX-MACA/mccl_tests提交 `1e44d4af1b177f2ab9e23bdd0b393ad757d08f4e`。已阅读该提交README、build.sh、Makefile及cluster.sh，后者实际参数为带slots的host列表、总进程数和测试名；不使用其默认IP/HCA或推测的子网。两机现有SDK为/opt/maca指向/opt/maca-3.8.2，MPI4.1.6，实际模型映射libmccl.so来自同一SDK。SDK自带测试二进制可用，但不以未知构建源码冒充上述提交。

仅在批准根的03-acceptance保存17个构建必需的验证工具文件，逐文件核对官方Git blob和SHA-256；05-tmp内构建AllReduce/AllGather/ReduceScatter，不执行install/clean、不改SDK、网络或SSH策略、不创建产品源码副本或Git checkout。原适配容器始终运行。

实际通信验证：CPU引导 `glm-mpi-container-bootstrap-a3-20261103` 的两个rank分别处于原101/102容器PID namespace，CUDA_VISIBLE_DEVICES为空，rc0。前两次引导的接收等待超时、拒绝OpenMPI环境前缀均保留；没有在这些失败中启动GPU测试。正式GPU预检前按冻结PID/start_ticks仅停止本任务原服务，并确认原进程退出、容器保持运行。

`04-runs/glm-mccl-suite-a1-20261103/` 已完成24组：两机分别8卡、双机各1卡、双机各8卡，每种拓扑均AllReduce/AllGather/ReduceScatter × FP32/BF16。每组64B至64MiB、倍增21个消息尺寸、warmup5、iterations20、每rank一GPU、`-c 1`；全部rc0、全部尺寸in-place/out-of-place错误0、终态Out of bounds values为0 OK。逐rank PID namespace/boot ID对应原容器，LD_DEBUG实载路径及库SHA核对一致；官方工具使用与模型相同的SDK MCCL，而非宿主库。没有残留mpirun/orted/测试进程。工具构建、原始逐尺寸延迟/algbw/busbw、命令及库加载trace均留在批准远端根。

实际跨机路径为 `inbond1` Socket。102的bond当前仅一条25Gbps成员up，另一成员down；两卡AllReduce大消息algbw约2.06～2.19GB/s，与这一路径量级相符，不将busbw当作网卡吞吐。bnxt用户态/内核ABI不匹配导致MCCL报告NET/IB No device found；RDMA未通过验证，未改驱动、SDK或网络配置。OpenMPI在NFS临时目录退出时产生PMIx权限/清理告警，原始告警保留；所有测试已正常返回且实际进程清理已复核，不将告警隐藏为无告警退出。

独立整理回执位于 `01-environment/glm-mccl-reviewed-a3-20261103/<host>/environment.json`：101 SHA `7380be92354c1867a56021df3d70a2f3f389f7393b07910e6e1ce31b498a157f`，102 SHA `04eaa2176a1fbd54004ed623038b6498911eb6ac680c480348d3a26055962dc0`。前两版整理脚本在读取参数时失败，不影响已完成通信结果；新回执重新读取并核对全部原始产物，未重新发送测试。该回执也记录当前组件、权重元数据、设备映射和共享脚本；正式阶段绑定仍需原生gate核验。当前源码检查正在补齐，eager/graph、sanity及全量GPQA尚未执行，不从通信通过推导模型验收通过。
