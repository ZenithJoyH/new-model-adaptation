# 011：GPQA Diamond 低分的评测模式与剩余精度差距

## 元数据

- 状态：`open`；首次出现及最后验证时间：2026-09-23。
- 模型：DeepSeek-V4-Flash W8A8；平台与 Host：MetaX C550 x8，`mx-59`；适配容器：`deepseek`。
- 工作根：宿主及容器均为 `/public-flash/jinghao/deepseekV4`，映射已核验。
- 服务：TP8+EP；原全量诊断为 `VLLM_COMPILE + Inductor + custom_ops=['all']`、有效 `FULL_AND_PIECEWISE`；配对诊断使用已恢复的 `mode=NONE`、有效 `FULL_DECODE_ONLY`。前缀缓存均开启。
- 源码 HEAD：vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`、Plugin `fd5c727fcdb607bc4354cd11384761bb5d5ecfba`、FlagGems `711cf839c4ee5557776c626e1f8b20cc4007fa63`、FlagGems-vllm `c0ffa628e945dc6b51af466d4f1a9b81df9ac4b8`；HEAD 不代表没有未提交的适配差异。

## 问题现象与证据

- 全量零样本 FlagEval `gpqa_diamond_generative_cot`：strict-match `125/198 = 63.13%`，flexible-extract `66/198 = 33.33%`；原始结果、配置、SHA-256 和服务信息见 [GPQA 诊断报告](../acceptance/gpqa-diamond-diagnostic-20260923.md)。这不是正式 accuracy 回执。
- 官方 [模型卡](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) 的 GPQA Diamond Pass@1 分别是 Non-Think `71.2`、Think High `87.4`、Think Max `88.1`。所询问的“至少 88”对应 Think Max，并非非思考模式。
- 官方 [技术报告](https://arxiv.org/pdf/2606.19348) 的知识/推理评测使用 temperature `1.0`，Non-Think / Think High / Think Max 分别用 `8K / 128K / 384K` 上下文；本轮 FlagEval 是 temperature `0`、最多生成 `18K`，服务 `max-model-len=50K`，模型又是 W8A8 量化版。因此原分数不能与官方 88.1 直接比较。

## 已有经验匹配

| 历史问题 | 相同点 | 差异及本次决定 |
|---|---|---|
| [009 图模式正确性](009-metax-graph-correctness.md) | 同一模型、Host、Plugin/FlagGems 适配和 compile 图路径 | 009 的固定短请求证明修复后的图服务功能可用，不证明 GPQA 全量精度；本问题另查请求模式和计分口径。 |
| [010 SQLite 启动锁](010-flaggems-sqlite-startup-lock.md) | 发生于 GPQA 诊断后服务恢复 | 仅影响首次恢复启动，与 198 条已完成 GPQA 回复及计分无因果联系。 |

`docs/troubleshooting/` 未找到匹配 GPQA/DeepSeek V4 思考模式的已验证条目；不凭关键词复用其他问题结论。

## 诊断与受控尝试

1. 核对 FlagEval 样本与评分：198 个唯一题目均有回复且 target 与正确选项对齐；无空回复、请求错误或 timeout。73 个 strict 错题中，62 个成功抽到 A–D 但选错，11 个未抽到严格格式；仅 1 个回复触及 18K 生成上限。即使把 11 个无效格式全部算对，strict 也只达 `136/198 = 68.69%`。因此 strict 正则不是 63.13% 的主要原因；flexible-extract 的 33.33% 另含明显的提取口径问题。
2. 按领域审计 strict：Biology `13/19`、Chemistry `44/93`、Physics `68/86`。错误集中在 Chemistry，但没有发现领域 target 错配；这一分布不单独证明量化或编译错误。
3. FlagEval 原请求只携带 `do_sample`、`max_gen_toks`、`temperature`、`until`，没有 `reasoning_effort`；vLLM 的 `deepseek_v4` tokenizer 在缺省时设 `enable_thinking=False` / `thinking_mode=chat`。直接向当前安全服务发送无数据集内容的探针：缺省回复无 reasoning，`reasoning_effort=max` 回复有 reasoning。这证明本部署的全量任务实际测的是非思考模式，而非官方 Think Max。
4. 从同一原始 GPQA 输入按固定哈希选择 32 题，在安全服务上保持温度、token 上限、prompt 和 strict 解析不变，仅比较原 compile 结果与当前非 compile 结果：前者 `18/32`，后者 `19/32`；无请求错误、无生成上限截断，19/32 的最终选项一致。由于服务图覆盖也从 `FULL_AND_PIECEWISE` 变为 `FULL_DECODE_ONLY`，这不是纯 Inductor 单变量试验；但该固定子集没有呈现足以解释约 25 分差距的准确率塌陷。
5. 同一安全服务对 8 道固定哈希选题逐题比较缺省与 `reasoning_effort=high`，其余请求参数相同。完成 `8/8` 对：缺省 `4/8`、High `6/8`；High 的 `8/8` 响应有 reasoning，而缺省 `0/8`。逐题变化为 High 单独答对 `3` 题、缺省单独答对 `1` 题、两者均对 `3` 题、均错 `1` 题；High 单独答对的包括两道化学题。缺省单独答对的那题，High 正好触及 `18K` 生成上限，未产生可抽取的最终选项。High 累计生成 `71,278` token，缺省仅 `3,187`，历时约 `2,671` 秒；无请求错误。只输出聚合，不保存或披露受保护的 GPQA 题目/答案。本轮小样本只验证模式及预算影响，不能外推成 198 题分数。

## 根因判定

- **已验证的口径错配**：任务未启用思考模式，官方 88.1 却是 Think Max；这是当前“应有 88+”预期与 63.13% 结果不能直接比较的首要原因。
- **尚未定位的剩余真实差距**：当前 63.13% 仍低于官方 Non-Think 71.2。temperature、prompt/评分实现、W8A8 量化、服务版本与图/算子栈均不同，不能在缺少同口径对照时把这约 8 分差距判为 FlagGems、Plugin 或 MetaX Inductor 缺陷。格式问题的最大影响已作上界计算，target 错配已排除。
- 本轮没有修改 Plugin、FlagGems、FlagGems-vllm 或 vLLM 产品代码；没有停止、重启或删除适配容器，也没有更改当前服务。诊断结束后服务 `/health` 为 HTTP `200`，仍是原 `mode=NONE`、TP8+EP、50K 配置。

## 解决方向与验证界限

- 后续 Think Max 的 61 题中止批次及阶段评分器口径漂移，另见 [012 问题记录](012-gpqa-max-partial-score-drift.md)。该新批次不能替代本记录的 198 题 Non-Think 结果，也不能直接宣称编译算子精度故障。

- 若目标是对照官方 88.1，先在正式评测配置中明确 Think Max、temperature `1.0`、prompt/答案提取协议及足够的上下文和生成预算，再核对模型权重是否与官方相同。当前 50K 服务和 18K token 任务不足以复现官方 384K Max 条件，不能只加一个参数就宣称达到官方口径。
- 在不改产品代码的前提下，先做同一量化服务的全量非思考/Think High 或 Max 配对，再与官方非量化模型的同协议结果比较，逐次只改一项；若有精度差，再做 eager/compile 与量化/非量化对照。避免把高思考带来的生成量和耗时当成服务回归。
- 正式验收仍受 profile revision 与 execution-mode/sanity 原生回执前置约束；不能把本诊断升级为通过状态。待冻结阈值、可比协议和证据后重跑正式 accuracy。
- 知识库状态：`needs-validation`；本例可沉淀为“核对 reasoning mode 与官方 benchmark 档位”的诊断顺序，不能推广当前模型的分数差距。
