# 2026-10-25 graph 端到端性能测量

范围：mx-101 / qwen3.8-flash，8×MetaX C550，BF16文本TP8，100000上下文，
max_num_seqs32、prefill6400，显式FULL_AND_PIECEWISE。服务为
`model-graph-performance100k-20261024`，PID2966585/start_ticks1122382130；
部署指纹7d11fb14052581da5757d4ef52b71eda288d65a91a4daf1668a7a10a23b800ef。
性能期间显式关闭prefix caching，实际命令、启动日志和原生服务观察均已绑定。
本次按用户要求只测graph，不判定业务性能达标；不声明optimized。

原生报告及完整产物校验通过：9场景×3轮，首轮预热不计摘要，后两轮均无profiler。
合计756个成功请求、0失败，输入2580480 token、输出548352 token；
其中正式测量504请求、输出365568 token。63份stdout/stderr/CSV产物逐项校验。
使用随机固定长度输入、ignore-eos、random-range-ratio0、random-prefix-len0；
并发值是客户端上限，请求数分别4/16/64，不代表32路满100K上下文容量。

以下为两轮正式测量的算术平均。P99列是“各轮P99的平均”，不是合并所有请求后重算的P99；
耗时来自原生benchmark区间，不含客户端Python进程初始化。完整逐轮指标保留在远端。

| 输入/输出token | 并发上限 | 每轮请求 | 耗时s | 输出tok/s | 平均TTFT ms | P99 TTFT ms | P99 TPOT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1024/128 | 1 | 4 | 40.95 | 12.50 | 2702.43 | 2781.80 | 59.34 |
| 1024/128 | 8 | 16 | 48.36 | 42.35 | 11011.10 | 14298.24 | 167.69 |
| 1024/128 | 32 | 64 | 133.23 | 61.53 | 27936.15 | 52722.35 | 485.80 |
| 1024/1024 | 1 | 4 | 257.13 | 15.93 | 3521.17 | 5585.99 | 59.41 |
| 1024/1024 | 8 | 16 | 188.60 | 86.89 | 12378.85 | 16032.48 | 89.94 |
| 1024/1024 | 32 | 64 | 351.68 | 186.35 | 26823.78 | 52648.18 | 167.97 |
| 8192/1024 | 1 | 4 | 300.31 | 13.64 | 14224.67 | 16031.73 | 59.56 |
| 8192/1024 | 8 | 16 | 362.35 | 45.22 | 47826.60 | 97598.05 | 163.64 |
| 8192/1024 | 32 | 64 | 1254.16 | 52.26 | 304055.24 | 518749.80 | 369.43 |

约1Hz的9958次服务遥测无采集错误，观测峰值运行32、排队30、KV占用99.8962%。
8192/1024并发上限32的预热及两轮正式测量各发生4次抢占重算，共12次；
其余场景未观测到抢占。上述延迟和吞吐完整包含重算影响，未删除请求或择轮。
该工况平均首token等待304.06秒，需结合业务请求形态评估；本次没有性能目标判定。
现场使用已冻结的默认FlagTune/MoE配置路径，未引入新的调优参数或修改产品代码。

## 原生证据

下列相对路径均位于已核实远端根`/public-flash/jinghao/qwen3.8-flash`：

| 证据 | 路径 | SHA256 |
| --- | --- | --- |
| 完整报告 | 04-runs/performance-measurement-20261024/Qwen3.8-Flash-Next/performance-graph-ninecases-20261024/benchmark-result.json | 92dc0b2c700d14739280ab52e23a80e2b82ff4fc2cb3a5037da073017c172935 |
| 原生测量校验 | 04-runs/performance-graph-ninecases-20261024/measurement-validation.json | 3fc3e14627d38dd108d0d738b81adb2ac43991d7be8e6a6780dc3b7eaf3d45a1 |
| runtime/服务绑定 | 04-runs/performance-graph-ninecases-20261024/runtime.json | b397f9c7fc8293edda8c9c4d6bc956bff4d9f39e42572579b4a1a589439b5cfb |
| 完整遥测 | 04-runs/performance-graph-ninecases-20261024/service-telemetry.jsonl | ea5d9d9ebab06c93a6ae5a86cf46e1069c80d5eabc756eff6d18eba2ee3beb3f |
| 请求原生指纹复核 | 04-runs/completion-graph-only-finalize-20261025/request-canonical-verification.json | ba24a8a43434bf40fb0eb48260ab10c7352c2fe87aa831cc5dbb8e3f6ff285a0 |

原生`perf_common.validate_report`校验器SHA256为
3a0a70a385f3a1fa9dedd487c2acc6da9eff7b5b11cba3502d23d8b546602545，
结果cases_verified9、runs_verified27、artifacts_verified63、errors空。
紧凑回执类型formal_performance在此只证明有效测量及服务绑定；无performance_targets，
不作为framework业务性能通过或optimized的依据。

## 范围变更与收尾修复

用户于2026-10-25取消eager端到端性能。旧客户端、控制器及服务已按准确进程身份停止，
部分产物保留在performance-eager-ninecases-20261024，未补跑、不提供完整模式性能比。
既有eager/graph数值一致性验证继续保留。范围变更和停止回执见[方法记录](performance-method.md)。

graph-only控制器在27轮全部完成后因包装层canonical实现错误停止：原生规则为
json.dumps(sort_keys=True, ensure_ascii=False, allow_nan=False)的默认分隔符，
包装误用了紧凑分隔符。完整请求逐字段相同，按未改动的原生framework_evidence.canonical复核后，
指纹仍为已冻结的a732ab9ca8d8782a135f85d1bccf6069a074992e6289ea1ab1896d736d2957cf；
错误算法得到c4a5d12d2c470c612af1e14b2373750bbddfc965c620456960222acb5b77bdb2。
原始报告、冻结文件、失败控制器均未改写，未重新执行性能测量。

接续脚本03-acceptance/finalize-graph-only-20261025.py，SHA256
bac45b4a96e01eaf72fb841f1de9bd96a6d1bd61b3833e88ea1a87c66a122c3e，
只复核已有产物并执行最终脚本交付。性能后安装组件、编译二进制、Git完整差异/新增集合
再次一致；模型五个配置/tokenizer文件及131分片索引/大小一致，未声称分片内容哈希验证。
