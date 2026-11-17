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

## 2026-11-12 证据告警复核

本轮仅检查本地记录、校验逻辑和已有归档，没有访问远端、运行评测或改写
`platform.yml`。原生 vLLM 的历史功能结论及 GPQA `176/198 = 88.89%` 保留。

| 告警 | 核对结果 | 补证要求 |
| --- | --- | --- |
| D1：adaptation 缺 architecture 前置 | architecture 为 `not_started`，无 verification | 核实对应模型快照并补齐结构分析绑定 |
| D2：adaptation 缺 environment 前置 | environment 为 `not_started`，无 verification | 核实原生服务的主机、容器、安装组件及工作根后绑定 |
| D3：acceptance 缺 architecture 前置 | 与 D1 相同的缺项影响验收 | 随 D1 补齐，不虚构一次独立测试 |
| D4：acceptance 缺 environment 前置 | 与 D2 相同的缺项影响验收 | 随 D2 补齐 |
| D5：acceptance 缺 adaptation 前置 | adaptation 为 `in_progress`，其 blocker 已说明前置未闭环 | 前置和源码/功能证据均有效后再核定完成状态 |
| D6：accuracy 缺 verification | `records` 为空；精度文档记有原生通过回执路径及 SHA-256，本地整理前快照中未找到该 JSON | 先取回并校验原 run 的正式回执及其配置、样本和服务绑定；不能仅据 Markdown 填入通过绑定 |
| D7：accuracy 缺 execution-mode 前置 | 子步骤为 `not_started`，无正式回执 | 核查与该原生服务相同范围的模式证据；缺失时重新验证 |
| D8：accuracy 缺 sanity 前置 | 子步骤为 `not_started`，无正式回执 | 核查相同实例的代表性请求及结果审阅；缺失时重新验证 |

这些告警是已记录的证据缺口，不能靠补写 `passed`、复制文档哈希或清空 blocker 消除。
[原始精度记录](acceptance/gpqa-c64-20260923.md)中的最终 run 为
`gpqa-full-c64-official-max-t1-p095-45k-20260923-v4`，正式回执记载 SHA-256 为
`67b286d41e89c8960ba2b7b4d70fb5b7975b6be9e5b04a7f9d5a3c88d5ae78f6`；本轮未读取远端
回执，不能声明已重新验证它。原件可恢复且身份、配置及完整产物仍匹配时，先做只读校验，
无需仅为绑定缺失立即重跑 GPQA；原件不可恢复或实际部署已变化时，再确定新 run 的范围。

此处结果属于原生 vLLM。已有 `vllm-plugin-fl` 工作区的 Plugin 诊断、退役记录和新契约状态
分别保留，不能用本轮原生分数替代其验收。接续正式验证前需选择与原生实现一致的 profile。
