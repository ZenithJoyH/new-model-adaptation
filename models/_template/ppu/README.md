# T-Head PPU adaptation

- Inventory group: `ppu`
- Hardware query: `ppu-smi`

平台根目录只保留本索引与 `platform.yml`。运行 `scripts/adapt-model` 后，环境材料、
适配过程和验收证据分别放入 `environment/`、`adaptation/` 和 `acceptance/`。
容器没有暴露 `ppu-smi` 时必须记录为环境阻塞，不得回退到其他平台命令。
