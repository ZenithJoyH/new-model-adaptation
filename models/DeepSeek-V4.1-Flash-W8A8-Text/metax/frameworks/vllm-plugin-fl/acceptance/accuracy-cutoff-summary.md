# GSM8K末题计错汇总

2026-11-05，用户明确要求“先直接把最后一道题目判错吧，然后汇总下得分情况”。本记录是该指定口径的独立汇总；保留原始完整运行及缓存，不将人工截止结果写成原生完整评测通过。

| 项目 | 结果 |
| --- | --- |
| 预定指标 | `exact_match,flexible-extract` |
| 完整分母 | 1319题 |
| 已缓存回答 | 1318份，均非空，无`<TIMEOUT>`标记 |
| 正确 | 1171题 |
| 已返回回答中按原生规则计错 | 147题 |
| 用户指定计错 | 1题，doc_id=1183（苹果题，参考答案11） |
| 错误合计 | 148题 |
| 得分 | **1171/1319 = 88.7793783169%** |
| 原门槛 | 95%，未达到，差6.2206个百分点 |
| 附带原生strict-match指标 | 0/1319，非预定验收指标；未修改其过滤规则 |

使用FlagEval容器中原任务、原生`hash_args`、原生`apply_filters`与`process_results`。以只读SQLite事务冻结1318条原始缓存，全部与原1319题请求键一一匹配，无额外缓存键，唯一缺失项为1183；先前进度条停在1317不代表缓存仅有1317份回答。仅为该缺失项在独立评分输入中添加显式人工计错标记，原缓存、原回答、题目、目标、评分器和0.95门槛均未改动，没有重新发送推理请求。两套filter各覆盖完整1319个唯一题号；独立读取快照、逐题文件及哈希后重算分子/分母，与汇总一致。147是原评分规则下的错误数，尚未逐题区分数学错误与答案提取/格式问题。

数据canonical SHA-256仍为`32c548f08195e19e33408b844dd7be6aa4bcae457d957bc05909ff4bd4a00595`。配置SHA-256仍为`5a4518ed89484afd983962a6e2e42738368b374b356d5583339046d7f486d3f5`；生成参数仍为thinking/high、temperature0、top_p1、max_gen32768、seed20261104、C8。运行使用v22共享启动脚本，FULL、TP8/PP2、async ON、prefix ON，Plugin v35 / FGV v43 / FG clone v3。

全部证据在批准根`/public-flash/jinghao/deepseekV4.1`：

- `04-runs/user-cutoff-score-v1-20261105/result.json`，SHA-256 `6518680d3b514df56abfaeeb985d8b6674b6a76a9e86974f830374e593199674`。
- 同目录`cache-snapshot.json`，SHA-256 `9fecbf191d5a27ddca30223242e1b2e4668eafc3a3aef4fd859aea19585e6dad`，保留原缓存BLOB；`scored-samples.jsonl`，SHA-256 `08f8c8ce030b9330052df0f976c42e1b092d2d9fbd56f2bc873d491e729a9712`，保留全部逐题及人工标记。
- 同目录保留授权、原配置、任务YAML与原始API日志快照；生成与评分控制在`03-acceptance/user-cutoff-score-v1-20261105/`。
- `03-acceptance/user-cutoff-stop-v1-20261105/result.json`记录仅向本轮CPU评测客户端发送SIGTERM。精确helper命名空间、脚本/config argv、PID/start_ticks/cmdline SHA及pidfd均核验。原生watcher在`04-runs/v41-gsm8k-full-v2-20261105/native-exit-status.json`保留退出143终态（2026-11-05T01:45:27.771823+00:00），evaluator源码前后一致，模型health200；没有停止模型服务或容器。

半小时结果检查已删除，聊天及证据保留。正式性能尚未测量；本分数未达原门槛，公开固定依赖、高精度质量比较和最终源码审查也仍未完成，不提升framework验收或整体适配状态。
