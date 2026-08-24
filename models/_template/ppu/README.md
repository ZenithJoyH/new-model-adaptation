# T-Head PPU adaptation

- Inventory group: `ppu`
- Hardware query: `ppu-smi`

依次记录环境准备、模型加载、服务启动、最小推理、性能基线、优化实验和最终
推荐命令。容器没有暴露 `ppu-smi` 时必须记录为环境阻塞，不得回退到其他平台命令。
