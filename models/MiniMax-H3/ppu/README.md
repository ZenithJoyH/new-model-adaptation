# T-Head PPU adaptation

- Inventory group: `ppu`
- Hardware query: `ppu-smi`

平台根目录保留本索引、`platform.yml` 和显式 `frameworks/` 工作区。新任务先运行
`scripts/new-framework <model> ppu <framework-id>`，再把环境、适配和验收记录分别放入该
framework 目录的 `environment/`、`adaptation/` 和 `acceptance/`。平台根目录已有的三个
同名目录只作为历史隐式 `vllm-plugin-fl` 记录保留。
容器没有暴露 `ppu-smi` 时必须记录为环境阻塞，不得回退到其他平台命令。
