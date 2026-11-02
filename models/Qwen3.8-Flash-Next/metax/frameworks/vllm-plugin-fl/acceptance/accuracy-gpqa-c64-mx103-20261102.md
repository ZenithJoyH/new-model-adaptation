# mx-103 GPQA Diamond198：客户端并发64（进行中）

2026-11-02，用户要求先停止ERQA，优先以64并发执行GPQA精度。使用项目本地
inference-accuracy-evaluation Skill 的 formal-full 操作；本轮没有更改产品源码、
服务启动脚本、采样/生成预算或质量阈值，没有停止任何其他任务或适配容器。

## ERQA停止及结果保留

旧运行 `/public-flash/jinghao/qwen3.8-flash/04-runs/full-accuracy-mx103-20261101-kv6g-b2048`
在224/400个唯一题完成时由用户主动停止，不能视为全量精度结果。
按容器归属、start_ticks、cmdline SHA256和pidfd核对后，仅终止旧ERQA客户端、
转发器、顺序控制器及等待它的一次性收尾进程，防止自动启动旧并发2 GPQA。
已确认原服务running/waiting均归零；原始请求、响应、日志和已完成题目未改写。
adapter短暂保留的Z状态进程表项不是活动评测。
切换证据为新运行根的 `switch-from-erqa.json`，旧根另保留
`user-stop-20261102-c64.json`。旧状态文件可能仍显示历史running/waiting，不能据此恢复。

## 本轮身份与配置

Host为mx-103 / bm-zksg-wx-zone1-d-mc550-64g-2-103。
模型容器qwen3.8-flash，ID
`31022d2372f941b64ad4da9c7cde8d1be5aacbaff650857e49e8f4e6d1201d89`。
批准根 `/public-flash/jinghao/qwen3.8-flash`，三个参与容器的同路径RW映射已核验。
评测容器沿用qwen38-mx103-llmeval-20261031；
没有选择第二套源码或使用PYTHONPATH。

复用现有服务实例 `full-accuracy-mx103-20261101-kv6g-b2048`，API host PID2121037 /
container PID1704721，start_ticks1191901738，命令SHA
`657f43b4d606f8a21550a5e22e613927a50167ad28f46caa7133fdfd5dcf8ec5`。
TP8、FULL_AND_PIECEWISE、100K、每卡KV6GiB、prefill2048、image16/video0、
prefix开启不变。共享启动脚本SHA
`5c5bd7ce11d468e1606399d054c04fd32cd179bc13fea6b66d78f02d999216ab`。

客户端并发64；服务 `max-num-seqs=32` 未改变，因此不能声称引擎同时执行64路。
全量198题、strict-match≥88%（至少175/198）、xhigh、最大生成96000、
temperature1/top_p0.95/top_k20、单请求超时21600秒、API/eval重试0。
超时计错，保留198分母；不使用ERQA部分结果或历史mx-101成绩替代本轮结果。
高并发长推理容量尚未通过本轮全量验证；保留实际排队、抢占及错误，不自动缩并发或重试。

## 证据与启动验证

新运行ID `gpqa-full198-c64-mx103-20261102`。
运行根 `/public-flash/jinghao/qwen3.8-flash/04-runs/gpqa-full198-c64-mx103-20261102`；
工具/冻结配置在对应 `03-acceptance/gpqa-full198-c64-mx103-20261102`。
配置 `gpqa-config.json` SHA
`7a598f8eb157486f3caeecbfa586895dae71a7daa9823f4613be91e3250b182a`。
Skill bundle SHA
`a1c3dce2e0dde6304b95d5a7ee0d54bf436dd4fab94ed4719c377737122fe6a2`。

4个安装组件的源码快照与旧评测开始时一致；新的服务observation已核验精确实例与8000监听。
原生预检通过并确认数据集198题；2026-11-02 10:04 CST启动正式请求，缓存命中0。
控制器host PID3733079，start_ticks1200576738，命令SHA
`6794eb3dd40dc712d1a8fc7d9f0f1c8e57dce5b03bc797ba415b52678145615c`。
10:07 CST观察到running32/waiting32、无抢占、持续生成约170 tokens/s，GPU瞬时利用率47–49%；
这是启动观察，不是正式性能测量或完整精度通过。暂未有已完成题目/全量精度分数。

既有原生runner和评分器保持不变；独立离线校验包装仅适配新路径、并发64断言和
UTF-8文件逐行读取，避免JSON字符串内Unicode分隔符导致错误拆行。
控制器将在原生客户端终态后调用原生完整性/逐题指标校验，并核对来源前后快照，
保存 `gpqa-full-verification.json`、`full-verification.json`。
未完成前不提升framework.yml状态；半小时只读汇报任务已改为跟踪本轮GPQA64。
