# 003：TP sample_tokens 超时与缓解

## 元数据与失败签名

Qwen3.8-Flash-Next / PPU-01 / `qwen3.8-flash`，TP8、graph，2026-09-06 正式 GPQA c32。
完成 3 个请求后，31 条 decode 与一条 462-token 新 prefill 混合调度时，生成计数停在 17237；
300 秒后 `sample_tokens` RPC 超时，通信 work 序号分叉、EngineCore 退出。

## 诊断、已有经验与受控尝试

匹配 [TP 超时知识条目](../../../../docs/troubleshooting/distributed-sample-tokens-timeout.md) 的症状顺序。
原记录保留 per-rank 证据并确认未见 OOM/设备故障；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
识别 `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS`，默认 300，同时用于 execute_model 和 sample_tokens。

唯一变更为 300 → 1800 秒；其他 graph、TP、上下文及批处理配置保持一致。原 c32 混合
prefill/decode 压力验证 40/40 HTTP 200，严格生成 22000 tokens，总耗时 213.636 秒。
这支持该负载下的缓解有效，不能单凭压力通过断言已经消除卡顿根因。

## 当前结论与生命周期

状态：mitigation，整模首次停滞的底层原因仍需根据实际进度和最早分叉 rank 排查。
失败后仅清理本任务孤儿 worker 350418–350425，确认退出；容器未停止，vLLM 未修改。
第二轮评测后续暴露了独立的 index SQLite 锁问题，不能合并为同一根因。

## 证据、限制与下一步

[历史进度与精确生命周期](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/history/progress.md)、[服务配置](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/runtime-config.yml)、
[验收总结](../acceptance/adaptation-summary.md)。重复试验的旧启动和压力脚本不作为当前执行入口。
本页仅整理历史证据，未新启服务。若停止进展或序号持续分叉，停止增加超时，排查最早异常。
正式 accuracy 尚不能据此视为通过；知识状态：needs-validation。
