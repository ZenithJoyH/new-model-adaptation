# 002：FULL 图模式的 GDN 能力限制

2026-10-20，H100-149、原生 vLLM 0.24.0、TP1、BF16、前缀缓存开启。

首先显式尝试 `--compilation-config '{"cudagraph_mode":"FULL"}'`，保留其余容量与硬件配置。编译后日志明确提示 `FULL is not supported with GDNAttentionBackend backend (support: AttentionCGSupport.UNIFORM_BATCH)`，随后自动选择 `FULL_AND_PIECEWISE`。本次 FULL 尝试记为未通过。

检查实际安装的 `vllm/v1/attention/backends/gdn_attn.py`：`GDNAttentionMetadataBuilder._cudagraph_support = AttentionCGSupport.UNIFORM_BATCH`，文件 SHA-256 `a76cddf32de48927b44e2db441ff551005f035cd0f3dd36aaa1ae0d3b850dcd2`。这是 metadata/批次能力声明，与 FlashInfer/Triton 的 GDN prefill 算术内核选择不同。审查了切换 prefill backend 的补救方向：它不能改变当前 backend 的 FULL 能力，因而不做无效重复启动或绕过公共守卫。重试 FULL 的条件是后端正式支持 mixed prefill/decode capture，包括动态 metadata 和 chunked prefill。

保留诊断后，仅向下一档，显式启动 `FULL_AND_PIECEWISE`。实际日志分别完成 mixed prefill-decode PIECEWISE 与 decode FULL 捕获；capture sizes 为 [1, 2, 4, 8, 16]，FULL decode 最大 batch 8。未尝试更低档位。七组请求的输出、prompt token 数及生成 token ID 与同构 Transformers 参考全部一致；混合 4x/16x 四并发与视频请求正常。

最终脚本固定此档位和正常前缀缓存，并经脚本自身启动后的复验。本轮没有性能比较，不声称性能最优或 optimized。用户已选择正式精度/性能另行安排。

证据在批准远端工作根：`04-runs/graph-full-20261020/service.log`、`02-issues/full-graph-limitation.json`、`04-runs/graph-full-and-piecewise-20261020/service.log`、`04-runs/graph-functional-20261020/parity.json`、`04-runs/graph-video-20261020/result.json`、`04-runs/final-functional-20261020/parity.json`、`04-runs/start-model.log`。功能与配置验证不替代 v2 完整 execution-mode 测量回执。
