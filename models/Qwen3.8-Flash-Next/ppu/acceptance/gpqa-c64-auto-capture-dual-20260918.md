# GPQA c64 双服务正式精度回归（2026-09-18）

## 结论

正式精度子步骤失败。GPQA Diamond 完整覆盖 198/198，strict 为 170/198（85.86%），低于冻结阈值
88%（至少 175/198）。7 个最终失败样本达到 60000-token 生成上限并按契约保留为错误；没有缺失、
无效样本或非 timeout 请求错误。

## 固定配置

- Host：`PPU-01`；容器：`qwen3.8-flash`；模型：
  `/mnt/cpfs/models/Qwen3.8-Flash-Next`。
- 两个 TP8 `FULL_AND_PIECEWISE` graph 服务分别使用 PPU 8–15 的 8038 端口和 PPU 0–7 的 8039
  端口；未显式配置 capture sizes，引擎自动选择
  `[1,2,4,8,16,24,32,40,48,56,64]`。
- `max-model-len=65536`、`max-num-seqs=32`、`max-num-batched-tokens=4096`、
  `gpu-memory-utilization=0.90`、异步调度；评测并发 64，轮询代理端口 8040。
- workload：GPQA Diamond full198，`temperature=1`、`top_p=0.95`、`top_k=20`、
  `max_gen_toks=60000`；客户端 timeout 7200 秒。
- run-id：`gpqa-full-c64-maxgen60000-index-put-int64-auto-capture-dual-20260918-v1`。
- 配置 SHA-256：`1e5c8d98934fe67efc023e8f40365712f138e8918fd190f578d9f449e7300a34`。

## 结果与错误归因

- 原生 receipt：170/198（85.86%）；结果覆盖 198/198；396 条 filter rows；无 malformed row。
- receipt SHA-256：`1846b8085e235326803b7a249f60fe2159657d96eaf8dbd8f5442a553c1f23a6`。
- results SHA-256：`861476d71c0c37848a1a368f8ddf6e1e5ae675aa46a689500ec9893e0315a34c`。
- samples SHA-256：`f561aa47829e599fd8db000836f5913c646830313e15e45b838b6072ad0562ce`。
- 两个后端合计 198 个请求全部返回 HTTP 200；最长请求 5515.856 秒，低于 7200 秒客户端 timeout，
  服务端无 RPC timeout、OOM、abort、非法内存或 traceback。
- 7 个 `<TIMEOUT>` 样本全部为 `finish_reason=length`、`completion_tokens=60000`、
  `content=None`。Qwen3 reasoning parser 在模型未退出 reasoning 时没有最终 content，评测器因此按最终
  timeout 记零。这些不是网络或异步调度超时，继续延长客户端 timeout 不会改变结果。
- 去除这 7 题只用于诊断时，其余样本为 170/191（89.01%）；正式计分不能删除它们。至少需要恢复其中
  5 题才能达到 175/198。
- completion token 中位数：正确样本 3110.5，21 个非上限错误样本 34342，7 个上限样本 60000。
  上限样本中 6 个属于 Chemistry，长 reasoning 的化学题是当前主要失分聚集。

## 数值一致性诊断

对 28 个错误或生成上限样本使用 `temperature=0,seed=1234,max_tokens=128` 做双服务短探针：并发时
17/28 分叉，严格串行时 20/28 分叉。再选 5 题，在每个服务上各严格串行重复 3 次、
`max_tokens=32`：同一服务内部输出始终相同，而两个服务之间始终不同。

这排除了客户端并发 race 和采样随机性，证明两个独立 graph 实例存在稳定的早期数值/状态路径差异。
它与 custom-op cache 参数/mutation 声明、graph output view 和独立图存储生命周期等候选机制一致，
但尚未通过单变量实验确认具体源码点。不同设备组的编译/autotune 路径及两服务不同 KV cache 容量也是
未排除变量。

- 严格串行探针：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/dual-service-deterministic-parity-sequential-20260918-v1/result.json`，
  SHA-256 `918fa38f66b449e69f9ac24765da586d959a7b93044b68fb5e5b9356c4407d7f`。
- 单服务重复性探针：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/dual-service-repeatability-20260918-v1/result.json`，
  SHA-256 `a8f6f72035cc6065b230bb666d26a648c9a776822560e4aac791d8c0a40f8891`。

正式轮次结束后的执行模式跟进不改变上述正式分数。将卡 0–7 的 8039 服务切为 eager 时，首个诊断
启动器漏带 8038 已有的 `_conv_depthwise2d,index,normal_` blacklist，导致 FlagGems `index` 在多 rank
首次调优 shape `[336,2560]` 时争用 SQLite DDL 锁，TP5 报 `database is locked`，HTTP 500 后服务退出。
补齐相同 blacklist 后 eager v2 正常就绪并完成 5 题三次重复探针。

修正对照中，每个服务对每题的三次输出仍完全一致；graph/eager 跨端分叉为 3/5，而原 graph/graph 为
5/5。doc 71、168 改为一致，doc 160 保持原 0–7 graph 轨迹，doc 30、89 形成第三条稳定轨迹。由此可知
graph/cudagraph 路径贡献部分 greedy 分叉，但不能解释全部分叉；设备组及 eager/graph 共用的算子或编译
数值路径仍需分离。结果位于
`/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/graph-eager-repeatability-corrected-20260918-v1/result.json`，
SHA-256 `73bc1e8004588cf6eee58533b2dd6fb81008e0045d026321d8f8a9f3756545b1`。

## 结论边界与下一步

FlagGems `index_put_` 大偏移 int32 溢出的整模严重退化已经消失；本轮不再复现 59.60% 和大量
stop/content-none 的故障形态。去掉显式 capture sizes 也没有导致服务不稳定。当前正式失败由 7 个真实
生成上限直接造成，剩余非上限错误与跨实例稳定分叉需要继续分开定位。

下一轮先在相同卡组上逐项回移 cache mutation ABI 和 non-owning graph view，以 5 题和 28 题
确定性短探针筛选具体机制。之后使用 `max-model-len=100000` 和更高的生成上限定向重跑 7 题，再以固定的
单一服务完成 full198。正式精度通过以前不启动性能子步骤。
