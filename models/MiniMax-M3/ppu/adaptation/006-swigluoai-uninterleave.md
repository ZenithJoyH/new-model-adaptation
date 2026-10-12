# 006：Plugin modular MoE 不支持 `SWIGLUOAI_UNINTERLEAVE`

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-15
- 最后验证时间：2026-09-15
- 模型：`MiniMaxAI/MiniMax-M3`，本地权重 `/mnt/cpfs/models/MiniMax-M3`
- 平台与 Host 别名：T-Head PPU-ZW810E，`PPU-13`
- 容器名称与镜像：`minimaxM3`；`harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`
- Plugin / FlagGems / vLLM revision：Plugin 基线 `29712e42dba86680577aef9f2f6b5b7f04050a89`；FlagGems `be05ef1db6758adca7a18de3bf529c18a6ac9a87`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：TP16 eager run4，dummy profile；packed w13、BF16、expert intermediate 3072、alpha 1.702、limit 7.0、beta 1.0（检查点省略该字段，由当前 vLLM MiniMax-M3 配置类明确提供）

## 问题现象

- 错误签名或症状：所有 rank 在 Plugin `apply_moe_activation` 抛出 `ValueError: Unsupported FusedMoe activation: MoEActivation.SWIGLUOAI_UNINTERLEAVE`。
- 发生顺序：59/59 权重加载 → partial-RoPE 通过 → sigmoid+bias router 通过 → TritonExperts GEMM1 → Plugin activation 分派失败。
- 影响范围：57 个 MiniMax-M3 MoE 层的 routed experts；shared expert 使用同一数学参数，也需要保持 packed/interleaved 语义一致。
- 精简证据及原始证据位置：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/eager-service-run4/server.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 上游 vLLM `apply_moe_activation` | 明确定义 packed w13 的 clamp/alpha/beta 公式 | CUDA op ABI 为五参数；当前 Plugin schema 仍是三参数 | 高 | 复用数学 contract，不调用不兼容 ABI |
| FlagGems `silu_and_mul_with_clamp` | packed gate/up、clamp、单 fused kernel | 只实现 alpha=1、beta=0，缺 MiniMax alpha/beta | 高 | 不直接复用，不把近似当等价 |
| Plugin `_C.swigluoai_and_mul` | 支持 alpha/limit | 输入是 interleaved gate/up，MiniMax w13 是 packed | 高 | 排除布局不兼容复用 |

## 诊断与假设

已验证上游 `FusedMoEQuantConfig` 已携带 `gemm1_clamp_limit`、`gemm1_alpha`、`gemm1_beta`，上游 `TritonExperts` 也保存这些字段；Plugin `TritonExpertsFL.apply` 直接调用自己的旧三参数 helper，既未识别新 enum，也未转发参数。

当前假设：在 Plugin modular activation 层新增 packed-layout Triton kernel，按 `gate=clamp(first_half,max=limit)`、`up=clamp(second_half,-limit,limit)`、`gate*sigmoid(alpha*gate)*(up+beta)` 写入既有 output buffer；调用处转发 quant config 参数，可无中间张量覆盖 eager 与 graph。

已排除：调用 interleaved `_C.swigluoai_and_mul`；调用缺 alpha/beta 的 FlagGems 三参数算子；修改 vLLM；把 model weights 重排为 interleaved。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 整模执行推进 | run3 router 失败 | run4 包含 router 修复 | `04-runs/eager-service-run4/server.log` | router 已越过，激活 enum 明确失败 | 新独立接口缺口 |
| 2 | packed 激活候选 | Plugin 不支持 | 实际 6144→3072 宽度 Triton 公式 | `04-runs/006-swigluoai-uninterleave-focused.log` | 3/3 通过：BF16 数值、clamp 边界、changed-input graph replay | 候选数学与图地址语义成立 |
| 3 | 联合回归 | 前三类修复 10/10 | 加入 packed 激活三个用例 | `04-runs/minimax-plugin-focused-final-v4.log` | 13/13 通过；vLLM HEAD 仍为 `ee0da84ab9e04ac7610e28580af62c365e898389` | 未发现联合回归 |

## 根因

- 已验证根因：Plugin modular MoE activation 实现与当前 vLLM enum/参数契约不同步，且 `TritonExpertsFL.apply` 丢弃了已存在的 clamp/alpha/beta 配置。
- 若未完全证实，当前假设与缺失证据：候选 Triton 实现的数值与 graph 已验证；整模 experts/shared-expert 路径尚待 run5 验证。

## 解决方法或 Workaround

- 修改思路：候选为 Plugin packed-layout Triton kernel，并扩展 helper 参数；调用处从继承的 TritonExperts 字段传递。
- 选定层级/扩展点、职责依据和替代方案：这是 Plugin modular expert pipeline 与上游接口同步，不是模型名或机器特例；不改变 vLLM model adapter。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：新增 enum 分支；既有 SILU/GELU/SWIGLUOAI 等分支保持不变，未知 enum 继续显式报错。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：若数值与 graph 通过则是；该 helper 是 Plugin 自有 modular pipeline 的正式扩展点。
- Plugin 内必要实现或回归测试路径：候选 `vllm_fl/ops/fused_moe/activation.py`、`fused_moe_utils.py` 与 focused test。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：补丁放 `05-tmp/006-swigluoai-uninterleave.patch`，原始测试放 `04-runs/`。
- 分支与 revision/commit：`main`，基线 `29712e42dba86680577aef9f2f6b5b7f04050a89`；修改未 commit。
- 正式回归测试路径：`tests/unit_tests/ops/test_fused_moe_activation_thead.py`，联合 `tests/unit_tests/dispatch/test_thead_minimax_m3.py`、`test_apply_rotary_emb_thead.py`、`test_fused_moe_router_thead.py`。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：新分支只命中 `SWIGLUOAI_UNINTERLEAVE`；其他 enum 分支代码未改，13/13 联合回归通过。
- workaround 的适用条件、默认策略/性能影响和退出条件：候选为 correctness 实现；性能必须在整模正式测量中确认。
- 服务停启操作及核对结果：run4 因异常自然退出并释放端口；容器未停止或重启。
- vLLM 未修改证明：保持 `ee0da84ab9e04ac7610e28580af62c365e898389`，后续重验。

## FlagGems 证据

- 同步后的 revision 与检索证据：`be05ef1db6758adca7a18de3bf529c18a6ac9a87`；`silu_and_mul_with_clamp` 公式固定 alpha=1/beta=0。
- 已有算子及接入方式，或缺失结论：没有 packed、可传 alpha/beta 的等价算子；三参数 `_C` schema 与当前上游五参数 ABI 不同。
- 如为 FlagGems 缺陷，工作根 `07-bugs/<issue>/`、容器对应路径与复现命令：不判为 FlagGems 缺陷；这是当前 Plugin/vLLM 合约同步缺口。
- 如确因工具要求使用 `/bug`，记录指向同一目录的已批准映射或明确例外（不得复制已有用例）：不需要 `/bug`。

## 验证结果

- 最小回归：`04-runs/006-swigluoai-uninterleave-focused.log`，3/3 通过。
- `eager`：run4 负对照失败；run5 整模 dummy profile 与最小推理通过。
- `graph` capture/replay：focused changed-input replay 通过；整模 run2 6/6 捕获及两个 changed-input API 通过。
- 数值、dtype、shape、layout、边界条件：已覆盖 BF16、packed 6144→3072、limit 7、alpha 1.702、beta 1.0、clamp 两端及 changed-input replay，全部通过。
- 最终结论与通过标准：focused 数值/graph 和整模 eager/graph 全部通过，转 `resolved`。

## 限制与下一步

- 尚存限制：当前 FlagGems 近似算子不可作为等价依据；正式性能影响尚受验收门禁约束。
- 后续动作：合入前对共享 TritonExperts 调用者做更广泛的非 T-Head/非 MiniMax 回归。
- 设计审查结论及 PR 范围的影响：需确认参数透传、旧 activation 行为、图地址稳定和其他平台可编译性。

## 经验沉淀

- 是否可跨模型或平台复用：可用于所有 packed-w13 `SWIGLUOAI_UNINTERLEAVE` modular MoE，但当前仅在 MiniMax-M3/PPU 验证。
- 知识库处理状态：`local-only`
- 候选知识库条目：完整共享回归与性能证据前不提升。

## 2026-09-15 FlagGems dispatch 重分类

最新 FlagGems/FlagGems-vllm 仍没有独立的 packed
`SWIGLUOAI_UNINTERLEAVE(limit, alpha, beta)`；仅有普通 SwiGLU 或 fused-MoE 内部 enum，
不能替代 Plugin modular activation contract。因此 Triton kernel 保留，但从公共调用层
迁入 `dispatch/backends/flaggems/impl/activation.py`，由
`CachedOp("swigluoai_uninterleave")` 和 `default.flagos` 注册调用。PPU 数值/graph 3/3、
dispatch 280/280 通过。详见 [008](008-flaggems-dispatch-reclassification.md)。
