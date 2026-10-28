# MiniCPM-V-4.7-35B-A3B

已将旧名 `MiniCPM-V-4.7-35B` 合并至本目录。分别保留 NVIDIA 原生 vLLM、NVIDIA Plugin、PPU Plugin 与 PPU 原生框架；已有功能或诊断结果不代表四套工作区均完成正式验收。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| nvidia | [vllm-plugin-fl](nvidia/frameworks/vllm-plugin-fl/README.md) | H100-149 | v2 `blocked`；原记录 `environment_ready` |
| nvidia | [vllm-native](nvidia/frameworks/vllm-native/README.md) | H100-149 | v2 `blocked`；原记录 `functional` |
| ppu | [vllm-plugin-fl](ppu/frameworks/vllm-plugin-fl/README.md) | PPU-13 | v2 `blocked`；原记录 `environment_ready` |
| ppu | [vllm-ppu](ppu/frameworks/vllm-ppu/README.md) | PPU-13 | v2 `blocked`；原记录 `functional` |

仅保留骨架、尚未开展的平台：metax、ascend、mthreads、hygon。没有为它们新增阶段任务。

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

[别名、合并依据与原始快照](_shared/model-directory-merge.md)。

模型来源与身份以合并后的 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。
