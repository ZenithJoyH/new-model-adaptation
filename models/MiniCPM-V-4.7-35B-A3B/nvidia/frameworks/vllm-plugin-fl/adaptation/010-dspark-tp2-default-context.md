# 010：35B-A3B DSpark 双卡与默认上下文

## 范围和已核实身份

2026-10-10，按用户要求修改 H100-149 当前容器
`MiniCPMV4.7-1B-DSpark-gpu6`，ID
`a650538a4c01fe79d59d0bbacac4edc4cec52046e1072f3255f56c0161f23b11`。
容器保持运行，GPU0–5 的其他负载未操作；本服务选择空闲的物理 GPU6、GPU7。
宿主根 `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos` 对应容器 `/work`，
设备号及 inode 相同；完整 jinghao 挂载保留。

组件继承[009](009-dspark-plugin04-single-gpu.md)：vLLM 0.28.0，
Plugin `0.4.0-dev@e88e4db75ece36e482a5fcc288929d4461d53184`，
FlagGems `0dddb4628ae215931171a7f6e04a1183777dcd8a`。
主模型和草稿仍为 `/work/06-cache/dspark-35b-weights/{main,draft}`，没有再次复制权重。
本轮操作配置和原始证据的唯一标签为 `dspark-35b-tp2-20261010092547`。

## 启动配置

- `CUDA_VISIBLE_DEVICES=6,7`，`--tensor-parallel-size 2`。
- `--max-num-seqs 64`。
- 删除旧 `--max-num-batched-tokens 1024`：当前 vLLM 的 H100 API 服务默认值为 8192，实际启动日志也确认 8192。
- 删除 `--max-model-len 50000`：主模型配置和实际引擎均确认默认 262144。
- 保留 `FULL_AND_PIECEWISE`，删除原 TP1 的固定捕获尺寸 `[1,15]`，由 vLLM 自动选择。
- 保留 prefix caching、14 个 speculative token、原单图/禁用视频范围和 GPU memory utilization 0.94。

容器内部交付脚本 `/opt/flagos/dspark/start-35b-model.sh`；宿主脚本
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/start-dspark-35b.sh`
在容器中为 `/work/start-dspark-35b.sh`。
分别保留内部 `exec` 与用户宿主版本的 `nohup`、后台运行、相对日志路径，未互相覆盖。
vLLM 编译缓存隔离至 `/work/06-cache/<标签>/vllm`；内部服务日志写入
`/work/04-runs/<标签>/server-isolated-kernels-r2.log`。

## 双卡缓存问题与缓解

首次启动已加载两个 rank 的主模型及草稿，每卡模型占用约 34.61 GiB。
随后 TP1 在视觉 MLP 的 FlagGems/Triton autotune 路径失败：
`triton/runtime/cache.py:125` 清理 Parastor 上共享缓存临时目录时抛出 `Errno 16`。
日志为 `04-runs/<标签>/server.log`。
复用[003](003-triton-cache-concurrency.md)的隔离经验，但该记录基于 vLLM 0.24、
不同 GPU 和加载阶段，因此本轮重新验证，未直接视为已解决。

仅隔离 Triton 后，TP1 在模型初始化 `normal_` → FlagGems
`pointwise_dynamic.py:1840` 导入动态模块时报 `FileNotFoundError`。
日志为 `server-pid-cache.log`。FlagGems 生成代码仍在共享缓存目录；
并发写入与 Parastor 可见性问题为候选原因，未用最小复现判定底层责任。

运行环境缓解为同时按 Python PID 隔离 Triton 和 FlagGems 缓存。
仅当脚本显式设置 `FLAGOS_KERNEL_CACHE_BASE` 时生效；未设置该变量的进程保持默认行为。
容器安装文件 `/usr/local/lib/python3.12/dist-packages/flagos_triton_cache.pth`，
SHA-256 `7364eb71dcd5251529114c3cbd11529d2e5ef6208d3cc9d753237bf955e8c991`。
新进程已核实两条缓存路径都含自身 PID；实际 TP0/TP1 在各自
`kernels/{triton,flaggems}/pid-6733`、`pid-6804` 中生成文件。
该文件位于容器内部，镜像打包需包含它；不是另一份产品源码或 `PYTHONPATH` 覆盖。

停止仅针对本轮已核实的失败 API 及其子进程，精确 PID、信号和原因保留在
`stop-failed-service.json`、`failed-service-processes.json`；容器一直运行。
中间配置和钩子修改全部保存在 `01-environment/<标签>/`，没有删除失败日志。

## 当前证据与边界

隔离后的服务已通过两个旧报错位置，完成主模型、草稿加载、视觉预热与模型编译。
分段图 51/51、主模型解码全图 33/33、DSpark 全图 34/34 已全部捕获，
两 rank 均报告图内存 2.07 GiB。API health 200，9 项图文/多轮与 64 客户端并发
全部正确，共 73/73；验证后服务继续运行。详见
[双卡服务验证](../acceptance/dspark-tp2-validation-2026-10-10.md)。
默认 KV 缓存规划为 2,242,180 token；
262144-token 单请求的规划最大并发为 8.55x，不能解释成 64 个满长度请求同时驻留。
默认最大图捕获 token 数为 512；64 客户端通过不证明 64 个驻留序列都使用全图 replay。
本记录不声明精度、性能或完整适配验收通过。

本轮没有 Plugin、FlagGems、vLLM 推理源码变更，不新增黑名单，不改变 graph 等级；
完整 `.py/.so` 前后指纹已对比一致，继承的 dirty 文件保留。1B 启动器哈希保持不变。
缓存处理是容器运行环境缓解；移除条件是相同文件系统、双卡并发编译下共享缓存
通过独立复现与服务回归。没有测量其稳态性能影响；逐进程目录会增加首次编译和磁盘占用。
打包后新容器验证、262144-token 实际长输入和正式精度/性能尚未执行。
