# GPQA 精度结果与暂停记录

2026-10-28，用户要求整理当前精度后暂停。完整 **198 题**已结束，逐题核实 **174 题正确，strict-match＝87.8788%**。用户明确将门槛由 **88% 改为 85%**，当前结果达到新门槛（至少需 169 题正确）。没有重发题目。

这是全量原始证据的核验摘要。新的正式离线评分报告及双机 framework gate 尚未封存，不能据此声明全部适配验收完成。

## 实际运行与计分

- 原始运行：`glm-gpqa-final-v14-20261028`；2026-10-28 10:12:38 至 21:02:51（北京时间），约 10 小时 50 分钟。
- 范围：GLM-5.3-Flash-BF16，mx-101/mx-102，各 8 张 C550 64 GiB，TP8/PP2，FULL_AND_PIECEWISE，正常 prefix caching 开启。
- 配置：并发 4，temperature=1，top_p=0.95，max_gen_toks=60000，完整 198 题，API/eval 重试均为 0。
- 样本文件 396 行对应 198 个文档各含两个过滤器，不是 396 道题。strict-match 的 198 个唯一文档得分总和为 174，目标答案和文档哈希均匹配冻结审计。
- 原始日志有 198 个唯一 API 响应；9 个空答案全部为 `finish_reason=length`、`completion_tokens=60000`，不是实际 HTTP 超时。API 内容与原生样本一致，9 个空答案均为 0 分。

原生报告显示 `passed`、**92.0635%（174/189）**：它把 9 个 null 转成 `<TIMEOUT>`，汇总时排除了这 9 题。这不符合全量 198 题分母要求，不能用原生 92.06% 声称通过。正确结果为 **174/198＝87.8788%**：原 88% 门槛下未达标；用户新设 85% 门槛下达标。

原始配置、工具及评分源码均无漂移；报告和样本文件哈希一致。原缓存的 198 个键覆盖冻结全部提示，已逐字节备份，源 DB/WAL 备份前后哈希相同。原 88% 配置与原生报告保留，85% 变更单独冻结。

## 已保存证据

远端批准根：`/public-flash/jinghao/glm5.3-flash`。

| 证据 | 根下相对路径 | SHA-256 |
| --- | --- | --- |
| 当前结果核验与暂停记录 | `04-runs/glm-gpqa-final-v14-20261028/terminal-inputs-v18/accuracy-current-state.json` | `a5f79b24a58e0eda342815436e7328c42d3db1a68128f70a10be477f4ebaa532` |
| 未改写的完整缓存快照 | `04-runs/glm-gpqa-final-v14-20261028/terminal-inputs-v18/responses-original.sqlite` | `0be38b12a1efda5d6718afe463b7a4b5275f48ba9ba32eb6167bb13908b1c44d` |
| 用户批准的 85% 门槛 | `03-acceptance/gpqa-threshold-amendment-v18-20261028.json` | `a575dce1977bc1994761cb5d7d5c8228097fb82513c9b0306176e20e00afe4a2` |
| 原始 88% 配置 | `03-acceptance/gpqa-final-v14.json` | `cc1f6a7e92f735e302c7b509332a2b237c1b3b9d00cf6c91a59d954d6587d642` |

完整原生报告与样本位于 `04-runs/accuracy-results/glm53-metax-final-v14/glm-gpqa-final-v14-20261028/`。上表核验记录包含它们及原始日志的准确路径和哈希；原始日志、响应和缓存未复制到本地模型目录。

## 暂停时未完成项

原等待程序因原生 `passed` 未执行恢复。新工具已加入全量分母校验和显式门槛变更；恢复测试 20 项在本地和真实评测容器通过，相关生命周期、framework、精度证据及协作回归通过。

实际终态缓存的 189 个非空值为 `(response, usage)` 元组，9 个空值为 None。冻结 v2 工具的仅标量解码器拒绝继续，失败记录保留在 `04-runs/gpqa-terminal-snapshot-v17-20261028/`。后续需验证该格式支持，再生成正式离线回执与双机 gate；v18 已只读备份全部原始数据。用户要求暂停后没有继续修改解码实现。

性能测量、镜像实际推理验证和最终部署指南待恢复后继续。两机原 `glm5.3-flash` 容器均核实 `running=true, paused=false`，现有推理服务保留。当前不声明 optimized 或全部验收完成。
