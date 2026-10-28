# 性能测量计划（尚未执行）

操作为项目本地performance/full-suite，范围仍为两机16×C550、BF16文本、TP8/PP2、
65536上下文及已验full-and-piecewise。须先等当前GPQA198完整原生结果达到0.88并通过
accuracy gate，随后只重启本任务服务，通过同一SHA的start-model.sh --performance关闭
两机prefix caching。模型、代码、拓扑、图模式及其他基础参数不变。

计划版本v14包含以下完整六场景，按表顺序执行；输入/输出均为token数量。

| 输入 | 输出 | 客户端并发上限 | 每轮请求数 |
|---:|---:|---:|---:|
| 1024 | 128 | 1 | 4 |
| 1024 | 128 | 4 | 8 |
| 1024 | 128 | 8 | 16 |
| 8192 | 1024 | 1 | 4 |
| 8192 | 1024 | 4 | 8 |
| 8192 | 1024 | 8 | 16 |

每场景3轮（显式1轮warmup＋2轮无profiler测量），不选择性丢弃慢轮次；warmup失败同样
不能通过。最大单请求9216<65536，8路token预算73728低于当前graph KV420810，性能服务
启动后仍须重新核实实际容量和进程/监听/双机参与绑定。冻结实际request/runtime后先dry-run，
核对再只移除dry-run。使用独立冻结native-tools-pipeline-v1中的原始vLLM runner，
保留用户本地perf_common的其他修改，不将未审查的新版本混入当前验收。

测量请求计划使用当前tokenizer、served ID glm5.3-flash及/v1/completions，统计吞吐和
原生TTFT/TPOT/ITL。每轮仅4/8/16条请求，属于初步性能数据，不视作SLA尾延迟证明。
输出、请求/token数及全部原始JSON/CSV/stdout须由原生validate_report核验。

用户尚未冻结业务性能目标。本计划仅测量，不补造零门槛目标，不据正常退出将framework
performance或optimized标记通过；正式业务目标验收仍待另行冻结。性能后恢复普通
prefix开启启动，再完成镜像新容器验证及最终服务恢复。当前没有性能通过结论。
