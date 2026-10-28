# 2026-10-10：8000 服务 MMLU-Pro 每科 50 题、32 并发测量

## 结果

本轮按用户指定 `mmlu_pro + limit=50` 对全部 14 科各取原任务顺序的前 50 题，共 700 题。
运行 ID 为 `mmlu-pro-nv-l50-20261010-r1`。开始时间 17:26:43，结束时间 17:34:56，
完成核验时间 17:36:02（Asia/Shanghai），约 8 分 13 秒。

| 评分规则 | 正确数 | 准确率 | 无法提取 |
| --- | ---: | ---: | ---: |
| 当前 FlagEval `custom-extract` | 279/700 | 39.86% | 77 |
| 原始 `original-extract` | 279/700 | 39.86% | 77 |
| 最终答案 `final-answer-extract` | 317/700 | 45.29% | 12 |

三套规则使用同一批原始回复，不额外生成。严格规则为大小写敏感的
`answer is \(?([ABCDEFGHIJ])\)?`，取首个匹配。
最终答案规则先取最后一个 `</think>` 后的区段，支持 `Answer:`、`answer is`、
Markdown、`\boxed{X}` 和末尾独立答案字母；显式思考块未闭合、最终区段有相互冲突的
明确答案或没有明确答案时记为 `[invalid]`。无法提取保留并计错。
最终规则将严格口径下 45 条错误评分改为正确，同时将 7 条原先计对的评分改为错误，
净增 38 题、5.43 个百分点；不是仅救回严格口径错误样本的单向修正。

700 次生成均为 HTTP 200、`finish_reason=stop`；超时、请求错误均为 0。
每科核验 50 个唯一文档、与冻结题目 ID 一致；三套 filter 共 2100 行，
逐题输入、原始回复、目标答案在各 filter 间一致。原生程序退出码为 0。

| 学科 | 题数 | 原始严格规则正确数 | 最终答案规则正确数 |
| --- | ---: | ---: | ---: |
| biology | 50 | 30 | 31 |
| business | 50 | 24 | 32 |
| chemistry | 50 | 24 | 29 |
| computer_science | 50 | 19 | 19 |
| economics | 50 | 25 | 24 |
| engineering | 50 | 27 | 26 |
| health | 50 | 14 | 13 |
| history | 50 | 5 | 12 |
| law | 50 | 13 | 14 |
| math | 50 | 33 | 38 |
| other | 50 | 10 | 14 |
| philosophy | 50 | 10 | 15 |
| physics | 50 | 27 | 30 |
| psychology | 50 | 18 | 20 |

这是用户指定的子集测量，`formal_acceptance=false`；未执行全量 12032 题，
未冻结正式验收阈值，不更新正式 accuracy 状态、部署绑定或架构证据哈希。

## 当前服务与生效配置

- Host / profile：`H100-149` / `vllm-native`（当前 profile version 2）。
- 当前服务 `CUDA_VISIBLE_DEVICES=0`；GPU 0 为 NVIDIA H100 80GB HBM3，
  UUID `GPU-62954cac-bde7-68fe-d74b-3118a92bcdd4`。
- 服务容器：`MinicpmV4.7-1B-native`，ID
  `66a0c79a982769313637ac15000e059cd280443cd7a22dea49f37b763a2c898e`。
  镜像 ID `sha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4`。
- 当前模型 ID：`MiniCPM-V-4.7-1B-native`；endpoint：8000 `/v1/chat/completions`。
  实际加载路径为 `/data/models/MiniCPM-V-4.7-1B`，不是此前 `/data/models/MiniCPM-V-4.7/weights/1b`。
  配置架构为 `MiniCPMV4_7ForConditionalGeneration`，文本部分 hidden size 1024、24 层。
- API PID 28633，boot ID `995d16f5-2ee6-45d5-9c00-467c8eb5f202`，start ticks `302123928`，
  cmdline SHA-256 `adc7c13f1192980ba3481f653cc3f5e216b8f8d9aca311b4d87a51de024a1068`；
  开始前与结束后核对为同一实例。配置与 tokenizer 配置哈希也在前后核对一致。
- 现有命令含 `--enable-prefix-caching --gpu-memory-utilization 0.85` 和
  `--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}'`。
  本轮未修改或重启模型服务、产品代码与启动脚本，也未重做 graph 档位验收。
  根脚本取证 SHA-256 `bedb1299efd00b0408b2d53f49e25728d55a1eece00e65d21e4685e4f15ce6d5`，
  仅记录现有文件身份，不宣称本轮重新验证了该脚本启动。
- 生效采样参数：`temperature=1.0,top_p=0.95,top_k=20`；API seed 1234。
  `num_concurrent=32`，请求时间区间计算的最大重叠数为 32；API/evaluation retries 均为 0。
- 用户指定最大输出使用服务支持的最大长度。`/v1/models` 与文本配置均为 262144 上下文。
  原生 FlagEval CLI 显式设置 `max_gen_toks=262144`；评测请求适配器先调用当前服务
  `/tokenize`，将实际 `max_completion_tokens` 设为 `262144 - prompt_tokens`。
  不将输出上限与总上下文上限混用；保持原聊天模板、5-shot `first_n`、选项顺序与 `until=["</s>"]`。
- 700 题输入为 930–2531 tokens，因此实际允许输出为 259613–261214 tokens。
  `budget_capped_requests=700` 表示全部请求都按输入长度扣减输出预算，不表示模型生成被截断。
  实际输出为 97–16510 tokens，总输出 1017521 tokens；全部正常停止，无长度截断。
  逐条核对 tokenize 与生成 API 的输入计数相同，且总 token 数不超过 262144。
  本轮实际短上下文样本不构成 262144 长上下文正确性验证。

模型配置 SHA-256：`0d2f763cf97a0a5beec8f52b13b4cbf7262680df6fd35e1f0e48c09288c4bb12`。
Tokenizer 配置 SHA-256：`11d04ab77486ca63a9f2b2537e70bbd8f6b24e1850e53eedb32caa3ca771cb0d`。

## 数据、评测环境与复现

Host、模型容器及本轮评测容器的工作根均为
`/public/flagos/jinghao/MiniCPMV4.7-1B/native`，映射设备号:inode 核对为 `45:242118752009`。
配置/过程文件放 `03-acceptance/mmlu-pro-nv-l50-20261010-r1/`，
结果放 `04-runs/mmlu-pro-nv-l50-20261010-r1/`，本轮缓存与临时文件分别在
`06-cache/` 和 `05-tmp/` 下同名目录，没有复用旧响应缓存；核验 700 次真实生成请求。

评测镜像为 `harbor.baai.ac.cn/flageval/flageval-llmeval:v1`，image ID
`sha256:d6faaf5e502450346771e0b5387db22254b2cce6dff0a35a26ebce0bbf29a096`。
专用容器 `minicpmv47-1b-nv-mmlu-20261010-r1` 的 ID 为
`c9eaed6b41d33893108caede4569767e37eaf9403b2581f350689a2facd46c53`，
`/app` revision 为 `ca6ac05fbd23ad8127aa069f00039a9ac1422e97`。
当前共享评测容器和独立评测镜像的 MMLU 格式化 utils 与 OpenAI backend 文件哈希相同，
详情在 `verified-metadata.json`。

复用已验证的只读 Arrow 内存加载方法：冻结当前共享 `flageval-llmeval_lhc` 缓存的
文件清单及 SHA-256，通过本轮 localhost 18371 只读服务加载到内存；使用既有
`custom_dataset` 扩展及 `keep_in_memory=True`，不复制到磁盘或改写外部缓存。
数据修订目录 `54611cde22c74cca43dd78732198de6abe971398`，test 12032、validation 70。
Dataset info SHA-256 为 `6af75780a292247b90b286626e0593d74071faa6d9a8d3c1bb5c41afce864a1b`。
14 科所选文档哈希与此前原缓存加载的冻结清单一致；各题 ID 在 `task-manifest.json`。
最终答案 filter 的 8 个边界用例通过。

能力入口 `adaptation/accuracy` 选用 `formal-full` 原生执行方法，按照用户明确的 limit
覆盖为非正式子集测量。Skill bundle SHA-256 为
`5ba2c9b96040324baf067405c53ff48528ae463b2dcd06f0a062ce57ac3885ca`。
本轮使用当前仓库 `test/Accuracy_test/llmrun.py`、`acceptance_contract.py` 与 `score_progress.py`；
过程副本及工具哈希保存在上述 `03-acceptance` 中，不创建产品源码副本或使用 `PYTHONPATH`。
先执行 `python3 run_evaluation.py --config config.json --preflight-only`，
通过后以同一冻结配置执行 `python3 run_evaluation.py --config config.json`。
18370 仅作为本轮请求预算/参数记录适配器，实际模型生成转发到既有 8000 服务。

## 精确证据

以下路径相对于上述远端根；每科 `results_*.json` 与 `samples_*.jsonl` 的准确路径和 SHA-256
共 28 项完整保存在 `measurement-summary.json`。

| 路径 | SHA-256 |
| --- | --- |
| `03-acceptance/mmlu-pro-nv-l50-20261010-r1/config.json` | `19eb232f8e3ac70e57beab331df84cd2538731941c47bacd3007302bd4f9eff3` |
| `03-acceptance/mmlu-pro-nv-l50-20261010-r1/prepared.json` | `0333f226f0d7f413fbb9dce953a699a0fcf546ba41727682056847ce9838d472` |
| `03-acceptance/mmlu-pro-nv-l50-20261010-r1/task-manifest.json` | `81c4a708eb052e3a141b31483250d78ecfffba409e2de2f726e4239b54511feb` |
| `03-acceptance/mmlu-pro-nv-l50-20261010-r1/dataset-source.json` | `d96f535afa2b3a14885a1d64f9bd2482bbc6222beb42a6584cb4970407b213f1` |
| `03-acceptance/mmlu-pro-nv-l50-20261010-r1/final_filter_utils.py` | `2f634d453fcd6845f79f199825bbb7e4bdb7eca5eb74098b9f2a72f6c95945b4` |
| `04-runs/mmlu-pro-nv-l50-20261010-r1/measurement-summary.json` | `f5e12088f046492892fa8efd762dde85ff29368c987e9a0be653dbd5c04d424b` |
| `04-runs/mmlu-pro-nv-l50-20261010-r1/api-requests.jsonl` | `9a9a2d12b9a7bda180ccade02d3489acf06da7b71f4b28622be266f9c42bcb31` |
| `04-runs/mmlu-pro-nv-l50-20261010-r1/exit-status.json` | `050fd1ba1399783e7f9f4ef964cfb6ce1a60d2c99e020881116c08596700817b` |
| `04-runs/mmlu-pro-nv-l50-20261010-r1/verified-metadata.json` | `a8895780953cbaaaaf95e1bb6785cb7041eb91d1b4d872eeb858038bf8c8e36d` |
| `04-runs/mmlu-pro-nv-l50-20261010-r1/cleanup.json` | `6ea257d7812099a3f6cca3112c62fb44a30db3ade1e893551ad5c05b860eda87` |

原生逐科结果目录：
`04-runs/mmlu-pro-nv-l50-20261010-r1/results/MiniCPM-V-4.7-1B-native-mmlu-pro/`
`mmlu-pro-nv-l50-20261010-r1/mmlu_pro_nv_l50_<subject>/attempt-1/MiniCPM-V-4.7-1B-native/`。

核验完成后，已按容器 ID 与精确进程 argv 停止本轮独立评测容器和只读数据服务，保留所有证据。
模型容器及原共享 FlagEval 容器仍运行，8000 `/health=200`；原因、命令和验证见 `cleanup.json`。
请求适配器随原生 runner 正常退出。

本轮 prepare/start/finish 操作 playbook 语法检查及 H100-149 执行均成功。
按 playbook 维护要求执行的 `./scripts/syntax-check --offline` 中，252 项测试（1 skipped）、
6 项附加测试以及 shell/Python/playbook 语法检查通过，最终布局审计仍报告 12 errors、
78 need review，命令退出 1；没有用这些本地检查替代远端实测，也未修复或改写无关记录。
