# PPU-13 多模态启动参数删减对照

日期：2026-10-01。目标 Host `PPU-13`，容器 `minicpmV4.7-35B`，镜像
`sha256:52536a088a055b2c24cdfca21d0ea9e8d68c1f5f82fee7a40f7ec8f72e4a`。
宿主机与容器批准根同为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，此前已核实
bind mount 与设备号:inode；本轮再次核对同一路径的脚本 SHA。模型权重只读路径
`/mnt/cpfs/models/MiniCPM-V-4.7/weights/35b-a3b`。Plugin、vLLM、FlagGems
HEAD 分别为 `3a27a6fb2d514cdf55c00481bf813225dac63319`、
`ee0da84ab9e04ac7610e28580af62c365e898389`、
`1a38df24f72ca5a4a6a24650b5d66356709750ba`；本轮未修改产品源码、权重或容器。

## 方法与结果

从前一轮根级脚本 SHA-256
`4051002a7e813e81efc71123a5adf5db7c4ba62c44bb9844824d69ae0a258750`
逐行生成对照，固定 TP2/PPU 0、1、50,000 上下文、
`--mm-processor-cache-gb 0`、前缀缓存开启、`FULL_AND_PIECEWISE` 和图捕获尺寸
`[1,2,4,8,16,32,64]`。每轮都从批准的独立 `04-runs/` 工作目录启动，同用
`06-cache/start-model-piecewise/` 和 `05-tmp/start-model-piecewise/` 环境边界；
仅在核实当前模型/端口/四进程身份后停止本任务推理服务，适配容器持续运行。
使用 `02-issues/launcher-flags-20261001/probe.py` 依次发送文本、相同红图两次、
蓝图、再一次相同红图。图像均为 64×48 PNG，固定 `temperature=0`、
`max_tokens=4`、`enable_thinking=false`；逐项要求 HTTP 200、`stop` 及预期答案。

| 轮次 | 单一变化 | 生效后端与图捕获 | 图文结果 | 不可覆盖日志快照 SHA-256 |
| --- | --- | --- | --- | --- |
| `04-runs/no-data-20261001/` | 只删除 `--mm-encoder-tp-mode data`，恢复默认 `weights`；脚本 SHA `b54787fa24f9447a710d7e14b26635eeaed7502a06af77c112dac069c4855c82` | SDPA 保留；mixed PIECEWISE 7/7、decode FULL 7/7；`/health` 200 | 5/5：`42`、红、红、蓝、红，全部 `stop` | `502c73463841721e21e8cd4d008492d4e156cfaf22ef5f647256cd2637957d6c` |
| `04-runs/no-data-no-sdpa-20261001/` | 在上一轮基础上只删除 `--mm-encoder-attn-backend TORCH_SDPA`；脚本 SHA `1aac69a02c3fed37be7ce6fff446e5e22bd3edf9fae628e847d8f4abcbb4731a` | 日志明确选用 `FLASH_ATTN`；两类图各 7/7；`/health` 200 | 同样 5/5，全部 `stop` | `bba0bd680e310b7a45fee85b0bea8b0862c5fe18b3a75ff35d73f959166bf950` |
| `04-runs/start-model-mm-minimal-20261001/` | 将第二轮的同字节脚本安装到根级，并由根级脚本实际启动 | 日志确认 `FLASH_ATTN`、两类图各 7/7、前缀缓存开启；`/health` 200 | 同样 5/5，全部 `stop`；服务保持运行 | `4096911c179fccd57e7eba7f25b0d4bda50350e369f9416357cd1e9167c87250` |

每轮 `04-runs/<轮次>/` 均保存 `text.json`、`red-1.json`、`red-2.json`、
`blue.json`、`red-3.json` 与 `startup-and-smoke.log`。最后一轮五个结果的
SHA-256 依次为
`be40cee9209ac6825cfaab65103890e3fee147ca3aaab07313afee35fd922360`、
`a6eeffd09505f0f47d4cbe01b146e7e92102019dfc5dd37d5cbdc4d82bc5f91e`、
`87eb798f13e6b99591897a6cc856e9cb3d83d58b661eec7c5b379da55cb022f4`、
`5c7da445a896b6c823ea5fcd961bb233a7ece7848f92a6e8c5170f221b905bb9`、
`cd3be19f8a98b849759497255e3f6076e8001614d2af8ff4d6966a3dc12a5c01`。
该轮根级脚本 Host/容器路径均为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh`，权限 0755，
SHA-256 `1aac69a02c3fed37be7ce6fff446e5e22bd3edf9fae628e847d8f4abcbb4731a`。
Ansible 单 Host `--check --diff` 显示恰好删除两行，容器内 `bash -n` 与实际
服务进程参数已核实；该轮 API/EngineCore/TP0/TP1 PID 为
`1236939`/`1237419`/`1237704`/`1237705`。最终复验时 PPU 0、1 各占
91,974/98,304 MiB；PPU 2 的其他工作负载未操作。

## 结论与边界

在当前 PPU Plugin 实现及本轮短图文输入上，显式 `data` 和 `TORCH_SDPA`
都不是正确启动及完成这些请求的必要条件，可从根级脚本删除。早期默认
`weights`/`FLASH_ATTN` 曾出现视觉输出异常，但其后的 PPU 专属视觉数值修正
仍在当前 Plugin 中；不能将早期症状直接外推到修正后的代码。此次只做服务参数
对照，没有声称默认后端在复杂图像、视频、长上下文或高并发下已验证，也不能从
不同冷/热缓存的单次耗时作性能结论。

`--mm-processor-cache-gb 0` 继续保留：该轮 canvas M-RoPE 路径仍需未缓存的
视觉目标尺寸，尚无缓存开启后尺寸元数据稳定保留的受控证据。根级脚本仍使用
相对 `./service.log` 且缓存/临时路径由启动环境注入，本轮验证以此工作目录与
环境为条件，不能认定脚本可在任意目录独立启动。用户要求暂缓正式精度评测；
正式执行模式、sanity、精度、性能及总结验收状态保持未开始。
