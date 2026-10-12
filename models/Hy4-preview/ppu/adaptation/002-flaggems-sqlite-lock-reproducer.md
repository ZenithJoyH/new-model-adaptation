# FlagGems SQLite 并发锁复现

目标：PPU-07，容器 hy4，FlagGems 842b19d8ad5bd8bd66cce1e52b26ade54b0b851f，版本 5.3.5+g842b19d8a。

生产失败特征：TP16 worker 共享 TunedConfig_thead_triton_3_6.db，新 shape 触发 benchmark 表并发建表；FlagGems SQLPersistantModel.get_sql_model() 传播 sqlalchemy.exc.OperationalError: sqlite3.OperationalError: database is locked，随后 EngineCore 退出。原日志在 /mnt/nfs/users/jinghao/hy4-preview/reload-gpqa-20260906-QkrXVqar/hy4-preview.before.log。

复现 UT 为 CPU-only，不请求模型、不调用 PPU 算子。用 spawn 模拟独立 TP worker：一个进程持有 SQLite BEGIN IMMEDIATE 写锁，另一个进程直接调用 FlagGems SQLPersistantModel.get_sql_model() 创建 benchmark 表。短 timeout 必须复现原异常，大于持锁时间的 timeout 必须成功，两轮都要求 PRAGMA integrity_check=ok。

容器目录：/bug/hy4-flaggems-sqlite-lock-20260906。

命令：

    cd /bug/hy4-flaggems-sqlite-lock-20260906
    python3 -B test_flaggems_sqlite_lock.py --timeout 1 --hold-seconds 4 --expect locked
    python3 -B test_flaggems_sqlite_lock.py --timeout 10 --hold-seconds 4 --expect success

第一条命令的“通过”表示已捕获预期 database is locked，不是数据库操作成功。第二条证明连接 timeout 能作为缓解。这不是 FlagGems 根因修复；上游仍应实现有界退避重试、重新查表或多进程 DB 分片。eager/graph 不适用，因为失败位于 host 侧调优缓存 DDL，不在设备 graph 执行内。

## 2026-09-07 当前 revision 再次复现

用户重启服务进行评测后，`/mnt/nfs/users/jinghao/hy4-preview/hy4-preview.log`
在 16:22:19 再次出现同一故障族。首个致命错误位于日志第 6566 行附近：TP16 的多个
worker 从 `model_runner._prepare_inputs` 进入 `flag_gems.ops.index`，对
`/root/.flaggems/hy4-tp16.db` 中新的 index autotune benchmark 表并发查询/提交，累计
28 个 `database is locked` 命中；随后 EngineCore 退出。末尾 scheduler `KeyError`、
EngineDeadError 和 HTTP 500 是连锁错误，不作为根因。

当前 FlagGems 已变为 clean
`sparse-mla-opt@717a9ef60d38b559d8b4424488ca5cad2fe61a59`，因此不能直接把旧
revision 的 `/bug` 用例当作当前证据。新版用例已按批准目录规范保存在宿主和容器同路径：

`/mnt/nfs/users/jinghao/hy4-preview/08-bugs/flaggems-sqlite-lock-20260907/`

用例不使用 `/bug`，也不访问生产数据库。测试数据库、临时目录、缓存和 JSON 结果全部留在
该目录内。准确命令见远端 `README.md`；已验证的两组命令为：

```bash
cd /mnt/nfs/users/jinghao/hy4-preview/08-bugs/flaggems-sqlite-lock-20260907
python3 -B test_flaggems_sqlite_lock.py --timeout 1 --hold-seconds 4 --expect locked --db-path artifacts/locked.db --result-path evidence/locked.json
python3 -B test_flaggems_sqlite_lock.py --timeout 10 --hold-seconds 4 --expect success --db-path artifacts/success.db --result-path evidence/success.json
```

短 timeout 负对照稳定得到当前 `SQLPersistantModel.get_sql_model()` 传播的
`OperationalError: database is locked`；长 timeout 对照成功创建/反射同 schema 的
benchmark 表。两轮均为 Python 3.12.3、`spawn`、固定 seed 20260907，且
`PRAGMA integrity_check=ok`。结果分别在 `evidence/locked.json` 与
`evidence/success.json`。核心脚本 SHA-256 为
`cb4979452d77ccefa9dec0c5635f511a3daa16d48cfab28f927d3a51df43182b`。

此结果验证了当前 revision 仍会传播跨进程 SQLite 锁异常；10 秒对照只证明等待可以缓解
本用例，不足以直接确定生产 timeout，也不是根因修复。生产方案仍需评估有界重试、提交失败
后的 rollback/重新查表、每 rank 数据库分片或预热策略，并在真实 TP16 graph 服务上回归。
本轮没有修改或重启容器、服务、Plugin、vLLM、FlagGems、生产数据库或权重。

## 上游回归 UT 打包与验证（2026-09-07）

用户要求将当前复现整理为可提交给 FlagGems 的规范 pytest UT。上游目标为
`flagos-ai/FlagGems` 的 `master@dcd0cfeae8187dee691656c0616c1ed95899c2ae`；已核对
该 revision 的 `src/flag_gems/utils/models/sql.py` 与 PPU-07 当前
`/workspace/FlagGems` 对应文件字节一致。测试只使用 Python、SQLite、SQLAlchemy 和
`multiprocessing`，不调用模型或 PPU 算子。

提交包已保存在现有批准目录的 `upstream/` 子目录：

- `tests/test_sql_persistent_model.py`：期望行为回归测试；当前缺陷版本应由 pytest
  报告一个 `database is locked` 断言失败，修复后应通过。
- `0001-add-sqlite-lock-regression-test.patch`：相对 FlagGems 仓库根目录可直接应用的补丁。
- `README.md`：上游提交说明、运行命令、预期结果和边界。

部署前只读核验、check mode、部署和容器内验证的可重复命令依次为：

```bash
./scripts/playbook /private/tmp/inspect-ppu07-flaggems-sqlite-ut.yml --limit PPU-07
./scripts/playbook /private/tmp/deploy-ppu07-flaggems-sqlite-ut.yml --limit PPU-07 --check --diff
./scripts/playbook /private/tmp/deploy-ppu07-flaggems-sqlite-ut.yml --limit PPU-07 --diff
./scripts/playbook /private/tmp/verify-ppu07-flaggems-sqlite-ut.yml --limit PPU-07
```

验证命令将测试的所有临时文件和 cache 定向到
`08-bugs/flaggems-sqlite-lock-20260907/upstream/runtime/`，并从容器路径直接调用
`/workspace/FlagGems/src`。验证任务把 pytest `rc=1` 且输出包含当前测试名和
`database is locked` 定义为“缺陷已复现”，不会把红测误报为修复成功。

最终验证结果：PPU-07 可达，`hy4` 保持运行；容器内 FlagGems 为
`717a9ef60d38b559d8b4424488ca5cad2fe61a59`。最终 UT 的 pytest 返回 `rc=1`，
测试名和 `database is locked` 签名同时命中，符合受影响代码上的预期红测。补丁还在
`master@dcd0cfeae8187dee691656c0616c1ed95899c2ae` 的干净临时 checkout 上通过
`git apply --check`、实际 `git apply`、`git diff --check` 和 Python 语法检查。

远端最终文件 SHA-256：

- UT：`db516ee6c7320f78e7c2c81fd20c648e3364cdb6fd1303e7603433bfcf275432`
- patch：`664ea39e2540a22bfd5b4d0be347902bc7b46f7b1dde743d7e6d934efc1f2937`
- README：`b1b8668ca9a8e029a7892da24e8e28a9aeedb0157c22596f21d289e7abd97b0b`

此次只在批准的 `08-bugs/.../upstream/` 下新增提交材料和隔离 runtime 文件；未修改
`/workspace/FlagGems`、vLLM、Plugin、生产数据库或服务，也未停止或重启容器。
