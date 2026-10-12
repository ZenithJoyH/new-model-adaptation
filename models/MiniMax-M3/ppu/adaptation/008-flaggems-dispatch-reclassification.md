# 008：MiniMax-M3 缺失算子迁入通用 FlagGems dispatch

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-15
- 最后验证时间：2026-09-16
- 模型：`MiniMaxAI/MiniMax-M3`，权重 `/mnt/cpfs/models/MiniMax-M3`
- 平台与 Host 别名：T-Head PPU-ZW810E，`PPU-13`
- 容器名称与镜像：`minimaxM3`；镜像 digest 见 `platform.yml`
- Plugin / FlagGems / vLLM revision：Plugin `support-minimax-m3@aee54f38580e0b8b3db5ed433663ed5359ca308b`（tree `6fac31e4cdf13f6d31cf4e37b23e1f88ef38d2c0`）；FlagGems `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85`；FlagGems-vllm `bfe7ac06b3ebf95c6aba7dead56ff7d465019939`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：单算子 eager/changed-input graph、Plugin dispatch 回归；既有 TP16 graph 服务未重启

## 问题现象

- 错误签名或症状：已通过 PPU 验证的 MiniMax-M3 fused preprocess 与 packed SwiGLUOAI Triton kernel 位于 `vendor/thead` 或公共调用层，导致实现所有权、provider kind 与其可移植 Triton 属性不一致；sigmoid router 也被不必要地限制为 T-Head。
- 发生顺序：用户审查当前实现归属 → 要求先复用 FlagGems/FlagGems-vllm → 缺失算子必须经 Plugin 的通用 FlagGems dispatch 调用。
- 影响范围：MiniMax-M3 attention preprocess、vision partial RoPE、MoE sigmoid+bias routing、`SWIGLUOAI_UNINTERLEAVE`；所有加载 Plugin FlagOS backend 的平台均受注册边界影响。
- 精简证据及原始证据位置：初次重分类证据位于 `04-runs/plugin-flaggems-dispatch-redesign/`；最终 vLLM 调用点补丁证据位于 `04-runs/plugin-minimax-dispatch-callsite-patch/{focused-tests,dispatch-regression}.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| GLM-5.3 issue 029 | FlagGems 实现曾错误注册为 `vendor.thead` | 本轮还包含 Plugin-owned missing kernels 与 vLLM 模型调用点 patch | 高 | 沿用“实现归属与 provider kind 一致”，但逐个审查算子语义 |
| 本模型 issue 001/004/005/006 | 已有数值和 graph 证据 | 原实现只按 PPU bring-up 组织 | 高 | 保留数学 contract，改变 ownership/dispatch，不改模型调用语义 |

## 诊断与假设

同步前先确认两个依赖均为干净上游分支；随后将 FlagGems `master` 快进至 `3c6f7537`，FlagGems-vllm `main` 快进至 `bfe7ac06`。检索与接口审查确认：

- FlagGems-vllm 已有 partial-capable `apply_rotary_pos_emb`，可适配 vLLM standalone `ApplyRotaryEmb`；
- FlagGems/FlagGems-vllm 已有支持 `scoring_func=1` 的 `grouped_topk`，Plugin 原有 `CachedOp("grouped_topk")` 可直接复用；
- 两者均无 MiniMax-M3 精确 packed QKNorm+RoPE+main/index cache-insert contract；
- 两者均无独立 packed `SWIGLUOAI_UNINTERLEAVE(limit, alpha, beta)` 算子。

因此只有后两项需要 Plugin-owned Triton fallback；它们应位于 `dispatch/backends/flaggems/impl/` 并注册为 `default.flagos`。PPU prefill index-topk 的 Triton constexpr 编译器问题仍是 T-Head 专属补丁，不迁移。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | FlagGems revision | `be05ef1d` | clean `--ff-only` 至 `3c6f7537` | `/workspace/FlagGems` | 同步成功，仍无 MiniMax 精确 op | 不能伪复用 DeepSeek-V4 contract |
| 2 | FlagGems-vllm revision | `7eda432f` | clean `--ff-only` 至 `bfe7ac06` | `/workspace/FlagGems-vllm` | 找到 rotary/grouped-topk；仍缺两项 | 复用已有两项，只补真实缺口 |
| 3 | provider ownership | fused op 为 `vendor.thead`；激活 kernel 绕过 dispatch | 三项新增 FlagOS 注册，移除 MiniMax T-Head provider | Plugin editable source | 运行时四个相关 op 均解析为 `default.flagos` | ownership 与 policy 一致 |
| 4 | 回归范围 | 原提交前 13 项 | redesign 聚焦 14 项及 dispatch 全套 | `04-runs/plugin-flaggems-dispatch-redesign/` | 14/14；280/280（1 deselected） | PPU 数值/graph 与共享 dispatch 未回归 |
| 5 | vLLM 缺失算子入口 | 在 `ops/minimax_m3.py` 合成私有 `_C` schema | 仅在原生 symbol 缺失时 patch `vllm._custom_ops` 的 MiniMax 专属包装函数，经 `CachedOp` 进入 dispatch | `04-runs/plugin-minimax-dispatch-callsite-patch/` | `native_schema=False`、`python_patch=True`；focused 15/15；其余 dispatch 277/277 | 不修改 vLLM、不占用私有 ABI，原生平台保持原路径 |

## 根因

- 已验证根因：首次 bring-up 按当前 PPU 可运行性放置实现，未完成第二轮跨平台 provider/ownership 审查；已有 FlagGems-vllm 能力也未纳入当时的复用检查。
- 若未完全证实，当前假设与缺失证据：通用 dispatch 可达性已验证；除 PPU 外的 NVIDIA、Ascend、MetaX、Moore Threads、Hygon 等实机执行尚未验证。

## 解决方法或 Workaround

- 修改思路：MiniMax fused preprocess 与 standalone packed SwiGLUOAI kernel 迁入 `flaggems/impl`；`ApplyRotaryEmbFL` 仅做 OOT contract adapter 并通过 `CachedOp("apply_rotary_emb")` 复用 FlagGems-vllm/FlagGems rotary；sigmoid+bias router 无平台名判断，统一进入现有 grouped-topk dispatch。
- 选定层级/扩展点、职责依据和替代方案：`patches/minimax_m3.py` 只在 vLLM 原生 symbol 缺失时替换 MiniMax 专属 Python 包装函数；Plugin 负责参数 contract、FlagOS provider 注册和缺失 Triton fallback；不再通过 `torch.library` 合成 vLLM 私有 `_C` ABI。PPU 专属的编译器兼容逻辑独立位于 `patches/minimax_m3_thead.py`。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：新增实现受 `use_flaggems_op`、平台配置和 dispatch policy 控制；本机策略解析四项均为 `default.flagos`。其他平台不再被硬编码排除，但不能由 PPU 结果推断实机通过。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：是；缺失项对应稳定 vLLM/MoE contract，且 14 项 focused 与 280 项 dispatch 回归均通过。
- Plugin 内必要实现或回归测试路径：`vllm_fl/patches/{minimax_m3,minimax_m3_thead}.py`、`vllm_fl/dispatch/backends/flaggems/{flaggems.py,register_ops.py,impl/{minimax_m3,activation,rotary}.py}`、`vllm_fl/ops/rotary_embedding.py`、`vllm_fl/ops/fused_moe/{activation,router}.py` 及对应 tests；旧 `vllm_fl/ops/minimax_m3.py` 已从工作树移除。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：初次 staging 位于 `05-tmp/plugin-flaggems-dispatch-redesign/`；最终重命名包位于 `05-tmp/minimax-m3-patch-rename-v4.tar.gz`（SHA-256 `1c035e60af8aa7e7023121ca32c98dd5eda0b38612a78a5a1d244a3c96737ae7`）；旧 ABI bridge 可恢复保存于 `05-tmp/minimax-m3-dispatch-callsite-patch/removed/vllm_fl-ops-minimax_m3.py`，旧 `minimax_m3_dispatch.py` 可恢复保存于 `05-tmp/minimax-m3-patch-rename/removed/`；测试缓存位于 `06-cache/plugin-minimax-dispatch-callsite-patch/`。
- 分支与 revision/commit：容器分支 `support-minimax-m3` 已移除旧提交并将当前 redesign 提交为 `aee54f38580e0b8b3db5ed433663ed5359ca308b`，父提交为 `29712e42dba86680577aef9f2f6b5b7f04050a89`；GitHub 同名分支已通过以 `86ec92fd` 为显式 lease 的 force-with-lease 更新，并从本机与容器两侧核对为 `aee54f3`。
- 正式回归测试路径：`04-runs/plugin-minimax-dispatch-callsite-patch/focused-tests.log`（SHA-256 `3090fba268b4848424396a397d464e446841b4a333fa92dfd4a9c48f7e4ee9d2`）；`dispatch-regression.log`（SHA-256 `6b7309570c0fa0be0dd5f09932654ac077193c7f1a27ed9d52dd75b65fdfc508`）。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：focused 15/15 包含自动 general-plugin 加载、无私有 ABI 注入、eager/graph 和注册；其余 dispatch 277/277 通过、5 个已在 focused 覆盖的 MiniMax 项显式 deselected；`git diff --check` 与本地 `py_compile` 通过。容器无 `ruff` 可执行文件，未伪称 Ruff 通过。
- workaround 的适用条件、默认策略/性能影响和退出条件：Plugin-owned kernel 仅在上游无精确等价实现时存在；上游补齐且完成逐平台数值/性能对照后可删除。正式性能尚未重跑。
- 服务停启操作及核对结果：未停止/重启服务或容器；当前 graph 服务 PID 1551482 保持运行，提交后 `/health` 为 200。
- vLLM 未修改证明：本轮未写 `/workspace/vllm`，revision 仍为 `ee0da84ab9e04ac7610e28580af62c365e898389`。

## FlagGems 证据

- 同步后的 revision 与检索证据：FlagGems `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85` clean；FlagGems-vllm `bfe7ac06b3ebf95c6aba7dead56ff7d465019939` clean。
- 已有算子及接入方式，或缺失结论：复用 `apply_rotary_pos_emb` 与 `grouped_topk(scoring_func=1)`；MiniMax fused preprocess 和 standalone packed SwiGLUOAI 为缺失项，由 Plugin FlagGems backend 提供 Triton fallback。
- 如为 FlagGems 缺陷：不判为 FlagGems 缺陷；这是 vLLM-specific contract 尚未覆盖。
- `/bug`：不需要。

## 验证结果

- 最小回归：15/15 passed，23.43 秒；其余 dispatch 277/277，19.84 秒；标准 general-plugin loader 后 `PlatformFL` 生效、`native_schema=False`、`python_patch=True`。
- `eager`：dense/sparse preprocess、partial/full RoPE、packed activation、sigmoid routing 数值均通过。
- `graph` capture/replay：三类新增/复用路径 changed-input replay 均通过。
- 数值、dtype、shape、layout、边界条件：保持 issue 001/004/005/006 已冻结 contract；含 78/80 partial RoPE 尾部 bit-exact、BF16 packed 6144→3072、cache padding slot、FP32 sigmoid router。
- 最终结论与通过标准：代码归属、vLLM 调用点与 dispatch 选择均已修正；PPU 聚焦与共享 dispatch 回归通过，转 `resolved`。

## 限制与下一步

- 尚存限制：当前证据只覆盖 PPU-13；NVIDIA、Ascend、MetaX、Moore Threads、Hygon 等平台尚未实机验证。performance/evidence/summary 也尚未执行。
- 后续动作：如继续验收，下一顺序子步骤为 performance，必须使用显式 `--no-enable-prefix-caching` 的专用服务；其他平台需各自实机验证。
- 设计审查结论及 PR 范围的影响：GitHub 同名分支已包含新提交；尚未创建 PR，PR 前仍需确认目标 base 和跨平台 CI 范围。

## 经验沉淀

- 是否可跨模型或平台复用：FlagGems provider 归属和 `CachedOp` 复用原则可跨模型复用；具体 MiniMax fused contract 仅适用于该模型族。
- 知识库处理状态：`local-only`
- 候选知识库条目：模型 bring-up 后必须二次审查“kernel 所在目录、provider kind、policy 与上游 FlagGems/FlagGems-vllm 能力”是否一致。
