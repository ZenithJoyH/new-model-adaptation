# DeepSeek-V4.1-Flash / nvidia

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)

当前 framework 记录：
- [vllm-plugin-fl](frameworks/vllm-plugin-fl/README.md)（v2；历史结论不自动成为新门禁通过）。

旧平台阶段记录按原位置保留（不作为新增执行入口）：
- [问题台账](adaptation/README.md)。
- [验收记录](acceptance)。

## 整理前平台说明（历史原文）

- Inventory group: `nvidia`
- Hardware query: `nvidia-smi`

平台根目录只保留本索引与 `platform.yml`。运行 `scripts/adapt-model` 后，环境材料、
适配过程和验收证据分别放入 `environment/`、`adaptation/` 和 `acceptance/`。

## Native vLLM adaptation

- `H100-149` 上的 NV 原生 vLLM W8A8-BF16 适配已完成最小功能验证：TP8 服务 ready，确定性聊天请求返回正确结果 `42`。
- 适配范围、源码哈希、失败根因和原生证据路径见 [001：原生 vLLM 支持 W8A8 视觉塔与 BF16 Engram](adaptation/001-native-vllm-w8a8-bf16.md)。
- GPQA Diamond 全量 198 题、64 并发、模型资料采样参数（`reasoning_effort=max`、
  `temperature=1.0`、`top_p=0.95`）及 `max_gen_toks=45000` 的最终 strict-match 为
  `176/198 = 88.89%`，达到 88% 门槛；6 个输出截断按错误保留。原生精度收据
  `passed`；与两种确定性生成上限的对照见 [GPQA 64 并发精度评测](acceptance/gpqa-c64-20260923.md)。
- execution-mode 与 sanity 的正式前置回执尚未绑定，performance 未执行，因此不代表完整 acceptance 已完成。
