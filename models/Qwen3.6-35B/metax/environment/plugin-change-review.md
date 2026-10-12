# Plugin 变更设计审查

审查日期：2026-09-17。基线 Plugin `main@d1653d9ff0450ce0366686bfcde5d8aecab44755`，
目标 vLLM `bc150f50299199599673614f80d12a196f377655`，FlagGems-vLLM 同步前
`main@12bcf25c78d15be57badef6f54cf47e4351dde71`。

## 所有权与扩展点

GDN 的框架 metadata/state 生命周期继续由 vLLM 管理；Plugin 只在 MetaX patch 中将低层
chunk/recurrent 计算适配到 FlagGems-vLLM。fused MoE 继续由 Plugin 的既有
`TritonExpertsFL` 承接 vLLM 调用：无 LoRA/无 expert-map 使用整算子快速路径，其余场景
保留分阶段结构。分阶段 op 的 dispatch 所有权仍为 `default.flagos`，FlagOS adapter 在
MetaX 上委托 FlagGems-vLLM 的 no-TLE align、专用 GEMM 和 sum。kernel、调优配置和 MetaX
specialization 均由 FlagGems-vLLM 所有。

备选方案中，直接修改 vLLM 被排除，因为它是外部 dirty 只读树；在模型 adapter 中按
Qwen3.6 名称硬编码被排除，因为算子语义并非模型专属；调用 FlagGems-vLLM 高层 GDN
包装被排除，因为当前版本不转发 `chunk_indices/chunk_offsets`。

## 影响矩阵

| 调用方 | 预期行为 |
|---|---|
| MetaX Qwen3.5/Qwen3.6 GDN prefill | FlagGems-vLLM MetaX chunk 实现，保留变长 metadata |
| MetaX Qwen3.5/Qwen3.6 GDN decode | FlagGems-vLLM recurrent，实现前保留 FP32 gate 语义 |
| MetaX 无 LoRA、无 expert-map routed MoE | FlagGems-vLLM MetaX `outplace_fused_experts`，由 Qwen shape 分支选择专用 kernel |
| MetaX LoRA 或 expert-map MoE | 保持 Plugin 分阶段结构；三个 op 解析到 `default.flagos`，内部调 FlagGems-vLLM MetaX 实现 |
| 非 MetaX 的 FlagOS staged MoE | import 已改为 FlagGems-vLLM 通用实现；本轮未做其他硬件数值回归 |
| NVIDIA/ROCm/其他 OOT 平台 | 保持既有条件和调用目标 |
| KDA 或 FlagGems-vLLM 未覆盖参数组合 | 明确调用原实现，不扩大未经验证能力 |

## 最终审查

实际产品改动限定在 Plugin：MetaX GDN patch 增加 FlagGems-vLLM chunk/recurrent 适配；
`TritonExpertsFL.apply` 增加 MetaX `outplace_fused_experts` 快速路径；共享 FlagOS fused-MoE
实现及 facade 改为调用 FlagGems-vLLM 并兼容 `_topk_ids`；MetaX dispatch 配置将三个 staged
op 固定到 `flagos`。此前放在 MetaX vendor adapter 的 staged 改动已恢复到修正前备份。没有
修改 vLLM、FlagGems、FlagGems-vLLM 或模型权重，也没有引入模型名/机器名判断。

MoE 没有采用 `ops_moe_mxq.fused_moe`，因为其拆分权重与独立量化 ABI 不匹配；没有直接调用
`fused_experts_impl`，因为它是 MetaX outplace/inplace 接口共享的内部实现。选定入口来自
`flaggems_vllm.runtime.backend._metax.ops` 的导出面，且实测解析到
`_metax.ops.fused_moe`。

`git diff --check`、两组 mock 路由契约、GDN 数值、MetaX Qwen shape MoE 数值、整算子与
分阶段 Plugin 真实入口集成测试均通过；E=256 目标 shape 的三个 staged op 实测均解析到
`default.flagos`。证据与哈希见适配问题 001。FlagGems-vLLM 同步因网络失败，仍停留在已记录的
clean revision。未测试整模 eager/graph、LoRA、非恒等 EP map、量化和非 MetaX 平台，不能外推。
