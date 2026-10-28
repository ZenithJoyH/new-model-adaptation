# MiniCPM-JEV 推理适配

当前范围是用户给定的 Qwen3.5-2B 双图 OCR 一致性 value-head checkpoint，不包含缺失权重的 vocab head。结构和输入输出契约见[架构与推理链](architecture-and-inference.md)。

| 平台 | Framework profile | 状态 | 最近验证 | 备注 |
|---|---|---|---|---|
| NVIDIA | - | `not_started` | - | - |
| PPU | [vllm-plugin-fl](ppu/frameworks/vllm-plugin-fl/README.md) | 功能实测通过 | 2026-10-23 | PPU-01，minicpm-jev-vllm；12样例/并发/图像消融通过，正式验收未完成 |
| MetaX | - | `not_started` | - | - |
| Ascend | - | `not_started` | - | - |
| Moore Threads | - | `not_started` | - | - |
| Hygon | - | `not_started` | - | - |

其他平台未执行；当前不能宣称完整验收或 optimized。
