# 001：原生 PPU vLLM 接入 4.7

日期：2026-10-08。状态：真实权重 eager 与 graph 功能验证通过；未进行正式精度、性能验收。

原始 wheel 只有 4.6 注册。checkpoint 使用 `qwen3_5_moe_text`、256 专家选 8、
`mrope_mode=canvas`；4.6 的 Dense 构造和三通道顺序位置不能直接复用为 4.7 注册别名。

已在实际安装目录作三处产品修改：

1. `model_executor/models/registry.py` 添加 4.7 架构入口。
2. `minicpmv4_6.py` 提取骨干选择 hook，默认仍为原来的 Dense 类与类型；4.6 原调用路径
   保持原行为。构造期间的顶层类型临时切换仍用 finally 恢复。
3. 新增 `minicpmv4_7.py`，按 text_config 选择原生 Qwen3.5 MoE；复用 4.6 的视觉塔、
   merger、多模态处理器和权重映射。按实际图像/视频 feature 的网格尺寸与结构 token
   调用 checkpoint canvas helper，vLLM 的 decode delta 使用 helper delta + 1。
   缺失几何时明确报错，当前服务配置 `mm_processor_cache_gb=0`。

未添加 T-Head 独立 vision 文件、FP32 workaround、FlagGems 黑名单或替代包路径。
原文件在批准根 `05-tmp/before-20261008/`，diff、新文件 SHA 在
`04-runs/bringup-20261008/product-v1.json` 及同目录 diff 中。

当前已验证：

- ModelConfig 正常解析 4.7、MoE、M-RoPE、多模态及 262144 上下文。
- `02-issues/check-positions.py` 使用实际处理器处理单图、宽图、长图、多图、两帧视频，
  与 checkpoint canvas helper 逐值对照，另验证文本位置与 decode 起点。六组均通过；
  结果 `positions-processor-v1.json`。
- eager TP1/PPU3 已加载全部 16 shard，占用约 65.72 GiB；HTTP 8/8 返回 200、stop
  且内容符合预期：算术 42，红/蓝图，横向与纵向切片、双图和两帧视频均识别正确，
  重复红图也正确。原始请求、响应与汇总在 `eager-v1/smoke/`。
- eager API PID 1623、EngineCore 2109、tracker 2108 已按同一任务进程组 1623
  发送 SIGTERM 并核实退出，容器仍运行。首次端口 bind 检查遇到 TCP TIME_WAIT，
  随后使用 ss 核实 8022 无 listener；记录 `eager-v1/termination.json`。
- `product-review.json` 重核所有 1914 个 Python 文件，仅上述三个文件有增量，
  无删除。4.6 与 registry 修改前后哈希、4.7 新文件哈希完整保留。

eager 的 50000 上下文和多模态数量限制仅用于诊断；不能据该轮结果宣称正式精度、性能
或完整适配验收通过。

最终根目录脚本已实测启动 TP2、默认上下文 262144，未保留 eager 的长度、并发数或
多模态数量限制。显式 `FULL_AND_PIECEWISE` 捕获两类各七档图，十并发 10/10 正确。
1905-token 图文前缀按红、红、蓝依次请求，3/3 正确且 prefix cache 命中 1632 token。
详见 [功能验证与交付](../acceptance/functional-20261008.md)。
