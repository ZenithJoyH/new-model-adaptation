# 对齐后执行模式验证

2026-10-27，PPU-01 / minicpm-ocr-ppu-native，新部署指纹035672fd74d7a9a7d9a52188a0443e1ab8244c52260a99dcb1f86c75896720e0。

使用262144上下文、64序列、TORCH_SDPA、0.55显存及正常前缀缓存。独立测试固定8192批次token，与删除显式预算后的API实际默认值一致。eager及FULL_AND_PIECEWISE各6类OCR均匹配独立Transformers参考的prompt/生成token IDs。图直接计数538次capture_end、98次replay；不推断全图支持、正式精度或性能。关闭放大的极小图与参考模型同样识别退化，不能算正确转录通过。

原生执行测量在 `04-runs/aligned-execution-20261027/measurements.json`，具体输出在aligned-eager-20261027、aligned-graph-20261027。本轮视觉注意力变化没有解除原生GDN的UNIFORM_BATCH限制；原FULL失败保留，并以当前GDN组件版本、源码SHA及能力声明重新核对，按序继续使用FULL_AND_PIECEWISE。

最终API通过更新后的根级start-model.sh默认启动。实际启动记录核查max_seq_len=262144、64序列、TORCH_SDPA生效、8192批次预算、缓存开启及prefill PIECEWISE/decode FULL捕获。文本和两帧视频请求通过，视频包含已知文字HELLO OCR / TEST 01。不可变启动与补充结果在 `04-runs/aligned-api-20261027/startup.log`、extras-result.json，视频响应在 `04-runs/video-aligned-20261027/response.json`。

只代表声明场景的功能验证，不代表262144满长质量或64路满长同时运行。
