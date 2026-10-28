# MMLU-Pro 全部 14 科每科 50 题：FlagGems Aten 关闭诊断

2026-10-03 在 `PPU-13` 的 `minicpmV4.7-1B` 服务容器和 `flageval_llmeval-jinghao` 评测容器完成。Host/两容器已核对的同路径工作根为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B`；下列远端相对路径均以此为根。权重 `/mnt/cpfs/models/MiniCPM-V-4.7/weights/1b`；Plugin editable checkout `/workspace/vllm-plugin-FL` HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319` 加本模型未提交适配差异，vLLM 0.24.0，FlagGems 5.3.5、checkout `80d0000d93dad55320df06687eb088a5b6dad07d`。没有修改 vLLM、FlagGems 或权重。

## 对照条件和原生执行

- 服务在物理 PPU2、TP1/BF16，前缀缓存开启，显式 `FULL_AND_PIECEWISE`；实际 mixed prefill/decode 为 PIECEWISE、decode 为 FULL。服务未加 `--max-model-len`，有效默认 `max_seq_len=262144`。
- 算子配置 `VLLM_FL_FLAGOS_WHITELIST=attention_backend`。启动日志的 `only_enable failed: No op to register` 与有效 `04-runs/mmlu-atenoff-accuracy-service-20261003/oplist.txt` 相互印证：oplist 仅 `default.flagos` attention 一项，SHA-256 `f48fc99f0cf8af4020e83b333aa2e2c2e329eaf0f4709dd0f9bbaabd2c46ae76`。此设置也改变 Plugin 的非 Aten 算子分派，因此仅能将根因约束到关闭的算子路径集合。
- 冻结配置 `03-acceptance/mmlu-pro-all-limit50-atenoff-20261003/config.json` SHA-256 `b8403f6c74f0a321a79e0c691826315b053942b3c22f716cd781e27f28372d3f`。`tasks=[mmlu_pro]` 展开全部 14 科、每科 `limit=50`，32 并发、客户端 `max_gen_toks=32768`，`temperature=1.0,top_p=0.95,top_k=20`；请求超时 600 秒、重试 0，响应缓存置于独立 `06-cache/accuracy-mmlu-pro-limit50-atenoff-20261003/`。原生 runner 为 `03-acceptance/accuracy-v1/llmrun.py`，其实际调用参数在 `04-runs/mmlu-pro-atenoff-controller-20261003/runner.log`，最终报告 `All tasks completed successfully`。
- 原始结果 `04-runs/minicpm-v-4.7-1b-ppu/mmlu-pro-all-limit50-atenoff-20261003/`，14 个学科的样本文件均为 50 条唯一题号，合计 700 条，没有最终超时。核对摘要 `diagnostic-summary.json` SHA-256 `e5724d8d443c40446a008ceac3b6742c8e1701658639e0a5739ef435e7daba9c`；诊断计数脚本在 `02-issues/mmlu-corruption-boundary/summarize-atenoff.py`。服务日志 `04-runs/mmlu-atenoff-accuracy-service-20261003/server.log` 在服务停止后 SHA-256 `e9fa509cd49b9a19bda5c6907d046101851c2e5013b0e1f2f466436106e2de6a`。

| 学科 | 正确/50 | 答案格式无效 | 最终超时 |
|---|---:|---:|---:|
| biology | 26 | 8 | 0 |
| business | 19 | 8 | 0 |
| chemistry | 23 | 14 | 0 |
| computer_science | 22 | 10 | 0 |
| economics | 26 | 4 | 0 |
| engineering | 21 | 4 | 0 |
| health | 18 | 4 | 0 |
| history | 3 | 22 | 0 |
| law | 10 | 13 | 0 |
| math | 31 | 6 | 0 |
| other | 14 | 8 | 0 |
| philosophy | 10 | 10 | 0 |
| physics | 21 | 7 | 0 |
| psychology | 23 | 1 | 0 |
| **合计** | **267/700（38.14%）** | **119** | **0** |

700 条结束后，独立 `2+2` 短题仍连贯。原始故障实例在 health 50/50 乱码，且独立短题持续乱码；同设置白名单的另一个新鲜实例先前完成 7 科各 50 题加重复 health 50 题，批后短题均连贯。对比支持该算子配置能缓解持续乱码，但无法区分 Aten 注册、Plugin 非 Aten 分派及负载随机性各自贡献；`index_put_` 单独加入黑名单的长负载反例仍出现乱码。详见 [问题 007](../adaptation/007-long-accuracy-output-corruption.md)。本报告是限定样本数的诊断结果，不替代正式 GPQA Diamond 精度回执；较低的 history 分数和 119 条格式无效也仍需调查。

## 用户指定 final-answer-extract 规则重计分（2026-10-03）

直接对上述同一批 700 条原始 `resps` 使用评测容器原生 `RegexFilter` 与 `TakeFirstFilter`，未请求模型重新生成，未改写原样本、原评分或服务配置。用户给定模式为 `(?im)(?:\b(?:the\s+)?answer\s+is\s*\(?|\*{0,2}\banswer\*{0,2}\s*[:：]\s*\(?|\\boxed\s*\{\s*)([A-J])(?=$|[\s)\}.,;!:])|(?:^|\n)\s*\(?([A-J])\)?[.!]?\s*\Z`，`group_select=-1`、`fallback="[invalid]"` 后接 `take_first`。原生 `group_select=-1` 取最后一次正则匹配，再选其中非空捕获组；未额外删除思考文本、扩大匹配或挑选对题答案。输出为单个 A–J 字母或无效标记，按任务原有忽略大小写的 exact_match 判定。

| 学科 | 原规则正确/50 | 新规则正确/50 | 新规则得分 | 新规则无效提取 |
|---|---:|---:|---:|---:|
| biology | 26 | 31 | 62% | 1 |
| business | 19 | 24 | 48% | 0 |
| chemistry | 23 | 29 | 58% | 0 |
| computer_science | 22 | 26 | 52% | 1 |
| economics | 26 | 28 | 56% | 0 |
| engineering | 21 | 22 | 44% | 2 |
| health | 18 | 19 | 38% | 1 |
| history | 3 | 8 | 16% | 0 |
| law | 10 | 13 | 26% | 1 |
| math | 31 | 36 | 72% | 1 |
| other | 14 | 16 | 32% | 0 |
| philosophy | 10 | 13 | 26% | 1 |
| physics | 21 | 26 | 52% | 2 |
| psychology | 23 | 22 | 44% | 0 |
| **合计** | **267** | **313** | **44.71%** | **10** |

同样的 700 条分母，分数由 38.14% 升至 44.71%（+6.57 个百分点），无效提取由 119 降至 10。120 条提取结果改变，48 题由错变对、2 题由对变错，净增 46 题；175 条响应有多次正则匹配，全部遵循最后匹配规则，未对多次匹配题选择性保留旧分数。0 超时。原生结果分数与旧样本 exact_match 的逐科核对通过，700 条唯一题号、原始样本 SHA 在重计分前后核对不变。

精确过滤配置在 `03-acceptance/mmlu-pro-atenoff-final-answer-rescore-20261003/filter.yaml`（SHA-256 `6aee3cc6b449a450ac5bbb6deac3ffd38da6c1d9fefe5b8072267a81246a4aac`），一次性脚本 `02-issues/mmlu-final-answer-extract-20261003/rescore.py`（SHA-256 `614c69eb10d0dc5f3c14aabb751f16d9ca1a04c6d3021c098f67d9f54186ef09`）。容器工作目录仍为已验证映射的同路径根；执行 `python3 02-issues/mmlu-final-answer-extract-20261003/rescore.py --preflight-only` 通过，再执行同命令去掉 `--preflight-only`。派生汇总 `04-runs/mmlu-pro-atenoff-final-answer-rescore-20261003/summary.json` SHA-256 `51d7ca7cf1e28cc70b3ef9fd1633264a897d287fd3e2c9d834f38e32b48b2117`，逐题派生结果 `rescored-samples.jsonl` SHA-256 `3bac7a455dc627ecf3f5be474cab2a3d718da211aa4b25348f35794a9ad55a02`。汇总包含 14 个原始样本/结果文件哈希、冻结服务评测配置哈希及原生过滤器源码哈希。这是用户指定的事后提取规则诊断分数，正式验收状态不变。

## 当前服务启动脚本

完成评测后精确停止空闲诊断服务，核对原脚本 SHA 后保留备份 `02-issues/mmlu-corruption-boundary/start-model-before-atenoff.sh`，将同一 Host/容器映射的 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/start-model.sh` 改为上述白名单并将日志定向 `04-runs/`。2026-10-03 在容器内验证 `bash -n`、SHA-256 `baee3f4658befa9598b81104d5c30fcd51601cefb2b5be5b6e1e428e7da219f9`；预先确认端口空闲，然后通过脚本真实启动 API PID `351457`、EngineCore PID `351962`。实际命令绑定物理 PPU2、`0.0.0.0:8000`，模型 ID `minicpm-v-4.7-1b-ppu`；`/health=200`，`GET /v1/models` 正确，`2+2` 回答连贯，`04-runs/start-model-atenoff-verification-20261003/probe.json` 保留短题结果。启动日志 `04-runs/service-atenoff-20261003T082546Z-351451.log` 显示 `FULL_AND_PIECEWISE` 图捕获和 FlagOS attention；脚本没有服务端 32768 上下文限制。适配容器始终运行。此脚本为当前经诊断负载验证的缓解启动方式；正式图级别、GPQA Diamond 精度、性能和 summary 均未因此变为通过。
