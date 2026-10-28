# 003：GDN backend 将 full graph 限定为 decode-full

## 身份与问题

- 日期：2026-09-28；Host `H100-149`；容器 `MinicpmV4.7-35B-native`。
- vLLM wheel `0.24.0+cu129`，模型 adapter SHA-256
  `91696f38a69091e45bd75fe1c35dd86ca32837c2827dd4d9251fda469ed2931f`。
- 模型 `/data/models/MiniCPM-V-4.7/weights/35b-a3b`，物理 GPU 2/3，TP2，
  BF16，2048 上下文，prefix caching 开启。
- 请求图配置：`--compilation-config '{"mode":0,"cudagraph_mode":"FULL"}'`。
- 原始日志：`/public/flagos/jinghao/MiniCPMV4.7-35B/native/04-runs/graph-tp2-full-v1/service.log`。

## 证据与判定

eager 模式已通过文本、单图、两帧视频请求，故先在相同模型与拓扑上移除
`--enforce-eager` 并明确请求 `FULL`。两名 worker 均报告：
`CUDAGraphMode.FULL is not supported with GDNAttentionBackend backend
(support: AttentionCGSupport.UNIFORM_BATCH); setting
cudagraph_mode=FULL_DECODE_ONLY`。实际捕获日志为
`Capturing CUDA graphs (decode, FULL): 4/4`，无 prefill full graph。
这是现有 GDN backend 能力限制，不是模型 adapter 的注册失败；不能将本轮记为
覆盖 prefill 的 full graph，也不能以分段图冒充。按 profile 的最低图级别
`decode-full` 继续验证。

图服务 `/health` 与模型列表返回 200，文本得到 `42`，红色单图得到 `Red`，
红蓝两帧视频识别正确。原始响应分别见同一运行目录的 `smoke.json`、
`image-smoke.json`、`video-smoke.json`。诊断性十并发包含 8 道简单算术和
2 个红色图像请求，10/10 完成且答案符合预期，详情在 `concurrency-10.json`。
该集合不替代项目要求的固定 GPQA sanity 或正式精度评测。

## 处理与范围

分类：框架能力约束。最终普通服务直接指定
`FULL_DECODE_ONLY`，避免每次启动请求无法实现的 prefill full graph。
不修改公共 GDN 执行路径。日后若 vLLM/GDN backend 声明并验证支持 mixed
prefill full graph，再单独复测升级。性能和长上下文正确性尚未验证。
