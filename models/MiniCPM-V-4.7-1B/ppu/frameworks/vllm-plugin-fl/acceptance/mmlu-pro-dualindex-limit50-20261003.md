# MMLU-Pro 700 题：双索引写入黑名单诊断

## 范围和配置

用户明确要求把 `index_put_` 和 `_index_put_impl_` 加入根启动脚本黑名单，使用该脚本启动并评测 700 条 MMLU-Pro。目标为 `PPU-13` / 模型容器 `minicpmV4.7-1B` / 评测容器 `flageval_llmeval-jinghao`，物理 PPU2，TP1/BF16。Host 和两容器的已核实同路径工作根均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B`，设备号/inode `41:12343819932`；下文相对远端路径均以此为根。

根 `start-model.sh` 从全部 Aten 关闭白名单改为 `VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy,index,index_put_,_index_put_impl_`，显式 unset 原白名单，日志改为 `04-runs/service-dualindex-*.log`。脚本 SHA-256 为 `5c84a8206a0d5f6e7895887180a293ba4c7b30c7c4f1b4c4635f1a16d9b405d2`。保留 `FULL_AND_PIECEWISE`、前缀缓存、默认服务端上下文，不增加 `--max-model-len`。原脚本保存在 `04-runs/mmlu-pro-dualindex-final-20261003-controller/start-model-before.sh`。

核对旧诊断 API PID 358882 / 启动 tick 373529528 及 running/waiting 均为 0 后精确 TERM，确认 API、EngineCore 和端口释放，再通过根脚本启动 API PID 362280。新进程没有 int64 诊断挂钩或 whitelist；有效 oplist 不含两个 FlagGems 写入入口，其他算子仍启用。容器保持运行，vLLM、FlagGems、Plugin 产品源码未修改。完整进程身份、oplist、启动前短题和生命周期记录在上述 controller 目录。

评测为用户指定的限定样本诊断，**不是 formal-full 或正式精度通过回执**。沿用原生 runner、14 科每科 50 题、32 并发、600 秒请求超时、API/评测重试均为 0，`temperature=1.0,top_p=0.95,top_k=20,max_gen_toks=32768`。32768 仅约束客户端新生成 token。采用此前用户指定的 `final-answer-extract` 正则、`group_select=-1` 和 `take_first`，本轮直接在原生评测任务中计分。新任务仅调整任务名和过滤器，保留原生数据集、5-shot 提示和计分方法。

- 冻结配置：`03-acceptance/mmlu-pro-dualindex-final-20261003/config.json`，SHA-256 `0b93c98d98c44ec89f07b78196f6db98fe0d012809870e888450717c2c1a0ed6`。
- 任务定义、映射及固定 runner：同配置目录下 `tasks/`、`task-map.json`、`runner/`；完整输入哈希保存在 controller 的 `frozen-inputs.json`。
- 独立响应缓存：`06-cache/mmlu-pro-dualindex-final-20261003/`。首科确认 0 条缓存命中，50 条真实请求。
- 原始结果根：`04-runs/minicpm-v-4.7-1b-ppu/mmlu-pro-dualindex-final-20261003/`。
- 控制/日志根：`04-runs/mmlu-pro-dualindex-final-20261003-controller/`，包含 `status.json`、`preflight.log`、`runner.log`、运行进程身份及最终退出信息。

原生预检通过后于 2026-10-03 23:17（Asia/Shanghai）启动评测。第一次控制脚本的宽松进程匹配将自身检查命令误识别为服务，在发出推理请求或启动评测前失败；保留原版本和日志，收紧为命令前缀匹配后启动 v2 控制进程。模型服务没有因此重启，评测只启动一次。

## 最终结果（2026-10-03 23:55 核验）

原生 runner 于 23:54:02 报告 `All tasks completed successfully`，退出码 0；controller 于 23:54:03 完成批后短题，评测及批后检查约 36 分 49 秒。14 科均有 50 个唯一题号，700/700 条样本完整，逐科原生指标与样本计数一致。全部 700 题的题号、doc hash 和 prompt hash 与上一轮 Aten 全关基线一致。结果为 **331/700（47.29%）**、**0 超时**、**12 条无效提取**；无效样本保留在分母中。

| 学科 | 正确/50 | 得分 | 无效提取 | 超时 |
|---|---:|---:|---:|---:|
| biology | 34 | 68% | 0 | 0 |
| business | 23 | 46% | 1 | 0 |
| chemistry | 30 | 60% | 0 | 0 |
| computer_science | 22 | 44% | 2 | 0 |
| economics | 30 | 60% | 0 | 0 |
| engineering | 25 | 50% | 1 | 0 |
| health | 15 | 30% | 1 | 0 |
| history | 12 | 24% | 1 | 0 |
| law | 17 | 34% | 1 | 0 |
| math | 39 | 78% | 0 | 0 |
| other | 17 | 34% | 3 | 0 |
| philosophy | 17 | 34% | 2 | 0 |
| physics | 30 | 60% | 0 | 0 |
| psychology | 20 | 40% | 0 | 0 |
| **合计** | **331/700** | **47.29%** | **12** | **0** |

同一最终答案提取规则下，上轮 Aten 全关为 313/700（44.71%），本轮多答对 18 题、增加 2.57 个百分点；这是单轮采样结果的观察，不是统计显著性或泛化精度提升结论。两轮算子接管范围不同，不能把分数差异全部归因于两个入口。

本轮没有复现此前 300 题左右出现的跨请求持续乱码。700 条后独立 `2+2` 响应推理连贯并以 `4` 结束；`probe-after.json` SHA-256 `946a121b4c10754e94c1743a7ec5896cb83467520e8bdf10179e8b7735185064`。23:55 核对 API PID 362280 / 启动 tick 375624965 与评测前一致，`/health=200`、running/waiting 均为 0。服务按根脚本的双黑名单配置继续运行，未恢复旧白名单或 int64 挂钩。最终有效 oplist 80 项，两个索引写入入口均缺席；`oplist-after.txt` SHA-256 `65b3a194a6f3176b28c1449804bc9902d7404572b73ae01c52ea5c6291d23554`。

最终摘要 `04-runs/mmlu-pro-dualindex-final-20261003-controller/summary.json`，SHA-256 `b10187b8855e1e6b2d707610c818daa0d4395e30e1a22ce631e1c2b72b2d32cf`，包含所有 14 组原始样本/结果文件的路径与哈希、逐科核验及最后服务身份。固定输入和根脚本哈希均未变化。runner 日志 SHA-256 `b7ae07f2d3f940ae4184f5cf312c725b05892a6e02bb75b49f9bcaf261827dfd`；服务日志为 `04-runs/service-dualindex-20261003T151400Z-362274.log`，服务仍运行，日志可继续增长。服务实际 `max_seq_len=262144`，mixed PIECEWISE 和 decode FULL 各捕获 51 个形状。

双入口同时禁用由“未验证”更新为当前模型、Host、图模式和 700 题负载下的**已验证缓解**。未修改算子产品源码，实际 BF16 独立边界回归仍未补齐；本轮不覆盖其他模型、设备、TP 拓扑或图模式。正式 GPQA 失败和既有图级别、性能、summary 验收限制不变。

本地结构审计没有本次 PPU 记录的报错；全库仍存在其他已有模型/profile 证据过期问题，未改写无关历史哈希。
