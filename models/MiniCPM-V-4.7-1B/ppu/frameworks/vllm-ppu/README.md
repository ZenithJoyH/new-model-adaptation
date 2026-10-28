# 框架适配记录

记录于 2026-10-12 显式升级为 evidence v2 / profile v2。当前 `not_started` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

2026-10-08：在 PPU-13 的 `minicpmV4.7-ppu` 中新增 1B 启动脚本，复用已批准的
容器工作目录 `/mnt/nfs/users/jinghao/MiniCPMV4.7-ppu`，未启用先前建议的独立新根。
已验证生成版本的 eager、FULL_AND_PIECEWISE、图像/视频、十并发和前缀缓存。
本轮没有修改 vLLM 产品代码；没有签发独立模型工作项的阶段回执或完整验收。

- 挂载目录脚本：`/mnt/nfs/users/jinghao/MiniCPMV4.7-ppu/start-model-1b.sh`。
- 已验证生成版本的内部副本：`/opt/model-adaptations/minicpmv4.7-1b/start-model.sh`。
- 当前已验证服务：GPU 5、8023，模型名 `MiniCPM-V-4.7-1B`，前缀缓存开启。
- 挂载目录脚本在验证期间发生外部修改，最新观察版本指定 GPU 6、关闭前缀缓存；
  该版本只检查了语法与端口冲突拒绝，未实际启动，不能套用生成版本的通过结论。
- [本轮脚本及功能证据](acceptance/launcher-20261008.md)。正式精度、性能与镜像验证未执行。

本目录只保存当前模型、平台和 framework profile 的精简记录。框架定义见 `framework.yml`
引用的仓库级 profile；远端运行产物仍保存在该框架独立的已批准工作根目录。

- `environment/`：框架、容器、组件、Host 和平台环境分析。
- `adaptation/`：仅保存编号问题记录及解决结论。
- `acceptance/`：仅保存验收计划、结果、总结和复盘。

不要在这里保存脚本、源码、补丁、JSON 结果、原始日志、缓存或临时文件。
