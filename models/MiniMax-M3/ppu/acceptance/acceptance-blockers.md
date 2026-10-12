# MiniMax-M3 / PPU 验收门禁记录

## 当前判定

2026-09-16 已按用户确认的“GPQA Diamond 固定数据顺序前 10 题”完成 c10 sanity：`strict-match = 1.0`，10/10 题、0 timeout、0 request error。随后在同一 65K graph 服务实例上完成当前 redesign 的 GPQA Diamond 198 全量 c64：`strict-match = 177/198 = 0.8939393939393939`，0 timeout、0 refusal、0 request/runner error，原生 receipt 为 `passed`。`sanity` 与 `accuracy` 均已通过；`performance` 尚未执行，仅可通过下一子步骤的只读 gate-check 验证其前置状态。

## 已解决的输入

- manifest 冻结数据 Arrow SHA-256 `501f307f9e8bc34041af4120c8eb5a735f0ea29cd83c90167b913651071bb4c4`、任务模板/配置/process_docs 哈希、doc_id 0..9、问题、随机化后选项和答案；manifest SHA-256 为 `ca36a36fe88ca81556dd8823494095bb5d6d115bf8dfb76287f7f03c0b4ca4c7`。
- 用户将 GPQA Diamond 198 的 `exact_match,strict-match` minimum 指定为 80%；按 runner 契约冻结为 `0.80`，并将正式客户端并发度冻结为 `64`。
- 用户要求评测服务 max model len 开到 50000 以上；按“至少 50000”冻结，当前服务实际参数为 `--max-model-len 65536`。
- 评测使用当前 `inference-accuracy-evaluation/SKILL.md`、其 `references/project-contract.md` 和仓库 canonical runner；仓库总契约中另行指向不存在的 `references/accuracy-method.md` 是待修复的文档路径漂移，本轮未自拟或放宽评测方法。

## 当前后续

1. 如选择继续 `performance`，先运行其只读 gate-check，并切换到明确包含 `--no-enable-prefix-caching` 的性能专用 graph 服务。
2. `evidence` 与 `summary` 仍未选择和执行；平台 acceptance 继续保持 `in_progress`。
3. 若服务已重启或参数/源码变化，先停止并重新验证服务绑定。
