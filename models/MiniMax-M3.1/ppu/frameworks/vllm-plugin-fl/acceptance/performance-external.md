# 用户提供的性能结果核验

2026-10-08，在 PPU-07 只读检查用户提供的 `/mnt/nfs/users/jinghao/minimaxM3.1/test/perf_test/benchmark_results/MiniMax-M3.1`，并与同级上层目录的 `perf.log` 逐轮核对。测试日志日期为 2026-10-05，CSV 批次标识为 `20261005_091237`；日志未注明时区。本次未发出推理请求、重新评测、修改文件或停启服务。

## 已核验结果

三个场景均为输出 1024 token、最大并发 64、每轮 128 个请求，运行三轮并排除第一轮，SUMMARY 为后两轮各指标的算术平均。吞吐是整个服务的汇总值，不是单请求或单卡值。

| 输入 token | 输出吞吐 token/s | 总吞吐 token/s | 平均 TTFT 秒 | P99 TTFT 秒 | 平均 TPOT 毫秒 | 平均每轮耗时秒 |
|---:|---:|---:|---:|---:|---:|---:|
| 4096 | 113.97 | 569.83 | 10.01109 | 31.22951 | 551.12 | 1150.10 |
| 16384 | 98.62 | 1676.63 | 63.76699 | 605.99717 | 573.25 | 1328.99 |
| 32768 | 170.02 | 5610.64 | 188.16143 | 367.65769 | 152.47 | 770.92 |

核验范围及结果：

- 三场景全部九轮均记录成功请求 128、失败请求 0；合计 1152 个请求（包括被排除的三轮），计入汇总的六轮合计 768 个请求。
- 每轮总输出为 `128 × 1024 = 131072` token，输入总数分别为 524288、2097152、4194304，均与指定长度及请求数一致。
- CSV 每轮的全部 17 个数值指标与 `perf.log` 对应输出一致，SUMMARY 与后两轮平均一致，按显示精度容许 0.011 的舍入误差；数值均有限且非负。
- 日志中九轮客户端配置均为 `profile=False`、`random_range_ratio='0.0'`、`random_prefix_len=0`、`temperature=None`、`save_result=False`、`max_concurrency=64`。客户端未指定 temperature，日志提示由服务端默认值决定，不能套用外部 GPQA 的采样配置。
- 运行入口为 `vllm bench serve`，backend `vllm`，endpoint `/v1/completions`，本机端口 8025，模型名 `MiniMax-M3.1`，tokenizer 为 `/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`；random 数据集、`--ignore-eos`。该配置来自日志中的实际命令及参数打印。

32K 场景的输出吞吐高于 4K/16K，平均 TPOT 也明显降低；16K 场景 P99 TTFT 约 606 秒。这些是已测现象。现有产物没有服务端调度、缓存、资源和同期负载证据，不能判断差异原因或据此宣称某个配置优化成功。没有提供对照基线或性能通过阈值。

## 产物引用

以下文件均留在 PPU-07；本地仅保存本摘要。

| 绝对路径 | SHA-256 |
|---|---|
| `/mnt/nfs/users/jinghao/minimaxM3.1/test/perf_test/benchmark_results/MiniMax-M3.1/MiniMax-M3.1_4096in_1024out_c64_n128_20261005_091237.csv` | `b9e6fe3a358454b1b9ef3417a33c340b83bf6f63cec76da19c60e6401c16b235` |
| `/mnt/nfs/users/jinghao/minimaxM3.1/test/perf_test/benchmark_results/MiniMax-M3.1/MiniMax-M3.1_16384in_1024out_c64_n128_20261005_091237.csv` | `a3ad146689664fab9c4c95b4f8defee5aacc477bb5c394d8d3767e42028c3ca1` |
| `/mnt/nfs/users/jinghao/minimaxM3.1/test/perf_test/benchmark_results/MiniMax-M3.1/MiniMax-M3.1_32768in_1024out_c64_n128_20261005_091237.csv` | `0027fed4ac2180d47a12702a302be8f638219be340c0e8dcb282c3f6353635c2` |
| `/mnt/nfs/users/jinghao/minimaxM3.1/test/perf_test/perf.log` | `860474d623fd9450795074af6a52de174056a56bb7498d834b691c4bc6c8f021` |
| `/mnt/nfs/users/jinghao/minimaxM3.1/test/perf_test/vllm_perf.py`（核验时版本） | `a4a6af6103199ee33b495c76377782536a96b659bf315dbf116a3c1b7cdc66ea` |

## 验收范围与状态

已核验用户性能数据的数值一致性，性能结果不再记为“无数据”。目录中仅三个 CSV，未包含当前项目 schema 1 的 `benchmark-result.json`；上层脚本是独立旧实现，未提供当前原生 `perf_acceptance.py` 回执、runtime 配置或历史服务实例绑定。因此无法调用当前 `perf_common.validate_report` 对完整原生报告执行验证，也不将 CSV 标签 `SUCCESS` 转写为正式性能验收通过。

脚本头部注释建议 `--no-enable-prefix-caching`，不能证明被测服务实际关闭了 prefix cache；客户端 `random_prefix_len=0` 同样不能替代服务端证据。现有文件也未绑定当时的源码 revision/diff、graph 模式、设备拓扑、service_instance_id 或精度到性能的服务切换。当前正在运行的服务状态不能追溯证明 2026-10-05 的测试条件。

`framework.yml` 的 `external_performance` 记录本次只读核验，原生 `workflow.acceptance.substeps.performance` 保持 `not_started`，表示原生正式步骤尚无有效回执，并非用户没有测试性能。2026-10-08 用户确认已提供精度和性能结果并完成适配，项目 `project_completion.status=complete`；本批性能结果由用户接受。框架能力成熟度仍为 `functional`，原生证据限制如上保留；项目完成结论及汇总见[适配总结](adaptation-summary.md)。历史文件未迁移或改写。

本地 YAML、证据路径及状态检查通过，`git diff --check` 通过。`./scripts/audit-workspace --repository-only` 仍报 12 项 profile revision 错误、78 项待复核；本工作区 v4 与当前 profile v6 的版本差异未改写，未通过刷新历史绑定消除错误。
