# Hygon adaptation

- Inventory group: `hygon`
- Hardware query: `hy-smi`
- Process query: `hy-smi --showpids`
- Current state: blocked because no Hygon SSH host alias is configured.

新增海光主机后，先验证 SSH、`hy-smi` 和 Python 环境，再选择推理引擎与镜像。
`htop` 只用于交互式 SSH 排查。
