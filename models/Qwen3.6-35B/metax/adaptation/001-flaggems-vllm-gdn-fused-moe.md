# 001：Plugin 接入 FlagGems-vLLM GDN 与 fused MoE

状态：实现与算子级验证完成；整模 eager/graph 未执行。日期：2026-09-17。目标：
`mx-104` / `qwen3.6-35B`。

## 症状与所有权

当前 GDN 从 Plugin 进入 vLLM custom op 后仍调用 vLLM 自带 FLA；MetaX fused MoE 因
OOT 平台不满足 `current_platform.is_cuda()`，走 Plugin 自身分阶段 dispatch。用户要求改为
Plugin 显式调用 FlagGems-vLLM 的 GDN 与 fused MoE 算子。

模型适配和平台选择属于 Plugin；具体 kernel 与 MetaX specialization 属于
FlagGems-vLLM；vLLM 保持只读。现有扩展点分别是 MetaX patch 初始化和
`TritonExpertsFL.apply` 的无 LoRA 快速路径。不得把模型名或机器名散落进共享执行代码。

## 接口决策

1. GDN prefill 使用顶层 `flaggems_vllm.chunk_gated_delta_rule_fwd`，因为它会绑定 MetaX
   专用实现并完整接收 vLLM 的 chunk metadata；不使用会丢失 metadata 的高层包装。
2. GDN decode 在 Plugin 保留 `A_log/dt_bias/a/b` 的 FP32 门控预处理，再调用
   `flaggems_vllm.fused_recurrent_gated_delta_rule_fwd`；KDA 等 FlagGems-vLLM 未覆盖的接口
   明确回退原实现。MetaX 层禁用 packed recurrent shortcut，防止默认 decode 绕过新接口。
3. fused MoE 在 MetaX、无 LoRA 且 `expert_map is None` 时直接导入
   `flaggems_vllm.runtime.backend._metax.ops.outplace_fused_experts`。这个入口与 Plugin
   `apply(output, ...)` 的 out-of-place 语义一致，并明确绑定 FlagGems-vLLM 的 MetaX 自包含
   分发；不再由 Plugin 直接调用内部 `fused_experts_impl`。LoRA 或 expert-map 场景保留
   GEMM1/activation/GEMM2 的分阶段结构；三个 op 仍由现有 `default.flagos` dispatch 所有，
   但 FlagOS adapter 内的 align、两次 GEMM kernel 和 sum 已分别切到 FlagGems-vLLM 的
   no-TLE align、MetaX
   `invoke_fused_moe_triton_kernel` 和 MetaX `moe_sum`。其他平台的 dispatch policy 不变，
   但这三个 FlagOS 入口同样改为 FlagGems-vLLM 的通用实现，尚未做其他硬件回归。
4. 可选依赖在调用路径内延迟导入；不在模型文件全局替换 ATen，也不修改 vLLM 或 FlagGems。

MetaX 配置为上述三个分阶段 op 指定唯一候选 `flagos`，运行时解析结果均为
`default.flagos`。FlagOS backend 内部不再导入 `flag_gems` 的这三个算子：MetaX 分支延迟导入
FlagGems-vLLM 的专用实现，其他平台分支导入 FlagGems-vLLM 通用实现。Plugin 私有
`_topk_ids` 仅是旧 mcoplib 优化提示，FlagGems-vLLM ABI 不接收它；FlagOS adapter 明确丢弃
该提示，使用 align 阶段已经生成的 `sorted_token_ids/expert_ids`。

`flaggems_vllm.ops_moe_mxq.fused_moe` 被核实后排除：它是独立 QC-MoE 接口，接收拆分的
`w1/w3/w2` 与自己的路由/量化结构，没有被 MetaX runtime `ops` 导出，不能无损承接 vLLM
当前 `[E, 2N, K] + [E, K, N]` 契约。目标入口 `outplace_fused_experts` 内部会以
`_is_qwen_plain_half_shape` 选择 Qwen/MC550 专用配置与 kernel。

## 继承改动与风险

Plugin 的 MetaX fused_moe 文件在本任务前已有大量调优修改；最初把 staged 路由放到
`vendor.metax` 后，经用户复核确认所有权应保留在 `default.flagos`，已将 vendor 文件恢复到
修正前备份，并只在共享 FlagOS backend 中替换这三个 import。GDN patch 文件开始前 clean。
主要风险是 state layout、变长 chunk metadata、speculative token 索引、graph capture，以及
fused MoE 对非恒等 expert map、量化和 LoRA 的覆盖范围；非 MetaX 平台的 FlagGems-vLLM 通用
入口尚未做硬件数值回归。

## 实施与证据

- Plugin 基线仍为 `main@d1653d9ff0450ce0366686bfcde5d8aecab44755`。本轮修改后的
  `gdn_linear_attn.py` SHA-256 为
  `a601a2c1f5a20e40a2bb726303d610c5c86149912f63a2bdb10d09a4d3f21e95`；
  `fused_moe_utils.py` 为
  `46ad18bc632b55d1f358b7da74f39c5a4d4c280d05adf83fec137794d7a3d2c1`；
  FlagOS `impl/fused_moe.py` 为
  `6e0c350a8e9ec2d7f91703d584834db88a78f56661ca924efd338277e62e9ece`；
  FlagOS facade `flaggems.py` 为
  `de5c3e0ad24e1a4ad5497e8d37c07b25fdb0796fecce567c58da2cefde5ee074`；
  MetaX vendor `impl/fused_moe.py` 已恢复为修正前 SHA-256
  `b39aa9c03d7884b75d439cdd1fdcb824260232c30a83eb03217f591e18f648a0`；
  `dispatch/config/metax.yaml` 为
  `50a47216e904f3d7d0249131078e156a4e274b012240b3b8f049db0383ee4987`。
- 路由契约
  `/data/jinghao/qwen3.6/07-bugs/qwen36_gdn_moe_routing_contract.py`
  （SHA-256 `d33c815e5d38608829366375c2b6655f5ca1cec76e65972b045888241a32529a`）
  通过。测试把通用 `fused_experts_impl` 设为调用即失败，确认 MetaX 路径只调用
  `outplace_fused_experts`；同时覆盖 GDN metadata、FP32 gate/beta、KDA guard 和 packed
  recurrent 禁用。
- GDN 数值收据
  `/data/jinghao/qwen3.6/04-runs/gdn-flaggems-vllm-numerical-20260916.json`
  （SHA-256 `43f6835cdad6c2505a611e1c3397ca35c0cd6fce1dc8c2430e14428ad13a990e`）
  通过：变长 prefill 输出/state 与旧路径一致；decode 对纯 PyTorch 参考的输出最大绝对误差
  `1.907e-06`，state 最大绝对误差 `1.192e-07`。
- MetaX 专用 MoE 直接数值收据
  `/data/jinghao/qwen3.6/04-runs/moe-flaggems-vllm-metax-qwen-shape-20260916.json`
  （SHA-256 `6de04ded534967f712acd6bc3ea116c9239ad01b70d75d1c4bd7c79fbc334dc0`）
  通过。目标 BF16 shape 为 `x=[1,2048]`、`w1=[256,1024,2048]`、
  `w2=[256,2048,512]`、top-k 8；`_is_qwen_plain_half_shape=True`，实现模块为
  `flaggems_vllm.runtime.backend._metax.ops.fused_moe`，对 FP32 PyTorch 参考最大绝对误差
  `2.0702428e-06`、余弦相似度 `0.999992907`。
- Plugin 真实入口收据
  `/data/jinghao/qwen3.6/04-runs/plugin-moe-flaggems-vllm-metax-integration-20260916.json`
  （SHA-256 `6b2943383d17f3d63abcd2b9e9e348287636abdfb486aec317e7c5b730c543f3`）
  通过：由 `TritonExpertsFL.apply` 进入同一 MetaX outplace 算子，误差与直接测试一致。
- 修正后的分阶段 import/ABI 契约收据
  `/data/jinghao/qwen3.6/04-runs/flagos-staged-moe-flaggems-vllm-routing-contract-20260917.json`
  （SHA-256 `008cdfd9d797334f0d3e37bca0cd1ee0b7da5f4ddab3c9433afb837b37ac4191`）
  通过，确认 dispatch 所有权为 `default.flagos`，align/invoke/sum 的实际 import 均来自
  FlagGems-vLLM，并确认 `_topk_ids` 不会泄漏到其 ABI。
- 修正后的 Plugin 分阶段真实入口收据
  `/data/jinghao/qwen3.6/04-runs/plugin-flagos-staged-moe-flaggems-vllm-integration-20260917.json`
  （SHA-256 `179c055e0fc6af64b1e6baef3049035fd1ec58584a4f19e7dfbf404c3f0deb7c`）
  通过。以恒等 expert-map 强制进入分阶段路径，三个 op 均解析到 `default.flagos`；目标
  BF16 shape 为 `x=[1,2048]`、`w1=[256,1024,2048]`、`w2=[256,2048,512]`、top-k 8。
  对 FP32 参考最大绝对误差 `1.4150137e-06`、平均绝对误差 `2.9544435e-07`、余弦相似度
  `0.999991298`。
- Plugin 全树 `git diff --check` 通过；任务开始前的 8 个 tracked 修改和 1 个未跟踪备份均保留，
  当前多出的 GDN 修改与 MoE 快速路径修改已单独审查。

FlagGems-vLLM 保持 clean 的
`main@12bcf25c78d15be57badef6f54cf47e4351dde71`。按计划执行的 `git pull --ff-only`
因远端 HTTP/2 framing error 失败，HTTP/1.1 重试无进展后被中止；源码未变化，不能声称已同步到
远端最新 revision。

## 剩余范围

本轮只执行 adaptation，未启动模型服务，也未执行最小整模 eager、graph、正式准确率或性能
验收；因此平台适配仍为 `in_progress`。恒等 expert-map 的 E=256 分阶段路径已验证；非恒等
EP map、LoRA、量化 MoE 和其他平台没有通过本机结果获得支持声明。9 月 16 日验证期间另一套
VLLM TP 服务曾占用全部 8 卡，本任务未停止或重启它；9 月 17 日复测时设备已空闲。后续整模
验证必须确认实际权重 shape
命中上述专用分支，并分别覆盖 prefill 与 decode；失败时保留首个错误，不增加 broad fallback。
