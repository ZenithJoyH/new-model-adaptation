# 001：W8A8 MoE 缺失 split SwiGLU-OAI 路径

## 元数据

- 状态：`hypothesis`（仅静态差距，尚无 PPU 运行失败签名）。
- 首次/最后验证：2026-09-29。
- 模型/平台/Host：MiniMax-M3.1 W8A8，T-Head PPU-ZW810E，`PPU-07`。
- 容器：`minimaxM3.1`，镜像 ID `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`。
- 源码基线：Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c`；FlagGems `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 模式/负载：W8A8 MoE，预期 eager 与 graph；设备测试尚未执行。

## 现象与证据

模型 `config.json` 声明 57 层 MoE、128 routed experts、top-4，`hidden_act=swigluoai`，alpha `1.702`、beta `1`、clamp `7`。当前 Plugin `/workspace/vllm-plugin-FL/vllm_fl/quantization/w8a8/moe_experts.py` 的 `FlagGemsW8A8Experts` 只允许 `MoEActivation.SILU`；当前 FlagGems checkout 的 `fused_experts_impl` 也只接受 `silu`。用户提供的两个补丁分别扩展 FlagGems activation 与 Plugin W8A8 参数传递，`git apply --check` 均为 0，但尚未应用。参考文件 SHA-256 分别为 `b67df100fecde963d6312de65fa8578f70e733f61ed7c35ecbb7f09942ca1a06` 和 `9de164804ee05d3cd983e94762e55f9a6250848a0f8d284d05c46a018b61bff5`。

当前没有整模运行失败或前后数值对照，不能称为已证实根因。FlagGems `origin/master` 的远端头为 `ea95fce196252738c6f18bcca997fa0d8a481d19`，当前 checkout 是 `3c6f7537...`；必须完成单独授权的只快进同步并重新检索算子后，才能对“缺失”作最终判断。

## 已有经验匹配

旧 MiniMax-M3 的 [SwiGLU-OAI 边界问题](../../../../../MiniMax-M3/ppu/frameworks/vllm-plugin-fl/adaptation/001-swigluoai-boundary.md)涉及同一激活族，但模型版本、量化格式、Plugin/FlagGems revision、topology 与 graph 运行均不同，本次只将其视为候选假设。故障库的 TP `sample_tokens` timeout 与 shape-aware dispatch fullgraph ContextVar/RLock 尚无相同症状，暂不套用。

## 诊断与计划

1. 核对上游 FlagGems 同步后的确切 revision、现有激活符号和 W8A8 fused MoE 接口；保留同步前后状态。配置只读权重，禁止改模型目录或在工作根复制源码。
2. 用小张量在同一 PPU 环境对比 split gate/up 的 `gate=min(gate,7)`、`up=clamp(up,-7,7)`、`gate*sigmoid(1.702*gate)*(up+1)`，覆盖 dtype、边界、shape、stride 和多次变输入 graph replay；先证实算子差距，再扩大到 Plugin 路径。
3. 若同步后的 FlagGems 仍无兼容算子，按 profile 在 editable Plugin 的 W8A8 adapter/既有 MoE policy 路径接入 Plugin 自有 Triton 实现。FlagGems 参考补丁只作算法参考，不直接修改 FlagGems 产品树。守卫不命中时其他模型原有 `silu` 路径必须不变。
4. 验证 Plugin 导入、量化映射、真实整模 eager 与优先 full graph；每次扩大范围前先通过较窄层测试。最终审查 PR base、HEAD、继承 dirty、实际 diff、影响矩阵、测试和退出条件。

## 当前结论与限制

目前仅有静态接口不匹配证据。FlagGems 同步、算子数值、graph、Plugin 变更、整模和正式验收均未执行。`minimaxM3.1` 容器没有停止/重启，vLLM 源码仍为只读 clean。此问题保持 `hypothesis`，不提升故障库。

## 2026-09-30 受控实施与设备对照

用户授权后，FlagGems 在 `PPU-07` 从干净的 `3c6f7537` 只快进至干净的 `6b49cff993956bff8cef495abd84f2acb6a63df6`。新版本 `MoEActivation` 有 `SWIGLUOAI`，但 `fused_experts_impl` 入口仍硬断言 `activation == "silu"`，其通用 `SWIGLUOAI` 分支也按普通 SiLU 计算，缺少 split layout 和显式 alpha/beta/clamp。因此与本次 M3.1 W8A8 的完整失败签名相符；不把旧 M3 的经验当作已经证实的解法。

实现归属选择：FlagGems 产品树只作授权同步，vLLM 只读；在 editable Plugin 的 `quantization/w8a8/moe_experts.py` 激活守卫和既有 `ops/fused_moe/fused_moe.py` 两段动态 INT8 路径中接入 `swigluoai_uninterleave`。此分支沿 Plugin 的 `CachedOp`/PPU dispatcher 调用已有 split 激活算子；`silu` 继续走原 FlagGems fused 路径。未导入参考补丁中 GPTQ/W8A16/H100 代码。第一个候选方案复用 vLLM 0.24 `TritonExperts.apply`，设备算例在量化后首先报 `Unsupported compute_type: torch.int8`，故撤出该候选，未把它保留作静默 fallback。转用 Plugin 既有两段路径后，先遇旧调用 `_get_config_quant_dtype(..., ocp_mx_scheme=None)` 与当前 vLLM 0.24 签名不合；只移除此无效参数，复测通过。每次只改变对应一个接口变量；日志保存在 `04-runs/ppu-moe-repro-20260930.log` 的诊断过程，最终日志 SHA-256 `6129af516826635b853a0c96369f44a5b34f1de5bd185e9e691be3a0ff982841`。

最终单卡 PPU 小形状对照用 `07-bugs/ppu-moe-repro-20260930.py`（SHA-256 `d02f1b3a8ea4d7b387b6e8f818e4f8d484624d4f0785d1502ed17331a7b0507c`）运行：独立 split 激活相对 FP32 公式最大绝对误差 0；零权重完整两段 W8A8 输出为零；非零 INT8 专家、两个路由专家分别与 FP32 参考对照，最大输出 7.71875，最大绝对误差 0.15650，在冻结的 `atol=0.25, rtol=0.15` 内。运行中 `moe_align_block_size`、`invoke_fused_moe_triton_kernel`、`moe_sum` 走 PPU dispatcher；出现一次 `tle.distributed_barrier` 候选配置编译不支持，调优 fallback 后结果通过，性能仍须正式评估。CPU 聚焦回归 `04-runs/plugin-tests-20260930.log`（SHA-256 `aae4bf4edf62622b80df95217fcb848a9acb23d5e57190fc061661823af3a195`）为 18 passed，包括 `silu` 原路径与 split 参数守卫。

当前审查：Plugin HEAD 仍为 `cafe6363c8c3de5ba4693b91643089c17b3ab87c`，tracked diff 仅 `vllm_fl/__init__.py`、`vllm_fl/ops/fused_moe/fused_moe.py`、`vllm_fl/quantization/w8a8/moe_experts.py`；新 helper/测试为未跟踪文件，四个继承的 `.orig` 原样保留。vLLM 与 FlagGems clean；FlagGems-vllm 原有两处 tracked 修改未触碰。影响矩阵：PPU dynamic W8A8 split 分支已单卡测数值；原 `silu` 路径已有 CPU guard/转发回归；NVIDIA split 明确报不支持而不丢参数；TP16、vision、真实权重装载和 eager/graph 服务仍待验证。正式 PR base 未确认，尚不能做最终设计或验收结论。

## 2026-09-30 整模复验

在当前 Plugin/FlagGems/vLLM 修订与 TP16 BF16 下，48/48 权重分片完成装载。修复 prefill top-k 后，eager 聊天请求首次和热态均返回 HTTP 200、`1+1=2`；显式 decode-full 图完成 6/6 capture，`1+1=2` 和两次变输入 replay（`2+3=5`、`7-4=3`）均正确，EngineCore/API 未退出。证据见 `04-runs/eager-chat-warm-20260930.json`（SHA-256 `fc6b732964eb479df67f058248865e14e6e45faf67656e7577fb06852a4118f0`）、`04-runs/graph-decode-full-chat-20260930.json`（`16e715481804fd0e6e76bd15b0cc4ff4e32299c85e9e12d8545fbbc7e1234fab`）和 `04-runs/graph-decode-full-changed-input-20260930.json`（`10667232973d4c7d9ad589359134c5f095739ccdfbda35d0b87ed9b60366683e`）。这些证明目标 MoE 路径至少可用于实际服务和 decode 图；严格的十题/全量精度与性能仍需按冻结配置执行。FULL prefill+decode 因两个 vLLM MiniMax 后端能力检查被自动降级，详见 [004](004-full-graph-backend-coverage.md)。
