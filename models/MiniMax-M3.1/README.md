# MiniMax-M3.1

已完成（2026-10-08 用户验收确认）。GPQA 84.8484% 与三组性能结果的完成结论保持不变；原生证据和镜像验证限制继续作为维护备注，不自动重开评测。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| ppu | [vllm-plugin-fl](ppu/frameworks/vllm-plugin-fl/README.md) | PPU-07 | 用户验收 complete；v2 未重验 |

仅保留骨架、尚未开展的平台：nvidia、metax、ascend、mthreads、hygon。没有为它们新增阶段任务。

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。

## 整理前概览（原文保留）

以下原文保留当时的范围和结论；最新目录入口及 v2 状态口径见上方。

**当前进展：已完成。** 2026-10-08，用户在提供精度和性能评测结果后确认本次适配完成；结果文件已只读核验，本地记录按该验收结论收尾。

| 平台 / 主机 | 推理框架 | 项目进展 | 完成确认日期 | 结果 |
|---|---|---|---|---|
| T-Head PPU / PPU-07 | vLLM + vllm-plugin-FL + FlagGems | **已完成（用户验收）** | 2026-10-08 | GPQA 84.8484% ≥ 80.9%；4K/16K/32K 三组性能已核验并由用户接受 |

本次范围仅为 PPU-07 的 `minimaxM3.1` 容器与 W8A8 checkpoint `/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`。已验证服务方案为 TP16、BF16、`max_model_len=204800`、`max_num_seqs=64`、`FULL_DECODE_ONLY`；用户自行启动并完成外部评测。

- [适配总结与完整进展](ppu/frameworks/vllm-plugin-fl/acceptance/adaptation-summary.md)
- [平台概览](ppu/README.md) · [框架概览](ppu/frameworks/vllm-plugin-fl/README.md)
- [模型结构与推理链路](architecture-and-inference.md)
- [精度结果](ppu/frameworks/vllm-plugin-fl/acceptance/accuracy-external.md) · [性能结果](ppu/frameworks/vllm-plugin-fl/acceptance/performance-external.md)

其他平台不在本次适配范围。项目完成结论已写入 `model.yml` 的 `status: complete`，平台和框架的 `project_completion.status: complete` 同步记录。框架顶层 `status: functional` 表示已验证的推理能力；原生流程字段保留历史回执状态，不将外部结果伪装成原生通过。相关证据格式、版本绑定及已知技术限制集中保留在适配总结中，不再作为本次用户确认完成后的待执行任务。
