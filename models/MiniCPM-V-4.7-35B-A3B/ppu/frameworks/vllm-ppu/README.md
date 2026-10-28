# 原生 PPU vLLM：MiniCPM-V 4.7 35B-A3B

记录于 2026-10-12 显式升级为 evidence v2 / profile v2。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

2026-10-08：PPU-13 / `minicpmV4.7-ppu` 原生服务功能已验证。安装代码接入 MoE 与 canvas
M-RoPE，eager、图像/视频、双卡 FULL_AND_PIECEWISE 七档图、十并发和前缀缓存检查通过。
experimental profile；未完成正式精度、性能或镜像验收。

- 工作根与启动脚本：`/mnt/nfs/users/jinghao/MiniCPMV4.7-ppu/start-model.sh`。
- 当前服务：PPU3/4、TP2、端口 8022，模型名 `MiniCPM-V-4.7-35B-A3B`。
- [环境身份](environment/001-native-container.md)、[代码适配](adaptation/001-native-47.md)、
  [图模式边界](adaptation/002-gdn-graph-boundary.md)、[功能结果与交付](acceptance/functional-20261008.md)。
- [基础记录原生复核](acceptance/record-binding-20261008.md)已通过；完整精度/性能验收未执行。

本目录只保存当前模型、平台和 framework profile 的精简记录。框架定义见 `framework.yml`
引用的仓库级 profile；远端运行产物仍保存在该框架独立的已批准工作根目录。

- `environment/`：框架、容器、组件、Host 和平台环境分析。
- `adaptation/`：仅保存编号问题记录及解决结论。
- `acceptance/`：仅保存验收计划、结果、总结和复盘。

不要在这里保存脚本、源码、补丁、JSON 结果、原始日志、缓存或临时文件。
