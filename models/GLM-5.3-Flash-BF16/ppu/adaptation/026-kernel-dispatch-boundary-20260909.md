# 026：收敛 GLM-5.3-Flash kernel 与 dispatch 边界

## 元数据

- 状态：`verified cleanup`（整模冷启动未在本轮执行）
- 首次出现时间：2026-09-09
- 最后验证时间：2026-09-09
- 模型：`GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / 当前适配容器
- Plugin / FlagGems / vLLM revision：Plugin `support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8`；FlagGems `bca444b8569294e7d4e4deff7ddfec7f05682033`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：源码、注册和 CPU/import 专项回归；不改变当前服务进程

## 问题现象

- 错误签名或症状：`vllm_fl/kernels/glm5next/` 同时存放底层 kernel、CachedOp 门面、模型 CustomOp 编排、graph patch 辅助和 PyTorch reference 实现，目录职责混杂。
- 发生顺序：模型功能适配完成后进行代码精简审查，发现部分 portable 实现虽经 CachedOp 间接调用，却被注册成 `vendor.thead`，provider 所有权不准确。
- 影响范围：GLM-5.3-Flash sparse indexer、KDA/causal-conv 的注册和源码组织；不改变模型数学、tensor shape/dtype、权重加载或服务参数。
- 原始证据位置：远端 editable Plugin `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 020 Hy4 最小重整 | 要求复用 framework dispatch/registration | 本次只收敛 GLM kernel 所有权，不重做功能适配 | 高 | 延续既有 CachedOp 和 backend 注册扩展点 |
| 023 FULL decode graph | 关键算子需要在 graph 前完成 dispatch prepare | 本次不改变 graph 模式或 capture 边界 | 高 | 保留 `prepare_cached_ops()`，只纠正 provider 类型和文件归属 |

## 诊断与假设

- 已验证事实：原 `indexer_backend.py` 只定义 CachedOp 门面，不包含 kernel；原 `sparse_attn_indexer_kpool.py` 是 vLLM CustomOp/模型编排；原 `graph_metadata.py` 仅被 patch 使用。
- 已验证事实：原 `portable.py` 为纯 PyTorch reference 实现；`causal_conv1d_fn`、`chunk_kda_with_safe_gate`、pool 展开和 tail 拼接此前从 `vendor.thead` 入口导出。
- 待验证假设：将这些职责迁移到 `ops/`、`models/`、`patches/` 和 reference backend，并保持 CachedOp 名称不变，可在不改变数值逻辑的前提下完成目录精简。
- 已排除方向：把所有 kernel 直接搬到 dispatch；真实 PPU kernel 仍应留在 `kernels/`，由 vendor backend 延迟导入。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 源码职责与 provider 类型 | 混放于 `kernels/`；portable 被标为 vendor | 真实 kernel 留在 `kernels/`，其余按层迁移；portable 注册为 REFERENCE | PPU-13 editable Plugin | 目录、注册、import 和专项测试通过 | 假设成立 |
| 2 | kernel 文件内部死代码 | KPool 和 safe-KDA 仍含无调用 helper/旧 chunk 分支 | 仅删除全仓零调用且未注册的 9 个符号 | 同一 editable Plugin | 删除 355 行；核心 dispatch 候选及专项测试通过 | 可安全继续收敛 |

## 根因

- 已验证根因：早期 bring-up 以功能闭环为优先，把模型编排和 portable fallback 与底层 kernel 放在同一目录；后续接入 dispatch 时保留了 vendor facade 代理，导致目录和 provider 类型没有同步归位。

## 解决方法或 Workaround

- 修改思路：
  - CachedOp indexer 门面并入 `vllm_fl/ops/glm5next.py`；
  - sparse indexer CustomOp 编排迁移到 `vllm_fl/models/glm5next_indexer.py`；
  - graph metadata 辅助迁移到 `vllm_fl/patches/glm5next_graph.py`；
  - pure-PyTorch 实现迁移到 `vllm_fl/dispatch/backends/reference/impl/glm5next.py`；
  - 删除 vendor sparse facade 中的 portable 转发，新增明确的 reference 注册；
  - `kernels/glm5next/` 仅保留 `kpool_compress.py`、`prefill_tail.py`、`safe_kda.py`、包入口和 provenance。
- 选定层级/扩展点与职责依据：模型仅依赖 `ops` 契约；dispatch 负责 REFERENCE/DEFAULT/VENDOR 候选和策略选择；vendor 实现是唯一允许直接延迟导入 PPU kernel 的层。
- 替代方案：保留旧文件仅改命名不能纠正 provider 所有权；把真实 kernel 移入 dispatch 会混淆算子实现与注册策略，因此均未采用。
- 受影响的公共调用方和守卫未命中行为：CachedOp 名称保持不变；FlagGems input guard 未变；无匹配 FlagGems/vendor 实现时，四个通用算子按既有策略选择 `reference.torch`。
- Plugin 必要实现与回归测试：远端 `vllm_fl/{ops,models,patches,dispatch,kernels}/` GLM 文件；`tests/unit_tests/test_glm5next_support.py` 新增 provider 类型断言。
- 容器内仓库外临时过程代码：无；本机 `/tmp/glm-kernel-refactor-20260909` 仅用于生成可审查补丁，不属于本地仓库或远端工作根。
- 分支与 revision/commit：上述 Plugin base；工作树包含本次及继承的未提交/未跟踪适配代码，未 commit、未 push。
- 服务停启操作：本轮没有停止、重启或替换模型服务。

## 实际 diff 与影响审查

| 路径/调用方 | 变更 | eager | graph | 其他模型/平台 |
|---|---|---|---|---|
| `ops/glm5next.py` | 承接所有 sparse-indexer CachedOp 契约 | 名称不变 | 仍由 `prepare_cached_ops()` 预解析 | GLM 专属 |
| `dispatch/backends/reference` | 承接 portable 实现和四个 REFERENCE 注册 | 语义不变 | 不新增 manager/lock 热路径 | 新模块按需加载 |
| `dispatch/backends/vendor/thead` | 仅保留 PPU storage/KDA/conv kernel 绑定 | 语义不变 | 延迟导入方式不变 | vendor 限定为 thead |
| `models/glm5next_indexer.py` | 承接 CustomOp 与模型编排 | 仅路径变化 | CustomOp/capture 装饰不变 | GLM 专属 |
| `patches/glm5next_graph.py` | 承接 graph metadata buffer 辅助 | 无影响 | 仅 import 路径变化 | GLM 专属 |
| `kernels/glm5next/` | 删除 4 个非 kernel 文件 | 无影响 | 无影响 | 只余真实 PPU kernel |

- 基线/当前规模：目录总计由 2,576 行先降至 1,179 行，再降至 824 行；Python kernel 代码当前为 799 行。
- 继承改动：`dispatch/backends/reference/register_ops.py` 在本轮前已有 staged/working-tree 状态；本轮只追加 GLM reference model-op 注册，未重写其既有 MHC/indexer 迁移。
- vLLM/FlagGems 影响：两棵依赖仓库 `git status --porcelain` 均为空。

## FlagGems 证据

- 同步 revision：`sparse-mla-opt-w8a8-moe-fix@bca444b8569294e7d4e4deff7ddfec7f05682033`，本轮未修改。
- 现有算子接入：FlagGems sparse indexer 和 recurrent KDA 的 DEFAULT 注册保持不变；本轮只纠正 fallback/reference 与 vendor 边界。
- `07-bugs/` 复现：不适用，本轮不是 FlagGems 数值或 kernel 缺陷。

## 验证结果

- 目录检查：`kernels/glm5next/` 只剩 3 个实现文件、`__init__.py` 和 `PROVENANCE.md`；旧 4 个模块及所有旧 import 均不存在。
- 二次精简：从 KPool 删除未调用的 Torch Hadamard fallback、page-table/slot helper 和已由 reference dispatch 承接的 pool/tail helper；从 safe-KDA 删除未注册的 chunk-cumsum kernel、wrapper 和旧 chunk KDA 入口。
- 调用边界：全仓直接 import GLM kernel 的调用方只剩 `dispatch/backends/vendor/thead/impl/{sparse_indexer,glm5next}.py`。
- 新进程 dispatch：`causal_conv1d_fn`、`chunk_kda_with_safe_gate`、`sparse_indexer_expand_pools_to_tokens`、`sparse_indexer_append_tail_to_topk` 为 `reference.torch/reference`；tail persistence、KPool cache write、safe KDA 为 `vendor.thead/vendor`。
- 最小回归：310 个 Plugin/测试 Python 文件通过 `compile()`；二次精简后 GLM 及两项 dispatch 专项回归 `28 passed, 1 warning in 12.79s`；`git diff --check` 通过。
- 服务观察：既有 PID `2893015` 保持运行，`/v1/models` 返回 `GLM-5.3-Flash-BF16`、`max_model_len=65536`；该进程在源码变更前启动，只证明未干扰现有服务。
- eager / graph：不改变执行模式和 capture 装饰；未进行整模冷启动或新代码 graph replay。
- 最终结论：源码职责和 dispatch provider 边界已按目标收敛，专项静态/注册回归通过。

## 限制与下一步

- 尚存限制：当前运行服务没有重新加载本轮源码，不能作为新代码整模验证证据。
- 后续动作：由用户安排维护窗口后，用根目录 `start-model.sh` 冷启动，再做最小推理和 FULL decode graph replay；本轮不擅自重启。
- PR 范围：应把文件迁移、reference 注册和对应测试作为一个 cohesive change；提交前需区分本轮改动与已有 staged/未跟踪适配代码。

## 经验沉淀

- 可复用原则：`kernels/` 保存实现，`ops/` 保存模型侧契约，`dispatch/` 保存 provider 注册和平台绑定，`models/` 保存模型/CustomOp 编排，`patches/` 保存上游适配。
- 知识库处理状态：`local-only`，属于 Plugin 设计边界而非运行故障签名。

## 2026-09-09 第三轮精简复核（取代上文第二轮后的结构结论）

用户复核发现第二轮仍保留 `dispatch/backends/glm5next.py`、`ops/glm5next.py`，并为
GLM 修改了共享 `dispatch/manager.py`、`dispatch/types.py`。进一步检查确认：前两个文件
都是只做聚合或转发的模型命名层；后两个文件新增的 input predicate 和 stateful fallback
字段会扩大公共 dispatch API，不是该固定 BF16/PPU 配置的必要条件。

最终调整如下：

- 删除 `dispatch/backends/glm5next.py`、`ops/glm5next.py`、
  `dispatch/backends/vendor/thead/impl/glm5next.py` 和旧的
  `dispatch/backends/reference/impl/glm5next.py`；仓库中不存在这些文件的源码引用。
- 模型侧 `CachedOp` 调用和 mHC/clamp 小型模块回到 `models/glm5next.py`；sparse indexer
  调用契约放在实际调用者 `models/glm5next_indexer.py`，不再建立通用 `ops/glm5next.py`。
- DEFAULT、REFERENCE、VENDOR 注册分别直接进入各自的 `register_ops.py`。PPU 有状态的
  cache/KPool/tail/KDA/causal-update 路径只注册唯一 `vendor.thead` 实现，因此恢复上游
  fallback 语义后也不存在失败后切换 provider、重复修改状态的问题。
- PyTorch reference 按算子语义拆为 `reference/impl/kda.py`、
  `reference/impl/causal_conv1d.py` 和 `reference/impl/sparse_indexer.py`，不再用模型名汇总。
- FlagGems sparse indexer 只保留当前确实注册的 rotation、MQA、prefill/decode top-k；删除
  未注册的 FlagGems recurrent-KDA adapter 和失去调用方的 `supports_*`/FP8/cache/pack
  包装。bounded activation 的固定模型契约改为实现入口内校验，不保留单独 guard。
- `dispatch/manager.py`、`dispatch/types.py` 的工作树内容与
  `support-hy4-preview@d56f7b2` 完全一致；原 `test_input_support.py` 随公共扩展一并删除。
- 共享 dispatch 只剩 `dispatch/__init__.py` 的 27 行必要改动：用弱引用收集现有
  `CachedOp` 并在 torch.compile/FULL graph 前解析 provider 和 lazy import，避免 capture
  期间进入 `RLock`。没有修改 manager 选择算法、类型结构、fallback 或 policy。

验证证据：

- Ansible 单机 `PPU-13` check-mode/diff 后落盘；未停止、重启或删除适配容器，也未重启
  当前模型服务。
- 容器内 226 个 `vllm_fl/**/*.py` 文件全部通过内存 `compile()`；
  `test_glm5next_support.py` 加共享 manager/types/registry/call-op 回归共
  `101 passed, 1 warning in 11.07s`；`git diff --check` 通过。
- vLLM `/workspace/vllm@ee0da84` 与 FlagGems
  `sparse-mla-opt-w8a8-moe-fix@bca444b` 的工作树仍为空；既有服务 PID `2893015`
  仍存活。该进程在源码更新前启动，仅证明本次整理未干扰服务，不证明新代码冷启动或
  FULL graph 整模回放已完成。

本轮设计结论：用户指出的三类结构问题已消除，当前 diff 可继续作为 PR 候选整理；在用
新源码完成一次冷启动、最小推理和 FULL decode graph replay 前，适配状态仍不能升级为
新的整模验收通过。

## 2026-09-09 模型与 patch 文件合并（当前文件结构）

用户进一步要求一个模型只保留一个模型实现文件。检查目标权重
`/mnt/cpfs/models/GLM-5.3-Flash-BF16/config.json` 后确认 checkpoint 架构为
`Glm5NextForConditionalGeneration`，因此文本模型、sparse indexer、KPool cache contract
和 conditional/multimodal wrapper 都是同一 checkpoint adapter 的组成部分，不应以四个
模型模块分散保存。对应的 graph metadata、KPool 安装和 runner adapter 也都是同一 GLM
兼容 patch 的内部实现，不需要三个独立 patch 模块。

最终远端结构为：

- `vllm_fl/models/glm5next.py`：合并原主模型、indexer、KPool 和 conditional wrapper；
- `vllm_fl/patches/glm5next.py`：合并 patch 入口、graph helper、KPool integration 和 runner adapter；
- 删除原 `models/glm5next_{indexer,kpool,multimodal}.py` 与
  `patches/glm5next_{graph,kpool,runner}.py`，旧模块 import/注册路径同步改为主文件。

落盘前在容器内对生成结果做了内存编译和 AST 结构检查，并按源文件 SHA-256 拒绝并发覆盖；
原九个文件保存在
`/mnt/nfs/users/jinghao/glm5.3-flash/05-tmp/glm-file-merge-backup-20260909`，可恢复。
首轮回归发现给整个合并模型添加 postponed annotations 会使 vLLM
`support_torch_compile` 看不到 `forward` 的运行时 `torch.Tensor` 注解；只移除该行后，
合并内容不再改变原主模型的注解语义。

最终验证：模型文件 2,502 行，SHA-256
`7d6338f958ec5de9f6885b760be1283b338daedc094a3edf362841d402038609`；patch 文件
762 行，SHA-256 `3e5ffa933e1d5f5a0f605b995b39c74c268dc54c80c30d09121c29d2ddd1b8de`；
六个辅助文件均不存在；全 Plugin Python 源码通过内存编译，GLM 与共享 dispatch 聚焦回归
`102 passed`，`git diff --check` 通过。既有 8010 服务仍返回
`GLM-5.3-Flash-BF16`、`max_model_len=65536`，但该进程未重启，因此仍不作为新源码冷启动或
FULL graph 验收证据。

## 2026-09-09 分支发布

上述合并后的完整适配当前以 `support-hy4-preview@939e07826bfec9cfa3da4a75af3ebaedfcef9af2`
为父提交，已发布到
`support-glm5.3-flash@1bec1a407fac43304fcc84864999541e92590425`。两笔 commit 的 author 与
committer 均为
`ZenithJoyH <1355922182@qq.com>`，远端 branch ref 已回读验证。提交包含 33 个产品/测试文件，
未包含远端运行目录、模型权重、日志、bundle、凭据或本地管理记录；未创建 PR。

身份修正采用相同 tree/parent/message/time 的 commit 重建；GLM commit 仅因父 SHA 改变而
重建。两个分支通过原子 `force-with-lease` 从 `d56f7b2 → 939e078`、
`edcf4a2 → 1bec1a4`，两组 old/new tree 均无代码差异。

## 2026-09-09 upstream 同步验证

两个支持分支已同步 `flagos-ai/vllm-plugin-FL@main` 的
`8926c1188be20f805f62d42555697936ec781c20`。为避免再次改写上述身份修正提交，使用 merge：

- `support-hy4-preview`：`939e078 → 2f7bcc0bb653e24cf6b5558965ce6712e2002b60`；
- `support-glm5.3-flash`：`1bec1a4 → e1f941860bdc647aaab8928d6007391e8a0561d8`。

唯一冲突为 reference backend 注册列表；最终同时保留 upstream 的 optional fallback 跳过语义、
Hy4 BF16 indexer 和 GLM reference ops。PPU-13 上 230 个 Plugin Python 文件编译通过，受影响
回归 `107 passed`，工作树和 origin/upstream tracking 均 clean。两个分支通过非 force、原子
fast-forward 推送，未重启服务。

## 2026-09-09 线性历史最终整理

上述 merge 同步方式已被用户要求的 rebase/squash 历史取代。最终发布拓扑为：

`upstream/main@8926c118` →
`support-hy4-preview@06efe801ea3a47e20e492f048eef254ffcc337fa` →
`support-glm5.3-flash@424c0dd558f5c55619e68022de4f713d9b41b2a1`。

其中 Hy4 原 `5329cb1`、`795f7c9`、`939e078` 三笔自有提交已压为一笔，GLM 保持一笔且位于
最后；两笔提交的 author/committer 均为 `ZenithJoyH <1355922182@qq.com>`。新旧 Hy4、GLM
tree 分别逐项比较为零差异，故仅改变提交拓扑和 SHA，不改变产品或测试源码。

在 PPU-13 的 editable Plugin 中，正式 branch ref 移动前完成全源码 `compileall` 和受影响
回归，结果 `107 passed, 1 warning in 11.42s`。两个本地 branch ref 通过同一 Git
`update-ref` transaction 更新，GitHub 两分支通过单次 atomic、带旧 SHA lease 的强制推送
更新；最终 GitHub refs、容器内 local/origin/upstream refs 及 clean 工作树全部一致。现有
8010 服务仍健康，容器及服务均未重启；该结果不替代冷启动与 FULL decode graph 整模验收。
