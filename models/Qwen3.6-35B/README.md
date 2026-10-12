# Qwen3.6-35B

旧 mx-104 平台记录与 mx-59 Plugin 优化记录分别保留。mx-59 三组吞吐改善为 21.3% / 65.2% / 49.0%，但部分尾延迟上升；正式整模精度及镜像验收未执行。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| metax | [legacy 平台记录](metax/README.md) | mx-104 | environment_ready |
| metax | [vllm-plugin-fl](metax/frameworks/vllm-plugin-fl/README.md) | mx-59 | v2 `not_started`；原记录 `not_started` |

仅保留骨架、尚未开展的平台：nvidia、ppu、ascend、mthreads、hygon。没有为它们新增阶段任务。

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。
