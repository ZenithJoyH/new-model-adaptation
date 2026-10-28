# TP2 混合图服务脚本精简验证

2026-09-30；Host `H100-149`；容器 `MinicpmV4.7-35B-native`；模型
`/data/models/MiniCPM-V-4.7/weights/35b-a3b`。Host 与容器中的最终脚本均为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，权限 `0755`，
SHA-256 `1bca4bb0ac4c190cde1b30dc1da289b3361e2ac558340cfac820d8c7829efb54`。
工作根的 Host/容器路径相同且已核对映射。原版备份在
`02-issues/start-model-before-simplification.sh`，SHA-256
`195fd984d82769e8598f800d1a9d5e9dfd4f0e05b22da5a11caa48589aade662`。
Ansible `--check --diff` 确认此次仅删去 `HF_HOME` 和 `TRITON_CACHE_DIR` 两个 export。

`XDG_CACHE_HOME` 已将 Hugging Face 默认缓存置于 `06-cache/xdg/huggingface`；
在 `MINICPM47_TRITON_PER_PROCESS=1` 下，`01-environment/sitecustomize.py`
按进程设置 Triton 缓存到 `06-cache/triton-processes/<pid>`，所以两个删去的
export 没有生效用途。其余环境变量分别固定物理 GPU 2/3、容器动态库、
vLLM/Python/临时缓存的批准目录，以及 Triton 进程隔离加载路径。
脚本保留端口占用保护、工作目录切换、日志目录和 `exec`。

保留的服务参数及原因：模型路径与别名固定客户端调用目标；
`--host`/`--port` 固定本机监听 `127.0.0.1:8107`；`--tensor-parallel-size 2`
对应指定的两卡；`--max-model-len 2048`、`--max-num-batched-tokens 2048`、
`--max-num-seqs 8`、`--gpu-memory-utilization 0.8` 固定已验证的显存与并发上限，
若省略会采用不同默认值；`--trust-remote-code` 是权重的自定义配置加载条件；
`--enable-prefix-caching` 确保非性能场景保持已验证的缓存行为；
`--reasoning-parser qwen3` 固定 OpenAI 回复解析；
`--compilation-config '{"mode":3,"cudagraph_mode":"FULL_AND_PIECEWISE"}'`
固定用户指定的图模式。脚本没有性能专用的缓存禁用参数。

容器内 `bash -n` 通过，Host/容器 SHA-256 一致。只停止旧的本任务服务
PID/PGID `3149108` 后，用最终根级脚本启动新服务，Host PID/PGID `600304`；
适配容器保持运行。新服务 `/health` 和 `/v1/models` 均返回 200，启动日志记录
prefill/mixed PIECEWISE 捕获 5/5、decode FULL 捕获 4/4。
独立请求脚本 `03-acceptance/minimal-launcher-probe.py`，SHA-256
`b57bc75429378bde52041afc0fb772f0fdbec022567bdaeaf1870c3222fa1e24`；
结果 `04-runs/start-model-minimal-v1/probe.json`，SHA-256
`89b4b24dce618282dc511f0d9ea4a71e916800c6bf2708522dc91220930e0db5`；
本次启动日志快照 `04-runs/start-model-minimal-v1/service-startup.log`，SHA-256
`893f9ababc6d8208ed1417f27ced8f9027dafaf1a597f7efb7b68099e03dd829`。
文本 `17+25` 答 `42`、红图答 `red`、两帧视频按红蓝顺序回答；
十个混合并发请求 10/10 正确。运行后再次确认 `/health` 为 200。

`FULL_AND_PIECEWISE` 的 full 图覆盖限于 decode；GDN backend 尚不支持
prefill full graph，已有完整尝试与阻塞证据见 [003](../adaptation/003-gdn-full-graph-limit.md)。
本记录是请求级功能验证，固定 GPQA sanity、正式精度、性能与完整验收未执行。
