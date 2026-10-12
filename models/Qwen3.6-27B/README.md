# Qwen3.6-27B

MetaX mx-58 的模型结构、环境及 Plugin 适配过程已有记录；正式精度、性能与完整验收尚未闭环。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| metax | [vllm-plugin-fl](metax/frameworks/vllm-plugin-fl/README.md) | mx-58 | v2 `blocked`；原记录 `model_loading` |

仅保留骨架、尚未开展的平台：nvidia、ppu、ascend、mthreads、hygon。没有为它们新增阶段任务。

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。
