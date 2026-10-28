# DSpark：MATH500 与 MMLU-Pro 每科 50 题

## 范围与冻结配置

2026-10-08，用户要求沿用模型 `generation_config.json` 作为评测端配置，运行
MATH500 和每科 50 题的 MMLU；随后明确选择 **MMLU-Pro 14 科**，并确认
缺省采样采用贪心、评测端最大新增 token 为 **32768**。
本轮为指定数据集测量，`formal_acceptance=false`，不生成正式精度通过结论或更改
`framework.yml` 的历史状态。两项已完成，最终分数与完整性见下文。

- Host：`H100-149`；已核实 host root
  `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos` 与两容器的 `/work` 映射，
  设备号/inode 均为 `45:232972481026`。
- 服务容器 `MiniCPMV4.7-1B-DSpark-gpu6`，API PID 12778，GPU6/BF16/TP1，
  vLLM 0.28.0 + Plugin `0.3.0rc2+gaa4228e`（`support-minicpmV4.7` 基线与当时
  DSpark 适配差异）/FlagGems；FULL_AND_PIECEWISE，前缀缓存开启，
  服务端 max_model_len=50000。沿用上一轮独立脚本，不修改或重启服务。
- 评测容器 `minicpmv47-dspark-eval-20261008`，ID
  `5f055e30a4e7563a62429356dbc4ce107f6e1f3cd17a0a907b87b0c0ce13a7a0`，
  镜像 `harbor.baai.ac.cn/flageval/flageval-llmeval:v1`；host network，不分配 GPU。
- 评测入口为本仓库 `test/Accuracy_test/llmrun.py` 的通用诊断模式，同时部署
  `acceptance_contract.py`、`score_progress.py`，无评测库修改或临时评分替换。
- 主模型及 draft 权重路径与上一轮相同；服务身份、安装文件哈希核对保存在远端
  `03-acceptance/dspark-eval-20261008/service-identity.json`。

2026-10-09 用户要求 vLLM 0.28 改用 Plugin `0.4.0-dev`，迁移另见
[008](../adaptation/008-dspark-plugin04.md)。本文原生结果和后续 90 题人工复核
均基于旧 Plugin 环境的响应，不能作为新分支代码的精度结果。

`generation_config.json` 仅包含 EOS `[248044,248046]`、BOS `248045`、
`use_cache=true`、Transformers 版本信息，没有 temperature/top-p/top-k/输出长度。
原文件 SHA-256：`4dc190baaab3bc4bccb796ee73deb2c3dd776cd4feae3587b29bc22083e03415`。
经用户确认，客户端固定 temperature=0、do_sample=false、top_p=1、top_k=-1、
max_gen_toks=32768，seed=0 用于复现。显式 stop_token_ids 使用文件中的两个 EOS；
until/stop 为空，覆盖任务默认温度、28000 token 上限及不属于该模型的停止字符串。
BOS 由模型 tokenizer/chat template 处理，use_cache 由服务 KV cache 执行，
不将不受 OpenAI 请求支持的 Transformers 元数据传给接口。
原生 OpenAI adapter 将长度映射为 `max_completion_tokens`，已通过 payload 契约核对。

## 数据与评分

- MATH500：500/500，原生 `math_500` 提示和 boxed-answer 等价判定，0-shot。
- MMLU-Pro：14 科各取原生 process_docs 后测试集顺序前 50 题，共 700 题；
  原始 test 12032、validation 70，保留原生 5-shot/first_n 提示及
  `exact_match,custom-extract`，正则 `answer is \(?([ABCDEFGHIJ])\)?` + take_first。
  不使用此前 PPU 诊断中的派生提取规则。
- 数据源来自已有 FlagEval 容器的已缓存官方 MMLU-Pro Arrow 与 MATH500 JSONL，
  只读复制到本轮 `06-cache/dspark-eval-20261008/source/`，不修改旧容器或数据。
  自定义任务仅覆盖数据定位与本轮生成参数，原生提示/评分实现作为引用快照保存。
- 样本清单 `03-acceptance/dspark-eval-20261008/request-manifest.json`，SHA-256
  `6a4cff5df6f98a8a8b529a0ae485c575df20e1b418f09ee72d2bf78878c18094`，
  冻结每题、doc_id、题目哈希、few-shot 数据哈希及生成参数。
- 两份原生 preflight 已通过；实际请求并发 4，API/任务重试均为 0，单请求超时
  3600 秒，最终超时保留并计错。响应缓存使用容器内批准路径的独立 4 GiB tmpfs，
  避免共享文件系统 SQLite 锁问题；本轮新 nonce，首 task 0 条历史缓存命中。

## 远端运行证据

以下相对路径均以已批准 host root 为根；容器路径使用 `/work` 前缀。

- 冻结配置、任务、原生 runner、服务身份与生成文件：`03-acceptance/dspark-eval-20261008/`。
- `math500.json` SHA-256：`25ebc2ae70e21caeb94cbccf627e3dbba52a893ecd526ee06c21b6002efa00c5`。
- `mmlu-pro.json` SHA-256：`33c031e1c6e1ba63f8c7e8dcbf2dc9d87b2f4a41bbfaa91f1444941ab743e715`。
- 完整 bundle 清单 `bundle-hashes.json`，SHA-256
  `70bc20f1a3ae7daa9c39a7efc2518d62955e4f0ef1f1cf9403b7b1db70301446`。
- 控制与日志：`04-runs/dspark-eval-20261008/`，controller PID 536；
  `status.json`、两份 preflight、runner 日志、progress/observations、各 worker PID 可恢复核对。
- 原生结果：`04-runs/dspark-eval-20261008/results/MiniCPM-V-4.7-1B-DSpark/`，
  分 `math500/`、`mmlu-pro/` 两轮。最终必须逐 task 核对样本、唯一题号、超时、无效提取、
  完成数及结果文件，不能用早期完成样本的阶段分数替代最终分数。

## 首轮缓存失败与重跑

首轮在 2026-10-08 14:39 UTC 左右出现 SQLite `attempt to write a readonly database`。
现场核对发现 Docker 配置仍声明 tmpfs，但所有容器进程的 mountinfo 中该挂载已消失；
lm-eval 打开的数据库 FD 指向脱离挂载的路径。挂载消失的触发原因尚未确定，
不能归因于模型服务。服务健康检查为 HTTP 200，进程及容器未重启。
停止本轮 controller、runner 和 observer 后，lm-eval 进程已退出，三个父进程为僵尸状态。
失败现场为旧运行目录中的 `cache-failure.json`，原始 DB 保全为
`failed-cache-raw.sqlite`（58 条），无最终评分，不计入后续重跑。

重跑使用 `dspark-eval-20261008-r2` 同编号目录，2026-10-08 14:46:52 UTC 启动。
独立评测容器为 `minicpmv47-dspark-eval-20261008-r2b`，ID
`1be7bebf878fa918f49ec94c9045edbc59b9d7a01cfe24982a00e8988799155d`。
缓存卷 `minicpmv47-dspark-eval-20261008-r2-responses` 在容器内映射到
`/work/06-cache/dspark-eval-20261008-r2/responses`，mountinfo 核实为本地 XFS，
SQLite 写入/重新打开读取探测通过；该缓存由 Docker 管理，并非 host bind 目录中的文件。
数据、生成参数、原生提示和评分不变，样本清单 SHA 与首轮相同；缓存从零开始。
服务 boot ID、PID/start ticks、原始 cmdline SHA 及 Plugin/FlagGems 文件 SHA 全部匹配。

- 新 `math500.json` SHA-256：`6207f6b9c9937eafb4e9ce36fa47387e3d7a284202ed35b38b20e8e4d7dd5a25`。
- 新 `mmlu-pro.json` SHA-256：`b6b3f32baa85d5df77a80d812e513730660d12d1ef5a0ba7e53b2987501ccad7`。
- 新 bundle SHA-256：`ca23b0a13ca50912a8e2380c5aecdd6b544cfd9baf5163cd80a05c2e8a4cb768`。
- 新 controller PID 21、observer PID 23；两项 preflight 通过。
- 启动独立评测容器时曾因镜像默认 entrypoint 为 tail 导致 `...-r2` 容器退出；
  新容器 `...-r2b` 显式使用 `/bin/bash` 并验证运行。旧失败容器/记录均保留。

## 结果与完整性

MATH500 于 2026-10-08 15:35:54 UTC 完成：`exact_match,none=0.716`，
即 **358/500（71.6%）**，0-shot。500 条唯一样本、超时 0 条，
459 条 EOS/stop 正常结束，41 条 `length` 均为 32768 token。
原生 scorer 在 `</think>` 后提取 boxed 答案，允许自身的括号/全文回退；
40 条回答没有可提取的 boxed 答案，此诊断数不替代原生评分。
评分总和与汇总分数一致，strict sample validator、全部题目与冻结清单逐项比较、
API 日志回答与 samples 的多重集合匹配均通过，冻结 bundle 哈希不变。

- 汇总与哈希：`04-runs/dspark-eval-20261008-r2/math500-measurement.json`。
- 原生结果文件 SHA-256：`4d4b1f39b0e4978655b0bac9cd7246017ca1a032d4c6bb0e2705c7f5afee2668`。
- 原生 samples SHA-256：`f884cb286f26d4ee7bd603b394a32def28beb5b32b403423844a9361d31803e4`。
- SQLite 已从本地缓存卷只读 backup 到
  `04-runs/dspark-eval-20261008-r2/cache-export/math500/`，用于持久证据保存。
- 核对脚本保存在远端 `02-issues/dspark-eval-20261008-r2/summarize.py`，
  只读取冻结任务与原生结果，不替换提示/评分。

MMLU-Pro 于 2026-10-08 16:25:17 UTC（北京时间 10 月 9 日 00:25:17）完成：
原生 `exact_match,custom-extract` **280/700（40.0%）**，5-shot。
14 科各 50 题，逐科唯一题号、题目清单、API 回答与 samples、原生评分总和和
strict sample validator 均核对通过；所有样本保留，未跳过或替换失败回答。
各科样本数相同，因此 macro 与本轮 micro 汇总均为 40.0%。这是顺序前 50 题的
子集测量，不能代表完整 12032 题 MMLU-Pro 得分。

| 科目 | 正确 / 题数 | 原生得分 | 无效选项提取 | 长度截断 |
| --- | ---: | ---: | ---: | ---: |
| biology | 23 / 50 | 46% | 12 | 2 |
| business | 17 / 50 | 34% | 12 | 4 |
| chemistry | 27 / 50 | 54% | 6 | 3 |
| computer_science | 21 / 50 | 42% | 8 | 2 |
| economics | 27 / 50 | 54% | 1 | 1 |
| engineering | 21 / 50 | 42% | 5 | 5 |
| health | 16 / 50 | 32% | 2 | 0 |
| history | 7 / 50 | 14% | 17 | 0 |
| law | 8 / 50 | 16% | 9 | 1 |
| math | 38 / 50 | 76% | 4 | 0 |
| other | 16 / 50 | 32% | 6 | 0 |
| philosophy | 12 / 50 | 24% | 4 | 0 |
| physics | 29 / 50 | 58% | 3 | 2 |
| psychology | 18 / 50 | 36% | 1 | 0 |
| 合计 | 280 / 700 | 40.0% | 90 | 20 |

MMLU-Pro 超时 0 条，680 条 EOS/stop 结束，20 条 `length` 均触及 32768 token。
90 条原生 filter 未得到 A–J 合法选项，逐条确认 `exact_match=0`，已计入 700 题分母；
无效提取和长度截断可能重叠，不能相加当作额外错误题数。
以上原始运行未更换正则或事后重新定义得分；用户随后授权的补充复核见下节。

- MATH500 汇总 SHA-256：`134c8eb4d3f8afaf4a8bb338cdb43b276e798b86887a14cbe61708fce06a9a42`。
- MMLU-Pro 汇总：`04-runs/dspark-eval-20261008-r2/mmlu-pro-measurement.json`，
  SHA-256 `6536ff4acc2b62484d322fb05fd191e51e584bc18dc87dedef508b5e57ae3864`；
  包含逐科 results/samples/API 日志/cache-export 的完整路径及 SHA。
- 终态核对：`04-runs/dspark-eval-20261008-r2/final-verification.json`，
  SHA-256 `03f73106b91bea550f1ab4b353c64cf91dafbc31046d40dbd3f7899d12f51110`。
  两轮 returncode=0，冻结 bundle、4 个数据文件、全部结果产物哈希匹配；
  服务 boot ID、PID/start ticks、cmdline 与安装组件 SHA 未变，health=200。
- 模型容器与两只已运行的评测容器均保持运行，restart_count=0。
  评测完成不代表正式精度验收或完整模型适配完成。
- 本地 `./scripts/audit-workspace --json` 仍为既有 12 个 profile revision 错误与
  78 个历史布局警告；本模型当前 profile revision 待复核，没有新增本文布局告警。
  未通过改写历史 `framework.yml` 来消除此限制。

## 2026-10-09：90 条无效提取的补充人工复核

用户要求将这 90 条中实际答对的回复补计为正确。本次只分析已保存的响应，
不重新请求模型，保留其他 610 题原生评分和全部 700 题分母。
此节为事后答案格式复核统计，原生 `exact_match,custom-extract=40.0%` 保留，
不替代正式验收或完整 MMLU-Pro 得分。

先隐藏标准答案，逐条查看回复末尾；对没有明确结论的长回复，另看题目、选项、
回复开头及全文最后六处答案相关片段。接受 `Answer: C`、单独选项字母、
boxed 字母等明确最终选择；缺少 `</think>` 本身不否定明确答案。
存在反复犹豫、重复推理或未完成结论的回复不补完，不从中间候选择取。
例如复核编号 44 反复讨论 C、J 及公式缺陷，没有最终选项，保留未定。
先固定 90 条预测选项及理由、响应哈希和末尾摘录，再对照样本原有标准答案。

| 90 条复核分类 | 题数 | 计分处理 |
| --- | ---: | --- |
| 恢复出明确选项且与标准答案一致 | 39 | 补计正确 |
| 恢复出明确选项但与标准答案不符 | 34 | 保持错误 |
| 没有明确最终答案 | 17 | 保持错误 |

补充复核正确率为 **(280 + 39) / 700 = 319 / 700 = 45.5714%**，
相对原生 40.0% 增加 **5.5714 个百分点**。14 科题数相同，macro 与 micro 相同。
MATH500 的 358/500（71.6%）未作重新统计。

| 科目 | 原正确数 / 50 | 补计正确 | 复核后正确数 / 50 | 复核后正确率 |
| --- | ---: | ---: | ---: | ---: |
| biology | 23 | 10 | 33 | 66% |
| business | 17 | 7 | 24 | 48% |
| chemistry | 27 | 2 | 29 | 58% |
| computer_science | 21 | 4 | 25 | 50% |
| economics | 27 | 0 | 27 | 54% |
| engineering | 21 | 0 | 21 | 42% |
| health | 16 | 1 | 17 | 34% |
| history | 7 | 4 | 11 | 22% |
| law | 8 | 1 | 9 | 18% |
| math | 38 | 3 | 41 | 82% |
| other | 16 | 3 | 19 | 38% |
| philosophy | 12 | 3 | 15 | 30% |
| physics | 29 | 1 | 30 | 60% |
| psychology | 18 | 0 | 18 | 36% |
| 合计 | 280 / 700 | 39 | 319 / 700 | 45.5714% |

证据仍位于 H100-149 的已批准 host root，评测容器 `/work` 映射已复核。
原汇总及全部逐科 samples 的 SHA-256 在复核前、计分后均匹配，原文件未改写。

- 盲审冻结文件：`04-runs/dspark-mmlu-pro-answer-review-20261009/blinded-decisions.json`，
  SHA-256 `c1d62c7c28aa1bfa7ec589ca495868abce66535624c3e5c1890dc058b3fc212d`。
- 逐题标准答案比对及逐科汇总：
  `04-runs/dspark-mmlu-pro-answer-review-20261009/rescoring-report.json`，
  SHA-256 `0898d776d097368246c5b335ea8df348f7e86f1df7380682d1c07a4d62a51191`。
- 计分代码：`02-issues/dspark-mmlu-pro-answer-review-20261009/score_frozen_decisions.py`。
  只读取原结果及已冻结选项，核对身份/哈希后逐题比较；新报告使用独占创建，
  重复执行会拒绝覆盖已有报告。
