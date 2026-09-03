# 可重复执行命令索引

> 新的远程适配命令必须先以脚本或完整命令形式保存在 `adaptation/`，再执行。

| ID | 目的 | 文件或命令 | 目标 Host | 容器 | 执行模式 | 执行结果 | 关联进度轮次 |
|---|---|---|---|---|---|---|---|

## 环境与 baseline

```bash
# 只记录经过核对、不含密码、令牌、IP、SSH 用户或私钥路径的命令。
```

## FlagGems 同步与算子检索

```bash
# 记录 clean worktree、branch/upstream、fetch 和 fast-forward-only pull。
```

## Plugin 修改与测试

```bash
# vLLM 源码只读；Plugin/Triton 测试应分别覆盖 eager 和 graph。
```

## 服务启动、停止与 readiness

```bash
# 只控制当前适配服务或相关进程，不得停止、重启或删除适配容器。
```

每次服务生命周期操作应同时更新 `service-state.yml` 和 `progress.md`。
