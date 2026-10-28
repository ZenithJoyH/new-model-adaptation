# 007：Inductor 的额外数值偏差与原生 EagerAdaptor 图执行

2026-10-23，已验证 PPU-01 的 value-head 范围。

视觉插值修复且保留 vLLM 原生 FP32 分类头后，eager 原生 API 两轮 12 样例最大误差 0.004417300，通过冻结容差 0.005。显式 PIECEWISE + 默认 Inductor 两轮最大误差 0.005077541，末例超容差，保留 `04-runs/graph-vision-fp32-head-native-20261023/`，未放宽阈值。

使用当前 vLLM 已有 `EagerAdaptor` 作为分段编译 backend；仍保持 `CompilationMode.VLLM_COMPILE` 和 `CUDAGraphMode.PIECEWISE`，没有启用 `--enforce-eager`。原生 backend 返回分段 FX graph，同时按该 backend 默认保留 custom ops。CUDA Graph 捕获和重放由现有 Plugin GraphWrapper 完成；不修改 vLLM、编译器实现或公共默认值。

`04-runs/graph-piecewise-eager-backend-20261023/` 的日志包含 7 个捕获尺寸及真实请求 `Running batch with cudagraph_mode: PIECEWISE`。`graph-eager-adaptor-native-20261023` 两轮 24 请求最大误差恢复为 0.004417300；4/8 并发各 24 请求均通过。双图均值色消融使样例 s02 概率从 0.995437920 降至 0.374200732，恢复图片后概率完全恢复，证明多模态编码和变输入结果生效。

此配置只对本模型的启动参数生效。代价是保留更多独立算子而不使用 Inductor 融合；没有正式关闭缓存的性能数据，故不宣称更快或 optimized。恢复 Inductor 的条件是同一参考容差、变输入图重放及并发均通过，再以同条件原生性能评测选择。当前只完成推理功能验证，正式精度/性能仍待匹配的评测入口与冻结配置。
