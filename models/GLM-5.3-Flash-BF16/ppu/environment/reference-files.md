# 适配参考文件索引

| 参考文件 | 来源 | revision/日期 | 与当前适配的关系 | 是否采用 | 采用位置或拒绝原因 |
|---|---|---|---|---|---|
| 模型 `config.json` 与权重索引 | PPU-13 `/mnt/cpfs/models/GLM-5.3-Flash-BF16` | config/index SHA-256 见 architecture 文档，2026-09-03 | 唯一直接的模型结构与 shape contract | 是 | 架构、weight mapping、50K 上限计算 |
| 模型 README | 同一模型目录 | 2026-08-27 文件快照 | 发布方 320B/18B 声明和官方 serving 入口 | 部分 | 参数规模作为声明记录；不直接执行网络命令 |
| Hy4 PPU 插件适配 | `/workspace/vllm-plugin-FL-hy4-preview` 及 `models/Hy4-preview/ppu` | plugin baseline `1184859`；2026-09-03 | MLA/Indexer/MoE/vendor dispatch、graph 测试模式 | 候选 | 每项 contract 独立验证；不假定 KDA/mHC/GLM5 兼容 |
| vLLM 源树 | `/workspace/vllm` | `ee0da84ab9e04ac7610e28580af62c365e898389` | 只读接口契约与注册机制 | 是（只读） | 禁止修改 |
| FlagGems 源树 | `/workspace/FlagGems` | 同步前 `60d0430`，同步后另记 | 算子候选 | 待同步检索 | 必须先 `pull --ff-only` |

外部参考只作为证据和思路线索，不能未经验证直接执行。不要在此复制或记录密钥、
完整大日志或模型权重。
