# MiniMax-M3 / PPU Plugin 修改设计审查

## 范围与版本

- 对象：`PPU-13` / `minimaxM3` / editable `/workspace/vllm-plugin-FL`。
- 初始 Plugin：`main`，HEAD `29712e42dba86680577aef9f2f6b5b7f04050a89`，`main...origin/main`，clean。
- PR base：`origin/main` 与本地 `main` 同步于 `29712e42dba86680577aef9f2f6b5b7f04050a89`。最初的 T-Head-only 实现曾提交为 `86ec92fda1e7d329448f477a717e42e6a8d4f171` 并普通推送至 `ZenithJoyH/vllm-plugin-FL: support-minimax-m3`。2026-09-16 经用户明确授权，容器内同名分支已把该提交从本地历史移除，并将当前 FlagOS dispatch redesign 重新提交为 `aee54f38580e0b8b3db5ed433663ed5359ca308b`（tree `6fac31e4cdf13f6d31cf4e37b23e1f88ef38d2c0`，父提交仍为上述 base）。随后以旧远端 SHA `86ec92fd` 为显式 lease 执行 force-with-lease；本机临时仓库与 PPU-13 容器两侧 `ls-remote` 均核对 GitHub 分支为 `aee54f3`。未创建 PR。
- vLLM：`ee0da84ab9e04ac7610e28580af62c365e898389`，detached clean，只读。
- FlagGems：本轮再次从 `be05ef1db6758adca7a18de3bf529c18a6ac9a87` clean fast-forward 到 `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85`，master clean。用户补充提供的 FlagGems-vllm 从 `7eda432f7cd9495d4f4f292a0b3b40953f46a940` clean fast-forward 到 `bfe7ac06b3ebf95c6aba7dead56ff7d465019939`，main clean。
- 审查状态：`当前 redesign 已提交并推送`。新提交精确包含 20 个文件、1682 行新增/13 行删除；最终设计不合成 vLLM 私有 `_C` ABI。`git diff HEAD^ HEAD --check`、focused 15/15、其余 dispatch 277/277 通过。4 个 `.orig` 备份仍未跟踪且未删除。

## 当前问题与候选设计

首要触发是 PlatformFL 激活后 `torch.ops._C.fused_minimax_m3_qknorm_rope_kv_insert` 仍不存在。vLLM MiniMax-M3 nvidia 分支在 dense 和 sparse attention 的 forward 中直接调用该 op，因此完整构造/运行不能靠普通 FA3 backend 解决。候选顺序：同步后 FlagGems 兼容算子 → Plugin 现有 custom-op/platform hook 注册 → 必要时 Plugin-owned Triton/custom op。禁止修改 vLLM 或在模型路径中直接调用 FlagGems。

预期 contract 包括 BF16 QKV，64/4 heads，head dim 128，rotary dim 64，Gemma Q/K norm，dense 无 cache out 与 sparse main/index cache insert，padding slot、out buffer、in-place alias，以及 eager/graph capture/replay。最终实现必须用精确 thead/capability/contract guard，不改变 NVIDIA、ROCm 或其他 Plugin 模型默认行为。

## 预定回归矩阵

| 场景 | 目标 | 状态 |
|---|---|---|
| 无设备/其他模型 import 与重复注册 | 可选依赖隔离、幂等、guard miss | Plugin import/注册及 router 非 T-Head miss-path 通过；更广多平台 CI 待 PR 前执行 |
| MiniMax dense fused pre-process | norm/RoPE/QKV split，无 cache | focused 数值与 graph 通过 |
| MiniMax sparse fused pre-process | main/index cache insert、padding、out buffer | focused 数值与 graph 通过 |
| Gemma RMSNorm | normal/fused residual、alias | eager/graph 聚焦验证通过 |
| MSA indexer/sparse attend | prefill/decode、block 128、top-16 | 聚焦 prefill/decode 与整模 profile 通过 |
| MoE/SwiGLU-OAI | FP32 router、top-4/shared expert | router/activation eager+graph 及整模通过 |
| 整模型 | TP16 eager 与 graph | eager run5、graph run2 与 changed-input API 通过 |

## 实际变更审查

- registry/schema/backend：redesign 后 `patches/minimax_m3.py` 仅在原生 symbol 缺失时替换 `vllm._custom_ops` 的 MiniMax 专属包装函数，并通过 `CachedOp` 进入 dispatch；不注册或覆盖 vLLM 私有 `_C` schema。PPU 专属 top-k 编译器补丁独立在 `patches/minimax_m3_thead.py`。MiniMax Triton 实现与注册位于 `dispatch/backends/flaggems/`，原 `ops/minimax_m3.py`、`vendor/thead/minimax_m3.py` 和 T-Head provider 注册均已删除。
- 稀疏 attention：`patches/minimax_m3.py` 仅绕开 PPU Triton 对合法 constexpr assert 的误拒，在 Python launch 前保留不变量检查；decode 保持原路径。
- RoPE：`ApplyRotaryEmbFL` 仍在公共 OOT 扩展点承担 partial contract 适配，但计算通过 `CachedOp` 进入 FlagGems backend，优先复用 FlagGems-vllm rotary；focused 覆盖 78/80、128/128 和 changed-input graph。
- MoE：sigmoid+bias 等价 single-group 路径不再含平台名判断，统一复用现有 grouped-topk dispatch；packed `SWIGLUOAI_UNINTERLEAVE` Triton kernel 迁入 FlagGems impl，调用处只保留 `CachedOp` 与参数透传。
- FA3：只删除当前 vLLM 不存在且从未使用的 import，无行为重构。
- 证据：最终 redesign 后 `04-runs/plugin-minimax-dispatch-callsite-patch/focused-tests.log` 15/15、`dispatch-regression.log` 277/277（其余 5 项在 focused 覆盖），标准 general-plugin loader 观测 `native_schema=False`、`python_patch=True`，四个相关 op 的运行时选择均为 `default.flagos`。同一源码字节已完成 TP16 eager/graph、固定前十题 10/10 与 GPQA Diamond 177/198（89.39%）；Git 历史改写未改变工作树字节或运行中的服务实例。

## 最终结论与出口条件

- 结论：`职责重分类已通过 PPU 聚焦/dispatch/整模精度回归，并完成提交与受保护推送`。缺失且可移植的 kernel 已归 `default.flagos`，T-Head 目录只保留真实 PPU 差异；未见 broad exception fallback、vLLM 修改或模型名散布。GitHub `support-minimax-m3` 已指向新提交。
- 出口条件：PR 前执行可用的 NVIDIA/其他平台 CI，并确认目标 base；4 个 `.orig` 继续排除在产品提交外。
- 已知限制：本轮只在 PPU-13/MiniMax-M3 验证，不由此推断其他平台支持。

当前完整适配验收状态：execution-mode、固定前 10 题 sanity 和 GPQA Diamond 198 全量 c64 accuracy 已通过；performance/evidence/summary 尚未执行。设计审查状态与完整验收状态不互相替代；本轮已完成容器内 commit 与 GitHub 分支更新，未创建 PR。

上述当前验收结果绑定服务实例 `ppu13-minimaxM3-7ffdd70d-boot-e0f88877-pid1551482-start219575444-cmd4735fa06`。提交操作未重启服务或容器，提交后 `/health` 仍为 200。
