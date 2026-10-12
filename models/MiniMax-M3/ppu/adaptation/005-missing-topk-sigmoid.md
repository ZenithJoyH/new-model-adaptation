# 005：MiniMax-M3 MoE 路由缺少 `_moe_C.topk_sigmoid`

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-15
- 最后验证时间：2026-09-15
- 模型：`MiniMaxAI/MiniMax-M3`，本地权重 `/mnt/cpfs/models/MiniMax-M3`
- 平台与 Host 别名：T-Head PPU-ZW810E，`PPU-13`
- 容器名称与镜像：`minimaxM3`；`harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`
- Plugin / FlagGems / vLLM revision：Plugin 基线 `29712e42dba86680577aef9f2f6b5b7f04050a89`；FlagGems `be05ef1db6758adca7a18de3bf529c18a6ac9a87`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：TP16 eager run3，内存探测 dummy profile；FP32 router logits、128 experts、top-4、sigmoid、correction bias、renormalize

## 问题现象

- 错误签名或症状：所有 rank 在 MoE router 首次执行时抛出 `AttributeError: '_OpNamespace' '_moe_C' object has no attribute 'topk_sigmoid'`。
- 发生顺序：59/59 权重加载完成 → vision partial-RoPE 已越过 → language-model dummy forward → 首个 MoE router → 缺少 `_moe_C.topk_sigmoid` → EngineCore 退出。
- 影响范围：前三个 dense FFN 层之后的全部 MoE 层，服务无法完成内存探测或推理。
- 精简证据及原始证据位置：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/eager-service-run3/server.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| Hy4 PPU native operator inventory 的 `grouped_topk` | sigmoid、bias、renormalize 与 scaling 语义相近 | 不同 Host、Plugin/FlagGems revision、expert/top-k 配置 | 中 | 仅作候选，必须在 PPU-13 当前栈重验 |
| Plugin `_fl_grouped_topk` | 已通过 `CachedOp("grouped_topk")` 接入 FlagGems/vendor dispatch | 当前 `FusedTopKBiasRouterFL` 仍直接调用上游 `_moe_C.topk_sigmoid` | 高 | 验证 n_group=topk_group=1 是否精确等价 |

## 诊断与假设

已验证当前容器没有 T-Head native `_moe_C` bundle，Plugin `FusedTopKBiasRouterFL` 又直接调用上游 `fused_topk_bias`。MiniMax-M3 的非 grouped router 在 sigmoid+bias 路径因此进入缺失 native op。

当前假设：对 T-Head PPU，把非 grouped sigmoid+bias 路由映射到现有 `grouped_topk`，固定 `num_expert_group=1`、`topk_group=1`，可保持“bias 只影响选择、未加 bias 的 sigmoid 分数作为权重、renormalize、routed scaling”语义，同时复用 Plugin 既有 dispatch。

已排除：复制其他任务的 `_moe_C.abi3.so`（revision/ABI 未核实且属于外部二进制）；修改 vLLM；用捕获任意异常后的 broad Python fallback 隐藏缺失。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 整模执行推进 | run2 在 vision RoPE 失败 | run3 含 partial-RoPE 修复 | `04-runs/eager-service-run3/server.log` | 越过 vision，首次 MoE router 缺 op | 新的独立阻塞，不能归因于 RoPE |
| 2 | PPU grouped-topk 候选 | 尚未在当前栈验证 | FlagGems sigmoid+bias，n_group=1/topk_group=1 | `04-runs/005-topk-sigmoid/candidate.log` | eager 数值与 changed-input graph 通过 | 候选语义成立 |
| 3 | Plugin router 接入 | 直达缺失 `_moe_C.topk_sigmoid` | T-Head-only 单 group dispatch；其他平台保持上游 | `04-runs/minimax-plugin-focused-final-v3.log` | MiniMax Plugin 组合回归 10/10 | 算子级保留修复，待整模确认 |

## 根因

- 已验证根因：当前 PPU 环境未提供 vLLM 上游调用的 `_moe_C.topk_sigmoid`，而 Plugin 已替换 router 类却未把 `FusedTopKBiasRouter` 的 sigmoid+bias 路径接到 Plugin dispatch。
- 若未完全证实，当前假设与缺失证据：替代实现的数值与图回放已验证；整模 eager/graph 尚待。

## 解决方法或 Workaround

- 修改思路：T-Head-only router 分支复用 `_fl_grouped_topk`/`CachedOp("grouped_topk")`，以单一 expert group 表达普通 top-k。
- 选定层级/扩展点、职责依据和替代方案：路由算子能力属于 Plugin router/dispatch；模型仍通过 vLLM `FusedTopKBiasRouter` contract 调用。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：候选必须只在 `vendor_name=thead` 且 sigmoid+bias contract 命中；其他平台继续使用上游路径。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：若候选验证通过则是；它修复整个 MoE 共有路径，不能放在一次性脚本。
- Plugin 内必要实现或回归测试路径：`vllm_fl/ops/fused_moe/router.py`、`tests/unit_tests/ops/test_fused_moe_router_thead.py`。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：候选探针放 `02-issues/005-topk-sigmoid/`，输出放 `04-runs/005-topk-sigmoid/`。
- 分支与 revision/commit：`main`，基线 `29712e42dba86680577aef9f2f6b5b7f04050a89`；未 commit。
- 正式回归测试路径：`04-runs/minimax-plugin-focused-final-v3.log`，10/10 通过。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：T-Head 数值、changed-input graph 和非 T-Head 仍调用上游路径均通过。
- workaround 的适用条件、默认策略/性能影响和退出条件：仅 T-Head sigmoid+bias contract；现有 dispatch 无 native topk-sigmoid 时使用。兼容 native op 可用且完成对照后可退出；整模性能待验收。
- 服务停启操作及核对结果：run3 worker/EngineCore 因异常退出；精确核对残留进程组后仅对本次 API PID 发送 TERM，端口和进程均清空，记录在 `04-runs/eager-service-run3/termination-record.txt`；容器未停止或重启。
- vLLM 未修改证明：run3 前后保持 `ee0da84ab9e04ac7610e28580af62c365e898389`，待本轮结束复核。

## FlagGems 证据

- 同步后的 revision 与检索证据：`be05ef1db6758adca7a18de3bf529c18a6ac9a87`；存在 `flag_gems.fused.grouped_topk`，支持 FP32/FP16/BF16、sigmoid、bias、top-k、renormalize 与 scaling。
- 已有算子及接入方式，或缺失结论：Plugin 已有 `CachedOp("grouped_topk")` 和 FlagGems backend；当前非 grouped bias router 未使用它。
- 如为 FlagGems 缺陷，工作根 `07-bugs/<issue>/`、容器对应路径与复现命令：当前不判定为 FlagGems 缺陷。
- 如确因工具要求使用 `/bug`，记录指向同一目录的已批准映射或明确例外（不得复制已有用例）：不需要 `/bug`。

## 验证结果

- 最小回归：候选 eager/graph 2/2；接入后组合 10/10。
- `eager`：run3 作为负对照保留；run5 整模 dummy profile 和最小推理通过。
- `graph` capture/replay：聚焦 changed-input replay 通过；整模 run2 6/6 捕获及两个 changed-input API 通过。
- 数值、dtype、shape、layout、边界条件：覆盖 FP32 `[17,128]`/`[9,128]`、top-4、bias-only selection、未加 bias 权重、renormalize、scaling、int32 ids 与 changed-input replay。
- 最终结论与通过标准：算子级与整模 eager/graph 均通过，转 `resolved`。

## 限制与下一步

- 尚存限制：没有可核实的当前 ABI native `_moe_C`；不能引用其他容器二进制作为修复；正式性能证据仍受验收门禁约束。
- 后续动作：在其他 T-Head sigmoid+bias 模型上重用前复验完整 contract。
- 设计审查结论及 PR 范围的影响：若保留，将修改共享 router，必须有平台守卫及非 T-Head miss-path 测试。

## 经验沉淀

- 是否可跨模型或平台复用：可用于同一 T-Head sigmoid+bias router contract，但目前只有 MiniMax-M3/PPU 整模动机。
- 知识库处理状态：`local-only`
- 候选知识库条目：完成整模与共享回归前不提升。

## 2026-09-15 FlagGems 链路复核

同步后的 FlagGems-vllm 已明确提供 `grouped_topk(scoring_func=1)`；Plugin 原有
`CachedOp("grouped_topk")` 也是公共 dispatch 扩展点。因而移除 `vendor_name=thead`
判断，所有 sigmoid+bias single-group contract 都进入配置驱动的 grouped-topk 链路；
当前 PPU 实际解析为 `default.flagos`。不存在 correction bias 或非 sigmoid 时仍走上游
`fused_topk_bias`。数值、changed-input graph 和共享 dispatch 回归通过；其他平台尚需
实机验证。详见 [008](008-flaggems-dispatch-reclassification.md)。
