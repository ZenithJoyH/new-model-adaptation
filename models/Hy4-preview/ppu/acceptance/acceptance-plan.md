# 适配验收计划与证据

本轮为2026-09-04 PPU-07/hy4已修复W8A8服务，FlagGems842b19d、插件恢复完整批次调用。
除执行模式验收外，后续验收全部使用已通过的 `FULL_DECODE_ONLY` graph 配置。
完整身份、配置、命令与逐项证据见 [精度验收汇总](accuracy-results.md)。
前置检查曾因本索引缺失报错；已用规定adapt-model助手创建并补齐，不据文件存在推断验收通过。

## 4.1 执行模式验收

- [x] `eager` 模式完整服务可以运行
- [x] `graph` capture/replay 模式完整服务可以运行
- 2026-09-07 已在当前 vLLM / FlagGems / Plugin revision 与问题 016 的安全 blacklist 下重验：
  eager 与 graph 固定请求均返回 42；graph 完成 51/51 capture。当前证据见
  [执行模式与 sanity 结果](execution-mode-and-sanity-20260907.md)。
- 相同6354-token用例17+25均返回42、finish_reason=stop，graph51/51捕获；证据远端eager-large.json、graph-large.json。
- 命令与结果见 [精度验收汇总](accuracy-results.md)；TP16、100K、8010，原 graph 启动脚本不改。

## 4.2 八并发小批量精度与性能验证

- [x] 固定简单请求全部正确：两轮算术各8/8，数字序列8/8
- [x] 无错误、超时；持续decode sanity通过，初始短请求prefill有波动且已单独记录
- 2026-09-07 当前 graph 实例重验为 8/8、全部 stop、24.9877 秒、0 抢占且无 fatal 日志；
  该结果只作为正式 accuracy 前置 sanity。
- 并发数：8
- 请求集：i=1..8，Return only the integer: i +17，期望18..25。温度0、seed42、no_think、最多128token。
- 要求8/8、无HTTP/解析错误/超时、正常stop；180秒为硬超时，实际延迟/吞吐/资源曲线仍需复核。
- 证据计划：远端graph-sanity.json，含每条原始响应、时间、输出token及5秒PPU利用率/显存采样。
- 补充graph-sequence.json：8条各32个整数、每条64completion tokens，总512token，
  34.549秒，含prefill整体14.819 token/s；服务增量ITL504个间隔、总90.642秒，均值0.17985秒。
  0抢占、全部stop且正确。prefill开销仍存在，不声称平台性能已优化。

## 4.3 全量精度测试

2026-09-07更新：c32正式轮及12题定向重试已完成。最终result/sample覆盖198个唯一题目，strict 178/198（89.8990%），flexible 97/198（48.9899%）。重试恢复6题，剩余`doc_id` 15、71、81、88、145、147仍在40K上限后没有最终答案，runner记为`<TIMEOUT>`/refusal；实际HTTP超时、服务error/abort均为0。返回码1是`allow_timeouts=false`的结果校验失败。因仍有6个无效响应，正式精度验收未通过，不启动性能验收；详见[精度验收汇总](accuracy-results.md)。

- [x] 部署规定 `test/Accuracy_test/llmrun.py` 与同目录score_progress.py，未修改runner
- [x] 已核实 FlagEval v1 容器运行
- [x] 初始 `--preflight-only` 通过（正式启动前再次执行）
- [x] 样本数、输出文件、指标和通过标准已核实（结果为未通过）
- 最新正式配置：`llm_config-ppu07-fixed-c32-thinking40k-20260906.json`；32并发、198题、thinking/high、40000 token、timeout43200秒。
- 要求198唯一题、正式result/sample完整、0真实timeout/None/无效响应；分别报告strict/flexible。
- 用户未指定数值精度达标线，不把历史90.9091%擅自定为门槛；报告全量实际分数，不自行声明业务精度通过。
- 不复用旧 cache/output；阶段计分仅供诊断，最终以完整 result/sample 和正式契约为准。

## 4.4 正式性能与通信测试

- [x] 全量精度按用户指定 87% 业务阈值通过（strict 90.91%；保留 1 条 timeout 与原生 receipt 缺失限制）
- [ ] 使用 `test/perf_test/` 完成性能测试；当前性能专用 graph 服务正在启动
- [ ] 需要时使用 `test/nccl_test/` 完成通信验证
- 当前选择正式性能验收；使用 prefix-cache-disabled 独立服务、默认五工况、3 轮且首轮 warmup。
  启动与结果见 [Plugin 2fa 性能测试记录](performance-plugin-2fa-indexoff-20260911.md)。

## 4.5 验收证据完整性

- 证据见本轮报告，原始输出保存在 PPU-07 NFS 目录与评测容器本地 SQLite，本地仓库只保存 Markdown 结论和准确路径。
- 未完成：仍有6个生成上限无效响应；不宣称整体 optimized 或验收闭环完成。
