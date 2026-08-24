# 沐曦适配 Runbook

## 目标机器

- `mx-103`
- `mx-104`

## 1. 前置检查

```bash
./scripts/connectivity-check --limit metax
./scripts/accelerator-check --limit metax
```

## 2. 环境与权重

- 推理引擎：TODO
- 容器或虚拟环境：TODO
- 模型权重路径：TODO
- 模型代码 revision：TODO

## 3. 启动命令

将验证过的完整启动命令保存为本目录脚本或配置文件，并在此处链接：TODO。

## 4. 功能验证

- 最小文本推理：TODO
- 多卡正确性：TODO
- 输出一致性：TODO
- 关键算子兼容性：TODO

## 5. 性能优化

记录基线后逐项调整并行策略、批量大小、上下文长度、精度、KV cache 和算子实现。

## 6. 停止与回滚

记录服务停止命令、进程清理方法和回滚版本：TODO。
