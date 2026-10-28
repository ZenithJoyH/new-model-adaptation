# H100-149 / TP2 / 8020：仅恢复 Triton 进程缓存隔离

2026-09-30；容器 `MinicpmV4.7-35B-native`，vLLM `0.24.0+cu129`，
镜像 `sha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4`。
Host/容器同路径根级脚本为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，权限 `0755`，
SHA-256 `67d496ce89a943a8b8d53a12fc0056ce513e1f54c935a8d67049af59e17cee40`。
用户原始 8020 脚本备份 `02-issues/start-model-user-8020-before-recovery.sh`
SHA-256 `eb0a9ac33ee26eba21ee3c02edba1adc5f7e02467d46bbfd6acca2c993a1bf52`；
上一轮过度恢复的版本备份 `02-issues/start-model-before-triton-only.sh`
SHA-256 `b61e01e08818b014a767ad2b7ccf29a6e3bba3c4c010615f4ca52336753096f2`。

本次实际服务参数恢复到用户原始值：`127.0.0.1:8020`、GPU 2/3、TP2、
显存比例 0.85、`qwen3` parser、前缀缓存和
`--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}'`。
没有 `--max-model-len 2048`、`--max-num-batched-tokens 2048`、
`--max-num-seqs 8` 或 `mode=3`。启动日志显示生效的模型长度 262144、
`max_num_batched_tokens=8192`，图计划 PIECEWISE 51、FULL 51。
只加入 `PYTHONPATH` 指向 `01-environment/` 与
`MINICPM47_TRITON_PER_PROCESS=1`，使已验证的 `sitecustomize.py`
（SHA-256 `73669ec51bf6500cfcc854a7dedbcc4fb6a87d733a307e225185227adccf8ed8`）
为每个 Python 进程设置独立 `TRITON_CACHE_DIR`。
脚本的 `cd`、端口保护和 `04-runs/` 日志路径仅用于工作目录与服务安全，
没有改变模型服务参数。未恢复上一版的 `HOME`、`XDG_CACHE_HOME`、
`VLLM_CACHE_ROOT`、`PYTHONPYCACHEPREFIX`、`TMPDIR`。

先识别并停止本任务旧 8020 Host PID/PGID `1531420`，确认 GPU 2/3
空闲；8021 及其他服务未操作，适配容器保持运行。
新服务 Host PID `1632963`、PGID `1632956`，容器 API PID `30831`，
TP worker PID `31642`、`31645`。Ansible `--check --diff`、容器内
`bash -n`、Host/容器脚本 SHA-256 一致均通过。Triton 独立缓存目录
`06-cache/triton-processes/31642` 和 `/31645` 已出现。
启动完成 prefill/mixed PIECEWISE 51/51、decode FULL 51/51，
`/health` 为 200；快照日志未出现 `EBUSY`、`OSError`、`Traceback` 或 `ERROR`。

请求脚本 `03-acceptance/triton-only-8020-probe.py` SHA-256
`72af13c5f0991eb8a00de203eb054922647e503c425496ac596a2f56be567c76`；
结果 `04-runs/start-model-8020-triton-only/probe.json` SHA-256
`52c1f47c1e7a5cda6be63edea50dbfbf9b60f956c9a93a5954d103023512cc0d`。
文本 `17+25` 答 `42`，红图答 `red`，两帧视频依次识别红和蓝，
10 个并发混合请求 10/10 正确且均正常停止。重复运行脚本拒绝覆盖现有
8020 服务，健康检查仍为 200；端口保护输出 SHA-256
`6a45483ae0c8182b9f2ae0b97a843de63726e2117d19024a5bc150a56ff3ae95`。
日志快照 `04-runs/start-model-8020-triton-only/service-startup.log`
SHA-256 `801a7e7fed9fcc9d83a94a86365ea4eb4b44a370f49212472f73cff22a95d68c`。
部署身份文件 `01-environment/deployment-identity-triton-only-20260930.json`
SHA-256 `549d0cddf63a88e162ac651393da2c5492bf95b7c354f3c3b04fab0a65db61b3`，
指纹 `91d3c1ccfffef6dc234335e0af48f6ab6cf69bad304a25514e0da2b374f94000`。

本次修复组合只改变了 Triton 的进程级缓存隔离和脚本安全路径，
与原失败运行相比，默认缓存位置及启动环境也有差异；因此结果证明
此脚本可用，不把 `EBUSY` 的唯一根因归给单一变量。
图覆盖仍为 prefill PIECEWISE、decode FULL。262144 最大长度的实际长上下文、
长时稳定性、固定 GPQA sanity、正式精度与性能尚未验证。
按用户要求，其他运行时缓存沿用镜像默认位置；日志显示 vLLM AOT 缓存位于
`/root/.cache/vllm`，不属于远端批准工作根，本轮未迁移它。
