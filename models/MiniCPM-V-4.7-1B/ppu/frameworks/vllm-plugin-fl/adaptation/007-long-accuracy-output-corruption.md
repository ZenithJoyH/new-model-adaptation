# 007：32 并发长生成后持续输出乱码

## 元数据与故障签名

- 状态：`operator defect confirmed / diagnostic mitigation verified`；首次及最后验证：2026-10-03。int32 索引写入偏移溢出已独立复现，实际模型跨边界与 int64 定向对照形成根因证据；产品修复和正式精度复测尚未完成。此前小节保留各阶段当时结论，接续定位以文末交接快照为准。
- 目标：MiniCPM-V-4.7-1B，`PPU-13`，`minicpmV4.7-1B`，物理 PPU2，TP1/BF16；权重 `/mnt/cpfs/models/MiniCPM-V-4.7/weights/1b`。
- Plugin 可编辑 checkout `/workspace/vllm-plugin-FL` HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`，保留本模型适配的 2 个已改文件和 4 个未跟踪源码/测试文件；FlagGems checkout `80d0000d93dad55320df06687eb088a5b6dad07d` 且工作树干净，运行包 5.3.5；vLLM 运行包 0.24.0。未改产品源码、权重或容器。
- 服务：`FULL_AND_PIECEWISE`，实际 mixed prefill-decode PIECEWISE、decode FULL，前缀缓存开启，默认 `max_seq_len=262144`。评测端 32 并发、每科 50 题、`temperature=1.0,top_p=0.95,top_k=20,max_gen_toks=32768`、请求超时 600 秒、重试 0。用户明确要求 **不在服务启动时设置** `max_model_len=32768`；曾创建但未发起评测的 `--max-model-len 32768` 诊断实例已按 PID 核对停止。

## 现象与原始证据

首次使用用户当前服务（API PID `312631`，算子黑名单 `nonzero_numpy,index_put,nonzero,copy,index_put_,index`）启动 14 科评测后，biology 50/50 样本全部为 `[invalid]`、0/50 正确、0 超时；独立的 `2+2` 请求在负载中和空闲时均返回乱码。冻结配置 `03-acceptance/mmlu-pro-all-limit50-20261003/config.json` SHA-256 `59ceabaece5d68b545ddc7304e2509f078b06cdff549d243159b3933dcb71df7`，biology 样本 SHA-256 `4e071029724a48a6cfb2ae462343edba69f1d56b555b82bdcbe8be314334fdcc`，控制日志 `04-runs/mmlu-pro-controller-20261003/runner.log`，原服务日志 `service.log` 停止后 SHA-256 `38eaf7790ff63234ae3ee0acc0b128a4ea52b6d5bf76a4ce23aa0a11d8e55104`。只停止本次评测进程，退出码 143；之后停止已空闲的异常服务，容器始终运行。

新鲜服务对照：先以黑名单 `nonzero_numpy` 启动，再以 `nonzero_numpy,index` 启动；两次同一 `FULL_AND_PIECEWISE` 图模式和同一简单请求都得到连贯的 `2+2=4` 回答。两次均重启了服务，因此**不能把改善归因于黑名单差异**。后者仅新增 `index` 时仍可正常回答短题，但尚未证明它单独修复先前 FlagGems `index` JIT 非法页问题（见 [006](006-gdn-index-invalid-page-under-accuracy-load.md)）。

在最终新鲜实例（API PID `335984`，启动 tick `371500544`，黑名单 `nonzero_numpy,index`）上按用户修正后的配置运行，前六科各有 50/50 不重复样本、0 超时，分别得分 0.58、0.32、0.40、0.44、0.54、0.46。随后 health 科耗时约 14 分钟，50/50 样本全部输出乱码并被提取为 `[invalid]`，0/50 正确、0 超时；多数响应生成到 32768 token 上限。此后独立 `2+2` 请求也返回乱码，服务 `/health` 仍为 HTTP 200。故障表现是**跨请求持续的答案内容损坏**，不是 API 进程崩溃或答案正则单独失效。第八科 history 在跑时停止评测，后续科目未执行；控制进程及其 worker 均已退出，退出码 143。服务无在途请求后按精确 PID 停止，端口不可用、PPU2 释放，容器保持运行。

最终配置 `03-acceptance/mmlu-pro-all-limit50-index-maxnew32768-20261003/config.json` SHA-256 `b36dfb315a45655e7131d446eb38da99a09a326528a543f2ebc37a71073317c1`；结果根 `04-runs/minicpm-v-4.7-1b-ppu/mmlu-pro-all-limit50-index-maxnew32768-20261003/`，控制日志 `04-runs/mmlu-pro-index-maxnew32768-controller-20261003/runner.log`，服务日志 `04-runs/mmlu-pro-index-maxnew32768-service-20261003/server.log` 停止后 SHA-256 `712811511821d493f6352722cdae4c589e9aad57f4ad4178a3e4d0807253f185`。所有路径均以 Host/两个容器已核对同路径映射的 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B` 为根；原始样本和完整日志只留远端。

## 已有经验、诊断与假设

- [006](006-gdn-index-invalid-page-under-accuracy-load.md) 也在 32 并发、接近 28k token、GDN mixed prefill/decode 负载下发生，但首故障是 PPU `invalid page`，EngineCore/API 退出。本次无已观察到的非法页或进程退出，不能当作同一已证实根因。排除 `index` 仅是受限诊断/候选缓解。
- [003](003-gdn-full-graph.md) 说明 `FULL` 被 GDN backend 降为混合 PIECEWISE；本次有效图级别与之相符，但该事实本身不能解释长时输出损坏。
- [004](004-gpqa-strict-accuracy.md) 有长输出截断与严格解析无效；本次 health 的原始内容从开头就是跨语言杂乱文本，且独立算术题也失真，不能仅按解析格式或个别答案错误解释。
- 当前假设包括图 replay/GDN 状态或算子组合在长时大批量解码后污染后续请求、模型状态或缓存；尚无首个异常 token/层/算子数值证据。新鲜服务恢复正常支持进程生命周期相关性，但没有单变量重启对照，不能断言重启本身或某一黑名单项是根因。

## 受控尝试与结论

| 步骤 | 条件 | 观察 | 结论 |
|---|---|---|---|
| 当前服务评测 | 用户脚本 SHA-256 `9cf99b5cc88914a60bef0a991ad8bae7110d0afd9a186257a6a1a01c89375ebe`，较宽黑名单，32 并发、`max_gen_toks=28000` | biology 50/50 无效，简单题亦乱码 | 该实例已失去计分意义；故障发生前的输出基线未知。 |
| 新鲜服务短题 | 先仅 `nonzero_numpy`，再仅增加 `index`；相同模型、设备、图模式 | 两实例短题均连贯 | `index` 单独排除不引发启动即乱码；重启是混杂变量。 |
| 新鲜服务长负载 | `nonzero_numpy,index`、默认服务上下文、评测端 `max_gen_toks=32768`，32 并发 | 前六科可计分，health 50/50 无效，独立短题随后也乱码 | 已复现长时负载后持续输出损坏；尚不能定位首因。 |

本轮没有产品层修复、正式精度通过回执或可推广 workaround。下一步先在独立诊断实例缩小触发窗口，记录首个异常请求前后同一固定短题及 GDN 状态/logits 是否有限；只改一个变量对照图模式或算子路径，严禁把 `FULL_AND_PIECEWISE` 的后续乱码分数当精度结果。若改用较低图级别，也只能作为诊断，不能悄然替代用户指定模式。知识库处理：`needs-validation`，无足够证据推广。

## 2026-10-03 继续诊断：FlagGems Aten 接管范围

同一 Host/容器/PPU2、权重、`FULL_AND_PIECEWISE`、前缀缓存、默认服务上下文和 32 并发下，`02-issues/mmlu-corruption-boundary/repro-v2.py` 重放既有 MMLU-Pro 提示词；每题仅在客户端设置 `max_tokens=32768`。每批原生请求与独立固定短题均在 `04-runs/` 保存摘要，短题由内容人工复核；这些重放不代替 FlagEval 计分。

| 新鲜实例的算子设置 | 重放及批后短题 | 证据 | 判断 |
|---|---|---|---|
| `VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy,index` | 先健康题短批次 32×64、32×2048、32×8192、50×32768，再依次 biology、business、chemistry、computer_science、economics 各 50 题；computer_science 后短题正常，economics 后及空闲重复短题持续乱码 | `04-runs/mmlu-corruption-boundary-20261003/`；服务 `04-runs/mmlu-corruption-boundary-service-20261003/server.log` | 累积负载可再次触发，故障窗口缩到该实例的 computer_science 与 economics 之间；并非某一健康学科提示词单独触发。 |
| 同上、故障后更换提示词及添加独立 `cache_salt` | 原短题、新的法国首都题和 salted 短题全部乱码；API 均返回成功，GPU KV 使用回落到 0 | 同目录 `cache-salt-probe.json` | 普通前缀命中无法单独解释持续损坏；仍须排查 GDN/运行时状态。 |
| `VLLM_FL_FLAGOS_WHITELIST=attention_backend`，仅保留 FlagOS attention | 按顺序 7 科各 50 题，再重复 health 50 题，共 400 请求；每批后短题均正确，全部请求返回，答案文本连贯 | `04-runs/mmlu-corruption-whitelist-20261003/`；服务 `04-runs/mmlu-corruption-whitelist-service-20261003/server.log`，启动提示 `only_enable failed: No op to register` | 关闭这组非 attention FlagOS/FlagGems 路径是有效诊断缓解；白名单同时影响 Plugin 分派，不能仅归因于 Aten。此时尚未得到完整 14 科计分。 |
| 只在基线黑名单上增加 `index_put_` | 前五科后短题正常；第六科 engineering 后持续乱码，300 个请求均成功返回 | `04-runs/mmlu-corruption-noindexput-20261003/`；服务 `04-runs/mmlu-corruption-noindexput-service-20261003/server.log` | **反例**：仅排除 `index_put_` 不解决问题。有效算子记录仍包含 `flag_gems.ops.index_put._index_put_impl_`，说明这两个注册名称必须区分。 |
| `USE_FLAGGEMS=0` | 服务初始化失败，未开始请求；Plugin 的 thead attention 回退导入 vLLM 0.24.0 缺少的 `flash_attn_supports_fp8` | `04-runs/mmlu-corruption-nogems-service-20261003/server.log` | 不能用该启动方式做内容对照；白名单方式保留可工作的 FlagOS attention。 |

原生 GDN 预填充路径在运行包 `qwen_gdn_linear_attn.py` 的 `initial_state[~prefill_has_initial_state,...]=0` 与 `ssm_state[prefill_state_indices]=last_recurrent_state` 做索引写入，属于候选路径；两个注册入口必须分别验证。后续单独排除 `_index_put_impl_` 的长负载反例及独立算子定位见下节。

## 2026-10-03 全部 FlagGems Aten 注册关闭：完整诊断结果

使用 `VLLM_FL_FLAGOS_WHITELIST=attention_backend` 启动新实例；启动日志报告 `only_enable failed: No op to register`，有效 oplist `04-runs/mmlu-atenoff-accuracy-service-20261003/oplist.txt` 仅有一行 `default.flagos` attention，SHA-256 `f48fc99f0cf8af4020e83b333aa2e2c2e329eaf0f4709dd0f9bbaabd2c46ae76`。仍用 PPU2、TP1/BF16、前缀缓存及 `FULL_AND_PIECEWISE`；服务上下文保持默认 `262144`，仅评测客户端设置 `max_gen_toks=32768`。冻结配置 `03-acceptance/mmlu-pro-all-limit50-atenoff-20261003/config.json` SHA-256 `b8403f6c74f0a321a79e0c691826315b053942b3c22f716cd781e27f28372d3f`。

原生 FlagEval runner 完成全部 14 学科，每科 50 条唯一题号，共 700/700 条结果、0 超时、267 条正确（38.14%）、119 条答案格式无效。先前同配置范围的基线实例到 health 科时 50/50 乱码、独立短题也乱码；本实例在 700 条完成后，独立 `2+2` 短题仍连贯。health 科本次为 18/50，4 条格式无效。结果根 `04-runs/minicpm-v-4.7-1b-ppu/mmlu-pro-all-limit50-atenoff-20261003/`，其中 `diagnostic-summary.json` SHA-256 `e5724d8d443c40446a008ceac3b6742c8e1701658639e0a5739ef435e7daba9c`；控制日志 `04-runs/mmlu-pro-atenoff-controller-20261003/runner.log`；停止后的服务日志 `04-runs/mmlu-atenoff-accuracy-service-20261003/server.log` SHA-256 `e9fa509cd49b9a19bda5c6907d046101851c2e5013b0e1f2f466436106e2de6a`。逐科结果及限制见 [完整报告](../acceptance/mmlu-pro-atenoff-limit50-20261003.md)。

**判断：**关闭这一组非 attention FlagOS/FlagGems 算子路径是已验证的乱码缓解；不能据此断言某一个 Aten 算子已被定位。`VLLM_FL_FLAGOS_WHITELIST` 同时影响 Plugin 的其他算子分派，因此 Aten 与其他非 attention FlagOS 路径仍需分离对照。history 仅 3/50，主要伴随 22 条格式无效，表明本次缓解也不等同于精度达到目标。正式 GPQA Diamond 冻结阈值与图级别验收状态不变。知识库仍为 `needs-validation`，不推广单算子根因结论。

原根目录启动脚本经旧 SHA 核对并备份到 `02-issues/mmlu-corruption-boundary/start-model-before-atenoff.sh` 后，最小改动为上述白名单和日志落到 `04-runs/`。新脚本 SHA-256 `baee3f4658befa9598b81104d5c30fcd51601cefb2b5be5b6e1e428e7da219f9`，已在原容器真实启动，HTTP `/health=200`、模型 ID 正确、简短问答连贯；诊断评测实例在空闲时按 PID 停止，随后根脚本新实例仍运行，容器未重启。该脚本是当前诊断缓解配置，尚非 formal summary 通过回执。

同日随后按用户给定 `final-answer-extract` 正则、`group_select=-1`、`take_first`，使用评测容器原生过滤器对这批原始 700 条响应重新提取：**313/700（44.71%）**，无效提取 **10** 条，0 超时。原规则为 267/700、119 条无效，48 题由错变对、2 题由对变错；规则造成的分数变化与持续乱码的算子缓解属于不同观察。该事后重计分不请求模型、不改写原始样本，也不识别具体算子根因；配置、逐题派生结果、哈希及逐科对照见 [完整报告](../acceptance/mmlu-pro-atenoff-limit50-20261003.md)。

## 2026-10-03 独立算子定位：int32 索引写入偏移溢出

仅将黑名单改为 `nonzero_numpy,index,_index_put_impl_` 的新服务 API `352958` / EngineCore `353443`，在同样六科各 50 题、32 并发、客户端 32768 token 上限的回放中，第五科 economics 后短题正常，第六科 engineering 后短题持续乱码。300 条请求均返回；实际 oplist 中 `_index_put_impl_` 缺席而 `index_put_` 仍启用。证据：`04-runs/mmlu-corruption-noindeximpl-20261003-r2/` 和 `04-runs/mmlu-corruption-noindeximpl-service-20261003-r2/`。与仅禁用 `index_put_` 的反例互补，单独排除任一入口都不足以缓解。

独立数值测试先在空闲物理 PPU3 覆盖小状态池、连续/非连续布局、eager 与图重放、布尔清零以及 `copy_`，116 项无差异；另对词表 248094 的小批次 top-k/top-p 原生调用序列测试 sort、cumsum、scatter、softmax 和 argmax，共 48 项无差异。这些测试未覆盖大偏移边界，不能排除该条件下的错误。证据分别为 `04-runs/gdn-index-put-numeric-20261003/summary.json` 和 `04-runs/sampler-aten-numeric-20261003/summary.json`。

随后在同一容器的空闲物理 PPU3 上，以 FP32 `[8194,16,128,128]`、步长 `[262144,16384,128,1]` 和索引 `[8191,8192,8193]` 构造独立复现。目标张量前保留同一分配内的 `2^31` 个 FP32 元素，确保错误写入仍在测试自己的分配中。结果如下：

| 实现 | 索引类型 | 8191 | 8192、8193 | 前置保护区 |
|---|---|---|---|---|
| 原生 PyTorch `index_put_` | int32 | 正确 | 正确 | 未改变 |
| FlagGems `index_put_` | int32 | 正确 | 未写入目标位置 | 对应保护区被写入值 12、13 |
| FlagGems `_index_put_impl_` | int32 | 正确 | 未写入目标位置 | 同上 |
| FlagGems 上述两个入口分别测试 | int64 | 正确 | 正确 | 未改变 |

5 个测试中恰有两个 FlagGems int32 用例失败。源码生成 `cur_index * input_stride` 时没有在乘法前扩展到 int64；`8192 × 262144 = 2^31`，有符号 32 位偏移回绕到负数。索引范围检查只检查逻辑行号，无法发现乘法溢出。独立测试确认的是**索引写入算子缺陷**；实际模型缓存是否达到对应偏移、对该缺陷的定向处理是否消除乱码，仍须运行时记录及长负载对照。

复现脚本：`07-bugs/gdn-index-put-int32-boundary-20261003/repro.py`；结果：`04-runs/gdn-index-put-int32-boundary-20261003/summary.json`；日志：`04-runs/gdn-index-put-int32-boundary-controller-20261003/runner.log`。在原容器工作根以 `CUDA_VISIBLE_DEVICES=3 python3 07-bugs/gdn-index-put-int32-boundary-20261003/repro.py` 运行，脚本要求设备空闲且结果目录不存在，重复执行须选择新结果目录以保留证据。实际运行 FlagGems 包位于 `/usr/local/lib/python3.12/site-packages/flag_gems`，为非 editable 安装；`ops/index_put.py` SHA-256 `5c89d66ae2176ddc0c64d8293c3038ced6e13014e0df8d211a98bee29d2c7676`，与 checkout `80d0000d93dad55320df06687eb088a5b6dad07d` 的对应文件相同。

下一对照在 `02-issues/gdn-int64-diagnostic-20261003/sitecustomize.py` 中对进程内 `_index_put_func` 做诊断包装：记录真实 GDN shape/stride/int32 索引范围，调用相同 FlagGems 内核前将 int32 索引转换为 int64。保持上一失败实例的黑名单、图模式、设备、默认服务上下文和客户端请求配置。产品源码、安装包与根目录启动脚本均不修改；该包装仅用于验证因果，不是交付方案。新服务及回放证据分别保存在 `04-runs/mmlu-corruption-int64-service-20261003/` 和 `04-runs/mmlu-corruption-int64-20261003/`。

## 接续定位快照：2026-10-03 17:48（Asia/Shanghai）

本节按用户要求仅整理到本地项目，供另一会话接续。**没有因交接重新启动评测、修改远端文件、恢复或停止服务。** 本轮正式精度、性能、产品源码修复均未交付；整体状态仍为 `functional`。

### 当前问题分类与证据边界

| 问题 | 已观察现象 | 已验证结论 | 尚未解决/证据边界 |
|---|---|---|---|
| [002：视觉数值异常](002-visual-output-corruption.md) | 纯红图答白色，图片输出重复 `!`；视觉 attention 首次产生非有限值并扩散到 logits | 同设备同输入的 FP32 attention 对照恢复；Plugin 的 T-Head BF16 分块 FP32 OOT 缓解通过基本图像、7 项聚焦测试和两轮十并发图像诊断 | 底层 BF16 attention 内核原因仍未证明；跨模型、TP>1、高分辨率/视频未覆盖，不能与本次长文本乱码合并成同一根因 |
| [004：正式 GPQA 分数不达标](004-gpqa-strict-accuracy.md) | 198 题严格正确 39（19.70%），冻结阈值 25%；83 个严格无效，10 个终态超时，部分输出接近 2048 token 截断 | 格式、截断、超时均有样本证据；修改提示或关闭 thinking 的受限对照减少部分格式无效 | 灵活提取得到 50/198 不能替代严格指标；未证明调整后正式全量过线，也未证明该轮失败由本节索引缺陷导致 |
| MMLU-Pro 答案提取差异 | 同一批 Aten 全关的 700 条响应，原规则 267 正确/119 无效 | 用户正则 + `group_select=-1` + `take_first` 重计分为 313/700（44.71%）、10 无效、0 超时；48 题错变对、2 题对变错 | 只改变解析，没有重新推理；与运行时乱码不同，不能把所有错误都归于正则或据此宣布整体精度达到目标 |
| [006：服务崩溃](006-gdn-index-invalid-page-under-accuracy-load.md) | PPU 首报 `_index_jit_function` 的 invalid page，随后 EngineCore illegal memory access、API 500 并退出 | 首故障落在 FlagGems index JIT 设备写入；已提交 [FlagGems #6846](https://github.com/flagos-ai/FlagGems/issues/6846) | 原小形状 eager/graph 对照未复现；尚未证明与本节 `index_put` 溢出完全同因 |
| 本节：长负载后持续乱码 | 新服务初始正常，约 250–350 条长请求后独立短题持续乱码，健康接口仍 200 | 两个索引写入入口共享内核存在 int32 偏移溢出；实际 GDN 经过该入口且跨越边界；只扩展索引类型的 400 请求对照保持正常 | 尚无产品层修复；没有直接定位失效实例中被写坏的具体邻接张量，没有完成实际 BF16 布局的独立 eager/graph 边界复现 |

### 本轮最关键的新结果：400 请求定向对照完成

`2026-10-03 17:26:21–17:37:09`，诊断服务依次回放 biology、business、chemistry、computer_science、economics、engineering、health、health，每批 50 题、32 并发、客户端 `max_tokens=32768`，共 **400/400 请求成功返回**，8 次批后固定短题均连贯回答 `2+2=4`。回放日志最终为 `PASS 8-health`，Host controller PID `522914` 在 17:48 核对时已不存在。各批摘要里的 `answer_matches` 不是原生精度指标，**不能把这轮回放当成 FlagEval 得分**。

对照仅在前一失败配置 `VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy,index,_index_put_impl_` 基础上，通过一次性诊断包装把 `_index_put_func` 收到的 int32 索引转为 int64，再调用原 FlagGems 实现。`index_put_` 仍启用，有效 oplist 共 82 项，包含 `flag_gems.ops.index_put.index_put_`；attention 分派和其他 Aten 接管范围未按全关白名单缩减。相同黑名单、不加类型转换的前一实例在 engineering 后（300 题）短题乱码，本轮该节点及后续 100 题均正常。这比“全部 Aten 关闭”更直接支持索引偏移溢出为本次持续乱码的原因；仍应保留诊断插桩增加同步和分配这一局限。

### 实际 GDN 布局与临界条件修正

运行时调用栈为安装包 `vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py:1532`：`ssm_state[prefill_state_indices] = last_recurrent_state.to(ssm_state.dtype)`，进入 `flag_gems/ops/index_put.py:378` 的 `_index_put_func`。

- **实际状态是 BF16**，shape `[23275,16,128,128]`，stride `[294912,16384,128,1]`，索引 dtype 为 int32。此前从配置中 `mamba_ssm_dtype=float32` 推断运行态 FP32 的说法不适用于该服务，以实测为准；FP32 `[8194,...]` 是独立复现用例。
- 首维步长为缓存页大小，超过单槽有效元素数 `262144`。真实模型临界点不是紧凑 FP32 用例的 8192。
- 槽号 **7281** 的基址偏移 `2,147,254,272` 仍小于 `2^31`，但槽内后 **32,768** 个元素已经跨界；槽号 **7282** 的基址偏移 `2,147,549,184` 本身已超界。因此应覆盖 7281 的部分溢出和 7282 的整槽基址溢出，不能只测基址。
- 诊断记录共 36 条布局/偏移分桶变化记录，其中 12 条基址已超 int32；不是每次算子调用都记日志。记录到的最小跨界槽号为 **7415**，基址 `2,186,772,480`；最大已记录槽号 **9108**，基址 `2,686,058,496`。这证明真实工作负载会到达该缺陷区间；日志分桶不能用来反推第一条越界请求或真实全局最大值。
- 源码在乘法前没有将索引扩为 int64。边界检查仅判断逻辑索引是否在 `[0,input_shape)`，无法发现地址乘加的有符号 32 位溢出。可写映射内的错写能够污染邻近运行时张量而不触发 API 错误，符合跨请求乱码和重启恢复现象；本轮未取证实际被污染的是权重、缓存还是其他张量，不能断言具体对象。

### 当前服务、脚本和源码身份（接续前重新核对）

| 项目 | 17:48 交接状态 |
|---|---|
| Host / 模型容器 / 评测容器 | `PPU-13` / `minicpmV4.7-1B` / `flageval_llmeval-jinghao` |
| Host 与容器工作根 | 同路径 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B`，此前已核对映射；所有相对远端路径均以此为根 |
| 权重 / 服务模型名 | `/mnt/cpfs/models/MiniCPM-V-4.7/weights/1b` / `minicpm-v-4.7-1b-ppu` |
| 当前实际服务 | API PID `358882`，启动 tick `373529528`；EngineCore PID `359391`；物理 PPU2，端口 8000，`/health=200`；running/waiting 均为 0 |
| 当前模式 | `FULL_AND_PIECEWISE`，mixed PIECEWISE 与 decode FULL 各 51 个捕获形状；前缀缓存开启；服务默认上下文 `262144`，没有服务器 `--max-model-len 32768` |
| 当前黑名单 | `nonzero_numpy,index,_index_put_impl_`；无 whitelist |
| 当前诊断挂钩 | `PYTHONPATH=<root>/02-issues/gdn-int64-diagnostic-20261003`，`MINICPM_INDEX_WIDTH_DIAGNOSTIC=1`，诊断日志目录 `04-runs/mmlu-corruption-int64-service-20261003` |
| 根目录 `start-model.sh` | **与当前进程配置不同**：仍为 `VLLM_FL_FLAGOS_WHITELIST=attention_backend` 的全部 Aten 关闭缓解；SHA-256 `baee3f4658befa9598b81104d5c30fcd51601cefb2b5be5b6e1e428e7da219f9`；本轮未编辑、未从它启动当前进程 |
| 服务生命周期 | 先核对空闲 API `352958` 的命令、设备、黑名单、启动 tick `373307107`，再 TERM；核实 PID/端口释放后启动现有诊断服务。记录 `04-runs/mmlu-corruption-int64-service-20261003/previous-service.json`；容器始终运行 |
| Plugin | editable `/workspace/vllm-plugin-FL`，HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`；本轮未编辑产品源码，保留此前 2 个跟踪修改和 4 个未跟踪模型/测试文件 |
| FlagGems | 实际非 editable 安装 `/usr/local/lib/python3.12/site-packages/flag_gems`，5.3.5；checkout `/workspace/FlagGems` HEAD `80d0000d93dad55320df06687eb088a5b6dad07d`，本轮先前核对干净；未编辑或重装 |
| vLLM | 非 editable 0.24.0+empty，实际安装路径 `/usr/local/lib/python3.12/site-packages/vllm`；本轮未编辑 |

FlagGems 实际 `ops/index_put.py` 与 checkout 相同，SHA-256 `5c89d66ae2176ddc0c64d8293c3038ced6e13014e0df8d211a98bee29d2c7676`。**另有版本差异**：实际 `ops/index.py` SHA-256 `47a7108bcf8424a96651021703f8731f1866a0e2eff88a1ac647e574ccf7e61d`，checkout 为 `88faa12ea63a30663cd155f5b8097aece39e6dffe5d130897921c28f99fc36cd`；差异是 checkout 的 `tl.program_id(axis=0)` 后增加 `.to(tl.int64)`，运行安装包仍无该转换。它可能与 006 有关，但本次持续乱码的基线已禁用 `index`，不能用该差异单独解释 007。不要把 Git HEAD 等同于实际安装内容。

### 可恢复的原始证据索引

| 远端相对路径 | 内容 / SHA-256 |
|---|---|
| `07-bugs/gdn-index-put-int32-boundary-20261003/repro.py` | 独立 FP32 大偏移复现，`61adf1f0d2721f95aa0de6349bcdaea5753711df0566b0c11c4014cc2287a34c` |
| `04-runs/gdn-index-put-int32-boundary-20261003/summary.json` | 原生 int32 与两个 FlagGems int64 通过，两个 FlagGems int32 失败；`f82d96b2709a0b68181a61f1a542cf762ba17106d293918006daec4b6c340785` |
| `02-issues/gdn-int64-diagnostic-20261003/sitecustomize.py` | **远端实际执行版本**，`a79a00c2667b0a0a9ad404830fae4b4083509c17c809b4f9bbc8bbf4b08c8f75` |
| `04-runs/mmlu-corruption-int64-service-20261003/index-width-359391.jsonl` | 实际 shape/stride/dtype、调用栈及跨界索引；17:48 快照哈希 `c1c038e304a35474b7c8f2d730f9c21a0bb9887a3c47406bb631abddc54593e2`，若服务收到新请求可继续增长 |
| `04-runs/mmlu-corruption-int64-service-20261003/oplist.txt` | 82 项，`index_put_` 仍启用；17:48 哈希 `7e84e7369778c23670b295a7190fa3dcb917482c587e7b5507323d6d5cbda007` |
| `04-runs/mmlu-corruption-int64-service-20261003/server.log` | 当前运行实例日志，仍可增长；不将临时哈希当终态服务日志 |
| `04-runs/mmlu-corruption-int64-20261003/replay.log` | 8 批 400 请求完成及批后短题，`06b227f33537625f4fb01abeff67360097defa29144c9b7fae44a19a11246190` |
| `04-runs/mmlu-corruption-int64-20261003/` | `1-biology-50x32768.json` 至 `8-health-50x32768.json`、对应 `probe-after-*.json`、`replay.pid`；controller 已结束 |
| `04-runs/mmlu-corruption-noindeximpl-service-20261003-r2/server.log` | 未转换索引的失败服务，`0d224170bd8815e2b7306b2dc83096ddd801ff22262ec6de1ddace46f2e89041` |
| `04-runs/mmlu-corruption-noindeximpl-20261003-r2/replay.log` | 第 6 批后乱码反例，`28994fd53f80a3b3fff3283b3cebc0c5f147906ed529a93818dc9417ba5167a9` |
| `02-issues/mmlu-corruption-boundary/repro-v2.py`、`replay-int64.sh` | 现有诊断请求生成/回放工具；不可在已有结果目录覆盖重跑 |

独立复现最初使用物理 PPU3；进入下一次测试前仍须重新核对空闲状态。控制脚本 PID 文本曾包含字面量 `\\n`，只影响第一次结果读取，随后兼容读取取得完整 5 项测试结果；不要将读脚本的 `ValueError` 当算子失败。当前远端诊断 `sitecustomize.py` 向 stdout 打印安装信息，曾干扰 cpuinfo 子进程 JSON 解码并留下 traceback，但服务随后完成初始化及 400 请求。已有本地临时修订改成文件日志，**未部署**；下一会话若复用挂钩应先读取远端实际版本，并避免向子进程机器协议 stdout 输出。不要盲目把 `/private/tmp` 的暂存文件当权威运行版本。

### 下一会话推荐顺序与停止条件

1. 先读本节、002/004/006 及当前仓库 Skill/policy，核对现有 API PID/启动 tick/env、请求空闲和原始证据。用户偏好常驻 SSH 会话合并只读检查，减少重新连接和频繁 `./scripts/playbook`；远端变更仍遵守仓库入口和既有审批。不要重复启动已完成的 400 请求回放。
2. 在空闲独立设备，用**实际 BF16 状态布局**补齐最小边界复现：stride0 `294912`、索引 7280/7281/7282/7415/9108，比较原生、两个 FlagGems 注册入口、int32/int64，并覆盖 eager 与 graph replay、槽内尾部及同一分配内保护区。该扩展尚未创建/运行，不要标记已通过。
3. 若要更精确关联最早异常，增加时间/请求或 batch 边界记录，并检查失效前后的状态/logits；当前分桶日志不能还原第一条溢出调用。不要通过一次短题通过推断完整精度。
4. 在现有 Plugin 注册/dispatch 边界评估最小可维护缓解，或提交上游修复所需证据。只禁用 `index_put_`、只禁用 `_index_put_impl_` 均已失败；**两个同时禁用的配置尚未验证**。源头修复应在地址乘加前使用足够宽的整数，不能靠扩大模型上下文或修改答案正则处理。FlagGems/vLLM 源码修改不在当前 profile 授权内；不得把诊断 monkey patch 当最终产品实现。
5. 完成受控修复验证后，再决定是否替换根脚本的全关缓解，并按用户配置做新的原生 FlagEval 全 14 科计分。沿用用户给定最终答案提取规则，32 并发、每科 50 题、温度 1.0/top_p 0.95/top_k 20，32768 只作为客户端最大新生成 token；**不得在服务添加 `--max-model-len 32768`**。不得复用 400 回放的 `answer_matches` 充当分数。

正式 GPQA 失败、profile 图级别阻塞及性能/summary 未验收均保留。本轮未提交新 GitHub issue 或给 #6846 添加评论，未 commit/push。知识库处理维持 `needs-validation`，优先完成实际 BF16 边界与可维护修复验证，再决定是否推广。

本轮本地 `./scripts/syntax-check --offline` 中 250 个 workflow 测试（1 skipped）、6 个 operations 测试及 shell/playbook 语法检查通过；全库结构审计仍因其他模型已有 profile/architecture 证据过期报 3 个错误，并有历史布局告警。未为让检查通过而改写这些无关记录或历史哈希。

## 2026-10-03 18:07 再次只读核验

按用户“定位精度异常具体原因”的请求，重新通过 `./scripts/connectivity-check --limit PPU-13`，只读检查上述容器、运行进程、实际安装源码和原始证据；没有启动新评测、发送推理请求、修改远端文件或重启服务。容器 ID 与 `/mnt` bind mount 和记录一致，容器运行中。

- 独立边界 `summary.json`、int64 回放 `replay.log`、未转换对照 `replay.log`、诊断 `sitecustomize.py`、实际安装 `index_put.py`、根启动脚本及重计分 `summary.json` 的 SHA-256 均与上文一致。重新读取独立结果确认两个 FlagGems int32 入口将值 12/13 写进保护区，而目标槽保持 -7；原生 int32 和两个 FlagGems int64 入口均正确。
- 实际安装 `flag_gems/ops/index_put.py:121` 加载索引，`:132–136` 生成未在乘法前扩宽的 `cur_index * input_stride` 及总偏移，`:152` 用该偏移写入；模型实测调用栈明确来自 `qwen_gdn_linear_attn.py:1532` 的 GDN 状态写回。36 条运行时布局记录及哈希未变，末条仍为 BF16、stride0 294912、int32 槽号 9108，元素基址偏移 2686058496，超过有符号 int32 范围。
- 原始对照日志再次确认未转换实例在第六批、300 条请求后短题乱码；int64 实例到第八批、400 条请求均完成且批后短题连贯。诊断包装包含 CPU 取索引和额外转换分配，因此保留其同步/分配混杂因素；独立算子错写本身已确定，不将 400 请求回放解释为正式精度通过。
- 18:07:07（Asia/Shanghai）API PID 358882 / 启动 tick 373529528 与 EngineCore PID 359391 仍对应上述诊断实例，`MINICPM_INDEX_WIDTH_DIAGNOSTIC=1`，黑名单仍为 `nonzero_numpy,index,_index_put_impl_`；健康接口 200、running/waiting 均为 0。根脚本仍是全部 Aten 关闭缓解，与当前进程不同。

当前证据支持长负载持续乱码的主要原因为 FlagGems 索引写入的 int32 地址偏移溢出；不能据此合并解释早期视觉非有限值、GPQA 严格解析/截断/超时或 006 的 index JIT 崩溃。实际 BF16 布局独立 eager/graph 边界回归、失效实例具体被污染张量以及可维护产品修复仍未完成。框架和验收状态不变。

## 2026-10-03 23:55：双入口黑名单 700 题验证完成（最新状态）

用户明确要求将两个入口加入根启动脚本黑名单并使用该脚本跑 700 条 MMLU-Pro。已在原 Host/两容器映射核对后，将根脚本改为 `VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy,index,index_put_,_index_put_impl_`，unset 原白名单；空闲旧 API 358882 精确停止后，使用根脚本启动 API 362280，无 int64 诊断挂钩。容器始终运行，产品源码未修改。原脚本、旧进程身份及全部执行证据保留在 `04-runs/mmlu-pro-dualindex-final-20261003-controller/`。

32 并发、客户端 32768 token、14 科各 50 题，采用已确认的最终答案提取规则，**700/700 完整、331 正确（47.29%）、0 超时、12 无效提取**。每科原生指标与样本计数一致，全部 700 题的题号、doc/prompt 哈希与上一轮一致；同规则的 Aten 全关基线为 313/700（44.71%），本轮多 18 题，但单轮采样不能证明泛化提升。700 条后独立短题连贯、最终答案为 4，没有复现此前持续乱码。

因此，上文“两个同时禁用尚未验证”现已被本轮证据更新为**当前模型/Host/配置/负载下的已验证缓解**；先前单入口禁用失败与 FP32 独立偏移溢出证据继续保留。没有交付 FlagGems 内核修复，实际 BF16 大偏移 eager/graph 独立测试仍未完成，不能外推其他模型或执行模式。

23:55 API 362280 / 启动 tick 375624965 与评测前一致，`/health=200`、running/waiting=0，双黑名单服务继续运行。根脚本 SHA-256 `5c84a8206a0d5f6e7895887180a293ba4c7b30c7c4f1b4c4635f1a16d9b405d2`；实际服务与脚本配置一致，默认上下文 262144、前缀缓存开启、mixed PIECEWISE/decode FULL 各 51 个捕获形状。最终 oplist 80 项，两个写入入口均缺席。最终 `summary.json` SHA-256 `b10187b8855e1e6b2d707610c818daa0d4395e30e1a22ce631e1c2b72b2d32cf`，逐科结果、原始路径、控制脚本首次身份检查失败及修正、退出码和证据哈希详见 [双黑名单诊断报告](../acceptance/mmlu-pro-dualindex-limit50-20261003.md)。本轮不是正式全量验收，正式 GPQA、图级别和性能/summary 状态不变。

## 2026-10-08：双入口源码修复及 BF16 eager/graph 回归

用户要求复现 `index_put_`、`_index_put_impl_` 并提交上游 issue/PR。只在 `PPU-13` / `minicpmV4.7-1B` 的原工作根及 profile 允许的 FlagGems 安装/源码树执行，使用空闲物理 PPU3。宿主与容器根目录 device:inode 同为 `41:12343819932`，`/mnt` 为 RW bind。解释器 `/usr/local/bin/python3`，实际导入 `/usr/local/lib/python3.12/site-packages/flag_gems/__init__.py`，版本 5.3.5。

### 根因与改动

两个函数共用生成内核。原版加载的 int32 索引与 int32 步幅先发生乘法，再参与地址计算；超过 `2**31-1` 会回绕。修复在乘步幅之前扩展加载索引到 `tl.int64`，同时扩展 program offsets 及其派生坐标，使 input/index/value 地址计算保留足够位宽。没有修改 API 参数、输入索引 dtype 或 vLLM。

实际安装和 `/workspace/FlagGems/src/flag_gems/ops/index_put.py` 的 SHA-256 都从 `5c89d66ae2176ddc0c64d8293c3038ced6e13014e0df8d211a98bee29d2c7676` 变为 `ee8233b3356db377055c8453ba5b9d60d2312f7f0cc04a5fcc3c072ec441d55a`。checkout HEAD 仍为 `0958d2da98055f1e2198a56201e3eea6f7591981`；保留此前 flash 修改，未在脏 checkout 执行 pull。已与当时上游 master `c778fea4ab7825e5461d44fd5131eab2d3df9811` 比较，相同的未修复 index_put 源码仍在上游；没有整包升级或导入路径覆盖。对应原 checkout 测试文件只追加本次回归，原内容与 Git HEAD 核对后才写入；原始文件逐个备份在复现目录 `before/`。

### 独立回归

| 实际安装版本 | int32 | int64 | 合计 |
| --- | --- | --- | --- |
| 修复前、清理完善后的 v2 对照 | 8 失败 | 8 通过 | 16 项，0 跳过、0 error |
| 修复后，新进程 | 8 通过 | 8 通过 | 16 项，0 跳过、0 error |

FP32 覆盖 stride0=102400 的边界前/后行、两个入口及 `accumulate=False/True`。BF16 使用 `[9109,16,128,128]`、strides `[294912,16384,128,1]`，保留真实 GDN 步幅并缩短未访问的第一维；检查 7280、7281、7282、7415、9108，包含 7281 尾部跨界、非连续索引/values、eager 及修改 values 后两次 graph replay。每项都有同布局 native ATen 对照；分配 `2**31` 元素前缀保护区，使旧版负偏移落在同一分配中，并检查修复后预测回绕位置的哨兵。

第一次对照是 8 失败、7 通过、1 因显存跳过，未当作完整结果。增加测试 finally 清理后重新执行，得到上表无跳过结果。另尝试原 checkout 完整 `tests/test_index_put.py --quick --ref=cpu`，在收集前因新 conftest 依赖安装包不存在的 `flag_gems.cli_override` 退出 4；不是回归通过，亦未为此升级环境或伪造模块。上游匹配安装的完整模块由 CI 验证。

### 证据与上游提交

以下均位于宿主/容器同路径根 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B`：

- `07-bugs/index-put-int32-20261008/regression.py`：16 项独立回归，实际导入安装包，无 `PYTHONPATH` 覆盖。
- `07-bugs/index-put-int32-20261008/apply_candidate.py`、`applied.json`、`before/`：哈希校验、产品改动清单与备份。
- `04-runs/index-put-before-20261008-v2/{pytest.log,result.xml,summary.log}`：完整未修复负对照。
- `04-runs/index-put-after-20261008/{pytest.log,result.xml,apply.log,module-pytest.log}`：修复后结果及完整模块的收集失败原始记录。

检索发现同一账号已有同根因的 [Issue #6411](https://github.com/flagos-ai/FlagGems/issues/6411) / [PR #6413](https://github.com/flagos-ai/FlagGems/pull/6413)，因此更新这组提交而非重复开单。标题明确两个入口，公开内容无当前模型名，并提供无需权重/服务的保护区复现。PR 追加提交 `330dd99d5c661f4d6a9745b68c5dd1e30773210a`，保留旧 HEAD 为父提交并同步当前上游 master；净差异只有通用算子文件及 `tests/test_index_put.py`，新增 16 项测试。两文件本地 Black、isort、flake8 通过；CI 状态以随后核验为准，未合并。

14:19 只读检查 PPU2 原 EngineCore 宿主 PID `2271447` 未变、`/health=200`，PPU3 已释放至 1 MiB，容器保持运行。本轮没有修改启动脚本/黑名单，没有重新开启两个服务算子或重跑模型精度/性能。上文“没有交付源码修复、BF16 独立回归未完成”由本节更新；重新启用后的服务长负载与正式精度仍待验证，不能用 16 项算子测试替代。

14:21–14:22 又逐字运行公开 issue 中的 uint8 最小脚本：两个入口的未修复 int32 都得到目标 `[1,17,17]`、预测回绕保护区 `[2,3]`；int64 对照及修复后所有组合都是目标 `[1,2,3]`、保护区 `[17,17]`。driver 在哈希校验后临时切换实际安装文件，`finally` 恢复修复版，再用新进程验证修复；任务退出 0，末次安装哈希仍为 `ee8233b3356db377055c8453ba5b9d60d2312f7f0cc04a5fcc3c072ec441d55a`，源码 checkout 未回退。输出在 `04-runs/index-put-after-20261008/public-repro-{before,after,driver}.log`，脚本在同一 `07-bugs/` 目录；已将实际错写输出补充到 Issue 评论。

证据 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `07-bugs/index-put-int32-20261008/regression.py` | `c73181d28492b0dfbd781aaf78ea76c13f865ce4541c038b20142e90054a7d90` |
| `07-bugs/index-put-int32-20261008/repro_index_put_offset.py` | `cb0456ea998b6471636f259b6589367c1cf1c5663b4bbf1e6969300a83e26089` |
| `04-runs/index-put-before-20261008-v2/result.xml` | `39ed9888818fa1503ce7da7c199026792af6b32bcaa92cef32fd16975a382d2a` |
| `04-runs/index-put-after-20261008/result.xml` | `7ca5e0335c38b2dce11b2f9704d93e81a248431dcc9d1046b2a8ea3aff030472` |

本地 `./scripts/audit-workspace --json` 已运行，仓库返回 90 项既有诊断，本 profile 的诊断是 `profile revision 已变化，必须复核证据`。本轮不修改 `framework.yml` 或重标既有验收通过；该审计不等于远端算子回归结果。

### 上游 NVIDIA CI：完整模块结果

[python-op job](https://github.com/flagos-ai/FlagGems/actions/runs/37737031162/job/113179006578) 已成功。日志核对实际 checkout 是 `a98eaadcd0ad64bf3418c5974bd3ad4e2d555f9e`，即 `330dd99...` 与 `c778fea...` 的 PR merge tree；`CHANGED_FILES` 只有本次两个文件，执行的是 `tests/test_index_put.py`。

- 普通模式：收集 146 项，139 passed、7 skipped，106.42 秒。进度中跳过的是新增 FP32 大内存边界用例的后七项；这些用例在 free-memory 检查不足时显式跳过，不能计为通过。
- quick/CPU-reference 模式：收集 74 项，74 passed、0 skipped，77.12 秒。两个新增测试的参数矩阵不依赖 QUICK_MODE，16 项均包含并执行；真实 FlagGems 运算仍在 NVIDIA GPU，不能把 `--ref=cpu` 误写为仅 CPU 测试。
- 这补上了匹配上游 package 的完整测试模块验证；PPU 本地完整模块的 conftest 不匹配失败继续保留。规则 aggregate 已通过，样式检查及 unittest aggregate 当时仍待结束。
