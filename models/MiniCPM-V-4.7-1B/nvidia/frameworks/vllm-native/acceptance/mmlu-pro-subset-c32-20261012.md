# 2026-10-12：范围纠正后的 MMLU-Pro 每科前 50 题评测

## 结果与范围

用户明确纠正范围为全部 14 科、每科前 50 题，共 700 题，仍使用 32 并发。
原全量任务 mmlu-pro-nv-full-20261012-r1 已停止，停止原因、准确对象与健康检查保留在
原结果根 scope-correction.json / scope-correction-verification.json；旧结果和冻结配置未删除。
原任务停止记录中的 exit=137 是按用户范围纠正停止辅助容器的结果，不作为模型计算失败。

新独立运行 ID 为 **mmlu-pro-nv-l50-20261012-r1**；启动于 2026-10-12 **18:13:28**，
完成并自动核验于 **18:21:13**（Asia/Shanghai）。700 个生成请求全部 HTTP 200、
finish_reason=stop，超时与请求错误为 0。实际最大请求重叠 32。

| 评分口径 | 正确数 | 准确率 | 无法提取 |
| --- | ---: | ---: | ---: |
| 当前 FlagEval custom-extract | 336/700 | 48.00% | 3 |
| 原始严格 original-extract | 292/700 | 41.71% | 80 |
| 最终答案 final-answer-extract v2 | 338/700 | 48.29% | 4 |

三套规则对同一批输出评分，不额外生成。无法提取的样本保留并计为错误。
当前模板 custom-extract 为整段文本首次匹配；original-extract 是旧大小写敏感 answer is 规则。
最终答案 v2 先剥离思考区段，明确答案冲突判无效，支持末尾独立字母；末行 X. 选项文字
仅在字母与选项全文对应时接受。其代码 SHA 与此前全量准备时一致，未改写共享模板。

| 学科 | 题数 | 当前规则正确数 | 最终答案正确数 |
| --- | ---: | ---: | ---: |
| biology | 50 | 30 | 30 |
| business | 50 | 30 | 30 |
| chemistry | 50 | 32 | 33 |
| computer_science | 50 | 27 | 27 |
| economics | 50 | 27 | 27 |
| engineering | 50 | 23 | 23 |
| health | 50 | 14 | 14 |
| history | 50 | 12 | 12 |
| law | 50 | 10 | 10 |
| math | 50 | 39 | 39 |
| other | 50 | 19 | 19 |
| philosophy | 50 | 18 | 18 |
| physics | 50 | 34 | 35 |
| psychology | 50 | 21 | 21 |

本轮是限定样本测量，formal_acceptance=false，没有冻结正式准确率阈值，
不更新 v2 正式验收状态或宣称模型适配完成。此前发现的基准标签疑点仍保持原标签。

## 数据、参数与服务身份

- Host / profile：H100-149 / vllm-native，control.mode=agent。
- 当前服务：MinicpmV4.7-1B-native、8000、模型 ID MiniCPM-V-4.7-1B-native，
  加载路径 /data/models/MiniCPM-V-4.7-1B。
- 原服务容器 ID 为 66a0c79a982769313637ac15000e059cd280443cd7a22dea49f37b763a2c898e。
  API PID 28633、start ticks 302123928，cmdline SHA-256
  adc7c13f1192980ba3481f653cc3f5e216b8f8d9aca311b4d87a51de024a1068。
  开始前与结束后绑定同一进程；模型配置与 tokenizer 配置在前后核对一致。
  本轮没有修改或重启模型服务，其正常前缀缓存和 FULL_AND_PIECEWISE 配置保持原样。
- limit=50；expected_samples 对 14 个任务分别为 50。题目按各科原任务顺序取前 50 个，
  所选文档 SHA-256 与原缓存读取的已冻结前 50 题清单逐科相同；共 700 个唯一 question_id。
- 原缓存修订目录 54611cde22c74cca43dd78732198de6abe971398，完整 test 12032、validation 70；
  validation 仅作为原 5-shot first_n 来源。使用已验证的只读 Arrow 内存加载扩展，
  原数据未迁移或改写。题目 ID、选项顺序、标准答案与各科文档哈希在 task-manifest.json。
- 生成参数 temperature=1.0、top_p=0.95、top_k=20，API seed=1234；并发 32；
  API/evaluation retries 均为 0；每题 max_completion_tokens=262144-prompt_tokens。
  700 条请求逐条核验参数、模型 ID、tokenize 与 usage 的输入计数、总 token 预算。
- 输入 930–2531 tokens，实际输出 97–11576 tokens，全部正常停止，无长度截断。
  budget_capped_requests=700 表示每题均从总上下文扣除了输入，不表示模型回复被截断。
- 独立评测容器 minicpmv47-1b-nv-mmlu-l50-20261012-r1，ID
  5b4d06a28f48f02aa9ce819c194b0ebbd72d141f86f618691f5d1b76fc9a9f93。
  镜像 sha256:d6faaf5e502450346771e0b5387db22254b2cce6dff0a35a26ebce0bbf29a096。
- Host、模型容器与评测容器工作根均为 /public/flagos/jinghao/MiniCPMV4.7-1B/native，
  映射设备号:inode 为 45:242118752009；本轮新响应缓存没有复用原全量响应。

## 核验与收尾

采用当前仓库 llmrun.py、acceptance_contract.py、score_progress.py，先 preflight-only
退出 0，再以同一冻结配置后台测量。原生执行与 supervisor 结束核验退出码均为 0。
逐科核验 50 个文档、与清单 ID 一致；三套 filter 的输入、原始回复与目标逐题一致；
每科结果指标与逐题正确数一致，共 2100 行。事后重新核对全部 28 项原生结果/样本文件 SHA，
并确认冻结配置及工具哈希未变化。

启动状态检查后来执行时，本轮已 completed，因其只接受 running 而拒绝执行，未生成
launch-verification.json；保留这次检查失败。随后读取真实 completed 回执及结果，按完成状态
核对完整产物，不重复启动任务，也不修改旧哈希来绕过该条件。

supervisor 已核对对象后停止本轮辅助评测容器与只读数据服务，完整日志和样本保留远端。
模型容器仍运行，收尾 /health=200，事后读取时健康检查亦为 200。
准备/启动 playbook 语法及目标执行通过；./scripts/syntax-check --offline 退出 0。

## 精确证据

远端控制目录：
/public/flagos/jinghao/MiniCPMV4.7-1B/native/03-acceptance/mmlu-pro-nv-l50-20261012-r1/。
远端结果目录：
/public/flagos/jinghao/MiniCPMV4.7-1B/native/04-runs/mmlu-pro-nv-l50-20261012-r1/。
缓存和临时文件位于 06-cache/、05-tmp/ 下同名目录。全部结果和样本只保留远端。

Skill bundle SHA-256：355bdf2946456710e0dbaaa9b331062f86be2ec4e5740f7be91ac57a6daa167d。
下面前四项位于控制目录，其余位于结果目录。

| 文件 | SHA-256 |
| --- | --- |
| config.json | 92e773f27dcded04308b8a3c6e8c21e26509d0029192115dd2924357f512b5e1 |
| prepared.json | 51accbeac230322f0783beb1873e538acb4136f81752e401cf2bbd60345d616c |
| task-manifest.json | 918265c69b8634ee21b78d7f4c0273f5aa0773a9be88807bde82b55d574101eb |
| final_filter_utils.py | 9bab4ec30bb00866e1e755345824ecd2035cfb7ddb4857beede931be66355045 |
| measurement-summary.json | 53b1e3bd531466e7b13e521b0c9dbd2dcc37a6ff3a03267f592511e23bd66295 |
| api-requests.jsonl | 4af96040bb75c9a92f5a39d3a306eea8ff13071b4b9169f48e78fac9b77ad98e |
| exit-status.json | 2bfd2f42fd5f4aee3fa18dcd4f49c59b021e71ac3be7238b2de1ea3ae5dd18e2 |
| cleanup.json | d192cbf280671ec6ac1abdd462336c204d86bb37d2680078fddd8e029b57fa95 |

每科 results_*.json / samples_*.jsonl 的准确路径与 SHA 共 28 项在 measurement-summary.json；
各科目录为 results/MiniCPM-V-4.7-1B-native-mmlu-pro/mmlu-pro-nv-l50-20261012-r1/
mmlu_pro_nv_l50_<subject>/attempt-1/MiniCPM-V-4.7-1B-native/。
