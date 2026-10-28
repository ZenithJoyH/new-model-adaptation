# 适配验收索引

记录当前 framework profile 的执行模式、小批量验证、正式精度、性能、证据汇总、最终启动
脚本和复盘。文件存在不代表已经执行或通过。

- [2026-10-10 DSpark 双卡验证](dspark-tp2-validation-2026-10-10.md)：当前 GPU6/7、TP2、
  64 序列、默认 batch token 8192 与模型长度 262144；图捕获及 73/73 功能验证通过，非正式精度/性能。
- [2026-10-09 35B-A3B DSpark 服务验证](dspark-service-validation-2026-10-09.md)：
  当前 1B DSpark 容器中 TP1 eager 9/9、FULL_AND_PIECEWISE 19/19，草稿实际参与解码；
  十客户端排队，非正式精度/性能或完整适配验收。
- [2026-10-08 双模型共用代码验证](unified-code-validation-2026-10-08.md)：新容器安装
  同一 Plugin，双模型各 TP2 eager 6/6、FULL_AND_PIECEWISE 19/19，不设置旧 attention 黑名单。
  功能回归通过，未运行正式精度/性能；以下各轮记录及 profile 判断保留为历史证据。
- [2026-09-30 历史端口 8019 服务验证](service-validation-2026-09-30.md)：先前脚本的
  重启、图捕获、6/6 图文和 10/10 十并发功能回归。
- [2026-09-30 已安装 Plugin 的服务验证](service-validation-installed-plugin-2026-09-30.md)：
  当时端口 8021 脚本的图捕获、6/6 图文和 10/10 十并发回归。
- [2026-10-01 启动脚本精简验证](launcher-simplification-2026-10-01.md)：
  上一版脚本的实际启动、图捕获和 6/6 图文回归。
- [2026-10-01 用户新脚本验证](user-revised-launcher-validation-2026-10-01.md)：
  当前原文脚本的实际启动、262,144 上下文配置和 6/6 图文回归。

2026-09-28：TP2 `FULL_DECODE_ONLY` 的最小文本、图像和变输入 replay 已通过；
用户随后选定 `FULL_AND_PIECEWISE`，其显式启动日志已确认 mixed prefill/decode
分段图 5/5、纯 decode 全图 4/4。当日堡垒机短暂返回 `no available gateway`；
2026-09-30 已恢复连接并完成当时脚本的 API 与图文验证；2026-10-01 验证了精简脚本及用户再改的脚本。该模式的分段 prefill 不符合 profile 对 full 图的
首选或 decode-full 回退的正式验收条件；不据此通过 `execution-mode`、sanity、
accuracy 或 performance。原始日志位于
`H100-149:/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/graph-full-piecewise-tp2-seqs10-cacheids-20260928/server.log`。
