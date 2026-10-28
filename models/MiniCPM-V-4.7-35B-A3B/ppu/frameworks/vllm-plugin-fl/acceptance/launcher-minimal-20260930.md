# PPU-13 根级启动脚本精简与复验

日期：2026-09-30。用户要求从已启动的 `FULL_AND_PIECEWISE` 脚本中删除
非必要设置。唯一目标 Host 为 `PPU-13`，容器 `minicpmV4.7-35B`，
批准根的宿主机与容器路径均为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`；映射设备号:inode
`41:14016406509` 已在首版安装前实测。本次只替换当前任务拥有的根级脚本
并重启当前任务的模型服务，适配容器持续运行。

本页记载当时已验证版本；用户随后再次编辑根级脚本，该轮实际启动在图捕获期间
OOM，见[006 问题](../adaptation/006-user-launcher-graph-oom.md)。目前根级脚本已
进一步删减并重新启动验证，见[参数删减记录](launcher-mm-flags-20261001.md)；
本页中的脚本 SHA 和进程号均为历史证据。

## 精简内容与保留依据

安装的 `huggingface_hub/constants.py` 在缺少 `HF_HOME` 时从
`XDG_CACHE_HOME/huggingface` 推导缓存位置。因此删除冗余的 `HF_HOME`
导出和对应的 `mkdir cache/hf`；实际新服务进程中只有
`XDG_CACHE_HOME=/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/06-cache/start-model-piecewise`，
新模块缓存实际位于该根下的 `huggingface/modules`。删除在 `docker exec -d`
启动方式下无人消费的 `service_log` 标准输出打印。其余参数保持一致：
TP2/设备 0、1、50,000 token 和最多 8 序列是已验证资源配置；
`trust-remote-code`、视觉缓存禁用、SDPA 与 data 模式对应模型正确性；
显式开启前缀缓存是非性能阶段要求；mode 3 与 `FULL_AND_PIECEWISE`
是用户指定模式及其编译前提；服务名、监听地址与端口保持现有 API 合同；
其他缓存/TMP 环境变量限定隐式写入到批准根。首版逐项依据见
[启动脚本记录](launcher-20260930.md)。未更改权重、Plugin、vLLM 或容器。

## 变更与实测

- 当前宿主机/容器脚本：
  `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh`，mode `0755`，
  SHA-256 `e486d32980a24d7cb3607abd7015783cf7dd9f0bd0f4005c6ba7a314250c1a04`。
  本地及容器内 `bash -n` 通过，Ansible 单 Host `--syntax-check`、
  `--check --diff` 和实际复制均通过。首版脚本原样保存在
  `04-runs/start-model-validation-20260930/start-model-before-minimal.sh`，
  SHA-256 `75f3d9ba4dc78416fdd8a40ad13c9a8563e7c3e78e92fe73a3b6e3c4add3a973`。
- 重启前逐项核实原 API PID `1073768`、EngineCore `1074546`、TP0/TP1
  `1074831`/`1074832` 与命令、模型、TP2、端口和图模式一致。只向该 API
  发 TERM，确认四进程均退出，随后用新脚本启动。当前 API PID `1190044`、
  EngineCore `1190533`、TP0/TP1 `1190818`/`1190819` 均运行；容器未停启。
- 当前实例日志为 `04-runs/start-model/service-20260930T100054-1190044.log`；
  启动与基本请求的不可覆盖快照在
  `04-runs/start-model-minimal-20260930/startup-and-smoke.log`，SHA-256
  `a615c973a40b6f1f91951129eaf74e5e5bf09765f417b93f06c5bc7d89898288`。
  17/17 权重 shard 加载；生效 `enable_prefix_caching=True`、
  `cudagraph_mode=FULL_AND_PIECEWISE`，混合 prefill/decode PIECEWISE 捕获
  5/5、decode FULL 捕获 4/4，`/health` HTTP 200。
- 同一服务下基本文本返回 `42`，红色单图返回 `红色`，均 HTTP 200 且正常停止。
  原始结果分别为 `04-runs/start-model-minimal-20260930/text-full-smoke.json`
  （SHA-256 `0e0d39016a36534e40225e32b0c53db652ab9544417810b1cb4d5a6fe87ad253`）
  和 `04-runs/start-model-minimal-20260930/image-full-smoke.json`
  （SHA-256 `9a3ccedb44f69abf53e5cd63473bdca4d36ca98a87928060e3c5f24ec033dab0`）。
  一次性探针在 `02-issues/launcher-minimal-20260930/probe.py`，SHA-256
  `6b755dffafe8724a50223ed90eafbddb182a9682aa2db5f4b737dd619026fefb`。

本次仅核验精简脚本及基本推理；精度、性能和正式执行模式验收状态未更新。
当前 profile 不把 piecewise prefill 视为通过正式 full graph 验收的证据。
