# 005：pooling 图模式能力与真实生效级别

2026-10-23，状态：图初始化/数值诊断中，尚未通过 graph 验收。

## 按序检查

| 请求级别 | 验证入口 / 证据（工作根下） | 实际结果 |
| --- | --- | --- |
| FULL | 完整服务 `04-runs/graph-full-cli-fixed-20261023/` | vLLM 配置阶段改为 PIECEWISE |
| FULL_AND_PIECEWISE | 原生 EngineArgs 配置入口 `04-runs/config-full_and_piecewise-20261023/` | PIECEWISE |
| FULL_DECODE_ONLY | 原生 EngineArgs 配置入口 `04-runs/config-full_decode_only-20261023/` | PIECEWISE |
| PIECEWISE | 上述完整服务的实际模式先做诊断；最终需显式设置重验 | 待真实捕获/重放及数值核验 |

第一次 FULL 启动使用了当前版本不支持的 `--observability-config`，在参数解析时退出，保留 `04-runs/graph-full-20261023/`；改用实际 CLI `--cudagraph-metrics` 后重试 FULL。此参数错误不作为 FULL 能力阻塞依据。

## 根因、边界与修复评估

只读 vLLM `config/vllm.py:1233` 在 `current_platform.support_static_graph_mode()` 且 `pooler_config is not None`、请求模式 `has_full_cudagraphs()` 时明确打印 `Pooling models do not support full cudagraphs. Overriding cudagraph_mode to PIECEWISE.`。三档 FULL 相关模式均命中同一能力守卫。两个配置探针按顺序运行真实解析/配置构造，不分配完整模型；其调用上下文默认 batching budget 与 API 服务不同，但 pooling 守卫不依赖 token budget，完整服务 FULL 日志已独立证明该限制。

模型是 LAST pooling 的两类 value head，没有 token decode。改成 generation runner 或移除 pooler 会改变任务语义，无法作为修复。删除 vLLM 的能力守卫既超出只读边界，也不能证明完整 pooling 图安全，因此不采用。恢复更高图级别需原生 pooling 生命周期支持 FULL，并通过变输入 capture/replay 及数值/性能验证。

另一个更底层限制是 GDN metadata builder 声明 `AttentionCGSupport.UNIFORM_BATCH`；即使未来解除 pooling 守卫，也不能直接声称混合 prefill FULL 支持。

当前选取 capture sizes 1/2/4/8/256/512/1024，覆盖单请求样例 222–782 token 及 prefix-cache 尾段。超过 1024 token 的 batch 可能走框架原生 eager，需披露覆盖范围，不能声称所有长度都捕获。最大 context 仍为 50000，并未下调图像预算或 checkpoint context 来规避问题。

初次 torch.compile 用时 44.31 秒。后续只读栈采样确认进入 FlagGems PPU narrow-N mm 的 Triton 编译/自动调参，不是凭日志不增长判断死锁。最终捕获、重放、数值与性能结果待补充；不把自动降级算作 FULL 通过。
