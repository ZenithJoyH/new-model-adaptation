# DeepSeek-V4.1-Flash

NVIDIA 原生 vLLM 已有最小功能与 GPQA 176/198（88.89%）记录；execution-mode/sanity 的正式前置绑定及性能未闭环。Plugin 工作区单独保留。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| nvidia | [legacy 平台记录](nvidia/README.md) | H100-149 | functional |
| nvidia | [vllm-plugin-fl](nvidia/frameworks/vllm-plugin-fl/README.md) | H100-149 | v2 `blocked`；原记录 `model_loading` |
| metax（实际目标为 V4） | [误存历史材料](metax/README.md) | mx-59（V4 历史记录） | 不属于 V4.1 验收 |

仅保留骨架、尚未开展的平台：ppu、ascend、mthreads、hygon。没有为它们新增阶段任务。

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。

MetaX 的 001—004 问题在原索引中已明确更正为 **DeepSeek-V4-Flash INT8**，此处只保留原历史位置，不能据此认定 V4.1 开展了 MetaX 适配。接续入口为 [V4 工作区](../DeepSeek-V4-Flash/metax/frameworks/vllm-plugin-fl/README.md)。

## 整理前概览（原文保留）

以下原文保留当时的范围和结论；最新目录入口及 v2 状态口径见上方。

当前仅完成模型结构与推理链路的只读分析。现场权重位于
`H100-145:/public/models/DeepSeek-V4.1-Flash`；尚未选择或执行 environment、adaptation、
acceptance、retrospective 阶段。

- 主干：约 552B CED + CSA2 + MoE + mHC。
- 完整逻辑参数：约 763.205B（含 196.929B Engram、14.225B DSpark/MTP 和视觉组件）。
- 当前权重：48 个 safetensors 分片，约 475.251 GiB。
- 官方激活量：prefill 约 8B/token，decode 约 16B/token；尚未在本机运行时验证。
- 详细证据见 [architecture-and-inference.md](architecture-and-inference.md)。

| 平台 | 状态 | 推理引擎 | 最近验证 | 备注 |
|---|---|---|---|---|
| NVIDIA | `not_started` | - | 2026-09-15 | 已做 H100-145 静态容量分析；8 卡当前被无关服务占用 |
| PPU | `not_started` | - | - | - |
| MetaX | `not_started` | - | - | - |
| Ascend | `not_started` | - | - | - |
| Moore Threads | `not_started` | - | - | - |
| Hygon | `not_started` | - | - | - |

`not_started` 表示 NVIDIA 平台环境与适配尚未开始，不否定模型级 architecture 文档已经完成。
