# 029：迁移算子从 Thead 候选重分类为 FlagGems dispatch

## 元数据

- 状态：`verified`
- 首次出现时间：2026-09-10
- 最后验证时间：2026-09-10
- 模型：`GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / 当前适配容器
- Plugin / FlagGems / vLLM revision：Plugin
  `support-glm5.3-flash@163dd266174981dba3e00c41ff91e312c5e44655`；FlagGems
  `flaggems-for-day0@187fc1f7bc59616d0c9eadd8d463e8d6068b22d9`；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：TP16、BF16、`max_model_len=65536`、
  `FULL_DECODE_ONLY`、聚焦注册测试与最小推理

## 问题现象

- 错误签名或症状：算子实现已迁入 FlagGems，但 8 个调用仍注册为
  `vendor.thead`；实现所有权与 dispatch kind 不一致。
- 发生顺序：完成 028 的实现迁移和整模验证后，对 Plugin 注册链进行二次职责审查。
- 影响范围：causal-conv decode、recurrent/safe KDA、BF16 gather、graph-safe
  paged MQA、prefill tail 和两条 KPool cache 更新路径。
- 精简证据及原始证据位置：Plugin editable source 位于
  `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`；本轮启动日志位于
  `/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/service/dispatch-reclassification.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [026 kernel/dispatch 边界](026-kernel-dispatch-boundary-20260909.md) | 模型通过 `CachedOp` 选择 backend | 当时实现仍在 Plugin | 高 | 保持模型调用名不变，只重分类 provider |
| [028 FlagGems ownership](028-flaggems-kernel-ownership-20260910.md) | 7 组 Triton 实现已经归入 FlagGems | 注册仍标成 Thead | 高 | FlagGems 实现注册为 `default.flagos` |
| [023 FULL decode graph](023-full-decode-graph-without-breakable-20260908.md) | capture 前需要预解析 lazy callable | provider 由 vendor 改为 default | 高 | 沿用 FlagGems `_prepare` lazy path |

## 诊断与假设

- 已验证事实：模型对目标函数均通过独立 `CachedOp` 调用，因此可以按 op 混合选择
  FlagGems 与 Thead，而不需要把整个 sparse-indexer backend 固定为单一 provider。
- 已验证事实：`sparse_indexer_capabilities`、BF16 identity-scale `prepare_query` 和
  environment/storage contract 是 PPU 语义，应继续归 `vendor.thead`。
- 已验证事实：8 个迁移算子的实现和直接依赖均来自 `flag_gems`；把它们注册成
  `vendor.thead` 会让 provider 统计、policy 和 blacklist 语义失真。
- 已验证事实：`CachedOp` 在 non-strict 模式下可能在实现抛错后进入 manager fallback；有状态
  cache/state 写入不能同时保留指向同一实现的 default/vendor 双候选，否则存在重复执行风险。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | dispatch kind | 8 个 FlagGems 实现注册为 `vendor.thead` | 迁入 `default.flagos` 并删除 vendor 候选 | Plugin 两类 `register_ops.py` | 聚焦测试 `26 passed` | 注册边界和 lazy fullgraph 测试通过 |
| 2 | 整模 runtime provider | 静态注册断言 | TP16 冷启动并检查 16 个 worker 日志 | `dispatch-reclassification.log` | 8 个 op 均为 `default.flagos`，无 `vendor.thead` 命中 | 实际 policy 与注册一致 |
| 3 | full graph replay | provider 重分类前已通过 | 重分类后捕获并连续发送两个不同输入 | 8010 chat completion | graph 7/7，返回 `2`、`5` | 重分类未破坏 capture/replay |

## 根因

- 已验证根因：028 只完成了实现文件所有权迁移，未同步重分类 Plugin 中的 provider 注册。

## 解决方法或 Workaround

- 修改思路：FlagGems backend 新增 8 个 `default.flagos` 注册；sparse-indexer 的调用签名适配
  移到既有 FlagGems adapter；Thead adapter 只保留 PPU storage contract。
- 选定层级/扩展点、职责依据和替代方案：不修改 model、manager、types 或 vLLM；继续复用
  `CachedOp → OpRegistry → policy` 和 capture 前 `_prepare`。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：GLM 的 CachedOp 名称不变；
  FlagGems 缺失或被 blacklist 时不注册候选，并按既有 policy 明确失败。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：Plugin 仍需承担框架级 op 名到
  FlagGems API 的签名适配与 provider 注册，但不包含 Triton kernel。
- Plugin 内必要实现或回归测试路径：两类 `register_ops.py`、两类
  `impl/sparse_indexer.py`、`dispatch/config/thead.yaml` 及两个聚焦 lazy-dispatch 测试。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：控制端临时 playbook 位于
  `/private/tmp/glm53-*`；远端只新增当前编号的 run/cache 证据。
- 分支与 revision/commit：本轮最初以 `0990e2a` 发布 dispatch 精简；随后按用户要求与
  `1fe6a43` GLM 初始适配合并，并在最终审查时 rebase 到最新 Hy4 base。当前 Plugin
  最终提交为 `163dd266174981dba3e00c41ff91e312c5e44655`，已使用精确旧 ref 的
  `--force-with-lease` 更新 `ZenithJoyH/vllm-plugin-FL:support-glm5.3-flash`；
  author/committer 均为 `ZenithJoyH <1355922182@qq.com>`。
- 正式回归测试路径：`tests/unit_tests/dispatch/test_flaggems_lazy_dispatch.py`、
  `tests/unit_tests/dispatch/test_thead_lazy_dispatch.py`。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：FlagGems dependency blacklist、
  Thead-only contract、lazy import 与 fullgraph prepare 均有断言。
- workaround 的适用条件、默认策略/性能影响和退出条件：不是 workaround；Thead policy 对
  8 个已验证算子显式使用 `[flagos]`，防止有状态操作跨 backend 重试。
- 服务停启操作及核对结果：确认唯一服务 PID 3884356 和端口 8010 后 TERM，端口释放；
  `glm5.3-flash` 容器保持 running、restart count 为 0；修改后已启动新服务验证。
- vLLM 未修改证明：`/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389`
  的 `git status --porcelain` 为空。

## FlagGems 证据

- 同步后的 revision 与检索证据：容器与远端均为
  `187fc1f7bc59616d0c9eadd8d463e8d6068b22d9`；该提交已 rebase 到官方
  `master@749a6d2a7a2e503c2e955a20324460d7c931b0c8`，当前 ahead 1 / behind 0。
- 已有算子及接入方式：本轮不修改 FlagGems；只调整 Plugin 对 028 已提交算子的注册归属。
- 如为 FlagGems 缺陷：不适用。

## 验证结果

- 最小回归：发布前完整聚焦集合 `26 passed, 1 warning`；对最终发布提交再次运行两份
  lazy-dispatch 测试，结果 `5 passed, 1 warning`。warning 是既有 FlagGems replay
  benchmarker event-timing fallback。
- `eager`：注册、blacklist 和 provider kind 测试通过。
- `graph` capture/replay：TP16 `FULL_DECODE_ONLY` 捕获 7/7；所有 16 个 worker 对 8 个目标
  op 均记录 `default.flagos`，无 `vendor.thead` 命中；服务 health 200。两个不同输入请求分别
  返回 `2`、`5`，均为 HTTP 200、`finish_reason=stop`。
- 数值、dtype、shape、layout、边界条件：算子实现和输入契约未改变，只改变 provider 注册。
- 最终结论与通过标准：TP16 full decode capture、实际 `default.flagos` 选择日志、health
  和两个变更输入请求均通过；问题关闭。

## 限制与下一步

- 尚存限制：本轮不构成正式 GPQA accuracy 或 performance 验收。
- 后续动作：如继续正式验收，固定已发布的 Plugin/FlagGems revision 后再执行 GPQA 与性能测试。
- 设计审查结论及 PR 范围的影响：最终 Plugin 提交已经把 028 的文件删除、薄适配改线与本轮
  provider 重分类合并为一个完整职责迁移提交。

## 经验沉淀

- 是否可跨模型或平台复用：实现迁移必须同步 provider kind、policy 与失败重试语义，此原则
  可跨模型复用；具体算子目前只在 T-Head PPU 验证。
- 知识库处理状态：`local-only`
- 候选知识库条目：实现仓迁移时同步审查 provider kind、blacklist、policy 和有状态 fallback。

## 2026-09-10 最终 PR 收口

- 删除已无调用者的整个 `vllm_fl/kernels/`；Plugin 不再保留迁出后的 Triton 实现或旧
  provenance 空包。
- 删除独立 `flaggems/impl/bounded_activation.py`。`silu_and_mul_with_clamp` 是通用模型
  activation 能力，FlagGems 与 reference 实现分别归入各自既有 `impl/activation.py`；
  注册辅助函数和注释改为 capability 语义，不再以 GLM/adaptation 命名。
- 将唯一 GLM 提交 rebase 到当前
  `support-hy4-preview@ff87b683ec9c6c1925dbedf12261914e45569b52`，最终 HEAD 为
  `163dd266174981dba3e00c41ff91e312c5e44655`，PR 范围严格为一笔提交、27 个文件。
- 最终树在 PPU-13 容器中 `17 passed`；冷启动加载 120/120 shard、decode FULL graph
  7/7、health 200，首次执行/replay 返回 `2`、`5`，终止错误 0，容器保持
  `running`/restart 0。
- PR：[ZenithJoyH/vllm-plugin-FL#2](https://github.com/ZenithJoyH/vllm-plugin-FL/pull/2)，
  base/head 为 `support-hy4-preview`/`support-glm5.3-flash`；同一 head 当前仅此一个打开的 PR。
