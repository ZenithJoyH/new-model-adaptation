# MetaX 环境与调用链分析

核实时间：2026-09-16（Asia/Shanghai）。本轮唯一目标为 inventory SSH 别名
`mx-104`、容器 `qwen3.6-35B`、模型 `/data/Qwen3.6-35B-A3B-nomtp`。
`connectivity-check`、`accelerator-check`、`health-check` 均为
`failed=0 unreachable=0`。

## 主机、设备与容器

- 宿主机名 `bm-zksg-wx-zone1-d-mc550-64g-2-104`。根文件系统 877G，采集时使用
  449G、可用 392G。
- 8× MetaX C550，每卡 65536 MiB；`mx-smi 2.3.1`，Kernel Mode Driver
  3.8.1，MACA 3.7.1.5。采集时每卡约 858 MiB、利用率 0%，状态 Available。
- 容器持续为 running，启动时间
  `2026-09-16T01:55:55.062349767Z`，工作目录 `/workspace`。镜像为
  `harbor.baai.ac.cn/flagrelease-public/qwen36-35b-a3b-metax001-gems5.0.2-tree0.5.1-cxnone-plugin0.2.0-vllm0.20.2-cp312-pt28-maca37-x64-3.8.1:202607280210`，
  image ID `sha256:26050e208e6b5ca684a9e9daee9f0b41f6730a8df44438a133b492b75f84b0a8`。
  容器 Ubuntu 22.04.3、Python 3.12.11、PyTorch `2.8.0+metax3.7.0.7`，
  `torch.version.maca=3.7.0.7`。
- 采集时容器内只有交互 shell，没有模型服务。本任务不停止、重启或移除容器。

## 远端工作边界

宿主批准根与容器根均为 `/data/jinghao/qwen3.6`；容器以读写方式 bind mount
`/data` 到 `/data`。根目录和 `01-environment/` 至 `07-bugs/` 在宿主/容器两侧的
device/inode 完全一致，证明路径映射真实有效。新运行配置、诊断、验收、输出、临时文件和
缓存分别限制在这些目录。模型权重只读；产品改动只允许落在已核实的 Plugin 可编辑源码树。

## 运行代码身份与继承状态

| 组件 | 可编辑源码 / 版本 | revision 与状态 |
|---|---|---|
| Plugin | `/workspace/vllm-plugin-FL`，`vllm-plugin-fl 0.2.0+gd1653d9ff` | `main@d1653d9ff0450ce0366686bfcde5d8aecab44755`；开始前已有 8 个 tracked 修改和 1 个未跟踪备份，必须保留 |
| FlagGems-vLLM | `/workspace/FlagGems-vllm`，`flaggems_vllm 0.1.0` | `main@12bcf25c78d15be57badef6f54cf47e4351dde71`，跟踪 `origin/main`，采集时及适配后均 clean；fast-forward-only 同步因 HTTP/2 framing error 失败，revision 未变 |
| FlagGems | `/workspace/FlagGems`，`flag_gems 5.0.2` | detached `3123859968915e361e8452dd796dc6b27c956324`，开始前已有多项修改；本轮不写、不同步 |
| vLLM | `/workspace/vllm`，`0.20.2+empty` | detached `bc150f50299199599673614f80d12a196f377655`，开始前已有 8 个 tracked 修改和 2 个未跟踪文件；本轮严格只读 |

Plugin 继承修改涉及 MetaX activation/attention/fused_moe/backend/config 以及两处 fused_moe
公共文件；后续补丁必须最小化并重新核对完整 diff。vLLM 的 GDN、采样与 runner 修改也是
继承工作，不能复原、覆盖或据此宣称为本轮成果。

## 当前调用链结论

- GDN：Plugin 的 MetaX pluggable-layer 补丁最终仍调用
  `torch.ops.vllm.gdn_attention_core`。该 custom op 回到 vLLM
  `GatedDeltaNetAttention._forward_core`；prefill 默认调用 vLLM FLA
  `chunk_gated_delta_rule`，decode 默认可能调用 packed recurrent 或
  `fused_sigmoid_gating_delta_rule_update`。历史启动日志也显示
  `Using Triton/FLA GDN prefill kernel`，因此当前没有调用 FlagGems-vLLM GDN。
- FlagGems-vLLM 的 MetaX `chunk_gated_delta_rule_fwd` 与 vLLM 0.20.2 低层 ABI 对齐，
  包含 `cu_seqlens`、`chunk_indices`、`chunk_offsets` 并返回七元组；公开高层
  `chunk_gated_delta_rule` 没有转发两个 chunk metadata，不能直接替换当前变长 prefill。
- decode 的 FlagGems-vLLM recurrent 算子接收已经计算好的 `g` 与 `beta`；Plugin 适配层
  必须保留 vLLM 的 FP32 `softplus/exp` 衰减和 sigmoid 语义，再调用
  `fused_recurrent_gated_delta_rule_fwd`。为了覆盖默认纯 decode，MetaX 层还需禁用会绕过
  该接口的 packed recurrent 分支。
- fused MoE：Plugin 的 `TritonExpertsFL.apply` 已有“无 LoRA 整算子快速路径”，但它仅在
  `current_platform.is_cuda()` 时导入 `flag_gems.fused_experts_impl`。MetaX OOT 平台因此走
  Plugin 分阶段 dispatch。FlagGems-vLLM 的 MetaX runtime 明确导出
  `outplace_fused_experts`，其内部包含 Qwen plain-half shape 判定、专用 tile/kernel 与 MetaX
  `moe_sum`，适合作为 MetaX、无 LoRA、无 expert-map 快速路径。独立
  `ops_moe_mxq.fused_moe` 的拆分权重 ABI 与当前 vLLM 契约不匹配；LoRA 和 expert-map 必须
  继续走分阶段路径。适配后，这条分阶段路径的 `moe_align_block_size`、
  `invoke_fused_moe_triton_kernel` 和 `moe_sum` 由 MetaX per-op policy 固定选择 `flagos`，
  运行时实现 ID 均为 `default.flagos`；FlagOS adapter 在 MetaX 上分别延迟导入
  FlagGems-vLLM 的 no-TLE align、专用 staged GEMM 和 sum，不再调用旧 `flag_gems` 算子。

## 环境阶段结论

主机、设备、容器、模型、可编辑 Plugin、只读 vLLM/FlagGems、可同步的 clean
FlagGems-vLLM 以及宿主/容器工作根映射均已明确，可以进入适配阶段。环境检查不代表
新算子已通过数值、eager、graph 或整模验证。
