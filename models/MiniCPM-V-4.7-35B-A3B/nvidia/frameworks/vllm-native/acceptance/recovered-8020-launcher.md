# H100-149 / TP2 / 8020 启动脚本恢复验证

2026-09-30；容器 `MinicpmV4.7-35B-native`，vLLM `0.24.0+cu129`，
模型 `/data/models/MiniCPM-V-4.7/weights/35b-a3b`。最终根级脚本的
Host/容器路径均为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，
权限 `0755`，SHA-256
`b61e01e08818b014a767ad2b7ccf29a6e3bba3c4c010615f4ca52336753096f2`。
用户原脚本先备份至 `02-issues/start-model-user-8020-before-recovery.sh`，
SHA-256 `eb0a9ac33ee26eba21ee3c02edba1adc5f7e02467d46bbfd6acca2c993a1bf52`。
Ansible `--check --diff` 后写入，容器内 `bash -n` 通过，Host/容器哈希一致。

保留用户的 `127.0.0.1:8020`、物理 GPU 2/3、TP2、0.85 显存比例、
模型别名、`qwen3` reasoning parser、远端代码加载与正常前缀缓存。
补回 `--max-model-len 2048`、`--max-num-batched-tokens 2048`、
`--max-num-seqs 8`，固定已验证的资源上限，避免上次隐式采用 262144
长度与 51/51 图计划；`--compilation-config`
固定 `mode=3` 与用户指定的 `FULL_AND_PIECEWISE`。
`PYTHONPATH` 与 `MINICPM47_TRITON_PER_PROCESS=1` 激活
`01-environment/sitecustomize.py` 的进程级 Triton 缓存隔离，规避
[005](../adaptation/005-user-launcher-startup-blocked.md) 的共享缓存 `EBUSY`。
`CUDA_VISIBLE_DEVICES` 固定设备；`LD_LIBRARY_PATH` 补入镜像默认缺失的
CUDA 驱动库搜索路径。`HOME`、`XDG_CACHE_HOME`、`VLLM_CACHE_ROOT`、
`PYTHONPYCACHEPREFIX` 和 `TMPDIR` 将隐式写入限制在批准工作根的
`05-tmp/`、`06-cache/`，已核实生效进程环境。
脚本明确进入根目录，日志写 `04-runs/start-model-8020.log`，
端口已被占用时拒绝覆盖；不停止或重启适配容器。

变更前仅停止本任务旧 8107 服务 PID/PGID `1258682`，确认 GPU 2、3
释放、另一 8019 服务未受影响。由新根级脚本启动 8020 服务，Host
PID/PGID `1531420`，容器 API PID `28671`。
启动日志记录 prefill/mixed PIECEWISE 5/5、decode FULL 4/4，
API `/health` 与 `/v1/models` 均为 200。Triton 缓存实存于
`06-cache/triton-processes/29278` 与 `/29281`；本次启动日志没有
`OSError`、`Traceback` 或 `ERROR`。

请求脚本 `03-acceptance/recovered-8020-probe.py` SHA-256
`cc0bc80d16e93e8218a584a8dfeb8e2e922203e611efdf27247708e27a79611e`；
结果 `04-runs/start-model-8020-v2/probe.json` SHA-256
`5ea38d3e7b30faebd5f591876805c96ea9d327c5da5fd3a18c5ba630643c2e73`；
日志快照 `04-runs/start-model-8020-v2/service-startup.log` SHA-256
`0684302f6fa35810cbf9e835681856342b8c9b7e3e2aa1c32d6ba9203ce45ba6`；
端口保护结果 `04-runs/start-model-8020-v2/port-guard.log` SHA-256
`6a45483ae0c8182b9f2ae0b97a843de63726e2117d19024a5bc150a56ff3ae95`。
文本 `17+25` 答 `42`，红图答 `red`，两帧视频依次识别红和蓝；
10 个混合并发请求 10/10 正确，均正常停止。重复运行脚本拒绝覆盖
8020 服务，之后 `/health` 仍为 200。

本配置的 full 图覆盖仍限于 decode，prefill 为 PIECEWISE；
2048 以上上下文、长期稳定性、固定 GPQA sanity、正式精度和性能未验证。
