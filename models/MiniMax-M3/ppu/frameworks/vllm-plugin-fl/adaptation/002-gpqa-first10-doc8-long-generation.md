# 002：固定 GPQA 十题中 doc_id=8 的超长生成与失分

## 元数据

- 状态：`hypothesis`；首次出现与最后验证均为 2026-09-24。
- 模型/平台/Host：MiniMax-M3，T-Head PPU-ZW810E，`PPU-07`。
- 容器：模型 `minimaxM3-latest-20260924`；评测 `minimax-m3-eval-latest-20260924`。
- 源码：Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c`；FlagGems-vllm 基线 `1f9ac0e0caf3c32111f6be44c8e4d2fef2359546` 加 001 记录的未提交边界修复；FlagGems `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 模式/负载：`FULL_AND_PIECEWISE`，TP16，服务 `max_model_len=65536`，固定前十题 `doc_id=0..9`，并发 10，`max_gen_toks=30000`。

## 问题现象

`/mnt/nfs/users/jinghao/minimaxM3-new/04-runs/gpqa-sanity-first10-latest-20260924/` 的原生结果完整 10 题、零超时、runner 退出码 0，但 `exact_match,strict-match=0.9`，不满足本项目 sanity 的逐题全对要求。唯一错误为 `doc_id=8`：数据集目标 `(C)`，模型提取答案 `D`。该样本 `completion_tokens=30000`，正好触及冻结的生成上限；输出长约 106,994 字符且末尾仍在推理，没有可靠的结束答案。其余九题正确。评测结果文件和 samples JSONL 均保留于上述 run root；固定题清单为 `03-acceptance/gpqa-sanity-first10-manifest-20260924.json`。

先前 9/10 的实时进度不能当作十题通过；正式汇总确认 9/10。服务 `/health` 200，单次真实推理、eager 与目标 graph 验证均已通过；现无证据表明该失分来自算子数值或 dispatch 错误。

## 已有经验匹配

没有找到同时匹配该题号、冻结输入/生成上限、模型修订及 PPU-07 目标图模式的已验证条目；不沿用 PPU-13 的历史 GPQA 结果。

## 诊断与假设

- 已验证：第九道固定题涉及分子 C3h 对称性，目标为 C；模型在回答中反复比较选项，最终在 30,000 token 上限返回并被 strict filter 提取为 D。
- 假设：超长生成和不稳定结论是模型在该采样设置下的行为；延长生成上限可能改变这题的输出，但是否能修正答案尚未验证。
- 排除：本次不是缺失样本、请求超时、服务不可用或错误数据集。不能仅凭此样本证明算子实现正确，也不能把其失分归咎于算子。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 证据与结果 | 结论 |
|---|---|---|---|---|---|
| 1 | 固定十题基线 | 无 | `max_gen_toks=30000`、10 并发 | `04-runs/gpqa-sanity-first10-latest-20260924/`；10/10 完整，strict 9/10 | sanity 未通过 |
| 2 | 全量评测生成上限 | 30,000 | 50,000；其余冻结配置保持 | 用户明确要求；30,000-token 全量尝试仅启动后被精确终止，退出码 143，原始目录 `04-runs/gpqa-diamond-c64-latest-20260924/` 保留；50K 全量 strict 178/198，但 runner 校验失败 | 全量诊断，不替代十题复验或正式验收；见 [003](003-gpqa-runner-config-conflict.md) |

## 根因与处理

当前仅确认“输出达到 30,000-token 上限且答案错误”的直接事实；为什么模型在该题反复推理并选 D 尚未证实。未改变模型源码、题目、判分器或过滤规则。用户在获悉 9/10 后明确授权仍运行 198 题、64 并发诊断；随后又要求把 `max_gen_toks` 提高到 50,000。全量评分的**运行前冻结**阈值为 `exact_match,strict-match >= 0.8`；用户随后指定 0.88，已观测的 0.89899 也高于此值，但不得追溯修改原生标准。framework 前置阶段不完整，sanity 未全对，且原生回执失败，因此本轮只记诊断分数，不标记正式精度验收通过。

## 限制与下一步

- 50,000-token 全量 run 已完成，198 个唯一题目、零 timeout/空响应/样本错误，strict 178/198；但 `acceptance-result.json` 为 `failed`，详见 [诊断报告](../acceptance/gpqa-diamond-gen50k-diagnostic-20260924.md)。
- 若要重新判定 sanity，必须冻结新的独立十题配置和 run ID，按同一固定 `doc_id=0..9` 完整重跑；不能用全量中的重叠样本或改动后的单题结果代替。
- 本问题目前属于模型输出/评测诊断，不构成 Plugin 或 FlagGems-vllm 产品代码变更依据；其他平台未验证。知识库处理状态：`local-only`。
