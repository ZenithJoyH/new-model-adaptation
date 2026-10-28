# 004：GPQA Diamond 严格匹配未达冻结门槛

## 元数据

- 状态：`hypothesis`；首次及最后验证时间：2026-09-29。
- 模型：MiniCPM-V-4.7-1B；平台与 Host：T-Head PPU，`PPU-13`；容器：`minicpmV4.7-1B`，评测容器 `flageval_llmeval-jinghao`。
- Plugin 源码基线 `3a27a6fb2d514cdf55c00481bf813225dac63319` 加本任务差异，FlagGems `80d0000d93dad55320df06687eb088a5b6dad07d`，vLLM 源码 `ee0da84`（完整身份见环境记录）。
- 模式与负载：PPU2，`decode-full` graph，前缀缓存开启；GPQA Diamond 198 题，客户端并发 32，`max_gen_toks=2048`，每题超时 600 秒，无 API/评测重试。

## 问题现象

正式配置 `03-acceptance/accuracy-v1/gpqa-diamond-full-v1.json` SHA-256 `73280a2228b065becf536aaad56178ebe77bf8df50006614d1fd2daca724eab2` 冻结 `exact_match,strict-match >= 0.25`。198/198 请求结束，原生 runner 退出 1；`exact_match,strict-match=39/198=0.19696969696969696`，故原生报告 `status=failed`。`flexible-extract=50/198=0.25252525252525254` 是诊断值，不能替代严格指标。原生回执 `04-runs/minicpm-v-4.7-1b-ppu/gpqa-diamond-full-v1-20260929/acceptance-result.json` SHA-256 `f660aec6985753e211e766ccdbf254dca4b358bcb77178cc3fa4de6026423d6a`；样本在其 `gpqa_diamond_generative_cot/attempt-1/`，保留原始文件及报告中的哈希。

## 已有经验匹配

已检索项目 `docs/troubleshooting/` 和现有模型问题记录，没有与 GPQA 严格提取、长输出截断和当前 PPU 图模式同时匹配的经验证条目。分布式 `sample_tokens` 超时条目的首故障签名不同，不复用其超时参数缓解。

## 诊断与假设

- 已验证：样本文件有 198 个题号、每题严格和灵活两条过滤结果。严格过滤有 83 个 `[invalid]`，其中 21 题灵活提取正确。严格正确但灵活错误另有 15 题，因此两指标不能互相替换。
- 已验证：60 题 completion token 数至少 1900，严格 `[invalid]` 中 48 题达到该范围；10 题终态 timeout 保留在 198 题分母并计零。83 个严格无效输出中，25 个仍能匹配到 `The best answer is <字母>`，其中 11 个字母与标准答案一致，但句尾或大小写格式未满足原生严格正则。样本中也有长推理在 2048 token 附近被截断。
- 待验证假设：提示词要求逐步推理且只要求结尾模板，模型输出格式不稳定和较长生成共同降低严格匹配；精确贡献需在只改一个变量的对照后确认。不能把 `flexible-extract` 的过线解释为严格指标通过。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 结果 | 结论 |
|---|---|---|---|---|---|
| 1 | 冻结基线 | 无 | 原生 GPQA CoT 模板、2048 token、600 秒 | 严格 0.197，10 timeout | 未通过，保留全部证据 |
| 2 | 仅提示词尾段 | 选取原始题号 0–63，原提示词严格答对 8/64、解析无效 31/64 | 保持服务、温度 0、并发 32、2048 token 和严格正则，仅改为简短思考并强制末行带句号 | 13/64、无效 25/64、请求错误 0；25 个无效输出全部因达到 2048 token 上限而结束 | 格式要求消除了短输出解析无效，但长生成仍截断；诊断不能作为全量验收 |
| 3 | 仅提示词尾段 | 同一 0–63 题，原提示词严格答对 8/64、解析无效 31/64 | 要求只输出带句号的一句答案，其他设置同轮 1 | 11/64、无效 26/64、请求错误 0 | 单纯更强的文字指令未解决默认思考模式的长输出 |
| 4 | 仅请求级思考开关 | 同一 0–63 题、原始题目提示词和其他设置同轮 1 | `chat_template_kwargs.enable_thinking=false` | 严格 11/64、解析无效 16/64、请求错误 0 | 原生模板开关减少格式无效，但准确数仍未证明可过正式门槛 |

第 2 轮脚本为 `02-issues/gpqa-prompt-diagnostic-v2.py` SHA-256 `c81a78d8bc4e72b8bf7c35d7e542e179da9bb7afe98b95cc52daacb7c57f785e`，结果 `04-runs/gpqa-prompt-diagnostic-v2-20260929/result.json` SHA-256 `826154a5bad409be922f24bb7ea1a195fdeac83db7783df1d3c9f793a9a91e0f`。第 2 轮只用于诊断，且样本为确定的前 64 题，不能外推正式全量门槛。

第 3 轮脚本 `02-issues/gpqa-prompt-diagnostic-v3.py` SHA-256 `0ef59cb76d91a4544e383f833014bc11aa3d8f603a23b614c7ea7aad3a7ac356`，结果 `04-runs/gpqa-prompt-diagnostic-v3-20260929/result.json` SHA-256 `ab7fdd7b458e608551f3c26eb2031e62c5e305101e381ab4c13ffaba78ab63fb`。只读检查权重 `tokenizer_config.json` 的 chat template 末段发现：默认生成会插入 `<think>`，请求级 `enable_thinking=false` 会插入空 `<think></think>`；现有 vLLM OpenAI Chat 协议和 FlagEval 客户端都支持 `chat_template_kwargs`。此为可检验的请求配置变量，不能由提示词诊断直接推断得分。

第 4 轮脚本 `02-issues/gpqa-thinking-off-diagnostic-v1.py` SHA-256 `3066815ce436984a7290d5d85411ce63320e0dd547f6b62404e527bd1cfcfa2e`，结果 `04-runs/gpqa-thinking-off-diagnostic-v1-20260929/result.json` SHA-256 `3ebbd90d2f8e34f4bdf814649548f6da0f8202ba85a74fe14a41a3d455c66505`；原始提示词和严格正则未变，只有请求级思考开关改变。

## 根因与处理

目前只能确认严格输出解析失败、部分长输出和终态超时存在；这些对最终分数的独立因果贡献未完成对照。不得更改已有报告、降低冻结门槛、丢弃 timeout 样本或把后处理指标冒充正式得分。后续若按用户选择开展新配置，应在 `03-acceptance/` 中单独冻结，先做受控小样本对照，再按框架前置规则重跑正式全量；现有失败运行保持不可变。无需修改 Plugin/vLLM/FlagGems 产品源码，也未停止当前服务或容器。

## 验证与下一步

用户要求暂不继续精度测试；提示词与请求级思考开关的组合诊断仅在本地暂存，未向远端发布或启动。四个已启动的正式/诊断 controller 均有终态退出码，评测容器无活跃评测进程；服务 `/health=200`、`/metrics` 的 running/waiting 均为 0，正常前缀缓存服务继续运行。正式 accuracy 未通过，performance/evidence/summary 不得标记通过。将来若恢复重测，须先核对服务身份、数据集、完整样本、实际输出格式及框架上下文失效规则。此问题当前仅针对本模型本配置，知识库状态 `needs-validation`；设计审查不提出通用产品改动。
