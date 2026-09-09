# 新模型适配故障知识库

这里只记录经过验证、能够跨模型复用的故障定位方法。当前模型或当前平台独有的过程
记录应留在对应的 `models/<model>/<platform>/adaptation/`，FlagGems 算子复现应留在
已批准工作根的 `07-bugs/` 并通过已核实的容器对应路径原地执行。已有用例不得再复制到
`/bug/`；只有必要工具明确要求时才使用指向同一目录的已批准映射或明确例外。

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

## 经验复用闭环

1. 适配前检索故障关键词、症状顺序、平台、模型结构、执行模式和软件 revision。
2. 在当前模型平台 `adaptation/` 下对应的编号问题记录中写明候选条目，以及本次环境的
   相同点和差异，并在 `adaptation/README.md` 中建立索引。
3. 将已有经验作为待验证假设，每次只改变一个实质变量并保留基线对比。
4. 验证成功后补充来源证据和复验日期；失败时记录反例并缩小或废弃适用范围。
5. 复盘时审计尚未提升的候选经验，避免有价值的定位结论只停留在单个模型目录。

## 已收录条目

- [TP worker `sample_tokens` 超时、通信序号分叉与 EngineCore RPC 退出](distributed-sample-tokens-timeout.md)
- [Shape-aware Plugin dispatch 进入 fullgraph 后触发 ContextVar/RLock](shape-aware-dispatch-fullgraph-contextvar-rlock.md)

## 条目要求

新增条目必须包含：

- 可稳定识别的症状或错误签名。
- 适用平台、软件 revision 和边界条件。
- 最小复现或证据位置。
- 已验证根因，或明确标注仍为假设。
- 修复方法、验证方法、`eager`/`graph` 影响和已知限制。
- 原始模型适配记录、工作根 `07-bugs/` 与容器对应路径；如实际使用 `/bug`，再记录其映射或例外。

使用 [entry-template.md](entry-template.md) 创建新条目。不要记录聊天内容、未经验证的
猜测、密钥、完整大日志或模型权重。
