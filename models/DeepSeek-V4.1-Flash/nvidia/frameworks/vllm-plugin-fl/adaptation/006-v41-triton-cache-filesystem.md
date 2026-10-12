# 006：Parastor 上 Triton 多进程编译缓存清理失败

## 元数据

- 状态：`resolved`（H100-145 同参数对照越过缓存错误；H100-149 已获独立授权）
- 首次出现及最后验证：2026-09-23
- 模型/Host/容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-145`，`xingchen4-flagos`
- 模式与拓扑：TP8、eager、`max_model_len=2048`、正常前缀缓存

## 症状与归因

Plugin 注册了 V4.1 架构和 renderer 后，EngineCore 可启动并创建 TP8
workers。首次在 `/public/flagos/jinghao/deepseekV4.1/06-cache/h100145-eager-20260923`
下运行 Triton 编译时，首批失败 worker 为 PID 129251/129264，均在
`triton/runtime/cache.py:put` 的 `os.removedirs(temp_dir)` 报
`OSError: [Errno 16] Device or resource busy`，随后 EngineCore 退出。
容器中 `df -T` 确认 `/public` 为 `parastor`，`/tmp` 为容器本地 `overlay`。
此错误发生在模型构造和权重加载前，不是 V4.1 算子数值错误。原始日志：
`H100-145:/public/flagos/jinghao/deepseekV4.1/04-runs/h100145-eager-20260923/service.log`。

先前 H100-149 NV-native 环境曾以本地 overlay 缓存规避同类文件系统
行为，但其授权不自动适用于本 Host。本次用户已单独允许 H100-145 的
`xingchen4-flagos` 容器使用 `/tmp/deepseek-v41-h100145` 作为编译缓存与
临时文件目录。第二次诊断启动脚本保存在
`01-environment/h100145-flagos-20260923/start-diagnostic-eager.sh`；
模型参数与首轮相同，仅缓存路径变化，日志仍写入批准工作根的 `04-runs/`。
复试越过 TP8 Triton 编译阶段，在模型构造的 ViT 接口处失败；因此确认
本地缓存消除了本轮首次文件系统错误，但不代表整模推理通过。H100-149
新容器的独立授权路径为 `/tmp/deepseek-v41-plugin-h100149`。容器及挂载未
停启或更改，vLLM 源码未修改。

知识库处理状态：`needs-validation`；目前只核实这两台 H100 的指定容器。
