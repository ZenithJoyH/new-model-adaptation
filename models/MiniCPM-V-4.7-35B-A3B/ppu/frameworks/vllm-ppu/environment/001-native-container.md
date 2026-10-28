# PPU-13 原生容器环境

日期：2026-10-08。用户指定新容器 `minicpmV4.7-ppu`、模型
`/mnt/cpfs/models/MiniCPM-V-4.7-35B-A3B`，明确允许修改实际安装的 vLLM；
另确认工作根 `/mnt/nfs/users/jinghao/MiniCPMV4.7-ppu`。

- 容器 ID：`a7171373be0a93b76f4e91f840914e81a754e3048e4a456350f89497fb40b770`。
- 镜像：`sha256:9168c1a258c5ef3d5a3d3dfdc6dfa32436c5765174d220c527980e0157bd2eca`。
- `/mnt` 为 host `/mnt` 的 RW bind；批准根在两侧 realpath 一致，device/inode
  `41:33436207060`。容器保持运行。
- Python `/usr/local/bin/python3.12`；vLLM `0.23.0+v0.2.0.ppu2.1.0`，普通 wheel，
  实际包 `/usr/local/lib/python3.12/site-packages/vllm`，无 editable/Git 来源。
- PyTorch 2.10.0、Transformers 5.8.1；没有 Plugin 或 FlagGems，没有 PYTHONPATH。
- 原 8010 服务占用 PPU0/1，另一服务占用 PPU2；新任务选择空闲 PPU3/4、端口 8022。

原生 PPU wheel 不符合既有 `vllm-native` 的 NVIDIA/editable 来源要求，也不符合
`vllm-plugin-fl` 的组件结构与 vLLM 只读边界。因此新增限于原生 PPU 的 experimental
`vllm-ppu` profile，写入范围仅实际安装的 vLLM Python 产品代码。权重、checkpoint
配置/处理器、PyTorch、驱动及二进制内核保持只读。

远端证据根：`04-runs/bringup-20261008/`（相对批准根）。`baseline.json` 保存
1913 个 vLLM Python 文件及 checkpoint 小文件 SHA；`baseline-config-result.json`
及日志保存未修改代码的负基线：4.7 架构不受支持。缓存、临时文件分别位于批准根
`06-cache/`、`05-tmp/`，未选择另一份产品源码。
