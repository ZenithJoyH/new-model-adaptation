# 028：将 GLM-5.3-Flash Triton 算子归入 FlagGems

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
- 执行模式与负载：TP16，BF16，`max_model_len=65536`，
  `FULL_DECODE_ONLY`，冷启动、专项数值回归和最小推理

## 问题现象

- 错误签名或症状：Plugin 中仍保存 7 组新写 Triton 实现，算子所有权与 FlagGems
  provider 边界不一致。
- 发生顺序：在 Plugin 目录精简后继续做 PR 级职责审查；迁到目标 FlagGems day0
  分支后的首次整模 capture 又出现 `AssertionError: Unsupported h_q`。
- 影响范围：causal-conv decode、BF16 indexer gather、graph-safe BF16 paged MQA、
  recurrent/safe KDA、KPool compress/decode update、prefill tail persistence，以及 sparse
  MLA small-head 支持。
- 精简证据及原始证据位置：Plugin 与 FlagGems editable 源码分别位于
  `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`、
  `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems`；首次失败日志为
  `/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/service/flaggems-migration.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [021 small-head sparse MLA](021-flaggems-sparse-small-head-no-padding-20260908.md) | TP16 本地 `HQ=4`，旧 FlagGems 只接受 64/128 | 本次目标变为 `flaggems-for-day0` | 高 | 精确移植原生 small-head 修复，不恢复 padding workaround |
| [026 kernel/dispatch 边界](026-kernel-dispatch-boundary-20260909.md) | 模型通过 CachedOp 与 backend 注册调用关键算子 | 本次进一步把实现所有权移出 Plugin | 高 | Plugin 保留 vendor/capability contract 与薄适配，Triton 实现归 FlagGems |
| [023 FULL decode graph](023-full-decode-graph-without-breakable-20260908.md) | dispatch 必须在 capture 前预解析，decode 用 full graph | 本次改变 lazy callable 的实际所属仓库 | 高 | 保留 `_prepare` 预解析路径并增加惰性导入回归 |

## 诊断与假设

- 已验证事实：Plugin 新增 Triton 实现分布在 Thead `impl/` 的 4 个文件和
  `kernels/glm5next/` 的 3 个文件，共 7 组；模型调用已经通过现有 CachedOp/dispatch。
- 已验证事实：目标 day0 分支已有通用 `bf16_paged_mqa_logits` 和量化
  `cp_gather_indexer_k_quant_cache`。前者不应被 GLM graph 约束覆盖；后者不能处理无 scale
  bytes 的 BF16 cache。
- 已验证事实：首次冷启动在第一个 FULL decode capture 进入 day0
  `flashmla_sparse.py:1107`，本地 `HQ=4` 命中 `HQ == 64 or HQ == 128` 断言；失败 worker
  为 TP15。原 `sparse-mla-opt-w8a8-moe-fix` 的
  `717a9ef60d38b559d8b4424488ca5cad2fe61a59` 只修改该实现并新增 small-head eager/graph
  测试。
- 已排除方向：不在 Plugin 恢复 head padding；不覆盖 FlagGems 原通用 BF16 MQA；不把
  W8A8 MoE 或两个分支间的其他大范围差异带入 day0。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | Triton 实现所有权 | 7 组实现在 Plugin | 实现迁入 FlagGems，Plugin 仅薄适配 | 两棵 editable 源码树 | Plugin 24 项、FlagGems 新增 8 项通过 | 所有权迁移成立 |
| 2 | 通用 BF16 MQA 兼容边界 | 直接替换 day0 既有实现 | 恢复原实现，新增 `graph_safe` 独立入口 | FlagGems `fused/` | 原 13 项与新增无效 block 测试通过 | 避免改变既有调用者 |
| 3 | FlagGems 分支 | 原 sparse 分支支持 `HQ=4` | day0 分支缺失 small-head commit | 首次冷启动日志 | FULL capture 报 `Unsupported h_q` | 分支能力缺口，不是迁移算子数值错误 |
| 4 | small-head 实现 | day0 仅允许 64/128 | 只应用 `717a9ef6` 的两文件补丁 | `flashmla_sparse.py` 及专项测试 | eager/graph `3 passed` | 原生无 padding 修复可复用 |
| 5 | 整模 graph | 首次 day0 启动在 capture 0/7 失败 | 加入原生 small-head 支持 | TP16、`FULL_DECODE_ONLY` | decode graph 7/7，health 200 | 无需 Plugin padding，整模 graph 可用 |
| 6 | graph replay | 仅专项 kernel replay | 连续发送两个不同输入 | `/v1/chat/completions` | 分别返回 `2`、`5`，均 `stop` | 首次执行和变更输入 replay 均正常 |
| 7 | 最新 upstream 漂移 | day0 基于 `45a1a0a` | fetch 官方 `master@749a6d2` 并比较双侧文件集合 | FlagGems Git DAG 与三点 diff | ahead 1 / behind 5，修改路径交集为空 | 静态看没有文件级冲突；未据此宣称 rebase 后运行正确 |
| 8 | upstream 同步 | 已发布 `39271555`，behind 5 | rebase 单个 day0 提交到 `749a6d2` | 容器验证后在本机以 `--force-with-lease` 推送 | 新提交 `187fc1f7`，ahead 1 / behind 0 | tree/patch 等价，且完成专项、dispatch 和整模 graph 验证 |

## 根因

- 已验证根因：早期 bring-up 把平台验证用 Triton 实现留在 Plugin；切换到用户指定的
  day0 分支时，又没有携带先前 sparse 分支中已验证的 small-head 支持。

## 解决方法或 Workaround

- 修改思路：7 组实现迁入 `flag_gems.fused`；Plugin 删除原文件，通过现有 Thead
  registration 和 sparse-indexer contract 延迟导入 FlagGems 函数。
- 选定层级/扩展点、职责依据和替代方案：模型数学和调用编排仍在模型 adapter；Plugin
  dispatch 保留 provider/capability 选择；可复用 Triton 实现在 FlagGems。没有把模型名或
  Host 例外写入共享 manager/types。
- 受影响的公共调用方及守卫未命中行为：原 CachedOp 名称不变；FlagGems 原量化 gather 和
  通用 BF16 MQA 保持原文件/入口；迁移入口仍只作为 `vendor.thead` 候选。
- Plugin 内必要实现或回归测试路径：FlagGems 与 Thead 的两类
  `register_ops.py`/`impl/sparse_indexer.py`、`dispatch/config/thead.yaml`，以及两个
  lazy-dispatch 聚焦测试。远端重写历史已经删除旧的 297 行综合测试，发布时没有将其恢复。
- 容器内仓库外临时过程代码：无新增远端过程脚本；运行日志与 cache 分别在当前编号
  `04-runs/`、`06-cache/`，本机 `/private/tmp/glm53-*` 仅为 Ansible 控制端临时文件。
- 分支与 revision/commit：FlagGems 目标 `flaggems-for-day0`；同步后的最终提交
  `187fc1f7bc59616d0c9eadd8d463e8d6068b22d9`，subject 为
  `feat: add graph-safe sequence kernels for day-0 serving`，author/committer 均为
  `ZenithJoyH <1355922182@qq.com>`。原提交 `39271555` 因 rebase 被替代；使用精确旧 ref 的
  `--force-with-lease` 更新 `ZenithJoyH/FlagGems:flaggems-for-day0`，并用远端 ref 复核。
- Plugin 最终提交为 `163dd266174981dba3e00c41ff91e312c5e44655`，subject 为
  `feat: support GLM-5.3-Flash on T-Head PPU`，author/committer 均为
  `ZenithJoyH <1355922182@qq.com>`。它以当前
  `support-hy4-preview@ff87b683ec9c6c1925dbedf12261914e45569b52` 为直接父提交，
  GLM 适配保持一笔提交；使用精确旧 ref 的 `--force-with-lease` 推送并与容器工作树对齐。
- 正式回归测试路径：FlagGems `tests/test_graph_safe_sequence_ops.py`、
  `tests/test_DSA/test_flashmla_sparse_small_heads.py` 及既有 BF16 MQA/量化 gather 测试。
- 服务停启操作及核对结果：只停止/启动本任务的 vLLM 服务；每次先核对精确命令/PID和
  8010，容器始终运行。未停止、重启或删除 `glm5.3-flash` 容器。
- vLLM 未修改证明：`/workspace/vllm@ee0da84` 的 `git status --short --branch` 只有 detached
  HEAD 标识，无工作树文件。

## FlagGems 证据

- 当前 revision 与 fork 证据：容器
  `flaggems-for-day0@187fc1f7bc59616d0c9eadd8d463e8d6068b22d9` 与
  `zenith/flaggems-for-day0` 一致，工作树为空；该提交的 author/committer 均为
  `ZenithJoyH <1355922182@qq.com>`。
- upstream 映射与版本：仓库没有名为 `upstream` 的 remote；`origin` 指向
  `https://github.com/flagos-ai/FlagGems.git`，其默认分支是 `master`，2026-09-10 fetch 后为
  `749a6d2a7a2e503c2e955a20324460d7c931b0c8`。`zenith` 指向用户 fork。
- 提交关系：同步前共同基线为 `45a1a0abaa44d03596fa4f7113f111ec0b716523`，day0 为 ahead 1 /
  behind 5；同步后官方 `749a6d2` 是 day0 的直接祖先，当前为 ahead 1 / behind 0。
- day0 三点 diff：11 个文件，`1918 insertions(+), 11 deletions(-)`。包括 7 个新增 fused
  实现文件、`fused/__init__.py` 导出、`flashmla_sparse.py` small-head 修改，以及 2 个测试文件。
- upstream 五个提交：新增 `embedding_renorm_`、`cumulative_trapezoid`、`cov`、`corrcoef`
  四个 NVIDIA 通用算子，并修复 `adaptive_avg_pool3d_backward` dispatch；从共同基线计算的
  双侧修改文件交集为空。该结论只表示当前静态路径不重叠，不代替 rebase 后编译、数值、
  eager/graph 与整模验证。
- 同步验证：rebase 前后 day0 patch ID 均为
  `975680ef0a95b2873d0aa892b48a603cd5464516`；本机发布提交与 PPU-13 已验证提交的 tree 均为
  `86007555663976fdaa354d95cc89e15d5b29265c`。
- 已有算子及接入方式：保留既有通用 BF16 paged MQA 和量化 gather；新增 graph-safe BF16
  MQA、BF16 gather、causal-conv、KDA、KPool 与 tail fused 入口。
- small-head 缺陷修复：精确复用 `717a9ef6` 中 head mask、tail-head store mask、BH16
  autotune 配置及 `HQ > 0` guard；没有引入该分支的 W8A8 MoE 或 merge commit。
- `07-bugs/`：本次完整调用栈和专项上游测试已经足够定位，未新增一次性 reproducer。

## 验证结果

- 最小回归：Plugin 发布前 ownership/dispatch `26 passed`，在发布提交上两个聚焦文件
  `5 passed`；FlagGems 迁移算子 `8 passed`；既有
  BF16 MQA `13 passed`；既有量化 gather `10 passed`；small-head sparse MLA eager/graph
  `3 passed`。所有聚焦源文件通过 `py_compile` 与 `git diff --check`。
- `eager`：迁移算子的数值 reference 覆盖 causal-conv、gather、safe/recurrent KDA、KPool
  compress/decode stash、tail persistence 和 graph-safe MQA。
- `graph` capture/replay：small-head `HQ=4` 专项 graph replay 通过；TP16 整模
  `FULL_DECODE_ONLY` 捕获 7/7，`/health` 返回 200。两个不同输入的连续请求分别返回
  `2`、`5`，均为 HTTP 200、`finish_reason=stop`。完整启动证据位于
  `/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/service/flaggems-migration-small-head.log`。
- upstream 同步后回归：迁移算子 `8 passed`、既有 BF16 MQA `13 passed`、既有量化 gather
  `10 passed`、small-head eager/graph `3 passed`、Plugin dispatch `5 passed`；整模重新加载
  120/120 shard，TP16 decode FULL graph 7/7，health 200。变更输入 replay 返回 `2`、`5`，
  均为 HTTP 200、`finish_reason=stop`。
- 最终 PR 树回归：删除 Plugin `vllm_fl/kernels/` 和独立
  `flaggems/impl/bounded_activation.py`，将 `silu_and_mul_with_clamp` 合入通用
  FlagGems/reference `activation` 模块；最新 Hy4 base 与 GLM 聚焦集合 `17 passed`。
  TP16 再次加载 120/120 shard、decode FULL graph 7/7、health 200；变更输入 replay
  返回 `2`、`5`，当前运行区间终止错误为 0。
- 同步后启动日志位于
  `/mnt/nfs/users/jinghao/glm5.3-flash/05-runs/service/service.log`。其中 FA2 不可用候选探测
  `1168` 条、UNICM 未配置设备 IP 探测 `128` 条，与同步前已验证日志的分类计数完全一致；
  其后服务选择可用后端并完成启动。排除这两类既有探测噪声后，非预期 ERROR 与
  `Traceback`/EngineCore failure/`Unsupported h_q`/illegal-memory 终止签名均为 `0`。
- 数值、dtype、shape、layout、边界条件：覆盖 BF16/FP32 state、分页 gather、无效 block、
  incomplete pool、in-place state 和变更输入 replay。
- 最终结论与通过标准：TP16 FULL decode capture、服务 readiness、首次推理及变更输入 replay
  均已通过；算子实现已从 Plugin 迁入 FlagGems，问题关闭。

## 限制与下一步

- 尚存限制：本轮未执行正式 GPQA 或性能验收，不能据此声明 accuracy/performance 阶段通过。
- upstream 限制：同步结论固定于 2026-09-10 的官方 `master@749a6d2`；不自动覆盖之后的新提交。
- 后续动作：若进入正式验收，应沿用已验证的 Plugin/FlagGems revision，单独执行
  accuracy/performance 流程。
- 设计审查结论及 PR 范围：FlagGems commit 应包含可复用 fused 实现、small-head 前置能力和
  同仓测试；Plugin 只包含删除实现与薄 dispatch 改线。

后续 provider kind 重分类见
[029](029-flaggems-dispatch-reclassification-20260910.md)；028 中记录的
`vendor.thead` 路由是该轮验证时的历史状态，不代表当前最终路由。

## 经验沉淀

- 可跨模型或平台复用：算子所有权边界、独立兼容入口和 small-head masked tile 可复用；
  当前仅在 T-Head PPU 验证，不外推其他后端性能或 graph 支持。
- 知识库处理状态：`local-only`
- 候选知识库条目：待整模通过后评估是否扩充 021 的适用分支说明。
