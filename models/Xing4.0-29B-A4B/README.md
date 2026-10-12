# Xing4.0-29B-A4B

PPU-13 的独立 Xing4.0 实现已有验证，最新重构后 graph 尚未重跑；NVIDIA H100-145 另有 MATH-500 432/500（86.40%）独立评测，不作为正式 acceptance。与 XingChen4 保持独立目录。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| nvidia | [独立评测记录](nvidia/README.md) | H100-145（独立评测） | 正式阶段 not_started |
| ppu | [legacy 平台记录](ppu/README.md) | PPU-13 | environment_ready |

仅保留骨架、尚未开展的平台：metax、ascend、mthreads、hygon。没有为它们新增阶段任务。

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。
