# Hygon adaptation

- Inventory group: `hygon`
- Hardware query: `hy-smi`
- Process query: `hy-smi --showpids`

依次记录环境准备、模型加载、服务启动、最小推理、性能基线、优化实验和最终
推荐命令。`htop` 仅用于交互式 SSH 排查，不作为批量脚本入口。
