# 005：MMLU-Pro biology 子集分数与答案提取诊断

## 元数据

- 状态：已证实严格答案提取损失；NV 相对 FlagOS 的模型计算回退未证实，未修改产品代码
- 首次出现/最后验证：2026-10-02 / 2026-10-03
- 模型/平台/Host：`/data/models/MiniCPM-V-4.7/weights/1b` / NVIDIA H100 / `H100-149`
- 容器/服务：`MinicpmV4.7-1B-native` 的 8000 graph 服务，对照为 `MinicpmV4.7-1B` 的 8001 FlagOS graph 服务
- 当前 NV adapter SHA-256：`e1bddd8ee92576ff8260ef8e5362a8a7fb7d47c3f4f70584e63944695c2cf86d`；NV 根脚本 SHA-256：`416ace884167c38d72ef61161eaec6a7fd9a41cd57d75888b124c28ec6208579`
- 工作根：Host/容器均为 `/public/flagos/jinghao/MiniCPMV4.7-1B/native`，本次写入前再次核对设备号:inode `45:242118752009`；容器一直运行

## 问题现象与原始证据

用户提供 `/public/flagos/jinghao/MiniCPMV4.7-1B/mmlu_cpm-1B_flagos.jsonl`（SHA-256 `55cfca9fffd81735f333fc55ec97e99599ab19f618691b9f3e5691f85c5b66`）和同目录 `mmlu_cpm-1B_nv.jsonl`（SHA-256 `0b472b41b1c12ce81dc6dc9fb5c5c2e7a5bbeb67bcc2094d1a685aa67ce67fe8`）。两份文件各 50 题，`doc_id`、题目/提示/目标哈希以及生成参数逐题一致，全部为纯文本请求，无 timeout。文件只含样本，不含评测启动命令和服务实例身份，因此不能从文件名反推精确进程版本。

按文件已有 `custom-extract`/`exact_match`：**NV 31/50、FlagOS 31/50**；成对比较 NV 独对 7 题、FlagOS 独对 7 题。因而这两份原始文件本身不支持“NV 低于 FlagOS”的结论。

2026-10-03 用户重新指定同一双文件为最新结果。现场 `mtime` 分别更新为当日 08:22:57/08:22:58，但两份文件的 SHA-256 **逐一与 10 月 2 日记录完全相同**，行数与有效生成参数也未变。重新逐题配对得：双方均答对 24 题、均答错 12 题、NV 独对 7 题、FlagOS 独对 7 题；没有新的模型输出证据。不能仅以较新的文件修改时间将其视为新一轮评测。

运行中 FlagEval 容器 `/app/lm_eval/tasks/mmlu_pro/_default_template_yaml`（SHA-256 `6345e901de9fe02fe59b374d11fc7c37e1d5f861f4fc81e3e9889da6888e9812`）的 `custom-extract` 使用 `answer is \(?([ABCDEFGHIJ])\)?`。逐条重算与文件中的 `filtered_resps` **50/50 一致**。NV 有 7 条 `[invalid]`，其最终回复却分别明确写出正确选项：doc_id `2,4,11,13,34,46,49`，多为 `Answer: X`；FlagOS 有 10 条 `[invalid]`，其中 4 条最终明确写出正确选项：`2,6,7,47`。只对严格无效项进行保守的末尾答案恢复，诊断分数为 **NV 38/50、FlagOS 35/50**；这是不同提取规则的诊断分数，不能覆盖原生严格指标。

样本中的有效 `arg_1` 为 `do_sample=false, temperature=1.0, top_p=0.95, top_k=20, max_gen_toks=258477`；上述任务模板默认 `do_sample=false, temperature=0.0, max_gen_toks=28000`。因此外部评测入口覆盖了模板默认生成设置；原始文件未携带覆盖来源、随机种子或服务身份。固定请求种子时温度 1 的重复回复相同，温度 0 的回复不同，证明温度设置会改变输出；不能仅凭 `do_sample=false` 字段认定原评测是贪心解码。

## 受控对照

只读核实的两边 vLLM `minicpmv4_6.py` SHA-256 均为 `fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`，`qwen3_5.py` 均为 `86ca256c5e3803245f27ac5c8d931cd3d3cb21611aaf2ba90961fb72646c5ca6`。两边 4.7 适配器在无视觉特征时均调用 4.6 文本位置路径。FlagOS 运行时还启用 Plugin/FlagGems 并设置 cuDNN attention 黑名单，NV 使用原生 vLLM；两边同权重、BF16、TP1、前缀缓存和 `FULL_AND_PIECEWISE`，但内核栈并非完全相同。FlagOS 适配器曾修正视觉 decode delta `+1`，NV 视觉分支目前没有这个修正；本次 50 题均无视觉特征，因此它不能解释这组 MMLU 文本分数。

以原 50 个相同提示词、`temperature=0`、`max_tokens=8192`、并发 8 做非正式诊断回放：

| 服务 | 原严格规则 | 严格无效 | 格式恢复诊断 | 未正常停止 |
| --- | ---: | ---: | ---: | ---: |
| NV graph 8000 | 30/50 | 5 | 34/50 | 1 条达到 8192 token 上限 |
| FlagOS graph 8001 | 32/50 | 7 | 38/50 | 1 条达到 8192 token 上限 |
| NV 临时 eager 8002 | 28/50 | 10 | 35/50 | 1 条达到 8192 token 上限 |

graph 同题成对比较 NV 独对 4 题、FlagOS 独对 6 题，精确配对检验双侧 `p=0.7539`；50 题和该差异不足以确认稳定回退。NV eager 并未优于 NV graph，因此未见图模式导致系统性降分。回放设定的 8192 token 上限与用户原评测不同，且各有截断；这些回放是定位实验，不能替代正式 MMLU-Pro 成绩。原始回放摘要和样本位于工作根 `04-runs/mmlu-greedy-20261002/`、`04-runs/mmlu-flagos-greedy-20261002/`、`04-runs/mmlu-eager-greedy-20261002/`；摘要 SHA-256 分别为 `6566e09208d481e4092fc95fc97502b9f27f4708848a783c7286872fe0ce75b7`、`8c768aa02b02f2f30c45c6993f2beb59ae7d960db0ffaa512b748e41a582ee1e`、`778178353869f4508f31253fd147ee5d75279e50f2d905d3868b0a5c21c3e564`。

在空闲 GPU 6 用权重自带 Transformers 参考实现对前 10 题做前 64 token 贪心对照：两边服务与参考提示词 token 数每题一致；NV 与参考逐字完全相同 5/10，FlagOS 7/10；其余样本在已有相同前缀后分岔。原始结果在工作根 `04-runs/mmlu-reference-parity-20261002/result-10.json`（SHA-256 `7309385dc208f59ce98a8553bf40437cb3defeced2977f7c8a65bd7705d1a6da`）和 `result-flagos-10.json`（SHA-256 `f6f04e84293abdc8344f45e9f6d125f3de527649a0b1c4a0d54a0effa4750645`）。这个短前缀检查不证明长链逐 token 等价，也不足以把小分差归因为某个内核。

## 结论与边界

已验证的主要评分损失是原 `custom-extract` 只识别一种尾句形式，NV 原始文件中 7 条明确正确的最终答案被计为无效。原文件两边严格分数相同；受控重放有小差异但没有稳定方向或足够证据定位为 NV 模型实现错误。生成参数覆盖模板默认值也是可复现的配置不一致，尚缺评测启动配置来确认覆盖来源。不能将 38/50 诊断分数当作现有正式成绩，也不应按模型名称在 vLLM 代码中改写答案。

后续若需比较模型精度，应冻结同一评测配置、seed、任务/数据修订、服务实例和完整输出，保留原严格指标，同时**新增并命名**可识别明确最终答案的格式容错指标；再对完整数据集复测。用户此轮先要求分析，故未改 vLLM、FlagEval 任务 YAML、现有 JSONL 或正式状态。临时 eager API PID `22129` 经身份核对后单独停止，EngineCore `22531` 退出、8002 端口关闭、GPU 6 显存归零；适配容器和 8000 graph 主服务保持运行，`/health=200`。

知识库处理：`needs-validation`；这是该任务的评分签名，尚未推广为跨模型结论。
