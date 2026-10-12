# 003：GPQA 全量结果达标但 runner 的数据集配置校验失败

## 元数据

- 状态：`hypothesis`；首次出现、最后验证：2026-09-24。
- 模型/平台/Host：MiniMax-M3，T-Head PPU-ZW810E，`PPU-07`。
- 容器：`minimaxM3-latest-20260924` 与 `minimax-m3-eval-latest-20260924`，均未停止或重启。
- 运行目录：`/mnt/nfs/users/jinghao/minimaxM3-new/04-runs/gpqa-diamond-c64-gen50k-20260924/`。
- 模式与负载：`FULL_AND_PIECEWISE`，TP16，198 题 GPQA Diamond、客户端并发 64、`max_gen_toks=50000`。

## 问题现象与证据

FlagEval 两次尝试均返回 0，各产生 198 个唯一题目、396 条双 filter 样本，strict 正确 178/198（89.90%）、零 timeout/空响应/样本错误。然而 `llmrun.py` 在汇总中两次报 `use either datasets or legacy dataset_path fields, not both`，最终 `exit-code.txt=1`，原生 `acceptance-result.json` 的 `status=failed`。完整证据和 SHA-256 见 [全量诊断报告](../acceptance/gpqa-diamond-gen50k-diagnostic-20260924.md)。本轮冻结的 minimum 为 0.80；用户在结果产生后指定 0.88，观测分数亦高于该值，但不能追溯改写冻结标准。

## 诊断与假设

- 已验证：源配置使用 `dataset_path`、`dataset_name`、`dataset_split`，没有 `datasets`。仓库原生 `test/Accuracy_test/llmrun.py` 的 `load_config` 把 legacy 字段正规化为 `datasets`，却仍保留 `dataset_path`；后续 `acceptance_contract.metric_errors` 调用 `validate_formal_config` 时拒绝两者同时存在。当前评测容器内 runner 的实际文件 SHA-256 是 `4f9076aaae6e3efb32246a66053f971d1d70b04d99f196599daf5e57ca2eb2cc`。
- 未验证：将新配置仅改用 task-keyed `datasets` 后，完整 runner 是否能生成 `passed` 回执；本轮未修改冻结配置或重跑。
- 已排除：不是样本缺失、请求超时、lm-eval 退出异常或模型服务不健康。

## 受控尝试

| 轮次 | 条件 | 结果 | 结论 |
|---|---|---|---|
| 1 | 冻结 legacy dataset 配置，50K 全量 | attempt-1 的 lm-eval 返回 0、strict 178/198；外层校验拒绝重复字段 | runner 配置处理缺陷或兼容问题 |
| 2 | runner 自动重试，复用同配置/响应缓存 | attempt-2 同样 198 题与 178/198；同一校验失败 | 重试不能修复静态配置冲突；不视为两个独立精度测量 |

## 影响与下一步

问题属于项目评测工具，不属于 Plugin/FlagGems-vllm 的模型算子修复；本轮仅提交 [001 修复](001-swigluoai-boundary.md) 的产品代码，不为通过门禁篡改已有原生回执。若继续正式验收，应先完成缺失的 architecture/environment/adaptation、execution-mode/sanity 前置回执，再修正 runner 或使用仅含 `datasets` 的新冻结配置及 0.88 阈值，按原生入口重新预检与评测。不得把此轮诊断结果直接标记为正式 `passed`。知识库处理状态：`local-only`。
