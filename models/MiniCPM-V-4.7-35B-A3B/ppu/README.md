# MiniCPM-V-4.7-35B-A3B / ppu

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)

当前 framework 记录：
- [vllm-plugin-fl](frameworks/vllm-plugin-fl/README.md)（v2；历史结论不自动成为新门禁通过）。
- [vllm-ppu](frameworks/vllm-ppu/README.md)（v2；历史结论不自动成为新门禁通过）。

## 整理前平台说明（历史原文）

- Inventory group: `ppu`
- Hardware query: `ppu-smi`

平台根目录保留本索引、`platform.yml` 和显式 `frameworks/` 工作区。新任务先运行
`scripts/new-framework <model> ppu <framework-id>`，再把环境、适配和验收记录分别放入该
framework 目录的 `environment/`、`adaptation/` 和 `acceptance/`。平台根目录已有的三个
同名目录只作为历史隐式 `vllm-plugin-fl` 记录保留。
容器没有暴露 `ppu-smi` 时必须记录为环境阻塞，不得回退到其他平台命令。

2026-10-09 的 `vllm-plugin-fl` 算子切换记录见
[013](frameworks/vllm-plugin-fl/adaptation/013-flaggems-vllm-moe-attention.md)。
Host/容器启动脚本：`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh`；
SHA-256 `03c096bdd0c7b191544e9a7b733059826d732082d8c03f1589c8650faea23298`，
0755，2026-10-09 22:28:34 +08:00 语法、实际启动和 8010 readiness 均已核验。
容器内部交付副本：`/workspace/model-launchers/MiniCPM-V-4.7-35B-A3B-ppu-flagos/start-model.sh`。
本轮是定向回归，未完成正式精度、性能或镜像验收。
