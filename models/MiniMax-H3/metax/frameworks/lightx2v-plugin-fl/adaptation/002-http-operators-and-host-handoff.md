# HTTP算子取证与104接续

2026-11-17，用户要求暂停57并切换104继续。57的诊断控制器、torchrun及8rank已由执行者只读确认退出，端口空闲、8卡仅858MiB/0%、无GPU进程；普通服务尚未恢复，按用户新指令不再执行57后续。容器保持运行，既有文件和失败原件保留。

57的HTTP-OPS-002首请求`NI8D-5NXB-GHIH-QWR8-4PU2`完成并下载媒体。观测器误把默认关闭的可选LibEntry缓存绑定分支当作必需命中，因此8rank取证回执仍为incomplete；不修改旧判据或回执翻pass。源码核对表明RMS使用`@libentry()`的默认`cache_binding=False`，实际通用缓存另走`kernel_cache`及`_first_run`路径。第二请求未提交。清理末尾出现进程身份采样异常，原错误保留；随后确认无本任务遗留进程，未把该异常推断为已证实的PID复用。

原件仍位于57共享目录`/public-flash/jinghao/minimaxH3-dependencies-20261116/04-runs/HTTP-OPS-002`及对应环境/问题目录。其部分真实native/kernel与Torch计数不转标为104结果，尚未完成独立全项分析；正式profile/精度/性能验收未通过。

已连接`mx-104`，实际主机`bm-zksg-wx-zone1-d-mc550-64g-2-104`；8张C55064GiB当前空闲，权重`/public-flash/models/MiniMax-H3`可见。104无H3容器，但已有与57相同摘要的基础镜像`sha256:1e73934aa791993ed5a67e1fc30eae952813ce4c27ef67b6d38abac574b53e1b`。独立工作根选在已授权用户目录下`/public-flash/jinghao/minimaxH3/mx104-20261117`；容器和应用基线尚待准备验证，不能把共享权重可见或同镜像当作104环境通过。

当前工作区只将接续目标改为104，profile快照、control.mode=agent、所有原not_started状态与空部署指纹保留。拟沿TP4×SP2、文本编码器TP8及同形状配置，先核新容器映射与固定应用基线，再修过程观测器的通用缓存判据；不修改数值算子、驱动或厂商Torch/FlagTree/FlagGems，不操作104其他服务。
