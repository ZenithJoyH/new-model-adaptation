# Qwen3.8-Flash-Next

PPU-01 的功能与算子归属整理已有记录；最新双实例正式精度为 171/198（86.36%），低于 88% 阈值。跨实例数值差异和生成上限问题保持未关闭。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| ppu | [legacy 平台记录](ppu/README.md) | PPU-01 | functional |

仅保留骨架、尚未开展的平台：nvidia、metax、ascend、mthreads、hygon。没有为它们新增阶段任务。

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。
