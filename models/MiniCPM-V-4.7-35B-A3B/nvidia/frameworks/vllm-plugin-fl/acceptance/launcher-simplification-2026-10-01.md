# TP2 模型服务启动脚本精简验证（2026-10-01）

> 本页记录较早的 2026-10-01 精简脚本。API PID `41096` 已在核实空闲后停止；用户再次修改的当前脚本及 PID `43939` 见[新脚本验证](user-revised-launcher-validation-2026-10-01.md)。

## 目标与差异

- Host：`H100-149`；容器：`MinicpmV4.7-35B`；宿主机与容器工作根均为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`。写入前核实 `start-model.sh` 两侧设备号与 inode 同为 `45:213708828429`，旧 SHA-256 为 `4e4982c7ef9c447c0e2759e569c46d31da9931e224a3aae675aeebe343a9ec51`。
- 该次可执行脚本两侧路径均为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/start-model.sh`，权限 `0755`，SHA-256 `4fefbc52ecf4fd9cccd359823fb96f117ab7387563eb2125f18a857f3adb316c`。旧脚本原文留在 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/service-full-piecewise-tp2-20260930T144750Z-38048/start-model.pre-simplification.sh`。
- 删除了没有管道可作用的 `pipefail`、在 `set -e` 下重复的 `cd ... || exit 1` 退出分支、缓存钩子检查的额外错误分支，以及显式 `--dtype bfloat16`。模型 `config.json` 声明 `dtype=bfloat16`；用当前容器的 `AutoConfig` 和 vLLM `_get_and_verify_dtype(..., "auto")` 实测得到 `torch.bfloat16`，新服务 EngineCore 日志也记录 `dtype=torch.bfloat16`。其余启动参数未改。
- 继续保留端口与 GPU 4/5 占用检查、`PYTHONPATH` 清除、逐进程 Triton 缓存钩子检查、日志与缓存根、视觉 SDPA 黑名单、前缀缓存开启及 `--mm-processor-cache-gb 0`。Plugin 的 `worker.py:264-289` 总会在 rank 0 记录 oplist；未设 `FLAGGEMS_ENABLE_OPLIST_PATH` 时 `envs.py:12-14` 默认写 `/tmp/flaggems_enable_oplist.txt`，故该变量仍需将输出限制在批准的 `04-runs/`。

## 实际验证

- 在端口 8021 被旧任务服务占用时，简化脚本明确拒绝启动。核实旧 API PID `38060` 的模型、端口、TP2、图模式与 metrics 的运行/等待均为 0 后，仅对该 PID 发送 `SIGTERM`；确认旧进程退出、端口关闭、GPU 4/5 无计算进程。容器始终运行。
- 从容器内直接执行该次脚本，不提供 `PYTHONPATH`。新运行目录为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/service-full-piecewise-tp2-20261001T000842Z-41084/`，API PID `41096`；`/proc/41096/environ` 显示 `PYTHONPATH` 不存在，`CUDA_VISIBLE_DEVICES=4,5`，缓存与临时文件位于批准的 `06-cache/`、`05-tmp/`，FlagGems oplist 产生在本次 `04-runs/` 目录。
- `bash -n` 通过。引擎实际为 BF16、TP2、100,000 token、端口 8021、前缀缓存开启、`FULL_AND_PIECEWISE`；mixed prefill/decode 的 `PIECEWISE` 和 decode 的 `FULL` 各捕获 51/51。`/health`、`/v1/models` 均返回 200。
- 两条文本、红蓝图片各一张、蓝图与红图重复请求共 6/6 正确，原生结果为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/service-full-piecewise-tp2-20261001T000842Z-41084/minimal-service-check.json`，SHA-256 `887561fd417634307cc69359f244da685e92ca72953305e17f9beba4136e81a0`。该次验证后 PID `41096` 保持运行，GPU 4/5 分别约占 65,115/65,079 MiB；后续已由当前用户脚本接替。

这次只改变启动脚本，Plugin、FlagGems 与 vLLM 源码未修改；先前十并发 10/10 属于 2026-09-30 脚本，本轮未重复。100,000 token 极限长度、视频、正式精度与性能未测；mixed prefill/decode 仍是分段图，不能据此通过 active profile 的正式 full graph 验收。`framework.yml` 状态保持 `environment_ready`，部署指纹和正式原生回执仍需按项目契约更新。
