# Hygon adaptation

- Inventory group: `hygon`
- Hardware query: `hy-smi`
- Process query: `hy-smi --showpids`

平台根目录保留本索引、`platform.yml` 和显式 `frameworks/` 工作区。新任务使用
`scripts/new-framework <model> hygon <framework-id>` 创建独立环境、适配和验收记录；平台
根目录已有的三个同名目录只作为历史隐式 `vllm-plugin-fl` 记录保留。
`htop` 仅用于交互式 SSH 排查，不作为批量脚本入口。
