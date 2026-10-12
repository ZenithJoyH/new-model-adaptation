# 030：GLM 与混元复用通用 row-wise top-k dispatch

## 元数据

- 状态：`verified`
- 首次出现时间：2026-09-10
- 最后验证时间：2026-09-10
- 模型：`GLM-5.3-Flash-BF16`，并审查相邻调用方 HY4
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / `hy4-ppu07-snapshot:20260903`
- Plugin / FlagGems / vLLM revision：Plugin
  `support-glm5.3-flash@d07e87035b253ba407772a168d266ab22c23d845`，父提交
  `support-hy4-preview@4f9630ca0701d5a569d8c8ee7cff6e039f15a9c9`；FlagGems
  `flaggems-for-day0@8fef991a6b97d85310f1a3cd9c6425e84d395e5d`；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：TP16、BF16、`max_model_len=65536`、`max_num_seqs=32`、
  `FULL_DECODE_ONLY`；聚焦单测、真实设备 graph replay 和最小整模推理

## 问题现象

- 错误签名或症状：同一个 FlagGems `top_k_per_row_decode` kernel 在 GLM sparse indexer
  和 HY4 BF16 indexer 中通过两套 Plugin adapter 调用；旧 HY4 adapter 对二维
  `[batch, next_n]` `seq_lens` 只取最后一列，再要求 provider 反推其余行长度。
- 发生顺序：在删除 Plugin 自有 Triton kernel、重分类 FlagGems provider 后，继续审查
  `top_k_per_row_decode` 的跨模型调用者时发现。
- 影响范围：GLM prefill/decode row-wise top-k；HY4 的 prefill 选择和 decode composite backend。
- 精简证据及原始证据位置：最终 22 项聚焦测试输出保存在远端
  `/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/shared-topk-20260910/pytest-converged.log`；本轮服务日志
  仍由最终启动器写入历史既有路径
  `/mnt/nfs/users/jinghao/glm5.3-flash/05-runs/service/service.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [026 kernel/dispatch 边界](026-kernel-dispatch-boundary-20260909.md) | 模型只持有语义，provider 通过 CachedOp/registry 选择 | 本次是两个模型复用同一 provider kernel | 高 | 建立通用 row-wise top-k capability，不新增模型聚合 dispatch 文件 |
| [029 FlagGems dispatch 重分类](029-flaggems-dispatch-reclassification-20260910.md) | kernel 所有权已在 FlagGems | 旧 top-k adapter 仍以 GLM sparse-indexer 命名且 HY4 有重复适配 | 高 | adapter 归入 FlagGems/reference 通用 capability 模块 |
| HY4 `bf16_indexer_decode` composite | 已包含 paged MQA、候选 top-k 与最终排序 | 不能把整个 composite 降级为裸 top-k 调用 | 高 | HY4 模型入口不拆散，backend 内部复用通用 top-k helper |

## 诊断与假设

- 已验证事实：FlagGems kernel 的低层 decode ABI 使用每个请求的最终长度和 `next_n` 推导
  各 token 行长度；它也可在 `next_n=1` 时把输入解释为逐行显式长度。
- 已验证事实：Plugin reference 路径原本已允许二维 `seq_lens` 表示每一行的显式有效长度；
  FlagGems HY4 adapter 却丢弃除最后一列外的数据，两个 backend 的契约不等价。
- 已验证事实：GLM 与 HY4 的候选选择数学均需要“只在该行有效 token 区间做 top-k”，所以
  kernel 能复用；HY4 仍需 composite backend 持有 paged logits 和最终候选排序。
- 已验证事实：真实 PPU 上 FlagGems prefill 返回的候选集合与 `torch.topk` 一致，但不保证
  降序排列；后续 sparse attention 将候选下标作为集合消费，排序不是高层契约的一部分。
- 已排除方向：不把 FlagGems 八参数低层 ABI暴露给模型；不在 HY4 model 中直接 import
  FlagGems；不修改 dispatch manager/types；不在 Plugin 新写 Triton kernel。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 2D decode 长度适配 | 只取最后一列并由 provider 反推 | flatten 为逐行长度并以 provider `next_n=1` 调用 | `test_flaggems_decode_uses_explicit_2d_lengths` | 显式 `[3,1]` 保持为 `[3,1]` | 不再丢失 HY4 调用方语义 |
| 2 | 1D compact ABI | 每请求最终长度 | 保持原 `next_n` 推导 | `test_flaggems_decode_preserves_final_length_abi` | `[5,7]` 与 `next_n=2` 原样进入 provider | 没有牺牲 GLM/常规 compact 路径 |
| 3 | capability 所有权 | GLM model-scoped op 名和两套 adapter | 通用 `top_k_per_row_prefill/decode` 注册与两类 backend module | lazy-dispatch 与 ownership 测试 | 旧 `sparse_indexer_topk_*` 不再注册 | 调用和实现解耦 |
| 4 | graph 动态数据 | 仅 Python ABI 测试 | PPU 上捕获后同时改变 logits 与二维长度再 replay | `test_flaggems_decode_2d_lengths_graph_replay` | 输出有效范围和 top-k 数值均与 Torch 对照一致 | 通用 wrapper 可用于 graph replay |
| 5 | 整模 GLM | 修改前服务已通过 | 新源码冷启动 TP16 | 最终 `start-model.sh` | 120/120 shard、decode graph 7/7、health 200 | GLM 调用迁移未破坏服务 |
| 6 | 变更输入 replay | 首次请求 | 连续请求 `1+1`、`2+3` | 8010 chat completion | 返回 `2`、`5`，均自然停止 | 整模 graph replay 正确 |
| 7 | HY4 prefill 调用面 | model 内本地 `torch.topk(sorted=True)` | 调用共享 `top_k_per_row_prefill` capability | 新 HY4 model/dispatch 单测与真实 PPU prefill 集合对照 | 候选集合和值一致，短行保持 `-1` padding | prefill 与 decode 均收敛到统一 dispatch，无需额外排序 |

## 根因

- 已验证根因：Plugin 将 provider 的低层函数签名当成模型 adapter 接口，导致 GLM 和 HY4
  分别持有重复适配；HY4 版本还把“显式逐行长度”错误收窄为“可由最终长度连续反推”。
- 缺失证据：当前容器没有 HY4 权重，未做 HY4 整模型服务或精度回归。

## 解决方法或 Workaround

- 修改思路：新增通用 `top_k_per_row_prefill/decode` dispatch capability。FlagGems backend
  隐藏 provider 的 stride/row-count/top-k ABI，reference backend提供同一高层契约。
- 选定层级/扩展点、职责依据和替代方案：GLM 与 HY4 prefill 均通过通用 CachedOp 调用；
  HY4 decode 继续调用 `bf16_indexer_decode` composite，因为 paged MQA、有效区间选择和
  最终排序属于一个 backend 原子职责；该 composite 内部调用同一个通用 top-k helper。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：GLM 与 HY4；T-Head
  profile 显式选择 `[flagos, reference]`。FlagGems 不可用时仍按既有 registry 使用 reference，
  不改变 manager fallback 语义。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：Plugin 只保留跨 provider 的稳定
  高层契约和 ABI adapter；实际 Triton kernel 仍唯一位于 FlagGems。
- Plugin 内必要实现或回归测试路径：`dispatch/backends/{flaggems,reference}/impl/
  top_k_per_row.py`、两类 `register_ops.py`、`dispatch/config/thead.yaml`、GLM model 调用点、
  HY4 prefill/model 与 composite backend，以及 `test_top_k_per_row.py`。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：过程 playbook 只在控制端
  `/private/tmp/glm53-*`；远端新增证据只在上述 `04-runs/shared-topk-20260910/`。
- 分支与 revision/commit：通用 capability 和 HY4 prefill/decode 调用面共 11 个文件已
  收敛到 `support-hy4-preview@4f9630c`；GLM 以该提交为新父提交重建为
  `support-glm5.3-flash@d07e870`，两者之间仍只有一笔 GLM 提交。两个提交的
  author/committer 均为
  `ZenithJoyH <1355922182@qq.com>`，并使用带精确旧值保护的原子 push 更新。
- 正式回归测试路径：`tests/unit_tests/dispatch/test_top_k_per_row.py`、
  `test_bf16_indexer_backend_ownership.py`、`test_flaggems_lazy_dispatch.py`、
  `test_thead_lazy_dispatch.py`、`tests/unit_tests/models/test_hy_v4.py`。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：FlagGems import 仍在函数内惰性
  发生；旧 model-scoped op 名明确断言为未注册；reference/FlagGems 的 1D、2D、prefill
  契约均覆盖。
- workaround 的适用条件、默认策略/性能影响和退出条件：不是 workaround；二维 flatten
  是显式长度的无损 ABI 适配，1D 路径保留 provider 的 compact fast path。本轮未作正式性能
  结论。
- 服务停启操作及核对结果：本轮源码收敛未停止或重启 8010 服务，也未停止、重启或删除
  容器。最终服务 health 200，容器 `running`、restart 0。
- vLLM 未修改证明：`/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389`
  工作树 clean。

## FlagGems 证据

- 同步后的 revision 与检索证据：`flaggems-for-day0@8fef991a6b97d85310f1a3cd9c6425e84d395e5d`，
  相对 `origin/master@749a6d2a7a2e503c2e955a20324460d7c931b0c8` 为 ahead 2 / behind 0，
  工作树 clean。
- 已有算子及接入方式：直接复用 `flag_gems.fused.top_k_per_row_prefill` 与
  `top_k_per_row_decode`；本问题没有修改或新增 FlagGems kernel。
- 如为 FlagGems 缺陷：不适用；缺陷在 Plugin 的重复 ABI adapter 和二维长度收窄。

## 验证结果

- 最小回归：上述 5 个测试文件共 `22 passed, 1 warning`；warning 为既有 FlagGems replay
  benchmarker event-timing fallback。
- CI：upstream PR #477 首轮仅因 `test_top_k_per_row.py` 一处 Ruff 换行格式失败；按 CI
  同版 `ruff 0.16.6` 修正后，HY4 的 `ruff check` 与 `ruff format --check` 均通过，新一轮
  GitHub `lint / Lint Check` 和 `build / Build Check` 已通过。CUDA unit job 仍在等待
  `self-hosted/Linux/X64/nvidia/gpu-8/cuda130` runner，不能把 queued 状态误报为测试通过。
- `eager`：reference 数值、FlagGems provider 参数、1D/2D 长度、HY4 prefill dispatch 和
  真实 PPU prefill top-k 集合通过。
- `graph` capture/replay：共享 FlagGems decode adapter 在真实 PPU 上捕获并以新 logits、
  新二维长度 replay 通过；整模 decode FULL graph 7/7。
- 数值、dtype、shape、layout、边界条件：FP32 logits、INT32 indices/lengths；二维显式长度
  与一维最终长度均覆盖，候选下标范围和对应值与 Torch top-k 对照一致。
- 最终结论与通过标准：通用 kernel 可跨 GLM/HY4 复用；HY4 prefill 已直接使用共享
  capability，decode 保留 composite model boundary 并在内部复用相同 capability；二维长度
  语义问题已修复。

## 限制与下一步

- 尚存限制：未在当前容器执行 HY4 整模启动、精度或性能；未重跑 GLM GPQA/性能验收。
- 后续动作：在 HY4 权重和验收环境可用时补整模 decode 多 token/变长请求回归；若性能验收
  显示二维路径有额外开销，再在不改变显式长度语义的前提下优化 provider ABI。
- 设计审查结论及 PR 范围的影响：共享能力、HY4 composite 修改及专项测试已进入
  `support-hy4-preview`，HY4 prefill 的本地 `torch.topk` 也已收敛；GLM PR 只消费该能力，
  不再把 HY4 变更算作 GLM diff。PR 仍只有一笔 GLM commit，并以新的 HY4 HEAD 为 base。

## 经验沉淀

- 是否可跨模型或平台复用：高层“逐行有效区间 top-k”契约可跨模型复用；当前真实设备只验证
  T-Head PPU/FlagGems，不能外推其他平台性能或可用性。
- 知识库处理状态：`local-only`
- 候选知识库条目：将 provider 的 compact metadata ABI 与模型显式 metadata 语义分离；
  共享 kernel 不等于直接共享低层调用签名。
