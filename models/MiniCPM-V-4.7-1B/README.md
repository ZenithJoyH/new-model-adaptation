# MiniCPM-V-4.7-1B

分别保留 NVIDIA 原生 vLLM、NVIDIA Plugin、PPU Plugin 和 PPU 原生框架记录。已有小样本功能结果不代表完整精度、性能或其他框架通过。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| nvidia | [vllm-native](nvidia/frameworks/vllm-native/README.md) | H100-149 | v2 `blocked`；原记录 `functional` |
| nvidia | [vllm-plugin-fl](nvidia/frameworks/vllm-plugin-fl/README.md) | H100-149 | v2 `blocked`；原记录 `model_loading` |
| ppu | [vllm-plugin-fl](ppu/frameworks/vllm-plugin-fl/README.md) | PPU-13 | v2 `blocked`；原记录 `functional` |
| ppu | [vllm-ppu](ppu/frameworks/vllm-ppu/README.md) | 未指定 | v2 `not_started`；原记录 `not_started` |

仅保留骨架、尚未开展的平台：metax、ascend、mthreads、hygon。没有为它们新增阶段任务。

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。

## 整理前概览（原文保留）

以下原文保留当时的范围和结论；最新目录入口及 v2 状态口径见上方。

模型结构见 [架构分析](architecture-and-inference.md)。NVIDIA 原生 vLLM 的独立适配
记录见下表；其他平台未测试。

| 平台 | Framework profile | 状态 | 最近验证 | 备注 |
|---|---|---|---|---|
| NVIDIA | `vllm-native` | `functional` | 2026-09-28 | H100-149；容器安装包直接适配，eager/decode-full 基本推理通过；正式精度和性能未完成 |
| PPU | - | `not_started` | - | - |
| MetaX | - | `not_started` | - | - |
| Ascend | - | `not_started` | - | - |
| Moore Threads | - | `not_started` | - | - |
| Hygon | - | `not_started` | - | - |

当前结论仅覆盖 `H100-149` 的单卡 TP1、2048 token 上下文及本轮文本/图像/视频
小样本；不推断跨平台或完整精度结果。
