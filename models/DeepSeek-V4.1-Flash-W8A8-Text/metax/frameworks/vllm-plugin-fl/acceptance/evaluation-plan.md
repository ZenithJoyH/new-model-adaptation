# 评测计划

当前用户指令更新：暂停GSM8K精度修复，完整GPQA198题按13异常计错后strict-match为171/198＝86.3636%；用户随后指定门槛0.86，已达到。原无阈值运行配置不改写，授权另行冻结，见[GPQA汇总](gpqa-score-summary.md)。另已完成[max_num_seqs64有界验证](max-num-seqs64.md)，当前运行64配置，8项原生sanity及140条诊断完成；既有完整GPQA分数不转移为64精度通过。下文GSM8K配置、原95%门槛和性能预备均作为历史记录保留；服务契约已按当前64配置重冻结，不自行重启旧评测或正式性能。

状态（2026-11-05）：最终候选v22已使用冻结的共享脚本、FULL、TP8/PP2、async ON启动，文本服务契约已冻结。完整v1在742/1319题时因Q:停止词造成14条空最终答案而终止，无可接受完整分数；原始证据保留。新的reasoning兼容停止条件任务已验证仅移除Q:，其余1319题输入、目标、评分不变，v2已按用户明确要求将唯一未完成题计错，独立汇总为1171/1319=88.78%，未达原95%门槛；原始运行和缓存保留，见[得分记录](accuracy-cutoff-summary.md)。公开依赖固定交付（plugin:D3）、高精度模型质量比较（plugin:H9）和最终源码审查尚未完成，候选测量不表示正式流程前置门禁已通过。

正式精度选择本地 accuracy Skill 的 `formal-full`，使用已准备的 FlagEval 工具容器和原生 `llmrun.py`。首轮任务为 `gsm8k_cot_zeroshot_v41_cached`，修正任务为 `gsm8k_cot_zeroshot_v41_reasoning_stops`；测试集仍为完整1319条、limit=0，metric为 `exact_match,flexible-extract`。在任何正式测量前预定最低值0.95；后续不得为使失败运行通过而降低该值或减少样本。原prompt、target、过滤和评分不变，停止词修正与同题对照见[017](../adaptation/017-reasoning-stop-condition.md)，数据传输和私有缓存见[工具记录](../environment/flageval-tooling.md)。

生成参数已冻结为thinking开启、reasoning effort high、temperature=0、top_p=1、max_gen_toks=32768、seed=20261104、并发8、timeout=7200秒；每个API请求仅一次尝试，无任务重试。实际原生1319题渲染后输入最大226 tokens，最大输入输出32994小于50000；按64-token页向上取整的8路保守容量264192，小于实际277438 cache tokens。8路文本sanity实际峰值running=8且输出经独立审阅。正常与精度保持prefix on。超时保留计入分母，非超时执行错误或样本不完整不能通过。

已终止首轮配置位于远端 `03-acceptance/full-accuracy-v1-20261105/config.json`，SHA-256 `222a38120af205e619314ef89e94aede0bab8cc5be4f9c0d91d19e538fa68b57`；完整运行ID为 `v41-gsm8k-full-v1-20261105`。容量依据为 `04-runs/gsm8k-capacity-profile-v2-20261105/result.json`。预先8题原生工具试跑为7/8：唯一错判回答包含正确160分钟及换算“2 hours 40 minutes”，原生flexible-extract取最后数字40；保留为错误，不改prompt、scorer或0.95门槛。

checkpoint README 的97.35等外部结果使用不同框架、采样与最大256000输出预算，不能作为本次结果或同设置基线。当前计划只验证该完整数学推理任务；不据此声称其他领域质量已被完整验证，量化/H9所需独立质量比较仍需按真实证据单独核对。

PP+async开发验证已完成相同最终运行时代码、FULL、TP8/PP2的ON/OFF对照：15组相同请求最终答案均正确，覆盖短并发、流式DONE、69-token和1694-token输入及中英文/思考请求；未复现这些场景内的额外异步故障，不外推所有压力场景。证据见 `04-runs/mx-102/pp-async-comparison-v2-20261105.json`。v21同权重eager/FULL三组生成token logprob最大绝对差1.4305046533991117e-6，每个rank实际FULL重放至少两次；它不替代H9高精度比较。v22无观察器8项文本sanity与独立审阅位于 `04-runs/v41-sanity-v1-20261105/`，原生needs_review报告保留。

正式性能在精度通过后选择本地 performance Skill 的 `single-scenario`，使用经容量验证的固定请求manifest。性能复用同一启动脚本字节和基础配置，仅通过 `--performance` 关闭前缀缓存；结束后恢复正常启动。场景及服务绑定尚未冻结，不提前声明吞吐、时延或优化收益。

后续性能候选场景固定为 `1024,128,8,32`（输入/输出/并发/请求数），runs=3、skip-first=1、每轮timeout3600，固定random-range-ratio=0、random-prefix-len=0及ignore-eos，原生入口 `test/perf_test/vllm_perf.py`，completions协议；每轮输出应为4096 tokens。8路请求的页取整容量9216小于已核实277438 tokens。当前只在本地做纯dry-run，不向正在评测的服务发送性能请求；原生客户端参数和性能阶段fresh服务绑定仍需执行前核实。首次测量无提速比较目标，不声明高精度端到端收益；H9要求的同设置高精度质量比较保持未完成；H10末尾建议的高精度性能比较因缺少经核实可用基线而未执行，不能据本次首次测量宣称量化收益。本地性能Skill bundle SHA-256 `3c46ddd2c4d73b11ca324b230d48429c3d4a40d0c82f56f5b27237d8e81bc9ff`，明确选择single-scenario；正式门禁未通过时只允许如实标注的候选诊断测量，不提升performance状态。

当前完整v2配置 `03-acceptance/full-accuracy-v2-20261105/config.json`，SHA-256 `5a4518ed89484afd983962a6e2e42738368b374b356d5583339046d7f486d3f5`；任务仅移除经复现冲突的Q:停止词，其余生成设置及原0.95门槛不变。新API/PP绑定SHA-256 `9f297b3ab9ffbafff7b1a8069973bc4b3a36b42023796842d1b49ed851118e1c`，服务契约仍为 `6e072a45831f15d29492c23d618c4d211d4017840e4fa426f0b76cd11df657ef`。新run/cache身份独立，不复用首轮部分响应，详见017。

用户补充（2026-11-05）：该权重暂时没有其他平台/框架的现成正确性或精度结果，要求“先跑出一个得分吧”。优先完成当前完整1319题测量并如实报告；不将缺少跨平台结果用于中止本轮，也不据此虚构H9所需高精度基线或改动原0.95门槛。

最新截止汇总见[accuracy-cutoff-summary](accuracy-cutoff-summary.md)：1318份原始缓存加1题人工计错，完整分母1319，1171正确、148错误（含人工1题），88.7794%；原0.95门槛不变且未达到。仅停止本轮CPU评测客户端，保留原生退出143记录和模型服务；定时检查已删除。正式性能与整体适配仍未通过。
