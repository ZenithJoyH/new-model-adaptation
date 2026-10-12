# Hy4-preview / PPU 平台适配计划

## 输入与现场

- 模型结构：`../../architecture-and-inference.md`。
- 环境证据：`environment-analysis.md`，目标 `PPU-07` / `hy4`。
- 批准工作根：宿主与容器均为 `/mnt/nfs/users/jinghao/hy4-preview`，由宿主
  `/mnt` → 容器 `/mnt` 的 RW bind 映射核实。
- 当前栈：vLLM clean `ee0da84ab9e04ac7610e28580af62c365e898389`；Plugin
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`，有一处本轮不处理的 inherited
  tracked 删除；FlagGems clean `717a9ef60d38b559d8b4424488ca5cad2fe61a59`。
- 已阅读仓库 `docs/plugin-contribution-policy.md`；本任务不修改 Plugin、vLLM 或
  FlagGems 产品代码。

## 当前差距与处理范围

| ID | 组件/阶段 | 调用链 | 问题 | 本轮处理 | eager/graph |
|---|---|---|---|---|---|
| sqlite-lock-20260907 | FlagGems `index` autotune | `model_runner._prepare_inputs` → `flag_gems.ops.index` → Triton autotune → `SQLPersistantModel` | TP16 首次遇到新 shape 时共享 SQLite，`OperationalError: database is locked` 逃逸并使 EngineCore 退出 | 在批准根的 `08-bugs/` 创建独立、固定输入、CPU-only 多进程最小复现及长超时对照 | host 侧 SQLite DDL/查询故障，设备 eager/graph 不适用 |

本轮不以降低并发、清除生产缓存、修改启动脚本、延长生产超时或绕过 FlagGems `index`
冒充根因修复。最小复现直接调用当前 FlagGems `SQLPersistantModel.get_sql_model()`，使用
`spawn` 表达 TP worker 的进程隔离，并将测试数据库和输出限定在复现目录中。

## 修改边界与共享影响

- 仅向 `/mnt/nfs/users/jinghao/hy4-preview/08-bugs/flaggems-sqlite-lock-20260907/`
  写入复现脚本、README 和简洁结果；不使用 `/bug`，不复制完整日志或模型数据。
- 不停止、重启或删除 `hy4` 容器；当前模型服务已因故障退出，本轮不拉起服务。
- vLLM、Plugin、FlagGems 和外部权重均只读；不处理 Plugin 的 inherited 删除。
- 用例针对 SQLAlchemy/SQLite host 缓存层，不改变 dispatch、dtype、shape、设备 kernel、
  graph capture 或任何模型默认行为，因此其他模型/平台只作为潜在同类调用者，不宣称已验证。
- 旧 `/bug/hy4-flaggems-sqlite-lock-20260906` 仅作为候选经验；当前用例必须在
  FlagGems `717a9ef6` 和批准的 `08-bugs/` 容器路径原地重新运行。

## 验证顺序

1. 核对目录尚不存在、容器映射和三套代码身份不变。
2. 短 timeout + 长持锁时间：必须稳定捕获 `database is locked`，并验证数据库完整。
3. 长 timeout + 相同持锁时间：必须成功创建/反射 benchmark 表，并验证数据库完整。
4. 核对所有新增文件和运行产物均位于该 `08-bugs/` 目录；记录 SHA-256 和准确命令。

## FlagGems 同步与交付

当前 FlagGems 工作树为 clean `sparse-mla-opt@717a9ef60d38b559d8b4424488ca5cad2fe61a59`。
用户本轮只要求打包复现，未授权或要求同步/修改 FlagGems，因此不 fetch/pull。复现结果是
上游修复输入，不代表数据库并发根因已修复，也不替代模型精度或性能验收。
