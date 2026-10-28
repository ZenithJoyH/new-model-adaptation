# MiniCPM-V-4.7-1B / ppu

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

2026-10-03，显式 [vllm-plugin-fl 工作区](frameworks/vllm-plugin-fl/README.md) 在 `PPU-13` 的当前启动脚本 Host/容器同路径 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/start-model.sh` 上验证 SHA-256 `baee3f4658befa9598b81104d5c30fcd51601cefb2b5be5b6e1e428e7da219f9`、语法、真实启动、健康检查、模型 ID 与短题。启用的 FlagGems Aten 注册关闭后，MMLU-Pro 14 科各 50 题完整返回且持续乱码未再出现；正式精度和图级别验收状态未变。证据与限制见该工作区的 [诊断报告](frameworks/vllm-plugin-fl/acceptance/mmlu-pro-atenoff-limit50-20261003.md)。
