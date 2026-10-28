# 002：初始 TP8 诊断中 Triton launcher 文件不可见

## 元数据和现象

- 状态：`mitigation_verified`；TP2 同代码、同模型、同拓扑的单变量对照复现共享缓存失败。
- 日期：2026-09-28；`H100-149` / `MinicpmV4.7-35B-native`，eager TP8。
- 原始日志：`/public/flagos/jinghao/MiniCPMV4.7-35B/native/04-runs/eager-v1/service.log`。
- 首批失败 rank 包括 TP4。GDN 首轮 `fused_post_conv_prep` 编译后加载
  `06-cache/triton/<hash>/__triton_launcher.cpython-312-x86_64-linux-gnu.so`，
  报 `ImportError: cannot open shared object file: No such file or directory`。
  检查时该目录随后存在 `.so` 与另一进程的临时目录，说明有时间相关竞争；
  尚不能仅据此断定唯一根因。

## 已有经验匹配

`models/XingChen4-29B-A4B/nvidia/adaptation/008-parastor-triton-cache-race.md`
在同 Host、vLLM 0.24.0、Parastor 与 TP4 首次编译中验证了共享 cache 竞争，
按 rank 隔离后启动通过。本轮是独立容器、TP8、不同 Triton kernel，报错点是
launcher 动态库加载而非临时目录 rename；作为中可信度候选，必须本轮复验。
DeepSeek V4.1 的相近文件系统问题报 `os.removedirs` 的 EBUSY，也不能直接套用。

## 受控对照

v1 仅设置统一的 `TRITON_CACHE_DIR=.../06-cache/triton`。v2 保留 v1 所有
服务参数，仅在 `01-environment/start-eager-v2.sh` 通过
`PYTHONPATH=.../01-environment` 和 `MINICPM47_TRITON_PER_PROCESS=1` 激活
`sitecustomize.py`，将每个 Python 进程的 Triton cache 指向
`06-cache/triton-processes/<pid>`。两版启动脚本 diff 仅这两个环境变量；
v2 已通过 `bash -n` 和单进程 PID 路径检查，尚未跑 TP8。

v1 服务 PID `2706846`，PGID `2706846`，命令包含精确模型和端口 8107。
因失败后进程未自行退出，2026-09-28 先对该精确组执行 `SIGTERM`；
10 秒后仍有同组 worker 占显存，复核 PID/PGID 后执行 `SIGKILL`。
验证目标容器保持原 `StartedAt=2026-09-28T01:55:36.932850768Z` 且仅余
`/bin/bash`。随后 GPU0 出现另一 1B 容器的约 27 GiB 占用，故暂缓 TP8 复测，
不会停止或更改其进程。

## TP2 受控比较

用户明确指定本模型用 TP2，不再以 TP8 为验收目标。TP2 首轮脚本
`01-environment/start-eager-tp2-v1.sh` 沿用按进程隔离的缓存配置，使用
物理 GPU 2、3；17 个 shard 加载完成并提供 HTTP 推理，未复现 launcher
文件不可见。由于拓扑同时改变，这不能证明隔离就是初始 TP8 失败的根因。
随后在同一 vLLM wheel、同一权重、GPU 2/3、TP2、2048 上下文、eager/graph
参数不变的条件下，只移除 `PYTHONPATH=.../01-environment` 和
`MINICPM47_TRITON_PER_PROCESS=1`，运行
`01-environment/start-graph-tp2-noisolation-v1.sh`。原始日志见
`04-runs/graph-tp2-noisolation-v1/service.log`。服务完成 17/17 shard 加载、
decode FULL 4/4 捕获、健康检查和模型列表；首个文本请求在 TP1 首先失败：
`_zero_kv_blocks_kernel` JIT 的 `triton/runtime/cache.py:121` 调用
`os.removedirs(temp_dir)`，报 Parastor 下
`/06-cache/triton/<hash>/tmp.pid_11124_...` 的 `OSError: [Errno 16] Device or resource busy`。
随后同 rank 的 `KeyError` 和 EngineCore 共享内存等待是后继症状；客户端
120 秒超时。不能把后继错误当成根因。

前一相同 TP2 graph 服务使用进程隔离的
`06-cache/triton-processes/<pid>`，已完成文本、图像、视频及十并发混合请求；
无隔离版本复现文件系统异常。因此按进程隔离是本 Host、本镜像和本拓扑的
已验证 mitigation，必须保留在最终 launcher；Triton/Parastor 的底层根因
尚未修复。缓存始终位于本任务批准的 `06-cache/` 下。

比较失败服务的 API/EngineCore/TP0/TP1 均属精确进程组 `2864420`；发送
`SIGTERM` 后核对容器只余原 `/bin/bash`，未重启或停止容器。
