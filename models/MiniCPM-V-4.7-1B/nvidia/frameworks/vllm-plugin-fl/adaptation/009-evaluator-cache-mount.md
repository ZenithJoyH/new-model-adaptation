# 009：精度评测响应缓存挂载消失

## 范围与失败证据

2026-10-09，H100-149 的 DSpark / Plugin 0.4 精度重测采用客户端并发 128，
服务端 max_num_seqs=4；服务模式 FULL_AND_PIECEWISE。评测容器
`minicpmv47-dspark-eval-20261008-r2b` 使用既有 Docker 本地 XFS 缓存卷的新子目录。
开始时 mountinfo、SQLite 写入/重新打开读取通过，样本清单与上轮一致。

北京时间 11:21:45，原生 sqlitedict 记录
`sqlite3.OperationalError: attempt to write a readonly database`。
随后容器进程 mountinfo 不再包含响应缓存挂载，原缓存路径不存在；
Docker inspect 仍声明该卷挂载，容器仍运行，restart_count=0。
lm-eval 的开放数据库 FD 路径已变为脱离挂载后的卷内相对根路径。
这是已核实的挂载/缓存写入故障；触发卸载的主体和根因尚未确认。

失败时模型服务 health=200，仍在生成，错误/中止计数为 0。
故障不能归因于模型精度、Plugin 或 CUDA；当轮没有有效最终分数。
相同症状曾出现在 [此前评测](../acceptance/dspark-math500-mmlu-pro-20261008.md)
的 tmpfs 缓存，本轮 XFS 卷复现说明更换介质没有消除挂载消失风险。

## 保全、停止与缓解

已批准宿主根：`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`。
失败证据位于 `04-runs/dspark-eval-c128-plugin04-20261009/`：
`cache-failure.json`、`container-at-cache-failure.json`、原生日志、
`failed-cache-fd-3.raw` 和终态 `final-verification.json`。
保全开放 FD 的数据库原始字节后，只终止本轮 controller 3987 与 lm-eval 3996；
两者已退出，相关父进程为僵尸状态。模型 API/Engine 未重启，队列清空，health=200。
失败样本与缓存不作为重跑的响应来源。

缓解方案是新建无 GPU 的独立 FlagEval 容器
`minicpmv47-dspark-eval-c128-plugin04-20261009`，ID
`f8835d7d297d6af77b05d5a5ab00352c453ec9e1a776440a8c48dc095913dcea`，
沿用同一已存在镜像 `sha256:d6faaf5e502450346771e0b5387db22254b2cce6dff0a35a26ebce0bbf29a096`。
仅分别映射批准根内 `03-acceptance`、`04-runs`，源数据单独只读映射；
容器 `/work/06-cache/<新运行>/responses` 位于本地 overlay，
没有嵌套响应缓存子挂载。每个绑定目录均核对宿主与容器设备/inode。
所有新缓存仍在批准的容器 `/work/06-cache` 内，完成后 backup 到宿主结果目录。
未修改评测库、评分、模型服务、宿主挂载配置或旧容器。

该方案属于缓存隔离缓解，不是卸载根因修复；新轮完整结果见
[128 并发测量记录](../acceptance/dspark-c128-plugin04-20261009.md)。

新轮已完整完成 500 + 700 题，全部样本、原生评分与响应缓存导出核对通过。
约 103.15 分钟内 observer 没有缓存读取或服务错误，最终 15 个 task 共 1200 条缓存，
缓存仍位于容器本地 overlay，未复现缓存写入故障；服务和容器保持运行。
这支持本轮隔离缓解有效，挂载卸载的根因仍未确认。
