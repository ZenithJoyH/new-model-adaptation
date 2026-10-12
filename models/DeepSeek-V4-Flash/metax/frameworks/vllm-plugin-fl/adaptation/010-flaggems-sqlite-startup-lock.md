# 010：MetaX TP8 启动时 FlagGems SQLite WAL 锁竞争

## 元数据

- 状态：`hypothesis`（已缓解，未完成独立最小复现或产品修复）
- 首次出现 / 最后验证：2026-09-23
- 模型 / 平台 / Host：DeepSeek-V4-Flash INT8 / MetaX C550 x8 / `mx-59`
- 容器：`deepseek`，image `harbor.baai.ac.cn/flagrelease-public/metax-vllm-0.24.0-pluginfl-tree3.6:xingchen4-0907`；适配容器未停止、重启或删除。
- Revision：Plugin `fd5c727fcdb607bc4354cd11384761bb5d5ecfba`，FlagGems `711cf839c4ee5557776c626e1f8b20cc4007fa63`，vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`。这些 HEAD 不包含工作树差异，完整适配背景见 [009](009-metax-graph-correctness.md)。
- 模式：GPQA 全量诊断结束后的安全服务恢复，TP8+EP、`mode=NONE + cudagraph_mode=FULL`、前缀缓存开启；与 GPQA 评分请求阶段无关。

## 现象与证据

- 首次恢复运行 `/public-flash/jinghao/deepseekV4/04-runs/gpqa-diamond-safe-restore-20260923-01/service.log`：rank6 在 worker/model 初始化期间调用 `/workspace/FlagGems/src/flag_gems/utils/models/sql.py:78` 的 `PRAGMA journal_mode=WAL`，报 `sqlite3.OperationalError: database is locked`，随后 EngineCore 初始化失败。首错不是后续的 API RuntimeError。该库位于批准根 `/public-flash/jinghao/deepseekV4/06-cache/flaggems-gpqa-diamond-safe-restore-20260923-01/config_cache/TunedConfig_metax_triton_3_6.db`；宿主存储 `nfs4`。
- 失败服务 PID/PGID `3406062` 及其 workers 均自行退出；确认没有 vLLM 残留后才重试。没有清理失败目录或数据库文件。
- FlagGems `LibCache` 在未设置 `FLAGGEMS_DB_URL` 时从 `FLAGGEMS_CACHE_DIR/config_cache/` 构造共享 SQLite URL；所有 TP workers 同时初始化同一个新库。源码已有 `timeout=30`，但连接事件中的 WAL pragma 仍可抛锁错误。此处证明失败链条，尚未用最小复现证明每次并发启动必失败，也不能把问题简单归因于 NFS 单因素。

## 已有经验匹配

| 历史记录 | 相同点 | 差异 | 本次决定 |
|---|---|---|---|
| [Hy4/PPU FlagGems SQLite 锁](../../../../../Hy4-preview/ppu/adaptation/002-flaggems-sqlite-lock-reproducer.md) | 多 worker 共享 FlagGems `TunedConfig_*.db`，`database is locked` 可传播并使 EngineCore 退出 | 历史是 PPU TP16、新 shape 的 benchmark 表 DDL / `get_sql_model()`；本次是 MetaX TP8、模型启动时 `PRAGMA journal_mode=WAL`，revision、硬件、时点均不同 | 只借用“先查最早 SQLite 异常、不要误判为模型算子”的诊断思路；不把旧 UT 当作本轮复现，也不推广旧缓解结论 |

## 受控尝试与结论

| 轮次 | 变化 | 准确位置 | 结果 | 分类 |
|---|---|---|---|---|
| 01 | 全新运行标签和 FlagGems 缓存，按先前安全脚本直接并发启动 TP8 | `01-environment/start-gpqa-restore-20260923.sh`、`04-runs/gpqa-diamond-safe-restore-20260923-01/` | rank6 WAL pragma 报锁，API 未就绪 | 失败基线 |
| 02 | 仍是全新运行标签/缓存及相同模型参数，只在启动 8 workers 前单进程创建该轮 SQLite DB 并置 WAL | `01-environment/start-gpqa-restore-20260923-02.sh`，SHA-256 `b38ce112eeaa8497e8c63d9a90ddcd6217c7382ab6af38f7a13f009ef59d44fd` | API PID `3431326` 健康 `200`，decode FULL 图捕获 `1/1`；两条冻结请求 `OK`/`5` 严格 `2/2`，`04-runs/gpqa-diamond-safe-restore-20260923-02/restore-smoke.json` SHA-256 `40c90d7f0986cf6f20217df2b7e0b383b8c2f8213d3dcbe4de4f3cf87884bd4c` | 恢复期规避，不是产品修复 |

“新标签”只用于避免覆盖历史产物，两轮均使用各自空缓存；主要受控差异为第二轮提前置 WAL。由于并发锁竞争可能非确定性，这个前后对照不足以证明预初始化在所有启动中可靠。没有修改 FlagGems、Plugin、vLLM 源码或改变模型推理参数；重试后服务保持运行。

## 边界与下一步

- 该错误发生在 CPU 侧数据库初始化，不能作为 `eager`/`graph` 算子数值失败证据。GPQA 198 题在之前的 compile 服务上已完整评测并退出 0，结果见 [精度诊断](../acceptance/gpqa-diamond-diagnostic-20260923.md)。
- 若要真正修复，应在当前 MetaX/FlagGems revision 下做独立多进程复现，验证并发 WAL 初始化、首次建表和 NFS 锁行为；再评估有界重试、单进程预初始化、每 rank 分库或本地可靠存储。任何产品改动须在授权源树和多平台回归范围内另行实施。本轮不新增 FlagGems bug reproducer，也不把一次成功重试提升为通用解决方案。
- 经验库决策：`needs-validation`。当前只引用历史相似问题，不新建跨平台 troubleshooting 条目。
