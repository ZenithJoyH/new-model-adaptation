# PPU-13 删除 `--max-model-len` 后的启动验证

日期：2026-10-01；目标 Host `PPU-13`，容器 `minicpmV4.7-35B`，模型只读路径
`/mnt/cpfs/models/MiniCPM-V-4.7/weights/35b-a3b`。批准工作根在 Host 和容器内
均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，映射已核实。Plugin、vLLM、
FlagGems HEAD 分别为 `3a27a6fb2d514cdf55c00481bf813225dac63319`、
`ee0da84ab9e04ac7610e28580af62c365e898389`、
`1a38df24f72ca5a4a6a24650b5d66356709750ba`。本轮未修改产品源码、
权重或适配容器。

## 变更与过程

用户修改的 Host/容器根级脚本为 `start-model.sh`，0755，SHA-256
`4819df586f8cb17286951fbe764615afa717ca9acd24543f9e3fef07f8f6f17c`。
与上一轮已通过脚本 SHA-256
`1aac69a02c3fed37be7ce6fff446e5e22bd3edf9fae628e847d8f4abcbb4731a`
逐行比较，仅删除 `--max-model-len 50000`。容器内 `bash -n` 通过；
模型 `text_config.max_position_embeddings=262144`。切换前确认端口 8016
上的旧服务是本任务的模型及四个进程；仅停止该推理服务，四进程退出后
从当前根级脚本重新启动，容器持续运行。单 Host Ansible playbook 的语法与
`--check --diff` 均通过。

本轮工作目录 `04-runs/no-max-model-len-20261001/`，其中保存同字节的
`launcher-under-test.sh`、五个响应 JSON、`service.log` 和不可覆盖的
`startup-and-smoke.log`。从该工作目录执行脚本；缓存使用
`06-cache/start-model-piecewise/`，临时目录使用 `05-tmp/start-model-piecewise/`，
由外部启动环境注入。根级脚本仍使用相对 `./service.log`，故本次结果以该
工作目录和环境为条件。

## 验证结果

- 启动日志确认 `max_seq_len=262144`、前缀缓存开启、TP2、
  `FULL_AND_PIECEWISE` 与捕获尺寸 `[1,2,4,8,16,32,64]`；混合
  prefill/decode PIECEWISE 7/7、decode FULL 7/7。`/health` 为 HTTP 200，
  `/v1/models` 报告 `max_model_len=262144`。
- 文本 `17+25` 返回 `42`；64×48 红图两次、蓝图一次、红图再一次分别
  返回 `红色`、`红色`、`蓝色`、`红色`。五次请求均 HTTP 200、
  `finish_reason=stop`，探针判定 5/5 通过。结果路径分别是
  `04-runs/no-max-model-len-20261001/{text,red-1,red-2,blue,red-3}.json`。
- 2026-10-01 08:44:17 +08:00 复验时，API/EngineCore/TP0/TP1 容器 PID
  分别为 `1238828`/`1239308`/`1239599`/`1239600`，健康检查仍为 200。
  PPU 0、1 分别占 91,960/98,304 MiB 和 91,968/98,304 MiB；
  PPU 2 的其他任务未操作。

`startup-and-smoke.log` SHA-256 为
`4466f84eb9c1e469a1eae64f57dcf395a052e35e424d2a347759731ecb073184`。
五个 JSON 按上述顺序的 SHA-256 分别为
`18ed6eea9a2bc00f1a21bfc8db2dbb40fa08169bbdac7e1c7d352cdd5df5413b`、
`3a1915b667dc56d986883096dc9c60edeac9f9346ec84d0ebd0417eef07cb689`、
`4ac9244e0bd58784674149024884132adc4c333cc309a5c15730d27b7c5f1f63`、
`e4ec12104a1e935afbb0a2d02f9f2008268c4db15a926cb605c16b42e02256d9`、
`bbfefe953480e0ba2ec259404fb8a75470614680dc0bc2825d436b90e8acb1d8`。

## 结论与边界

当前脚本不显式设置 `--max-model-len` 时，服务可启动并完成上述短图文请求；
vLLM 生效长度由 50,000 变为模型配置的 262,144。本轮没有发送接近该长度的
请求，也没有验证长上下文、显存边界、并发或吞吐，不能据此断言完整
262,144 token 负载可用。用户要求暂缓正式精度评测，本轮只验证启动与基本
推理；当前 prefill 仍为 PIECEWISE，正式执行模式、sanity、精度、性能和
总结验收均未通过，`framework.yml` 状态保持 `environment_ready`。
