# 海光适配 Runbook

## 当前状态

阻塞：SSH inventory 中暂时没有海光机器。新增机器后，先在 `inventory/hosts.yml` 的 `hygon` 分组登记别名。

## 1. 前置检查

```bash
./scripts/connectivity-check --limit hygon
./scripts/accelerator-check --limit hygon
./scripts/accelerator-check --limit hygon -e show_processes=true
```

平台健康检查使用 `hy-smi`，进程检查使用 `hy-smi --showpids`；需要交互排查时再使用 `htop`。

## 2. 环境与权重

- 目标机器：TODO
- 推理引擎：TODO
- 容器或虚拟环境：TODO
- 模型权重路径：TODO
- 模型代码 revision：TODO

## 3. 启动与验证

新增机器并完成前置检查后，补充启动脚本、最小推理、输出一致性和多卡正确性验证。

## 4. 性能优化与回滚

保存基线，再逐项优化；同时记录停止服务、进程清理和版本回滚命令。
