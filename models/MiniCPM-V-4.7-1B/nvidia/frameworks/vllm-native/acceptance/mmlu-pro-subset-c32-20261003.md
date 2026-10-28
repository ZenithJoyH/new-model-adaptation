# 2026-10-03：当前 NV 服务 MMLU-Pro 每科 50 题、32 并发测量

## 结果与范围

用户明确选择 `tasks=[mmlu_pro]`、每个学科 `limit=50`、32 并发，共 14 科、700 题。
运行 `mmlu-pro-nv-l50-20261003-r6` 已完成；700 次请求均为 HTTP 200、`finish_reason=stop`，
超时与非超时请求错误均为 0。每科完整保存 50 个唯一文档，三套 filter 共 2100 行样本；
每题的输入、原始回复与目标在各 filter 间一致。评测入口退出码为 0，结束时间为
2026-10-03 11:30:18（Asia/Shanghai），完成核验时间为 11:32:05。

| 提取规则 | 正确数 | 准确率 | 无法提取答案 |
| --- | ---: | ---: | ---: |
| 冻结时的现有 `custom-extract` | 271/700 | 38.71% | 103 |
| `original-extract`，原始 `answer is` 规则 | 271/700 | 38.71% | 103 |
| `final-answer-extract`，最终答案规则 | 314/700 | 44.86% | 16 |

冻结时的现有模板已恢复为 `answer is \(?([ABCDEFGHIJ])\)?`，所以前两套规则分数相同。
最终答案规则恢复了 45 条严格规则下的错误评分，同时有 2 条严格规则原先计对、最终答案
规则计错；净增 43 题、6.14 个百分点。所有分数使用同一批模型输出，没有因 filter 再生成、
删除样本或重试题目。无法提取的样本保留并计为错误。

| 学科 | 题数 | 现有严格规则正确数 | 最终答案规则正确数 |
| --- | ---: | ---: | ---: |
| biology | 50 | 25 | 34 |
| business | 50 | 22 | 27 |
| chemistry | 50 | 24 | 27 |
| computer_science | 50 | 19 | 22 |
| economics | 50 | 21 | 23 |
| engineering | 50 | 23 | 24 |
| health | 50 | 16 | 18 |
| history | 50 | 3 | 5 |
| law | 50 | 12 | 16 |
| math | 50 | 35 | 37 |
| other | 50 | 14 | 18 |
| philosophy | 50 | 10 | 11 |
| physics | 50 | 27 | 30 |
| psychology | 50 | 20 | 22 |

这是用户指定的子集测量：每科取原任务顺序的前 50 题，合计正确数除以 700。
没有配置正式验收准确率阈值，也没有执行全部 12032 个 test 样本；
`formal_acceptance=false`，不将本轮记录绑定为正式全量 accuracy 通过。

## 服务、数据与生效配置

- Host / framework：`H100-149` / `vllm-native`，profile version 1。
- 权重：`/data/models/MiniCPM-V-4.7/weights/1b`；模型 ID：`MiniCPM-V-4.7-1B-native`。
- 当前服务：`MinicpmV4.7-1B-native`、8000、API PID 20333；容器 ID
  `66a0c79a982769313637ac15000e059cd280443cd7a22dea49f37b763a2c898e`。
- 进程身份：boot ID `995d16f5-2ee6-45d5-9c00-467c8eb5f202`，start ticks `239339199`，
  cmdline SHA-256 `adc8e710fbe9ad510a476392572d29364486865818605570e03e149c3aac8fcb`。
  开始前和完成后核对为同一实例。
- 现有启动参数：GPU 0、TP1、`--enable-prefix-caching`、`--gpu-memory-utilization 0.85`、
  `--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}'`；未重启或修改模型服务。
  根脚本 SHA-256 `416ace884167c38d72ef61161eaec6a7fd9a41cd57d75888b124c28ec6208579`。
- 评测镜像：`harbor.baai.ac.cn/flageval/flageval-llmeval:v1`，image ID
  `sha256:d6faaf5e502450346771e0b5387db22254b2cce6dff0a35a26ebce0bbf29a096`。
  专用评测容器为 `minicpmv47-1b-nv-mmlu-20261003-r6`，ID
  `051f4e182ae3cc172e98429b7fd2c2d1a69c5d4027f561c4e368a93e31029811`。
- Host、模型容器及评测容器工作根均为
  `/public/flagos/jinghao/MiniCPMV4.7-1B/native`，写入前核对设备号:inode `45:242118752009`。
- 数据源为现有 FlagEval 容器的 `TIGER-Lab/MMLU-Pro` 缓存；test 12032 题、validation 70 题，
  数据修订目录 `54611cde22c74cca43dd78732198de6abe971398`。
  使用原任务描述、选项顺序和 5-shot `first_n`。14 科所选文档 SHA-256 均与原缓存加载
  预检完全一致，具体题目 ID 与摘要保存在 `task-manifest.json`。
- 项目能力入口 `adaptation/accuracy` 使用仓库原生 `test/Accuracy_test/llmrun.py`，
  配套 `acceptance_contract.py` 与 `score_progress.py`。按照用户的子集范围执行非正式测量；
  Skill bundle SHA-256 为 `5ba2c9b96040324baf067405c53ff48528ae463b2dcd06f0a062ce57ac3885ca`。
- 生成参数实际为 `temperature=1.0,top_p=0.95,top_k=20`，API seed 1234；将用户的 `top-p`
  拼写归一化为 `top_p`。任务默认 `max_gen_toks=28000`、`until=["</s>"]`，保持原聊天模板。
  客户端 `num_concurrent=32`，请求日志计算的最大重叠请求数为 32；14 科按原生 runner 顺序运行。
- 响应缓存开启，使用本轮独立身份，API/evaluation retries 均为 0；700 次实际 API 请求已核验。

服务本身 `/v1/models` 公布的上下文上限为 262144。当前 FlagEval 的 API backend 不会将
生成参数 `max_model_len` 转换为总 token 预算，因此本轮使用评测请求适配器：先调用同一服务
`/tokenize`，再将输出预算限制为 `min(28000, 32768-prompt_tokens)`。
预检证明 tokenizer 与生成接口报告的 prompt token 数一致；700 条实际 usage 再逐一验证。
所有请求都未超过 32768，本轮实际需要收紧默认 28000 输出预算的请求数为 0。

最终答案 filter 只解析最后一个 `</think>` 后的回复；支持 `The answer is (X)`、`Answer: X`、
Markdown 答案标记、`\boxed{X}` 和末尾独立字母行。未闭合的显式思考块、最终区段出现不同
明确答案或缺少明确答案时返回 `[invalid]`。未从一般选项叙述中猜字母，8 个边界用例已通过。

## 执行问题与收尾

前期准备保留在 r1–r5：同名任务覆盖被内置任务优先级忽略、外部 Docker overlay 缓存的
只读 bind 在后续进程中不可见、部分候选 mount 被 Docker/runc 拒绝。
r4 的评测客户端退出码为 1，没有发出题目请求；没有将它计入成功成绩。
这些失败轮次的已有文件均保留，不以重写原回执消除失败。

r6 使用 FlagEval 已有 `custom_dataset` 扩展，从 localhost 的只读服务读取原 Arrow 数据到
内存，逐文件验证 SHA-256，并用 `keep_in_memory=True` 进行学科筛选。原缓存没有复制到磁盘、
迁移或写入；模型服务及现有共享 FlagEval 容器也没有修改。该方式是已验证的本轮执行方法，
未把 bind 消失的底层原因宣称为已定位，也未推广为通用经验。

模型请求适配器在 runner 结束后退出。额外的只读数据服务已单独停止；本任务创建的 r1、r2、
r4、r6 辅助评测容器已核对 ID 后停止并保留，原始数据未删除。适配模型容器仍运行，
收尾后 `/health=200`；具体原因、命令和验证在 `cleanup.json`。

## 精确证据引用

以下均相对于上述已核验的远端工作根，完整结果与样本只保留远端。

| 文件 | SHA-256 |
| --- | --- |
| `03-acceptance/mmlu-pro-nv-l50-20261003-r6/prepared.json` | `c397e69c5452f3d9185ac0bacf0131e470af84a125be6c839ffea74987ea3ef2` |
| `03-acceptance/mmlu-pro-nv-l50-20261003-r6/config.json` | `3ed7c6eff4995e0c9de7ef26669ad79badaf9b68151b860f296add86718f06a2` |
| `03-acceptance/mmlu-pro-nv-l50-20261003-r6/task-manifest.json` | `23c4e3385b57c05b0747798f3dec1a78204418c70a64968aa36ff4c3f2046b75` |
| `03-acceptance/mmlu-pro-nv-l50-20261003-r6/dataset-source.json` | `d96f535afa2b3a14885a1d64f9bd2482bbc6222beb42a6584cb4970407b213f1` |
| `03-acceptance/mmlu-pro-nv-l50-20261003-r6/final_filter_utils.py` | `2f634d453fcd6845f79f199825bbb7e4bdb7eca5eb74098b9f2a72f6c95945b4` |
| `04-runs/mmlu-pro-nv-l50-20261003-r6/measurement-summary.json` | `eb9fa52a461580a910b02e4b6466caedad520a10541d0b7f9581cfc9d50e8e1e` |
| `04-runs/mmlu-pro-nv-l50-20261003-r6/api-requests.jsonl` | `c66fd889aba8424e82747e172d98b3145f6787f4a81c3d408400cd16d7310979` |
| `04-runs/mmlu-pro-nv-l50-20261003-r6/exit-status.json` | `8ba15c82725bba681583cf26488dbe276b2af80ac82cf87ac4e24679a12269ef` |

三件原生 runner 与包装在 `03-acceptance/mmlu-pro-nv-l50-20261003-r6/`，
先执行 `python3 run_evaluation.py --config config.json --preflight-only`，再执行
`python3 run_evaluation.py --config config.json`。数据只读服务的精确 argv 在
`04-runs/mmlu-pro-nv-l50-20261003-r6/dataset-server-process.json`；启动前必须核验其缓存来源。
当前已结束的 run 不可原样重复执行或复用缓存作为新服务证据；重测应冻结新 run 身份。

逐科原生 `results_*.json`、`samples_*.jsonl` 的准确路径与 SHA-256 共 28 项，均在
`measurement-summary.json`。每科结果位于
`04-runs/mmlu-pro-nv-l50-20261003-r6/results/MiniCPM-V-4.7-1B-native-mmlu-pro/`
`mmlu-pro-nv-l50-20261003-r6/mmlu_pro_nv_l50_<subject>/attempt-1/MiniCPM-V-4.7-1B-native/`。
本轮不修改产品代码、架构绑定、正式验收状态或既有 JSONL；当前框架仍为 `functional`。

本地维护检查：本轮操作 playbook 的语法检查和目标 Host 执行均成功。
`./scripts/audit-workspace --json` 退出 1，当前模型仍报告既有 `architecture: 本地证据已变化`，
没有通过刷新架构哈希消除该问题；它继续阻止正式流程完成。
`./scripts/syntax-check` 在入口第 22 行因空数组展开报 `inventory_args[@]: unbound variable`，
未执行后续通用检查；未修改无关公共工具或声称仓库总检查通过。
上述本地检查结果不替代本轮 700 条远端测量证据。
