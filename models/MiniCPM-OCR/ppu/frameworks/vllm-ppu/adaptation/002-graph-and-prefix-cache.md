# 002：FULL 图后端限制与原生前缀缓存默认值

2026-10-27，PPU-01 / minicpm-ocr-ppu-native / vLLM 0.23.0+v0.2.0.ppu2.1.0。属于运行配置调整，不修改平台后端或原生库。

## FULL 尝试与逐级选择

通过根级脚本请求 FULL。运行时明确报 `CUDAGraphMode.FULL is not supported with GDNAttentionBackend backend (support: AttentionCGSupport.UNIFORM_BATCH); setting cudagraph_mode=FULL_AND_PIECEWISE`。原始证据 `04-runs/graph-full-001/service.log`；实际安装 `vllm/v1/attention/backends/gdn_attn.py` 的 GDNAttentionMetadataBuilder 也声明 UNIFORM_BATCH。启动成功并不证明 FULL 成功。

检查本机 GDN 选择和编译分割：本模型 head_k_dim=128 使用原生 Triton/FLA prefill，GDN metadata 能力仅覆盖统一 decode batch；修改编译档位或 attention 后端名称无法增加动态 GDN prefill 的全图能力。未以修改能力声明伪装支持，也不替换只读 SDK/内核。完整 FULL 的退出条件为厂商提供可验证的混合 prefill GDN 图实现，并重新验证变输入捕获和回放。

按序仅降一级至 full-and-piecewise；不跳过 decode-full 或 piecewise，它们尚无需尝试。最终脚本显式选择 FULL_AND_PIECEWISE。该选择依据当前后端能力，不宣称已建立性能最优结论；experimental profile 无正式性能接口。

## 前缀缓存

最初参考 CacheConfig 的字段默认 True，未显式传 enable。实际 FULL 启动日志却为 `enable_prefix_caching=False`，因此该诊断实例不作缓存开启条件下的验收证据。保留日志，核对并停止本任务 API；容器持续运行。最终启动脚本明确保留 `--enable-prefix-caching`，性能分支使用 `--no-enable-prefix-caching`，不同时传相反参数。所有后续验证重新检查开启状态。

显式开启缓存的独立 eager/graph 测试在 `04-runs/execution-eager/`、`04-runs/execution-graph/`，日志同级 `execution-eager.log`、`execution-graph.log`。计数钩子只存在于 `03-acceptance/graph_execution.py` 的测试进程，产品源码未加入诊断。graph 测试重新请求 FULL，核查实际回退，直接统计 CUDAGraph capture_end/replay；是否通过以 summary.json 和输出为准。

最终批次 token 预算固定16384，以对齐独立 LLM 验证配置与服务端配置；上下文32768、8序列、PPU4/TP1、显存比例0.55。不是262144上下文或64并发的容量承诺。
