# 003：GDN attention 限制 mixed prefill/decode 全图

## 元数据

- 状态：确认，采用 profile 允许的 `decode-full` 级别
- 日期：2026-09-28
- Host/容器：`H100-149` / `MinicpmV4.7-1B-native`
- 模型及模式：1B、BF16、GPU 0 TP1、vLLM 0.24.0、非性能前缀缓存开启

## 失败签名和受控对照

`01-environment/start-minicpmv47-full.sh` 明确请求
`--compilation-config '{"cudagraph_mode":"FULL"}'`。
`04-runs/native-full-20260928/service.log` 显示模型权重加载并编译后，
vLLM 记录 `CUDAGraphMode.FULL is not supported with GDNAttentionBackend`
及 `AttentionCGSupport.UNIFORM_BATCH`，自动设为
`FULL_AND_PIECEWISE`；随后捕获 mixed PIECEWISE 和 decode FULL。
vLLM 的 `v1/attention/backends/gdn_attn.py` 静态声明
`_cudagraph_support = AttentionCGSupport.UNIFORM_BATCH`，
`config/compilation.py` 在这种条件下降级 mixed graph。
该配置不能作为 full graph 通过。

只改变 graph 参数为 `FULL_DECODE_ONLY`，其他模型、GPU、prefix cache 和容量
保持一致，`04-runs/native-decode-full-20260928/service.log` 记录
51 个 decode FULL graph 捕获完成，未自动降级。十并发文本、单图、双图、
视频变输入请求均正常结束；摘要为
`04-runs/native-decode-full-20260928/concurrent-summary.json`，
SHA-256 `19600f0270008d923a19f02837177f4d588006bb0cf38f008f6b2610017c6578`。

## 结论与退出条件

本轮 `full` 尝试未通过，显式 `decode-full` 已通过功能验证并是当前
正式验收可用的最高级别。按用户要求另行显式启动
`FULL_AND_PIECEWISE`，验证 mixed prefill/decode 的 51 个 PIECEWISE 图与
decode 的 51 个 FULL 图均捕获成功，十并发文本、图像、视频请求通过；
详情见 `acceptance/full-and-piecewise-diagnostic.md`。限制是 prefill 未用 full graph；不能把自动降级的
PIECEWISE 记作 full。若将来 GDN 后端支持 mixed FULL，需在相同
模型、修订和负载上重新请求 FULL，核对生效模式、捕获与回放，
随后重新执行下游精度和性能验收。知识库决定：`needs-validation`。
