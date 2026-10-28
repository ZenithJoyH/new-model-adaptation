# 006：MMLU-Pro math / other 配对结果与低分分析

## 元数据与范围

- 状态：`open`；已验证评分污染和具体答案错误，NV 适配计算回退的根因尚未证实。
- 验证日期：2026-10-12（Asia/Shanghai）。Host：`H100-149`。
- 对象：用户提供的 4 份 JSONL，每份 50 行，两个学科共 100 对同题结果。
- 工作根：`/public/flagos/jinghao/MiniCPMV4.7-1B/native`。
- 本轮仅只读分析已有结果及相关 FlagEval 提取代码，没有发出模型推理请求、重跑评测、
  改写结果、修改产品代码或停启服务；Host 为 unchanged。
- 本地控制权在开始及写入分析记录前均为 `agent`；没有改变 framework.yml 或 v2 验收状态。
- 生成这些文件时的模型权重/模板身份、引擎 revision、服务实例、seed、并发、API usage 和
  finish_reason 未随文件提供。本轮读取的是当前共享评测容器 `flageval-llmeval_lhc` 的代码，
  不据此补写当时的服务或评测环境绑定。

## 证据与一致性

四份文件的 mtime 分别为 2026-10-12 17:27:10（math）、17:27:11（other），这只是文件修改时间。
每科 FlagOS/NV 的 question_id 集合一致、各 50 个唯一值；doc、target、arguments、
doc_hash、prompt_hash、target_hash 均逐条 50/50 一致。选项顺序与格式相同。
现有 filtered_resps 与 exact_match 逐条一致；200 行均无 `[invalid]`、timeout=false，
没有 error/errors 字段报告错误。全部回复都有一次 `</think>` 和非空最终区段，没有明显空回复。
由于缺少 usage/finish_reason，本轮不正式断言已核实 API 终止原因或 token 预算。

所有行记录的生成参数相同：
`until=["</s>"], do_sample=false, temperature=1.0, top_p=0.95, top_k=20, max_gen_toks=258477`。
每条提示词为 system + user 两条消息，5-shot 内容位于 user 消息中；换行是真实换行，
没有将字面 `\n` 错当换行的损坏。100 对原始回复均不同；同一提取答案为 math 39/50、other 30/50。
相同自然语言输入与生成参数不证明两个服务实际使用相同 tokenizer、聊天模板、权重或采样状态。

| 学科 | FlagOS 原始 | NV 原始 | FlagOS 最终答案核对 | NV 最终答案核对 |
| --- | ---: | ---: | ---: | ---: |
| math | 41/50，82% | 36/50，72% | 40/50，80% | 36/50，72% |
| other | 22/50，44% | 16/50，32% | 20/50，40% | 16/50，32% |
| 合计（限定 100 题） | 63/100，63% | 52/100，52% | 60/100，60% | 52/100，52% |

原始配对：math 两边都对 36、只有 FlagOS 对 5、只有 NV 对 0、两边都错 9；
other 两边都对 14、只有 FlagOS 对 8、只有 NV 对 2、两边都错 26。
最终答案核对后：math 为 36/4/0/10，other 为 12/8/4/26，顺序同上。
因此原始 11 题差距中有 3 题来自 FlagOS 的首次匹配计分污染；按最终答案仍有净 8 题差距。
这些是当前样本的现象，不是 NV 引擎根因证明。

## 1. 当前过滤规则会计入思考答案

当前共享 FlagEval 模板 `/app/lm_eval/tasks/mmlu_pro/_default_template_yaml` 的生效规则为：

```yaml
regex_pattern: '(?m)(?:(?:the\s+)?[Aa]nswer\s*(?:is\s*)?\(?|[Aa]nswer\s*[:：]\s*\(?|\\boxed\{\s*)([A-J])(?=$|[\s)\}.,;!:])|(?:\n\n|\A)([A-J])\.\s+\S[^\n]*\Z'
```

`group_select: -1` 处于注释状态。当前 `/app/lm_eval/filters/extraction.py` 的 RegexFilter
默认 group_select=0，先 findall 再取首个匹配，tuple 中取首个非空 capture。
后面的 take_first 选择第一条重复生成回复，不将 regex 改为取最后一个答案。
用上述原始规则重算四个文件，filtered_resps 各为 50/50 一致，共 200/200。
模板 SHA-256：`38a8d4028c76bf62d52ac6c5c7aa6988aa1e56b72a689b0a62ae5dcbc50f2f1f`。

| 文件 / doc_id / question_id | 标准答案 | 原记录 | 最终明确答案 | 影响 |
| --- | --- | --- | --- | --- |
| math FlagOS / 40 / 7727 | F | F | J | 原计对，最终字母不匹配标签 |
| other FlagOS / 36 / 5096 | B | B | F | 原计对，最终答错 |
| other FlagOS / 49 / 5109 | H | H | D | 原计对，最终答错 |
| other NV / 39 / 5099 | B | G | H | 两个答案都错，正确数不变 |

最终答案核对先使用之前提供的 `minicpm_mmlu_final_choice_v1` 思考剥离、标记提取、
冲突判无效逻辑；无标记时，额外接受末尾 `X. 选项全文`，且要求字母合法、全文与该题选项
对应文字一致，不从一般解释中猜字母。全部 200 行都得到明确答案，未删除任何题。
同批回复使用当前 regex 的最后匹配，或先剥离 `</think>` 再按当前 regex 提取，
也分别得到上表的正确数。

之前给出的自定义 filter 单独重算为：math FlagOS 40/50、NV 35/50，other 20/50、16/50。
它会漏提 NV math doc_id=41 / question_id=7728 的末行 `H. 64.18 m`，
该题计算正确且原规则已计对；这是旧自定义 filter 的边界局限，不是本批 NV 低分的原因。
加入与真实选项文本对应的末行支持后，恢复为 NV math 36/50。
本轮仅诊断复算，没有修改任务 YAML、安装过滤器或替换原始成绩。

## 2. 可核验的 NV 推理与选项映射错误

| 学科 / doc_id / question_id | 正确计算或题目条件 | NV 回复中的错误 | FlagOS / NV / 标准 |
| --- | --- | --- | --- |
| math / 9 / 7696 | ℤ 的基为 {1}、{-1}，而 ℤ² 存在无穷多基，例如 {(1,n),(0,1)} | 声称 rank 1 有无穷基、rank n 只有 n! 个基 | G / F / G |
| math / 17 / 7704 | 条件概率 0.54/(1−0.20)=0.675 | 把互斥的两类学生重复相减，得到 34/60≈0.5667，选 0.560 | F / I / F |
| math / 18 / 7705 | 按题目顺序为 0.5、0.44、0.3 | 公式数值算对，最终将前两项调换，匹配成 C | D / C / D |
| math / 44 / 7731 | onto 表示满射，rank=4，nullity=6−4=2 | 忽略满射，将 rank 当未知，并随意选可取值 4 | E / D / E |
| other / 33 / 5093 | 理想绿色滤光片阻断入射红光，纸张缺少有效照明 | 先说红光被挡，又说剩下绿光且蓝纸仍显蓝，推理自相矛盾 | C / E / C |
| other / 39 / 5099 | 按题目所用时区偏移：12:00−6h=06:00 AM | 多次把减 6 小时算成 PM，并在 G/H 间改答 | B / G（最终 H） / B |

这些样本存在算术、概念、条件遗漏、回答顺序/选项映射问题；不属于答案正确但无法被 regex
识别的损失。其中 math 40 的差异另受多正确选项影响，不能把它作为确定的 NV 数学错误。
不少回复有反复修正和“Wait”式循环，但未做输出长度变量的受控测试，不能证明长输出预算
是错误原因；也没有依据缩短预算后宣称精度必然提高。

## 3. 扣分的学科分布

| NV math 来源 | 题数 | 正确数 |
| --- | ---: | ---: |
| abstract_algebra | 10 | 4 |
| high_school_statistics | 10 | 5 |
| elementary_mathematics | 23 | 21 |
| high_school_mathematics | 4 | 4 |
| college_mathematics | 3 | 2 |

| NV other 来源 | 题数 | 正确数 |
| --- | ---: | ---: |
| global_facts | 7 | 0 |
| sociology | 4 | 0 |
| security_studies | 8 | 2 |
| high_school_government_and_politics | 5 | 1 |
| miscellaneous | 18 | 8 |
| public_relations | 5 | 3 |
| human_sexuality | 2 | 1 |
| us_foreign_policy | 1 | 1 |

other 的 global_facts、sociology、security_studies 三组贡献 17/34 个错误，
呈现事实记忆和专业概念薄弱：例如把 new racism 按词面理解为 cyberspace 中的新现象，
或直接猜历史调查百分比。FlagOS 同三组也只有 4/19 正确，说明它们对两边都有难度。
此 50 题按文件顺序集中在特定来源，不代表全量 MMLU-Pro 的学科构成或总体准确率。

## 4. 数据质量疑点

- math doc_id=0 / question_id=7687：标签 H 为 False, True。但任意环同态 f 的核为零
  等价于单射：f(a)=f(b) ⇒ f(a−b)=0 ⇒ a=b；第一条声明应为 True。
  按通常 ℚ/ℝ 含义，ℚ 也不是 ℝ 的理想，例如 1∈ℚ 而 √2×1∉ℚ，应选 A=True, False。
  因而标签 H 至少与第一条定理矛盾。FlagOS 选 A、NV 选 E，原标签把两边都计错。
- math doc_id=40 / question_id=7727：F“所有八边形都是多边形”和 J“所有正方形都是四边形”
  都是成立的几何陈述，但标签只认 F。两边最终都选 J；原提取规则却从 FlagOS 思考里提到 F，
  形成原始配对中 FlagOS-only 的一题。

保留原标签与原指标；上述疑点需对照数据版本/原题另行核验，不据模型答案直接改写基准。

## 5. 尚未证实的适配根因与下一步

- 参数字段相同，但 temperature=1.0 不是贪心对照。当前共享 FlagEval 的 OpenAI backend
  `/app/lm_eval/models/openai_completions.py` 会 pop 掉 do_sample，并单独发送 temperature；
  因而不能用 do_sample=false 认定实际是 temperature=0。缺少本轮完整请求轨迹与种子。
- 原始输入字符串相同，实际聊天模板、token IDs、权重、dtype、采样实现和服务身份尚未绑定；
  两个引擎在随机生成下得到不同答案不足以直接证实某个 vLLM 算子/图模式数值错误。
- 005 biology 旧问题是严格格式提取遗漏；本次 200 行均可提取，已重新核对，不沿用旧根因。
- 先冻结生成两边 JSONL 的实际配置、模型/tokenizer/模板哈希、请求参数、种子与服务实例；
  评分取最终区段，支持末行明确选项，并将数据标签疑点独立记录。
- 若继续定位适配代码，先用相同权重、token IDs、temperature=0 和固定 seed 对上述具体
  错题做小规模受控回放；比较 NV、FlagOS 与参考实现首个分歧 token 的 logits。
  再按证据定位模板/加载差异、数值实现或模型本身的推理错误，不先修改 vLLM 或换图模式。

本轮没有执行这些新的对照、做修复、验证 eager/graph 数值一致性或建立正式精度回执。
知识库状态：`local-only`，不将尚未证实的引擎根因推广为通用经验。

## 原始文件 SHA-256

以下文件均直接位于上述已核验工作根，开始和结束读取时哈希一致：

| 文件 | SHA-256 |
| --- | --- |
| `mmlu_pro_math_flagos.jsonl` | `5bfbe51cd4301b3b5d0b900ed15509c276eaffafc73ba68844cfbd56754678dd` |
| `mmlu_pro_math_nv.jsonl` | `4b571cf8dc37d9b0475c8273713fa028a0a8e6241ea6ec1a97a3d3712960d5d6` |
| `mmlu_pro_other_flagos.jsonl` | `6cc8b41115a67f8281e7e54959e2ad5dbe2dd6b844d26951cc5b413ae90d5dff` |
| `mmlu_pro_other_nv.jsonl` | `104c8aa56300d9cd3204ec04142f86ea750269714ac99a65506e5696431e0508` |
