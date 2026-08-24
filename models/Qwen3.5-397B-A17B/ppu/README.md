# T-Head PPU adaptation

- Primary targets: `PPU-01`, `PPU-03`, `PPU-07`, `PPU-13`
- Hardware query: `ppu-smi`
- ModelScope: `1.39.1`

当前四台物理机可执行 `ppu-smi`，并已修复 ModelScope CLI。`PPU-231/240`
是未暴露 `ppu-smi` 的容器环境；`PPU-233/234` 当前被堡垒机报告为资产不存在。

下一步：确定 PPU 推理运行时与插件 revision，确认共享权重路径，完成模型代码
适配、最小推理和性能基线。相关脚本、配置、补丁和结果均保存在本目录。
