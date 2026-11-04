# CPU型号归因：排除GPU的补充实验

## 执行前范围与判据

用户要求进一步验证DeepSeek两机性能差异是否由CPU型号不同造成。沿用profile `vllm-plugin-fl`，仅`mxC588-5`、`mx-104`，不操作103。2026-11-04重新核对原容器ID、原launcher、8worker及映射：C588批准宿主/容器同根`/data/jinghao/deepseek`，104为`/public-flash/jinghao/deepseekV4`，容器名均`deepseekV4-flash`。control.mode仍为agent；旧mx-59正式目标及阶段状态不改。

既有015只能证明CPU侧路径差异，不能唯一拆分CPU、频率、系统内核和GPU驱动。现场新增确认：C588内核4.19.326、104内核5.15.0；104 intel_pstate/performance、最高3.7GHz，C588未暴露cpufreq policy接口；两机宿主负载也不同。因此新增不访问GPU的控制实验，不预设其一定支持CPU型号假设。

新产物仅放各自批准根`02-issues/cpu-proof-<Host>-20261104-01/`、`04-runs/cpu-proof-<Host>-20261104-01/`、`05-tmp/`。不修改服务源码、启动参数、亲和性、主机调频或内核设置，不停止服务/容器，不写外部cgroup控制。本轮只是CPU归因诊断，不是GPU算子性能验收或完整模型验收。

控制设计：

- 在104容器内用generic x86-64指令目标编译一次C探针与PMU共享库，再将相同ELF逐字节复制到C588并核对SHA256。依赖整数链使用固定公共指令；随机指针链覆盖L1/L2/L3/内存工作集，不使用GPU和厂商加速库。
- 固定单个CPU，C588 CPU0/56/98、104 CPU0/20/40，各覆盖多个核心/NUMA节点；数组在绑定后first-touch，计时前预热，7次重复。记录wall/thread CPU时间、调度等待、上下文切换、TSC reference ticks。
- 尝试对自己的诊断线程使用perf_event_open统计user cycles/instructions，记录time_enabled/running。若权限/硬件事件不可用，保留错误，不能把TSC ticks伪称实际core cycles，不能声称测得IPC。
- 相同容器Python/torch运行纯CPU日志、CPU Tensor创建、CPU view和Python对象操作；显式清空CUDA/MACA可见设备，检查CUDA未初始化、device count0，保留解释器/libpython/libc及logging源文件SHA。日志helper只执行原安装源的CPU定义，避免导入FlagGems GPU检测；这不是替换服务导入或证明GPU算子dispatch。
- 对比每操作CPU ns、cycles、instructions、IPC及可测得的有效频率，剔除/披露调度等待或PMU multiplex污染；固定指令本身的差异与CPU/内存平台有关，但仍不自动证明原14.55% E2E差距全部由CPU型号造成。

复核每端测试前后API/8worker PID、argv、launcher与健康状态。旧性能结果与新纯CPU结果分别保存，不能以CPU微基准代替E2E因果干预。若需要严格唯一归因，仍需相同GPU/驱动/系统下只改变CPU的硬件对照；当前两整机并不满足该条件。

## 已完成结果

两端均完成3个固定核心、每项7次，共105个原生C窗口和105个Python/CPU Tensor窗口；PMU cycles/instructions全部可用、无事件复用（running/enabled=1），固定核心未迁移。CUDA/MACA可见设备为空、CUDA未初始化、设备数0、GPU设备FD为空。软件侧Python/libpython/libc、libtorch_cpu/libtorch_python/torch._C/libstdc++和实际CPU回放脚本SHA256均逐项相同。

**新增直接证据：这些推理主机热点在C588上完成几乎相同的指令数，却消耗明显更多CPU周期；C588在这些窗口的频率指标反而较高。** 因此不支持用GPU速度、GPU驱动调用、C588低频或OS调度排队解释这些纯CPU测量差异，证据指向这类代码在两CPU平台上的每周期执行效率差异。

下表使用每端全部21个重复窗口按每操作CPU时间排序的中位数窗口，各列来自同一个窗口，避免拼接不同窗口的周期/频率。

| CPU-only路径 | C588 CPU µs/次 | 104 CPU µs/次 | C588额外CPU时间 | C588/104 指令数/次 | C588/104 周期数/次 | C588/104 IPC |
| --- | ---: | ---: | ---: | --- | --- | --- |
| 禁用日志检查 | 0.160 | 0.119 | +34.33% | 1755 / 1754 | 494 / 319 | 3.55 / 5.49 |
| once日志记录 | 5.638 | 4.385 | +28.58% | 41412 / 41460 | 16804 / 11980 | 2.46 / 3.46 |
| CPU Tensor创建 | 3.090 | 1.981 | +55.97% | 17640 / 17695 | 9574 / 5527 | 1.84 / 3.20 |
| CPU Tensor view | 4.443 | 2.947 | +50.76% | 21069 / 21128 | 13767 / 8223 | 1.53 / 2.57 |
| Python小对象操作 | 0.308 | 0.205 | +50.64% | 3159 / 3144 | 955 / 551 | 3.31 / 5.71 |

最直接的Tensor view例子：约21069对21128条指令（差0.28%），需要13767对8223个用户态周期（C588多67.4%），IPC1.53对2.57；线程CPU耗时4.443对2.947µs（多50.8%）。从用户态周期/线程CPU时间得到的频率指标约3.10对2.79GHz，因此本例不是C588低频造成。该频率指标在包含系统调用的日志case中会低估实际核心频率，不能用于精确解释该case的调频。

Tensor view全部21窗口的runnable等待最高C5880.063%、1040.149%；对应系统CPU时间最高0.442%/0.061%。小Tensor创建的系统时间最高0.945%/0.078%。约50%–56%的CPU时间差远大于这些扰动；两个热点的实际指令数差均小于0.4%。CPU-only replay不是GPU算子benchmark，也不是ATen GPU自动替换激活证明。

计数定义依据[Linux perf_event_open手册](https://man7.org/linux/man-pages/man2/perf_event_open.2.html)：使用CPU_CYCLES和退休指令事件，仅统计用户态，并核对time_running/time_enabled；IPC为实际指令数/周期。实际core cycles随频率变化，TSC reference ticks单独保存，不冒充core cycles。

## 反例控制与解释范围

固定公共x86-64整数依赖链的每次迭代，两端均约6条指令、约5个周期；C588约1.614ns、104约1.795ns，C588反而更快约10%。16KiB/256KiB/8MiB随机指针链C588也更快；128MiB链C588约97.52ns、104约66.57ns。大工作集包含内存系统差异，不能全部归为CPU核心。

这说明不能笼统宣称“海光所有CPU计算都慢”。本次证实的是**当前推理使用的Python/小对象/Tensor元数据路径，在这两台机器对应CPU上的单线程有效IPC明显不同**；与015记录的DeepSeek CPU调用密集、Qwen CPU余量更大相吻合。

本次没有换CPU，也没有做同GPU/驱动/内核下仅更换CPU的整模型对照。因此结论分两层：

- CPU侧热点执行效率差异已被硬件计数器直接确认，是CPU为重要影响因素的强证据；相同镜像下的差异并非仅GPU驱动回放或CPU利用率观测假象。
- **不能据此声称先前14.55% E2E差距100%由CPU型号造成。** 两Host的GPU、内核、驱动、内存及安全缓解机制仍不同。C588报告Retpolines/untrained-return-thunk，104为Enhanced/Automatic IBRS；未更改这些设置。模型worker均Seccomp0、Speculation_Store_Bypass为thread vulnerable，未发现一端单独开启SSBD造成的明显配置不对称。系统间接影响仍不能完全消除；严格唯一归因仍需匹配硬件/软件的CPU替换对照。

## 可复核证据与收尾

两端批准根下`04-runs/cpu-proof-<Host>-20261104-01/`的`result.json`保存全部原始窗口，`cpu-only-core*.json`保存各核心CPU回放和软件哈希，`summary.json`保存统一汇总，`final.json`确认原服务/launcher未变；C指令循环反汇编位于104同目录。源码与同一ELF位于相应`02-issues/`，未写产品源码。

| 产物SHA256 | C588 | 104 |
| --- | --- | --- |
| result.json | `0020abed7acc482d660d8e6fb708d5d7bf96a5d05b9d092ffc7735e2ecc5b0a0` | `e92ac45480e96bbe610d61624db3c92043ec438384d5849d22ef030b299d5ffd` |
| summary.json | `89558c95b5d26c50f28e9050a60c3b298eba5c2a3b5dd6ea5e3e012d95072005` | `1f0d386fe93e2b68e772a66a80e5a23a86e7ee0b3b0e5bbbd373a4be9e49f3da` |

两端共同CPU探针ELF SHA256为`50ad3657f8624e8d5893115a71867635f9aba88b1aac6b8883633eb968823b17`，PMU库为`c45eb2430e9258de0314a157319e6bc1d164e4bac8af2c41fe6b8385f3326db3`。libtorch_cpu相同SHA256为`257c6e17037782a82db5f09d1f2542382624cca9d212808b1be63863c4fd2759`；其余软件哈希逐项比较通过，保存在summary。

104首次收尾验证因JSON把rank键转成字符串，而运行时字典使用整数键，比较失败；修正验证器键规范化后通过，保留原失败回执，没有修改刺激或测量数据、没有重跑CPU测试以挑选结果。

两Host最终均verified，8worker/API PID、原argv、原launcher与测试前一致，健康且空闲；本轮无需恢复任何调频、cgroup、亲和性或源码设置，因为仅操作自己的诊断进程。未重启模型服务或容器，未操作103，未提交/发布。两个playbook语法检查通过；没有据此提升旧正式适配或验收状态。
