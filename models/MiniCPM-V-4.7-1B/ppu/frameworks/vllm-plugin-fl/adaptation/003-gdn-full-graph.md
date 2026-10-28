# 003：GDN backend 使完整 graph 请求降为混合 PIECEWISE

## 元数据与签名

- 状态：`mitigation verified`；完整 graph 阻断、显式 `decode-full` 捕获和新 Plugin 视觉缓解后的图像基本推理已在本 Host 实测，正式 execution-mode 回执待绑定。
- 日期/目标：2026-09-28，`PPU-13`、`minicpmV4.7-1B`、物理 PPU2、TP1、BF16、50,000 token 上限、正常前缀缓存。
- Plugin 基准 HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319` 加本任务 4.7 adapter；vLLM wheel `0.24.0+empty`、FlagGems wheel 5.3.5。
- 完整 graph 请求：`01-environment/fullgraph-start.sh` 用 `--compilation-config '{"cudagraph_mode":"FULL"}'`，其他模型、设备、容量、服务端口和缓存设置与 eager 一致，移除 `--enforce-eager`。

## 受控结果

切换前确认 eager 实例 PID 2612、启动 tick `330252502`、完整 cmdline SHA-256 `39607d13bd64d83161b1ccbdf69c7dff2ac852c7ecf857d110e3ba098196dc7f`、模型路径、端口、模式，且运行和排队请求均为 0。首轮停止脚本发现 Python `resource_tracker` 子进程，未发信号，失败记录为 `04-runs/eager-v1-20260928/stop-result.json`。第二轮确认 API、EngineCore 和 `resource_tracker` 均属该服务后，仅向 PID 2612 发 SIGTERM，并核实三者退出、端口不可用、容器保持运行；记录 `04-runs/eager-v1-20260928/stop-result-v2.json`，SHA-256 `c206abe431b37486ae8c5a509b5de7628224288433b3ad31a4bed999d6239db0`。

FULL 服务 `04-runs/fullgraph-v1-20260928/server.log` 的 EngineCore 有效配置为 `CUDAGraphMode.FULL`，随即明确报告 `CUDAGraphMode.FULL is not supported with GDNAttentionBackend backend (support: AttentionCGSupport.UNIFORM_BATCH); setting cudagraph_mode=FULL_AND_PIECEWISE`。实际捕获 mixed prefill-decode `PIECEWISE` 11/11、decode `FULL` 7/7；API 就绪。`04-runs/fullgraph-smoke-v1-20260928/result.json` SHA-256 `6e9a5e6230d20c2926262bc2f269f27d8f6bc1f3a8e21e20a71ccc12e11f4d60`：进程身份稳定、健康和文本/图片 HTTP 均为 200，文本最终回答 `2`，红图输出 64 个 `!`，见 [002](002-visual-output-corruption.md)。这是完整 graph 的明确平台/backend 阻断与图片 correctness 失败；不能把 mixed PIECEWISE 记为 `full`。

NVIDIA 同模型的 [004 记录](../../../../nvidia/frameworks/vllm-plugin-fl/adaptation/004-gdn-full-graph.md)也由 GDN backend 将 FULL 降级，属于候选经验。本任务已在 PPU 独立重现相同 backend 限制；设备、编译器、FlagGems 和 Plugin adapter 不同，不能沿用 NVIDIA 的 decode-full 结果。

## 后续

切换至显式 decode-full 前确认 FULL 请求实例 PID 38013、启动 tick `330506368`、cmdline SHA-256 `9e98869111591689247ab3cef12dde2f36a7d479c47ff9d7eb683dd5d91f63d5`，当前请求运行/排队均为 0。只向该实例发 SIGTERM，确认 API、EngineCore 和 `resource_tracker` 退出、端口不可用，容器不变；`04-runs/fullgraph-v1-20260928/stop-result.json` SHA-256 `de3e3beceddac5c3d4a438c3524b1fddfd7c98947384b716717625328c9b54d3`。FULL 诊断日志停止后 SHA-256 为 `c5914b953399a57941b6937ec696cc89cd025f8a9cf45b571914c225af14601d`。

只将 graph 参数从 `FULL` 改为 `FULL_DECODE_ONLY`，`01-environment/decodefull-start.sh` SHA-256 `dbef7535a1cf85d599c125867c3e3996d93a6960c0b075e428545c7509fe44f2`，日志/结果写入独立 `04-runs/decodefull-v1-20260928/`。有效 EngineCore 配置明确为 `CUDAGraphMode.FULL_DECODE_ONLY`，只捕获 decode FULL 7/7，没有 mixed PIECEWISE；服务就绪。文本最小请求最终答 `2`，图像最小请求仍输出 64 个 `!`。原始 `04-runs/decodefull-smoke-v1-20260928/result.json` SHA-256 `b7de2ee721a2984ed301a8c5b3d21896cb5788acfd870ba7884dd53c717a2580`。

2026-09-29 的 T-Head 视觉 attention Plugin 缓解后，本任务对 PPU2 的 decode-full 服务只停止并重启当前任务 API，容器仍运行；新脚本 `01-environment/decodefull-product-start.sh` SHA-256 `e36428e175e98a2bb424e1bc1e6b8a7dc2c07efdc0aa93915ed48ce035013923`。`04-runs/decodefull-product-v1-20260929/server.log` 显示有效模式 `CUDAGraphMode.FULL_DECODE_ONLY` 和 decode FULL 捕获 7/7，服务已就绪。`04-runs/decodefull-product-smoke-v1-20260929/result.json` SHA-256 `70bddc4172c7d3c53c0a18e1eb1b2a54ff59b47516896e3c809529e9bc9a2a8a`：文本最终答 `2`，红蓝 224/448 图像均正确区分颜色，健康与进程身份稳定，正常前缀缓存开启。图片故障的边界和缓解详见 [002](002-visual-output-corruption.md)。这满足基本图模式功能检查，但不是正式 execution-mode 原生回执；后续服务验证继续保留本 Host 当前最高可用的 `decode-full` 级别。若 GDN backend 后续支持真正完整图，应重新优先尝试 FULL 并重做验收。

BF16 作用域收紧后的 Plugin 最终源码由 `01-environment/decodefull-product-v2-start.sh`（SHA-256 `49e44f4ae09f1337b42cc25a899ab93eae2c0c43038ee4b141468d0199198f62`）启动；`04-runs/decodefull-product-v2-20260929/server.log` 再次显示 decode FULL 7/7，`04-runs/decodefull-product-smoke-v2-20260929/result.json` SHA-256 `93d564ca9ebd1c0844cd68b06822e1db6b096dd5a6d1a9fa0830b74b60caec6d` 再次验证文本与红蓝 224/448 图像正常。后续原生验收只绑定这一轮服务及其源码身份。
