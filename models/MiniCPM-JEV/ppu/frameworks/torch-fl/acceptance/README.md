# 适配验收索引

按 `framework.yml` 固定 profile 的 `acceptance.steps` 及已启用的 `substeps` 顺序记录计划、
结果、总结和复盘。只执行该框架声明的步骤，不套用其他框架的服务或评测要求。

- vLLM 服务型 profile：记录其声明的执行模式、小批量验证和后续验收；是否具备正式精度、
  性能及交付能力以当前 profile 为准。
- Torch-FL：记录设备、算子路由、eager 模型验证、可选 wheel 和总结，不自动要求 graph、
  OpenAI 服务或 FlagEval。
- experimental 只能通过已声明的独立验证，不能标记正式整体验收完成或 `optimized`。

文件存在不代表已经执行或通过；原始产物保留在批准远端根目录，本地只引用可核验的证据。
