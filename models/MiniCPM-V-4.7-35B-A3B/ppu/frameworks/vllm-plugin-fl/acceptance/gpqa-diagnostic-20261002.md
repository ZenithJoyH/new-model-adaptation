# GPQA 参考分差诊断（非正式精度验收）

日期：2026-10-02。目标 Host `PPU-13`、模型容器 `minicpmV4.7-35B`、
评测容器 `flageval_llmeval-jinghao`。批准工作根在 Host/容器均为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，映射已核实；只读模型路径为
`/mnt/cpfs/models/MiniCPM-V-4.7/weights/35b-a3b`。当前用户根级脚本
`start-model.sh` SHA-256
`398f50145f6f66f8423007233a9155e1004380255838a6f5a8608d32b20d03f1`；
诊断服务由其同字节副本 `04-runs/gpqa2/launcher-under-test.sh` 启动，
TP2/PPU 0、1、`FULL_AND_PIECEWISE`、指定 7 个捕获尺寸、前缀缓存开启。
Plugin、vLLM、FlagGems checkout HEAD 分别为
`3a27a6fb2d514cdf55c00481bf813225dac63319`、
`ee0da84ab9e04ac7610e28580af62c365e898389`、
`1a38df24f72ca5a4a6a24650b5d66356709750ba`。本次没有修改产品源码、
权重、根级脚本或适配容器。

## 输入与同口径结果

用户提供的 NV 文件 `gpqa_cpm-35B_nv.jsonl` SHA-256
`929a1562615d89cfe3cae66d267708b59b7c80454d5ff55c5926f32f8e3b5e0f`；
PPU 文件 `gpqa_minicpm-35B_ptg.json` SHA-256
`3b52e33973ffb9d370359a7ed9a3e9b341ae31f0699a079a9d171d9f3cbcb51d`。
两份都是 JSONL，各 198 题、396 行；题目、prompt、target 哈希逐题一致。
NV 严格匹配 152/198（76.77%），初始 PPU 143/198（72.22%），
0 timeout。NV 独对 16 题、PPU 独对 7 题；McNemar 精确双侧
`p=0.0931`。NV 当前服务 `H100-149` 使用 `--reasoning-parser qwen3`，
PPU 服务未使用；这解释了 PPU 样本显示思考文本和字符数显著偏长，
对原参考样本的答案提取结果无影响。两端的模型配置、生成配置、
tokenizer 配置、分片索引 SHA-256 均相同；分片文件名和大小相同。

按用户澄清，本次**保持原评测请求参数**。冻结配置为远端
`03-acceptance/gpqa-original-params-diagnostic-20261002/config.json`
（SHA-256
`f30312d7d27a81d2285c05fe54b1fd1947ba4111fb4dc654618b1fc69b8b2af7`），
温度 1.0、`do_sample=false`、`top_p=0.95`、`top_k=20`、
`max_gen_toks=18000`，32 并发，每请求超时 600 秒，重试 0。
原生 runner、评测数据 preflight、服务健康、Ansible 语法及
`--check --diff` 均通过。完整运行退出码 0，198 题、396 行齐全，
0 timeout、0 API 错误；与 NV 的 `doc_hash`、`prompt_hash`、
`target_hash`、`target` 均逐题 198/198 一致。

本次原生 task YAML 的严格正则要求答案字母后必须有句号或空白，
但两份参考文件的 `filtered_resps` 都能由允许裸字母结尾的同一提取式
逐题 198/198 重建：对 `resps[0][0]` 使用 Python
`re.findall(r'answer is[\s*]*[\(\[]?([ABCDEFGHIJ])', text, re.I)`，
取最后一次匹配，未匹配时记 `[invalid]`，再与 `target` 比较。
这是一条从参考文件反推的诊断提取式，并无原始 task 版本回执。
重跑的 11 条最终回答以裸字母结尾，被当前原生
正则记成 `[invalid]`；其中 4 条本来答对。因此**原生分数为
147/198（74.24%）**，按参考文件可重建的同口径提取式重计为
**151/198（76.26%）**，与 NV 仅差 1 题。与 NV 的配对结果为
共同正确 138、NV 独对 14、PPU 独对 13、共同错误 33，
McNemar 精确双侧 `p=1.0`。初始 PPU 到重跑有 15 题错转对、
7 题对转错；第 7 题重复感叹号与第 33 题乱码未复现。

## 原生证据与边界

原生结果位于
`04-runs/MiniCPM-V-4.7-35B-A3B/gpqa-original-params-diagnostic-20261002/gpqa_diamond_generative_cot/attempt-1/MiniCPM-V-4.7-35B-A3B/`：
`results_2026-10-02T09-56-59.872109.json` SHA-256
`6c3cff9e0ca3fc2d34dcaf1ffbee01a8f2d8addab078f4a8fe2dc7334c9b769e`，
`samples_gpqa_diamond_generative_cot_2026-10-02T09-56-59.872109.jsonl`
SHA-256 `16a835813c79d4725011fda54404cbf9f1cb47e6545d5d821757fc86753c4650`。
`04-runs/gpqa-original-params-diagnostic-20261002-controller/controller.log`
SHA-256 `0bd6cd081de390739d9750056e4ecfe8b33a18e080776f5dfcd680f8c18f88a9`；
`exit-code` 为 0。`04-runs/gpqa2/service.log` 无新 `invalid page`、
Traceback、EngineCore 故障或 RPC timeout；模型服务终态 `/health` HTTP 200。

先前温度零诊断虽完整覆盖 198 题，但 41 题超时，按错误计入后为
126/198。用户要求不变动评测参数，该结果仅作诊断，不作平台分数对照；
后续关闭思考的诊断运行已按此要求取消，退出码 130，子进程全部结束。

结论：当前没有稳定的 PPU GPQA 低精度回归，不能据初始单次 143/198
改动模型实现或放宽阈值。温度 1.0 的采样轮次波动是与现有证据相符的
解释，具体随机性/调度机制仍待验证。若以后要作正式 NV/PPU 比较，
应冻结相同评测代码与 task 哈希，并在原参数下重复测量；当前参考文件
缺少可验证的 task 版本回执。本次运行设置 `formal_acceptance=false`，
且尚未满足 profile 的正式执行模式等前置步骤，`framework.yml`
仍为 `environment_ready`、accuracy `not_started`。
