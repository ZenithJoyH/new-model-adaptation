# GPQA Diamond 完整198题计分汇总

2026-11-05，按用户明确指令“这13条异常都按错误计分，以完整198题为分母汇总得分”，对原始运行 `v41-gpqa-diamond-c32-v1-20261105` 的既有逐题分数做汇总。未重新推理、重试、修改回答、评分器或原报告；13条异常在原始逐题记录中本来均为0分，本次将它们全部保留在分母。

| 指标 | 正确 | 错误（含13条异常） | 分母 | 得分 |
| --- | ---: | ---: | ---: | ---: |
| exact_match,strict-match（主指标） | 171 | 27 | 198 | **86.3636%** |
| exact_match,flexible-extract（辅助指标） | 60 | 138 | 198 | **30.3030%** |

异常共13题：12题达到32768生成token上限、最终答案为空，另1题HTTP超时。原生样本将这13题统一标为timeout，不能据此称为13次HTTP超时。异常doc_id（从0起）为 `10,12,27,37,48,75,76,79,88,99,115,145,147`。strict-match另有14题错误；flexible-extract另有125题错误。

原生聚合排除了这13题，得到171/185＝92.4324%及60/185＝32.4324%；这些数值不能代表完整198题得分。原报告和原始响应保留不变，本文件单独记录用户授权的完整分母汇总。

本次只读复核在mx-102明确工作目录 `/public-flash/jinghao/deepseekV4.1` 执行：按JSONL物理行读取396条记录，两个filter分别恰有198题、doc_id完整且无重复，分数均为0或1；两组异常ID一致且分数全为0，逐题求和分别为171与60。原终态returncode=0、evaluator_source_unchanged=true、结束时health=200；原最终检查final_inspection_rc=1保持原样。该检查曾因用字符串splitlines切开合法JSON字符串内的U+2028而解析失败，本次物理行复核不覆盖旧失败记录。

用户随后明确将GPQA主指标阈值设置为86%（minimum=0.86），本轮171/198＝86.3636%达到该门槛，高出0.3636个百分点；辅助指标不设独立门槛。原运行是无阈值测量，原配置和报告不改写，新增授权及阈值单独冻结于远端 `03-acceptance/seq64-v1-20261105/mx-102/prepare/plan.json` 的 `gpqa_threshold_override`。该判定只覆盖原max_num_seqs=16服务的既有结果，不能直接转移到后续64序列配置。

这是用户指定口径的已有分数汇总，非新的正式验收回执。仓库 `recover_gpqa.py` 仅支持固定原生任务名及formal配置，本轮为独立cached任务别名且formal_acceptance=false，因此未强行改写配置调用该工具，也未生成或声称通过acceptance-result.json。分数达到用户新门槛，正式回执及完整适配仍未完成。

运行参数及服务：完整Diamond198题，客户端HTTP并发32，引擎max_num_seqs=16，其余排队；thinking/high、temperature=0、top_p=1、max_gen=32768、seed=20261104；v22、FULL、TP8/PP2、V2 runner、async ON、prefix ON。详见[运行记录](gpqa-c32.md)。

远端证据均在mx-102批准工作根 `/public-flash/jinghao/deepseekV4.1`，下列路径相对此根：

- 原始逐题文件：`04-runs/flageval-native/deepseek-v41-text-gpqa-diamond-c32/v41-gpqa-diamond-c32-v1-20261105/gpqa_diamond_generative_cot_v41_cached/attempt-1/DeepSeek-V4.1-Flash-W8A8-Text/samples_gpqa_diamond_generative_cot_v41_cached_2026-11-05T06-57-06.252297.jsonl`，SHA-256 `fa4bad55602784a18cf5c9ff05077f0c74cf94d343fbd553508a79b88131aa75`。
- 同目录原聚合文件：`results_2026-11-05T06-57-06.252297.json`，SHA-256 `812abd6f20981c433724323df02a2ffa7e3fe6fedd08c890d19326527f7ee1cd`。
- 冻结配置：`03-acceptance/gpqa-c32-v1-20261105/config.json`，SHA-256 `f0df73f265b7500cd733e2514316a9c1fb44209890856be0e0460d744180cfa1`。
- 原终态：`04-runs/v41-gpqa-diamond-c32-v1-20261105/native-exit-status.json`，SHA-256 `9c900a9751189b4702a93821b44cb3fc7fe3a31b5ed0dc889efb1e12de45818c`。结束于2026-11-05 14:57:09北京时间。
- 原始API日志、失败检查记录：`04-runs/v41-gpqa-diamond-c32-v1-20261105/flageval-client.log`、`final-inspection.stderr`。原测量终检失败，未产生measurement-result.json；不能将本Markdown当作该回执。

本轮仅只读访问mx-102，mx-103未操作，模型服务和全部容器均未停止或重启。完成后的定时检查已在此前删除。
