# 适配验收索引

用户指定的应用测试：[portable v1.1 三场景性能与 32 页质量结果](portable-v11-native-20261027.md)（2026-10-27，原生 FLASH_ATTN，PPU5 临时实例；不改变正式框架验收状态）。

既有测量分析：[原生 PPU 与 FlagOS 的性能差距](native-vs-flagos-gap-20261027.md)（逐请求耗时、输出与后端路由核对，尚无单算子归因实验）。

当前对齐配置见[新执行模式](parameter-alignment-execution.md)、[新sanity](parameter-alignment-sanity.md)、[对齐总结](parameter-alignment-summary.md)。下面为首次配置的历史记录，原始回执保留。

本次PPU-01原生基础验证：

- [冻结计划](acceptance-plan.md)
- [eager/graph与capture/replay](execution-mode.md)
- [原生5例4并发sanity](sanity.md)
- [源码、启动器、交付和限制总结](summary.md)

按 `framework.yml` 固定 profile 的 `acceptance.steps` 及已启用的 `substeps` 顺序记录计划、
结果、总结和复盘。只执行该框架声明的步骤，不套用其他框架的服务或评测要求。

- vLLM 服务型 profile：记录其声明的执行模式、小批量验证和后续验收；是否具备正式精度、
  性能及交付能力以当前 profile 为准。
- Torch-FL：记录设备、算子路由、eager 模型验证、可选 wheel 和总结，不自动要求 graph、
  OpenAI 服务或 FlagEval。
- experimental 只能通过已声明的独立验证，不能标记正式整体验收完成或 `optimized`。

文件存在不代表已经执行或通过；原始产物保留在批准远端根目录，本地只引用可核验的证据。
