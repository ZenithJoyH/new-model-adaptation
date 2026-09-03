# 新模型适配故障知识库

这里只记录经过验证、能够跨模型复用的故障定位方法。当前模型或当前平台独有的过程
记录应留在对应的 `models/<model>/<platform>/adaptation/`，FlagGems 算子复现应留在
适配容器的 `/bug/`。

## 分层隔离顺序

发生导入、编译、崩溃、精度或性能问题时，从最窄层开始验证：

1. 平台 runtime 与 Triton/flagtree backend。
2. FlagGems 单算子，包括数值参考和适用时的 graph capture/replay。
3. Plugin dispatch、backend、注册或平台绑定。
4. 模型组件组合与最小模型执行。
5. 完整服务及 `eager`、`graph` 两种模式。
6. graph 模式下的并发、全量精度、性能和通信验收。

每次扩大验证范围前，较窄层必须已经通过。Blacklist 或关闭 FlagGems 可以用于判断
问题归属，但不能作为未经论证的最终适配方案。

## 条目要求

新增条目必须包含：

- 可稳定识别的症状或错误签名。
- 适用平台、软件 revision 和边界条件。
- 最小复现或证据位置。
- 已验证根因，或明确标注仍为假设。
- 修复方法、验证方法、`eager`/`graph` 影响和已知限制。
- 原始模型适配记录或容器 `/bug` 路径。

使用 [entry-template.md](entry-template.md) 创建新条目。不要记录聊天内容、未经验证的
猜测、密钥、完整大日志或模型权重。
