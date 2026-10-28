# 2026-10-12：当前 NV 服务全量 MMLU-Pro 后台评测

## 用户范围纠正：已停止

用户明确纠正为“每个科目前 50 题”。已于 2026-10-12 18:10:12（Asia/Shanghai）
核验原全量评测停止；停止前记录了 1660 个完成请求。仅停止本任务独立评测容器与只读数据服务，
模型容器仍运行、8000 /health=200，原始文件均保留。

原 supervisor-state 记为 failed、runner exit=137，这是本次按用户指令停止辅助容器的结果，
不作为模型精度失败诊断。明确原因及精确操作记录在原结果根的 scope-correction.json 和
scope-correction-verification.json。新的正确范围使用独立运行 ID
mmlu-pro-nv-l50-20261012-r1，不修改原冻结配置或重用原结果冒充新评测。

## 停止前的启动核验快照

按用户“当前服务还在，挂一轮全量 MMLU-Pro”的请求，已启动后台运行
`mmlu-pro-nv-full-20261012-r1`。启动时间为 **2026-10-12 17:53:01**（Asia/Shanghai）。
启动后核验时间 **18:01:39**，已完成 **1505/12032** 个实际生成请求，均 HTTP 200、
finish_reason=stop，无请求错误；配置并发 32，请求时间区间观察到最大重叠 32。
这是一次进度快照，尚未取得全量最终分数或通过结论。

本轮用 `adaptation/accuracy` 的 `formal-full` 原生执行方法跑全部 test 样本，
`formal_acceptance=false`。用户没有指定正式验收准确率阈值；不更新框架阶段状态、
旧部署绑定、架构哈希或 v2 正式 accuracy 回执。仅测量现有服务，未修改或重启模型服务。

## 范围与冻结配置

- Host：`H100-149`；profile：`vllm-native`，固定 profile version 3；control.mode=agent。
- 模型 ID：`MiniCPM-V-4.7-1B-native`，原服务 8000 `/v1/chat/completions`。
- 当前加载路径：`/data/models/MiniCPM-V-4.7-1B`。
- `limit=0`，全部 14 科、12032 题；validation 70 条仅作为原 5-shot 来源，不计测试题。
- 实际生成参数：`temperature=1.0,top_p=0.95,top_k=20`；API seed 显式固定为 1234。
- 最大上下文 262144；FlagEval 的 `max_gen_toks=262144` 经本轮请求适配器转换为
  每题 `max_completion_tokens=262144-prompt_tokens`。输入计数来自同一服务 `/tokenize`；
  初始 1505 次请求已逐条核对实际 usage、参数、模型 ID 与预算。
- 前缀缓存保持开启，现有命令请求 `FULL_AND_PIECEWISE`，不重做或宣称 graph 档位正式验收。
- 客户端并发 32；API/evaluation retries 均为 0；单请求 timeout=7200 秒，
  allow_timeouts=true；使用新响应缓存，不复用旧评测结果。
- 保留原任务说明、选项顺序、5-shot first_n、聊天模板和 until=["</s>"]。
  原始基准标签保持不变，此前发现的数据疑点未据模型回复修改。

| 学科 | 全部 test 题数 |
| --- | ---: |
| biology | 717 |
| business | 789 |
| chemistry | 1132 |
| computer_science | 410 |
| economics | 844 |
| engineering | 969 |
| health | 818 |
| history | 381 |
| law | 1101 |
| math | 1351 |
| other | 924 |
| philosophy | 499 |
| physics | 1299 |
| psychology | 798 |
| 合计 | 12032 |

运行前已核对全部 12032 个唯一 question_id，14 科之和与原缓存 test 数一致。
各科前 50 题的文档哈希与原缓存读取的既有清单一致；完整题号及文档哈希在 task-manifest.json。

## 三套评分口径

同一批回复保存三个 filter，不额外生成、不删除无法提取的样本：

1. `custom-extract`：冻结当前共享 FlagEval 模板的原规则及首次匹配行为，供对照。
2. `original-extract`：原始大小写敏感 `answer is \(?([ABCDEFGHIJ])\)?`。
3. `final-answer-extract`：本轮 `minicpm_mmlu_final_choice_v2`；剥离思考区段，
   支持明确答案标记与独立字母，明确答案冲突或未闭合思考块判无效；新增末行
   `X. 选项文字` 支持，要求字母及对应选项全文相符，例如 H. 64.18 m。

第三套规则避免先前的思考首个匹配污染，并修正 v1 漏提末行完整选项的边界。
10 个过滤边界用例在启动前通过，版本与代码哈希独立冻结；没有改写共享 FlagEval 的 YAML。

原 `_mmlu_pro.yaml` 指定 aggregate exact_match、weight_by_size=true，
因此全量汇总主指标按所有正确数 / 12032 计算；另存每科准确率的等权平均，明确区分。

## 服务、镜像与数据身份

模型容器 `MinicpmV4.7-1B-native`，ID
`66a0c79a982769313637ac15000e059cd280443cd7a22dea49f37b763a2c898e`，
image ID `sha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4`。
API PID 28633，boot ID `995d16f5-2ee6-45d5-9c00-467c8eb5f202`，start ticks 302123928，
cmdline SHA-256 `adc7c13f1192980ba3481f653cc3f5e216b8f8d9aca311b4d87a51de024a1068`。
启动后仍是同一进程；实际服务 CUDA_VISIBLE_DEVICES=0，GPU 为 NVIDIA H100 80GB HBM3，
UUID `GPU-62954cac-bde7-68fe-d74b-3118a92bcdd4`，/health=200。
取证辅助进程的环境与实际 API 进程环境不同，以 launch-verification.json 中服务进程环境为准。

准备时 vLLM 为 0.24.0，import 路径为
`/usr/local/lib/python3.12/dist-packages/vllm/__init__.py`，PyTorch 为 2.11.0+cu129；
模型配置、tokenizer 配置与已安装 minicpmv4_7.py、qwen3_5.py、registry.py 哈希在 prepared.json。
权重 model.safetensors 为 3109054480 字节，记录路径、大小与 mtime；没有将文件 stat
当作完整权重内容 SHA-256。启动期 API system_fingerprint 为 `vllm-0.24.0-3497421c`。

评测镜像 `harbor.baai.ac.cn/flageval/flageval-llmeval:v1`，image ID
`sha256:d6faaf5e502450346771e0b5387db22254b2cce6dff0a35a26ebce0bbf29a096`。
本轮独立容器 `minicpmv47-1b-nv-mmlu-full-20261012-r1`，ID
`54b5847db6c053daf61d79b9b1589434ee47aab779bd1647727eccaff616b599`。
Host、模型容器与评测容器工作根均为
`/public/flagos/jinghao/MiniCPMV4.7-1B/native`，核对设备号:inode `45:242118752009`。

数据来自现有 flageval-llmeval_lhc 的 TIGER-Lab/MMLU-Pro 缓存，修订目录
`54611cde22c74cca43dd78732198de6abe971398`，dataset_info SHA-256
`6af75780a292247b90b286626e0593d74071faa6d9a8d3c1bb5c41afce864a1b`。
复用已验证的只读 Arrow 服务器和 custom_dataset 内存加载扩展；逐文件核对 SHA-256，
学科过滤 keep_in_memory=true；没有复制、迁移或改写外部数据缓存。

## 持久后台执行与查看结果

过程与冻结配置：
`/public/flagos/jinghao/MiniCPMV4.7-1B/native/03-acceptance/mmlu-pro-nv-full-20261012-r1/`。
结果根：
`/public/flagos/jinghao/MiniCPMV4.7-1B/native/04-runs/mmlu-pro-nv-full-20261012-r1/`。
本轮缓存/临时文件分别在 06-cache/、05-tmp/ 下同名目录。

Host supervisor PID 为 **2770147**，以独立会话启动；精确 argv 与 PID 在
supervisor-process.json / launch-verification.json。关闭聊天或 SSH 会话不结束它。
它调用原生 llmrun.py 配套 acceptance_contract.py、score_progress.py；
当前配置已先执行 preflight-only，退出 0，再使用同一配置实测。

在结果根查看：

- `api-requests.jsonl`：已完成实际请求及参数、usage、终止原因；行数可观察进度。
- `runner.log`：原生 runner 输出；每 100 题记录评分进度。
- `supervisor-state.json`：running/completed/failed，表示后台执行与完成核验状态，不是正式 gate。
- `results/`：逐科 results_*.json、samples_*.jsonl。
- `measurement-summary.json`：全部完成且核验通过后生成三套正确数、准确率、逐科结果和证据哈希。
- `verification.log`：结束后的覆盖、参数、逐题一致性和服务绑定核验；失败保留原始输出。
- `cleanup.json`：后台结束后仅停止本轮辅助评测容器与只读数据服务，保留全部文件；不停止模型容器。

本轮前置检查确认没有正在运行的评测，两个辅助端口 18370/18371 空闲。
目前尚未执行完成后核验或清理，不能将待生成的 summary/cleanup 作为现有成功证据。
如果任务失败，按现有 supervisor-state 和日志诊断，不重放 start 命令或复用旧 run 身份重启。

## 冻结证据

Skill bundle：`355bdf2946456710e0dbaaa9b331062f86be2ec4e5740f7be91ac57a6daa167d`。
以下前五项位于上述控制目录，最后一项位于结果根。

| 文件 | SHA-256 |
| --- | --- |
| config.json | `6b7b65a38fe061fa6857d5b481da3b310260e8802d85e6ccfbc00cec76ba0e98` |
| prepared.json | `f3a0a4fbfd9f92ae13cf4b0205f6fd3a12b62439fbc1ef4122c2505cdebe52e5` |
| task-manifest.json | `37162b2ffd4012d74b32fda457f334f68d5405602714e4eeebd7ae670072e616` |
| final_filter_utils.py | `9bab4ec30bb00866e1e755345824ecd2035cfb7ddb4857beede931be66355045` |
| supervisor.py | `7a0106ccd36240b45413c6d9b37cd74c79ce973e983d158bc4e36c75a89eb4a0` |
| launch-verification.json | `c702342c7e4f50855cbedbaee839f3c4b13beb25e34e595472ff2620b733adad` |

准备、启动、启动核验 playbook 的语法与 H100-149 执行通过。
./scripts/syntax-check --offline 通过，结构审计为 0 errors、9 need review（无远端成功含义）。
