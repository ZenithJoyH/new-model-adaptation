# Plugin 修改设计审查与 PR 准备

## 范围与版本

- 范围：Hy4-preview / PPU-07 / `hy4`；Plugin `/workspace/vllm-plugin-FL`。
- 审查日期：2026-09-07，Codex 依据只读 Git 身份和当前任务边界自审。
- 当前 branch/HEAD：`support-hy4-preview` / `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`。
- 当前工作树有 inherited tracked 删除
  `vllm_fl/dispatch/backends/vendor/thead/lib/PROVENANCE.md`；本任务未产生、未恢复、未暂存。
- vLLM 为 clean `ee0da84ab9e04ac7610e28580af62c365e898389`；FlagGems 为 clean
  `717a9ef60d38b559d8b4424488ca5cad2fe61a59`。

## 本任务结论

当前故障发生在 FlagGems host 侧 `SQLPersistantModel` 共享 SQLite autotune 数据库，复现
只需直接调用该接口，不需要 Plugin 扩展点或产品代码变化。本任务新增内容全部位于批准工作根
的 `08-bugs/`，不会进入 Plugin、vLLM 或 FlagGems checkout。

| 文件/共享符号 | 本任务改动 | 影响范围 | 结论 |
|---|---|---|---|
| Plugin 产品代码 | 无 | 无新增调用方或默认行为变化 | 无插件变更 |
| FlagGems `SQLPersistantModel.get_sql_model` | 只读调用 | 独立复现 host 侧跨进程锁传播 | 作为上游缺陷证据，不是修复 |

## 回归与风险

- 短 timeout 负对照应稳定捕获生产同类 `sqlite3.OperationalError: database is locked`。
- 长 timeout 对照应成功，并要求两轮 `PRAGMA integrity_check=ok`。
- eager/graph 不适用：问题发生在 kernel autotune 的 host 侧数据库访问阶段。
- 不处理当前 Plugin inherited 删除；其部署可重现性风险仍独立存在。
- 不宣称模型服务、正式精度或性能通过。

## 最终 diff 自检

- [x] 本任务没有修改或绕开 Plugin dispatch。
- [x] 没有捕获或隐藏生产异常；负对照显式断言锁错误。
- [x] 一次性复现不进入任何源码仓库。
- [x] inherited Plugin 删除已单独记录且未处理。
- [x] 结论对应当前 HEAD 和 dirty 状态。

结论：**无插件变更**。本任务无需提交、推送或创建 Plugin PR；复现完成后可单独提供给
FlagGems 维护者。完整模型验收仍为失败/未完成状态。
