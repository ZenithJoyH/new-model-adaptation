# Qwen3.8-Flash-Next

PPU-01 的功能与算子归属整理已有记录；最新双实例正式精度为 171/198（86.36%），低于 88% 阈值。跨实例数值差异和生成上限问题保持未关闭。

PPU部分于2026-10-12按历史记录整理；MetaX部分为2026-10-23起本轮真实适配，分别以对应记录为准。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| ppu | [legacy 平台记录](ppu/README.md) | PPU-01 | functional |
| metax | [vllm-plugin-fl](metax/frameworks/vllm-plugin-fl/README.md) | mx-101 | GPQA183/198通过；graph九场景测量及最终启动交付完成，functional；性能只测量不判定 |

仅保留骨架、尚未开展的平台：nvidia、ascend、mthreads、hygon。没有为它们新增阶段任务。

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。
