# PPU 适配 Runbook

## 目标机器

- `PPU-01`
- `PPU-03`
- `PPU-07`
- `PPU-13`

这四台机器已验证 `ppu-smi` 和 ModelScope 1.39.1。`PPU-231`、`PPU-240` 当前无 `ppu-smi`；`PPU-233`、`PPU-234` 当前堡垒机资产匹配失败，不作为首批目标。

## 1. 前置检查

```bash
./scripts/connectivity-check --limit modelscope_hosts
./scripts/accelerator-check --limit modelscope_hosts
```

## 2. 环境与权重

- 推理引擎：TODO
- 容器或虚拟环境：TODO
- 模型权重路径：TODO
- 模型代码 revision：TODO

下载前确认目标磁盘至少有 850 GiB 可用空间；当前四台机器根盘空间不足，不能直接下载完整权重。

## 3. 启动命令

将验证过的完整启动命令保存为本目录脚本或配置文件，并在此处链接：TODO。

## 4. 功能验证

- 最小文本推理：TODO
- 多卡/多 PPU 正确性：TODO
- 输出一致性：TODO
- 关键算子兼容性：TODO

## 5. 性能优化

先保存基线结果，再一次只调整一个变量：并行策略、批量大小、上下文长度、精度、KV cache 或算子实现。

## 6. 停止与回滚

记录服务停止命令、进程清理方法和回滚版本：TODO。
