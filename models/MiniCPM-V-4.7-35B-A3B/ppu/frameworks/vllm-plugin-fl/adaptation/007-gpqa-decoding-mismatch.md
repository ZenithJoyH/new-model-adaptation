# 007：GPQA 对照分差与服务响应差异

## 元数据

- 状态：`hypothesis`；首次与最近核对日期：2026-10-02。
- 模型、平台、Host：MiniCPM-V-4.7-35B-A3B、T-Head PPU、`PPU-13`；
  模型容器 `minicpmV4.7-35B`，评测容器 `flageval_llmeval-jinghao`。
- 执行路径：当前根级脚本 SHA-256
  `398f50145f6f66f8423007233a9155e1004380255838a6f5a8608d32b20d03f1`，
  TP2/PPU 0、1，前缀缓存开启，`FULL_AND_PIECEWISE`，七个指定图尺寸，
  上下文上限 262,144。当前 Plugin HEAD
  `3a27a6fb2d514cdf55c00481bf813225dac63319` 加既有工作树差异；
  vLLM、FlagGems checkout HEAD 分别为 `ee0da84ab9e04ac7610e28580af62c365e898389`
  和 `1a38df24f72ca5a4a6a24650b5d66356709750ba`，两树只读且干净。

## 问题现象与原始证据

用户给出的 NV 参考 `gpqa_cpm-35B_nv.jsonl`（SHA-256
`929a1562615d89cfe3cae66d267708b59b7c80454d5ff55c5926f32f8e3b5e0f`）
与 PPU 文件 `gpqa_minicpm-35B_ptg.json`（SHA-256
`3b52e33973ffb9d370359a7ed9a3e9b341ae31f0699a079a9d171d9f3cbcb51d`）
都位于批准工作根，后者虽然以 `.json` 结尾，实际也是 JSONL。每份有 198 个
`doc_id`、各两种 filter，共 396 行；逐行对齐的 `doc_hash`、`prompt_hash`、
`target` 均为 396/396 一致，未见题目或答案集差异。两份均无标记 timeout。

按样本字段汇总，NV `strict-match` 为 152/198，PPU 为 143/198；
`flexible-extract` 分别为 92/198、118/198，后者不能代替严格指标。
严格匹配有 16 题从 NV 正确变为 PPU 错误，另有 7 题相反；PPU 4 题
`[invalid]`。PPU 文本中 194/198 出现 `</think>`，NV 无此标记；
PPU 输出字符数中位数 5,220.5，NV 为 496.5。PPU 第 7 题生成到 18,000
token 后重复感叹号，第 33 题出现乱码。原文件没有附带足以证明 NV 与 PPU
服务修订、并发和完整采样请求一致的回执，不能把 9 题净差全部归因于硬件数值。

## 诊断与已有经验

两份样本都记录 `temperature=1.0`、`do_sample=False`、`top_p=0.95`、
`top_k=20`；`max_gen_toks` 元数据分别为 NV 257,253、PPU 18,000，
但用户明确说明两端实际评测参数相同，本问题不通过改变评测参数处理。
当前 FlagEval `openai-chat-completions` 客户端
`/app/lm_eval/models/openai_completions.py::_create_payload` 会丢弃
`do_sample`，并原样发送温度 1.0，因此两端均按相同采样设置对待；
不能把这一点单独作为 PPU 低分原因。

2026-10-02 对两端当前服务做只读核对：模型的 `config.json`、
`generation_config.json`、`tokenizer_config.json` 和权重分片索引 SHA-256
均相同，17 个分片的文件名和大小相同。NV `H100-149` 服务启用
`--reasoning-parser qwen3`，PPU `PPU-13` 服务没有；两边均为 TP2、
`FULL_AND_PIECEWISE` 与前缀缓存。NV parser 将思考文本从 `content`
分离，而 PPU 将思考及最终答案一起返回。对固定第 57 题发送同一条
`temperature=1.0`、`top_p=0.95`、`top_k=20`、18,000 token、
`seed=1234` 请求，两端都答 A：NV 生成 854 token、`content` 606 字符，
PPU 生成 969 token、`content` 4,778 字符且含 `</think>`。该题在原 PPU
文件为 D，说明其错误在当前实例的单请求中并不稳定复现。

历史样本的 `filtered_resps` 均可由一个允许末尾无标点的
`answer is...` 提取式重建（两端各 198/198）；当前评测容器的
GPQA YAML 正则要求答案后还有句号或空白，对原始 NV、PPU 输出分别有
107、12 题无法重建原有 `filtered_resps`。因此当前容器的 task 文件
不能直接证明参考文件的评分版本；题目和答案集仍然逐题一致。
在原 PPU 输出上模拟分离 `</think>` 前内容，再按可重建历史结果的
提取式打分，仍为 143/198，说明单独添加 reasoning parser 并不能
解释或修复 9 题净差。16 个 NV 对而 PPU 错、7 个相反的配对样本，
McNemar 精确双侧 `p=0.0931`；单次 4.55 个百分点差异尚不足以
证明系统性硬件精度损失。

同机同系列 [1B 的 004 问题](../../../../../MiniCPM-V-4.7-1B/ppu/frameworks/vllm-plugin-fl/adaptation/004-gpqa-strict-accuracy.md)
也观察到思考模式长输出和严格匹配受损，但模型规模、基线分数、生成上限及
并发不同，只作为候选经验。本项目 `docs/troubleshooting/` 没有同时匹配
本轮“参数矛盾、低分、异常输出”的已验证条目。

2026-10-02 使用当前根级脚本的同字节副本，在 `04-runs/gpqa2/` 独立启动
服务（首次短目录前的启动因 ZMQ IPC 路径超过 107 字符失败，失败日志保留在
`04-runs/gpqa-thinking-control-20261002/`）。图捕获 PIECEWISE/FULL 各 7/7，
服务健康检查 200。`02-issues/gpqa2/probe.py` 在同一服务上对 6 个固定
`doc_id` 成对请求，仅切换 `chat_template_kwargs.enable_thinking=false`，
两边固定 `temperature=0`、`max_tokens=4096`。默认模式答对 3/6，关闭思考
也是 3/6；第 33 题由默认模式的长度截断变为正确，第 57 题则由正确变为错误。
结果在 `04-runs/gpqa2/probe-*.json`。因此不能将“关闭思考”作为已验证的
全局修复，也不能从这 6 题估计全量分数。

## 受控对照与状态

在 `03-acceptance/gpqa-temp0-diagnostic-20261002/config.json` 冻结新的
**诊断**运行（SHA-256
`4f216f298f2297a8f1ada91707c968ee2df4c7a86a0310a5658f6bfd15b5e16a`）：
保留 GPQA Diamond 198 题、原任务模板、18,000 token 上限、思考默认值，
明确设置 `temperature=0`；并发 32、每请求 600 秒、API/评测重试 0，
前缀缓存保持开启。原生 runner 的 `--preflight-only` 已通过；
全量运行结果目录为
`04-runs/MiniCPM-V-4.7-35B-A3B/gpqa-temp0-diagnostic-20261002/`，
控制日志与终态退出码位于 `04-runs/gpqa-temp0-controller-20261002/`。
原生严格匹配 126/198；198 题完整覆盖，但 41 题请求在 600 秒超时，
均按错题计入。完成的 157 题中 126 题正确；服务无新的 `invalid page`
或崩溃，超时样本在旧 PPU 文件中的生成 token 中位数为 5,219，
非超时样本为 1,398。此改变评测参数的运行仅保留为诊断证据，
**不是修复或与 NV 的有效分数对照**。随后启动的关闭思考全量对照因
用户澄清“不变动评测参数”而对精确控制进程发送 SIGINT，退出码 130，
确认子进程结束，模型服务 `/health` 保持 200；结果不用于评分结论。

已在 `03-acceptance/gpqa-original-params-diagnostic-20261002/config.json`
冻结原 PPU 样本参数（SHA-256
`f30312d7d27a81d2285c05fe54b1fd1947ba4111fb4dc654618b1fc69b8b2af7`）：
温度 1.0、`do_sample=false`、`top_p=0.95`、`top_k=20`、
18,000 token，仍用 32 并发和 600 秒超时。语法、预演、原生 preflight、
服务健康均通过；全量诊断退出码 0，结果目录为
`04-runs/MiniCPM-V-4.7-35B-A3B/gpqa-original-params-diagnostic-20261002/`。
198 题、396 行完整且无 timeout 或非 timeout 请求错误；`doc_hash`、
`prompt_hash`、`target_hash`、`target` 与 NV 逐题 198/198 一致。
按当前 task YAML 的原生严格匹配为 **147/198**；11 道最终答案仅以
裸字母结尾，现有正则把它们记为 `[invalid]`，其中 4 道原本答对。
按能逐题重建两份参考文件 `filtered_resps` 的提取式，同口径重计为
**151/198（76.26%）**，NV 152/198（76.77%）。原 PPU 143/198
到这次 151/198 有 15 题由错转对、7 题由对转错；与 NV 的配对
不一致为 NV 独对 14、PPU 独对 13，McNemar 精确双侧 `p=1.0`。
原先第 7 题重复感叹号、第 33 题乱码均未重现；第 33 题此次答对，
第 7 题正常完成但答错。重跑样本 SHA-256
`16a835813c79d4725011fda54404cbf9f1cb47e6545d5d821757fc86753c4650`，
原生结果 SHA-256
`6c3cff9e0ca3fc2d34dcaf1ffbee01a8f2d8addab078f4a8fe2dc7334c9b769e`，
控制日志 SHA-256
`0bd6cd081de390739d9750056e4ecfe8b33a18e080776f5dfcd680f8c18f88a9`。
服务日志无新 `invalid page`、EngineCore 崩溃或 RPC 超时，终态 `/health`
HTTP 200。旧样本与服务日志未改写，
`formal_acceptance=false`，正式验收状态未变。

用户随后在根级服务脚本中新增 FlagGems 算子黑名单并重启服务；不改变
GPQA 请求参数和 32 并发，第二次全量诊断完成 198/198、0 timeout。
当前 task 原生严格匹配为 **146/198**，按上述参考文件可重建提取式为
**153/198（77.27%）**；NV 参考为 152/198。新结果与 NV 的配对
不一致为 NV 独对 13、PPU 独对 14。两次同参数 PPU 复跑的同口径分数
151、153，均未呈现稳定的 9 题低分。新的运行身份、样本哈希、
10 题答案提取差异及服务状态见
[重启后 GPQA 报告](../acceptance/gpqa-32c-after-restart-20261002.md)。
这是一轮新服务配置下的诊断，不可把 151→153 的波动归因于黑名单。

## 根因判断、后续验证与限制

已证实 NV 与 PPU 服务有 reasoning parser 响应格式差异，但对参考
`strict-match` 分数无直接影响。**两次原参数复跑的同口径分数分别为
151/198 和 153/198，未形成稳定的 PPU 精度缺陷证据**；
最符合现有证据的是温度 1.0 采样下
的轮次波动，但具体随机性/调度机制未独立证明。修复了本轮诊断结论：
撤回改变温度的建议，不改模型代码、生产启动脚本或正式评测参数。
另一个确定问题是当前 GPQA task 正则与两份参考结果的答案格式不一致，
应在未来的双平台正式比较中冻结同一评测代码和 task 哈希，避免把
评分规则变化算作模型精度变化；本轮不擅自修改评测标准。
若未来按同一冻结标准多轮复测仍持续偏低，再比较同题单请求/高并发、
eager/graph 与模型专用 Plugin/Kernels。
当前脚本的 prefill 仍为 PIECEWISE，
不满足 profile 正式执行模式验收；该诊断不更新 `framework.yml` 的
`environment_ready` 与 `acceptance.accuracy=not_started`。

知识库处理状态：`reject`（本轮没有可复用的 PPU 低精度根因修复）。
[008](008-gdn-index-invalid-page.md) 的高并发设备异常是单列问题，
原参数重跑未观察到该故障。
