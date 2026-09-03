# Hygon adaptation

- Inventory group: `hygon`
- Hardware query: `hy-smi`
- Process query: `hy-smi --showpids`

平台根目录只保留本索引与 `platform.yml`。运行 `scripts/adapt-model` 后，环境材料、
适配过程和验收证据分别放入 `environment/`、`adaptation/` 和 `acceptance/`。
`htop` 仅用于交互式 SSH 排查，不作为批量脚本入口。
