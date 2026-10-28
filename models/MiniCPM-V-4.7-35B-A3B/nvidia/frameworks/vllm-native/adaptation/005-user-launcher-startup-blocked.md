# 005：用户调整后的 8020 启动脚本未就绪

## 元数据

- 状态：仅恢复 Triton 进程缓存隔离的 8020 脚本已验证；原失败原因的唯一归因仍为 `hypothesis`。
- 时间：2026-09-30；`H100-149` / `MinicpmV4.7-35B-native`；NVIDIA H100，物理 GPU 2、3，TP2。
- 容器镜像：`sha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4`；vLLM `0.24.0+cu129` wheel，短 revision `gee0da84ab`。
- 本次没有修改模型权重或 vLLM 产品代码。用户修改后的 Host/容器同路径脚本是
  `/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，SHA-256
  `eb0a9ac33ee26eba21ee3c02edba1adc5f7e02467d46bbfd6acca2c993a1bf52`，权限 `0755`，容器内 `bash -n` 通过。

## 问题现象与证据

用户脚本改为 8020、`--gpu-memory-utilization 0.85`，省略此前的
`--max-model-len 2048`、batch/sequence 上限、编译 `mode=3` 和
Triton 进程隔离环境变量。vLLM 生效日志显示模型默认长度 `262144`、
`max_num_batched_tokens=8192`，图计划为 PIECEWISE 51、FULL 51。
17/17 shard 成功加载，KV 缓存分配成功。最早的明确错误是 TP1 于
19:25:54 在 `triton/runtime/cache.py:121 os.removedirs(temp_dir)` 报
`OSError: [Errno 16] Device or resource busy`；TP0 于 19:26:13 报同类错误。
mixed prefill/decode PIECEWISE 捕获停在 36/51，随后 EngineCore 每分钟报告
共享内存广播等待超过 60 秒。观察约 7 分钟，8020 `/health` 始终无法连接。
原始日志位于两侧同路径工作根的
`04-runs/user-script-20260930-v1/service.log`，SHA-256
`43e215a6677022f13ad7d66684c80845463a549dd042467613cb1335cc4cbdd9`。
没有执行请求级探针，因为服务未就绪。

## 已有经验匹配与诊断

[002](002-parastor-triton-cache-race.md) 在同一 Host、容器、TP2 与 vLLM wheel
的无隔离对照中，也于 Triton `os.removedirs(temp_dir)` 首先遇到
Parastor `EBUSY`；按进程隔离后完成图捕获和推理。本次的首个错误位置、
文件系统、rank 和共享缓存拓扑相近，但同时改变了上下文长度、batch 上限、
显存比例和图捕获规模，不能仅凭本轮证明 36/51 停滞的唯一原因。
状态保留为假设，`EBUSY` 事实已确认。

为使测试写入保持在批准工作根，运行时只额外指定工作目录
`04-runs/user-script-20260930-v1/`，以及 `HOME`、`XDG_CACHE_HOME`、
`VLLM_CACHE_ROOT`、`PYTHONPYCACHEPREFIX`、`TMPDIR`、`TRITON_CACHE_DIR`
和 `CUDA_CACHE_PATH` 到该工作根的 `05-tmp/` 或 `06-cache/`。
未注入 `PYTHONPATH` 或 `MINICPM47_TRITON_PER_PROCESS`，因此仍检验了
脚本省略 Triton 进程隔离后的共享缓存路径。这些外部路径设置是测试边界，
并不证明脚本独立运行时的隐式写入位置合规。

## 服务操作、结果与下一步

测试前核实本任务旧 8107 服务 PID/PGID `1038051`，只对其进程组发送
`SIGTERM`，确认 GPU 2、3 释放；另一 8019 服务属于不同进程组，未操作。
新脚本使用 `docker exec -d` 启动，Host PGID `1235947`、API PID
`1235968`，命令包含精确权重、8020 与 TP2。失败后先对该精确测试组
发送 `SIGTERM`；worker 未退出，经再次核实同组身份后发送 `SIGKILL`，
确认 GPU 2、3 清空，适配容器始终运行。

失败诊断时未覆盖用户的 `start-model.sh`。从已验证备份
`02-issues/start-model-before-mkdir-removal.sh` 恢复 8107 TP2 服务；
`/health` 为 200，文本 `17+25` 以 `stop` 结束并在 `content` 返回 `42`。
用户先要求恢复必要启动参数。先将其脚本备份至
`02-issues/start-model-user-8020-before-recovery.sh`，再在根级脚本补回
Triton 进程隔离、批准工作根内的缓存路径、2048 上下文及批量上限，
保留用户选定的 8020、GPU 显存比例 0.85、TP2 和
`FULL_AND_PIECEWISE`。新脚本 SHA-256
`b61e01e08818b014a767ad2b7ccf29a6e3bba3c4c010615f4ca52336753096f2`。
只停止本任务 8107 服务后，以该历史脚本启动 8020；图捕获完成、健康检查
200，文本/图像/视频与十并发 10/10 正确。详见
[恢复后的根级脚本验证](../acceptance/recovered-8020-launcher.md)。
由于当时同时恢复多个设置，结果证明整套配置有效，不单独证明
`EBUSY` 或 36/51 停滞只由某一设置造成；针对缓存竞争的控制对照仍见
[002](002-parastor-triton-cache-race.md)。262144 上下文和 51/51 图计划
未进一步评估。正式精度或性能评测未执行，未提交或推送代码。

## 2026-09-30：按用户纠正只恢复 Triton 隔离

将上述过度恢复版备份至 `02-issues/start-model-before-triton-only.sh`，
根级脚本改回用户原有 vLLM 参数，仅加入 `PYTHONPATH` 与
`MINICPM47_TRITON_PER_PROCESS=1` 来启用按进程分开的 Triton 缓存。
保留脚本工作目录、端口保护和工作根内日志位置。
实际 diff 删除了 2048 上下文、批量与序列上限、编译 `mode=3`，以及
`HOME`、`XDG_CACHE_HOME`、`VLLM_CACHE_ROOT`、`PYTHONPYCACHEPREFIX`、
`TMPDIR`。新脚本 SHA-256
`67d496ce89a943a8b8d53a12fc0056ce513e1f54c935a8d67049af59e17cee40`。
只停止本任务旧 8020 进程组 `1531420` 后重启；新进程完成
PIECEWISE 51/51 与 decode FULL 51/51 图捕获，服务健康检查 200，
文本/图像/视频与十并发请求通过。缓存目录按 worker PID 分开，
未复现 `EBUSY`。准确命令、日志和哈希见
[仅 Triton 隔离验证](../acceptance/triton-only-8020-launcher.md)。
此次服务独立运行时其他缓存沿用镜像默认位置，其中 vLLM AOT 位于
`/root/.cache/vllm`；这是用户要求不恢复其他缓存变量后的已知限制。

## 2026-10-01：缩小 PYTHONPATH 的作用范围

容器默认 Python 路径只加载系统 `sitecustomize.py`，故直接删除
`PYTHONPATH` 会禁用现有 Triton 进程隔离。对用户最新脚本的实际 diff
仅移除全局 `export PYTHONPATH` 并在 `nohup vllm serve` 命令前设置
`PYTHONPATH="$root/01-environment"`。其他行保持用户最新版本。
新脚本 SHA-256 `8243f7ce5faf16543941c633e305b7e4e29cb655a0bf0ea2a6f3d973eea58d48`；
新服务通过图捕获、健康检查和文本请求，worker 缓存目录仍独立，详见
[命令级设置验证](../acceptance/command-scoped-pythonpath.md)。
