# DeepSeek-V4-Flash

MetaX 的 eager 与 decode FULL graph 有最小请求记录；全链路图模式、正式精度与性能尚未完成。目标为 V4 INT8，不与 V4.1 混用。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| metax | [vllm-plugin-fl](metax/frameworks/vllm-plugin-fl/README.md) | mx-59 | v2 `blocked`；原记录 `blocked` |

仅保留骨架、尚未开展的平台：nvidia、ppu、ascend、mthreads、hygon。没有为它们新增阶段任务。

架构与推理链路文档尚未形成，不创建无证据的占位分析。 · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。

## 整理前概览（原文保留）

以下原文保留当时的范围和结论；最新目录入口及 v2 状态口径见上方。

本记录针对 `DeepSeek-V4-Flash-Quant-W-INT8-PerChannel-A-INT8-PerToken`，不是 V4.1。MetaX PR 427 适配已完成 eager 与 decode FULL graph 的最小真实请求；正式架构、精度与性能阶段未执行。

| 平台 | Framework profile | 状态 | 最近验证 | 备注 |
|---|---|---|---|---|
| NVIDIA | - | `not_started` | - | - |
| PPU | - | `not_started` | - | - |
| MetaX | [vllm-plugin-fl](metax/frameworks/vllm-plugin-fl/README.md) | `blocked` | 2026-09-22 | eager 与 decode FULL graph 请求通过；标准 torch.compile 语义错误及正式验收证据未完成 |
| Ascend | - | `not_started` | - | - |
| Moore Threads | - | `not_started` | - | - |
| Hygon | - | `not_started` | - | - |

完成一次适配后，在这里记录跨平台结论和推荐配置。
