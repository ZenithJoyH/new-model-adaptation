# TP2 FULL_AND_PIECEWISE 根级启动脚本验证

2026-09-28；Host `H100-149`；容器 `MinicpmV4.7-35B-native`；模型
`/data/models/MiniCPM-V-4.7/weights/35b-a3b`；vLLM wheel `0.24.0+cu129`。
用户明确要求将模型服务启动脚本调整为 `FULL_AND_PIECEWISE`。

根级脚本的 Host/容器路径均为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，
SHA-256 `195fd984d82769e8598f800d1a9d5e9dfd4f0e05b22da5a11caa48589aade662`，
权限 `0755`。原脚本备份在
`02-issues/start-model-before-full-and-piecewise.sh`，SHA-256
`5c12ac80b434444b124c7c9613ae951f3adbc2a1d8641abc11b0fae02bf85940`。
Ansible `--check --diff` 显示根级脚本仅将
`--compilation-config '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY"}'`
改为 `{"mode":3,"cudagraph_mode":"FULL_AND_PIECEWISE"}`；
其余端口、模型、GPU 2/3、TP2、2048 上下文、prefix caching、缓存和日志
路径均保持一致。容器内 `bash -n` 通过，Host/容器 SHA-256 一致。
已在端口占用时验证脚本拒绝替换现有服务。

重启前，核对诊断实例 Host PID/PGID `3109477`、精确模型、TP2 与混合图配置；
只向该任务进程组发送 `SIGTERM`。核对该组退出且容器原始 `/bin/bash`
保持运行后，用根级脚本启动新实例，Host PID/PGID `3149108`。
实际进程命令包含 `mode=3` 与 `FULL_AND_PIECEWISE`，服务 `/health` 为 200。
vLLM 的生效配置为 `VLLM_COMPILE`、非空 GDN/attention `splitting_ops`；
prefill/mixed batch 使用 PIECEWISE 图，decode 使用 FULL 图。

独立请求脚本是远端 `03-acceptance/full-and-piecewise-launcher-probe.py`，
结果在 `04-runs/start-model-full-and-piecewise-v1/probe.json`。
新实例的健康检查和模型列表均为 200，文本 `17+25` 返回 `42`，红图返回
`red`，两帧视频按顺序识别红、蓝；三个请求均为 200、stop，十个混合并发
请求 10/10 正确。此为请求级功能核验，不是固定 GPQA sanity、正式精度或性能。
GDN backend 仍不支持覆盖 prefill 的 full graph；`FULL_AND_PIECEWISE`
表示 prefill PIECEWISE 与 decode FULL。正式精度和性能继续暂缓。
