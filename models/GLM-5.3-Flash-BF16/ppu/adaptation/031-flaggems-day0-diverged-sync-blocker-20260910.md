# 031：FlagGems day0 分支分叉阻塞剩余算子补齐

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-10
- 最后验证时间：2026-09-11
- 模型：`GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / `hy4-ppu07-snapshot:20260903`
- Plugin / FlagGems / vLLM revision：Plugin
  `support-glm5.3-flash@db09b64afdc222d1c32e4e80f30820a243358e34`；FlagGems
  `support-glm5.3-flash@4a3cba029d87ec06b5222ed94542f1f1d2e267a0`；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 执行模式与负载：最终为 TP16、`FULL_DECODE_ONLY` graph、max model len 65536、max seqs
  32；算子/dispatch、最小生成、c8 与全量 GPQA c32 均已执行。

## 问题现象

- 错误签名或症状：用户要求补齐剩余 FlagGems 算子，但容器内 clean 的 editable FlagGems
  checkout 无法 fast-forward 到其 tracked branch。
- 发生顺序：逐项确认 37 个 GLM model-facing dispatch 后，按适配流程同步 FlagGems 基线时发现。
- 影响范围：`causal_conv1d_fn`、`chunk_kda_with_safe_gate`、pool 展开、tail 拼接以及现有
  pack/unpack 的 graph-safe 接入；当前已验证服务不受影响。
- 精简证据及原始证据位置：控制端只读 preflight/fetch 输出；未创建远端过程代码或新 run。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [028 FlagGems kernel ownership](028-flaggems-kernel-ownership-20260910.md) | 算子实现应归 FlagGems | 当前先遇到分支同步冲突 | 高 | 不在旧 revision 上新增实现 |
| [029 provider 重分类](029-flaggems-dispatch-reclassification-20260910.md) | Plugin 只保留 adapter/dispatch | 本轮需要新增 FlagGems 能力 | 高 | 同步完成前不编辑 Plugin 或 FlagGems |

## 诊断与假设

- 已验证事实：live FlagGems 分支和工作树为 `flaggems-for-day0@8fef991a`、clean，editable
  import 指向该 checkout；Plugin 和 vLLM 也均 clean。
- 已验证事实：tracked branch 为 `5e08615a`，共同祖先为 `187fc1f7`；`HEAD...tracked` 为
  left 1 / right 2，不能 fast-forward。
- 已验证事实：左侧独有 `8fef991a feat(fused): add Qwen3.8 day-0 kernels`；右侧独有
  `37716d41 feat(fused): add QSA, PLE, GDN and slot mapping kernels` 和
  `5e08615a fix(fused_moe): classify INT8 W8A8 configs correctly`。
- 已验证事实：官方 `origin/master` 已前移到 `e15b22dc8d16e9a4b7726a6da8191c093507d2fd`。
- 已排除方向：不在 stale `8fef991a` 上继续写；不 reset、强制更新、丢弃左侧提交或静默
  rebase 另一项工作的分支。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | source identity | 假设 checkout 可直接更新 | 核对 branch/upstream/status/editable import | PPU-13 当前容器 | 三棵源码 clean，身份明确 | 可以安全 fetch，不代表可更新 |
| 2 | tracked ref freshness | 本地 tracked 可能过期 | fetch Zenith day0 与官方 master | 当前 FlagGems checkout | ref 刷新成功 | tracked 与 upstream 均已前移 |
| 3 | fast-forward 条件 | live `8fef991a` | 比较 `HEAD...zenith/flaggems-for-day0` | `rev-list --left-right --count` | `1 2`，merge-base `187fc1f7` | mandatory FF-only 同步不可执行 |

## 根因

- 已验证根因：另一个工作流改写/推进了共享 `flaggems-for-day0`，而 GLM 已验证 checkout 保留
  旧历史上的 Qwen3.8 提交；两边同时有独有提交，已不是快进关系。
- 若未完全证实，当前假设与缺失证据：需要用户指定由谁整合 Qwen3.8 的两条历史，以及是否
  允许在共享分支上 rebase/重写；本任务不能自行决定。

## 解决方法或 Workaround

- 修改思路：先由用户授权并选择共享分支整合策略；同步到唯一 clean HEAD 后再逐项实现和验证。
- 选定层级/扩展点、职责依据和替代方案：缺失 Triton 能力归 FlagGems；Plugin 只添加通用
  dispatch adapter。不能用 Plugin 私有 kernel 绕过本阻塞。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：GLM KPool/KDA；HY4
  共享 top-k 不在本轮缺口。Qwen3.8 代码属于另一项工作，必须保留或由其所有者确认处理。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：Plugin 预计只需接线和契约测试；
  新计算 kernel 应进入 FlagGems。
- Plugin 内必要实现或回归测试路径：待同步后确定；当前未修改。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：仅控制端 `/private/tmp/glm53-*`；
  未在远端创建过程代码。
- 分支与 revision/commit：未提交、未推送、未改写任何 source branch。
- 正式回归测试路径：待同步后先做 direct-op eager/graph，再做 Plugin dispatch/component。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：尚未开始实现。
- workaround 的适用条件、默认策略/性能影响和退出条件：无 workaround；同步完成是退出条件。
- 服务停启操作及核对结果：未停止或重启服务/容器；preflight 时容器 running/restart 0。
- vLLM 未修改证明：`/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389` clean。

## FlagGems 证据

- 同步后的 revision 与检索证据：fetch 后 live `8fef991a`、tracked `5e08615a`、official
  `e15b22dc`；因分叉未执行 pull。
- 已有算子及接入方式，或缺失结论：live FlagGems 已有 `pack_seq_triton`、
  `unpack_seq_triton` 和 FP8 `indexer_k_quant_and_cache`；缺少完整 prefill causal-conv、
  chunk KDA、pool 展开和 tail 拼接。latest day0 的两个右侧提交未补这些能力。
- 如为 FlagGems 缺陷：当前是 source-history blocker，不是算子数值缺陷；未创建 `07-bugs/`。
- 如确因工具要求使用 `/bug`：不适用。

## 验证结果

- 最小回归：未执行新代码回归，因为同步门禁未通过。
- `eager`：未执行。
- `graph` capture/replay：未执行。
- 数值、dtype、shape、layout、边界条件：尚未实现，不作结论。
- 最终结论与通过标准：当前阻塞；只能在分支历史得到明确授权并同步后继续。

## 限制与下一步

- 尚存限制：不能基于 stale revision 选择或新增 FlagGems 算子。
- 后续动作：用户选择保留并整合 `8fef991a`，或明确以 tracked `5e08615a` 为唯一基线并处理
  左侧提交；随后同步官方 master、建立 direct-op 基线，再开始实现。
- 设计审查结论及 PR 范围的影响：尚无新 diff；预期 FlagGems 公共算子和 Plugin 接线应作为
  可独立审查的变更，不能混入另一项 Qwen3.8 历史整理。

## 经验沉淀

- 是否可跨模型或平台复用：共享算子分支必须在实现前固定唯一线性基线，可跨模型复用。
- 知识库处理状态：`local-only`
- 候选知识库条目：editable 依赖的已验证 HEAD 与共享 tracked branch 分叉时，禁止在旧树上
  继续实现，也禁止用 reset/rebase 隐式选择另一任务的历史。

## 2026-09-10 解除阻塞与最终验证

用户明确要求按模型拆分 FlagGems 分支。处理后两条分支均直接基于当时最新官方
`flagos-ai/FlagGems:master@e15b22dc8d16e9a4b7726a6da8191c093507d2fd`，并已非强制推送到
`ZenithJoyH/FlagGems`：

- `support-qwen3.8-flash@ffb3a8bf2f869fea1024719454eaf47c2fde6895`：只有一笔 Qwen3.8
  专属提交，文件范围为 `qwen3_8_flash_next/`、对应测试和统一导出。
- `support-glm5.3-flash@4a3cba029d87ec06b5222ed94542f1f1d2e267a0`：只有一笔 GLM/day-0
  算子提交，不携带 Qwen3.8 专属目录。

GLM 分支复用既有 `pack_seq_triton`、`unpack_seq_triton`，新增通用的 device-side pool/tail
mapping、变长 prefill causal-conv 和 fused-gate chunk KDA。Plugin 不新增 kernel 或模型特判，
只在既有 FlagGems capability registration 中增加六条薄绑定，并以单一 GLM 提交
`support-glm5.3-flash@db09b64afdc222d1c32e4e80f30820a243358e34` 发布到
`ZenithJoyH/vllm-plugin-FL`。容器内两个 editable checkout 均已对齐相应远端且 clean；vLLM
仍为 `ee0da84ab9e04ac7610e28580af62c365e898389`，未修改。

验证结果：

- FlagGems PPU 数值回归：`11 passed, 1 warning`。
- Plugin GLM 聚焦回归：`9 passed, 1 warning`。
- 实际 dispatch：`sparse_indexer_pack_seq`、`sparse_indexer_unpack_seq`、
  `sparse_indexer_expand_pools_to_tokens`、`sparse_indexer_append_tail_to_topk`、
  `causal_conv1d_fn`、`chunk_kda_with_safe_gate` 全部为 `default.flagos`。
- 只停止已核实的旧 vLLM PID `29810`，未停止或重启容器；新服务 PID `42996`，16/16
  worker、decode FULL graph 7/7、health 200、启动后致命错误 0、容器 restart 0。
- 最小请求 `finish_reason=stop`、content=`2`，证明真实 prefill 与 decode 链路可执行。

原始证据位于
`/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/flaggems-gap-20260910/`：

- `flaggems-pytest.log`：SHA-256
  `ea33a759a75a4423116afc9735cb8bc9b3c897ca38f5a8d9c344937f5466c0e0`。
- `plugin-pytest.log`：SHA-256
  `25c1163e23d4ba0e002ebc4faeb2cfd016b5650f2eae0f864d699f92fd981644`。
- `dispatch-audit.log`：SHA-256
  `211338f058d8e5d51400cfb423fd749500692cce9c6009db6f1010459af081f8`。
- `smoke-response.json`：SHA-256
  `5505706c60d093633396b93607aa750049b6f568966c37cf1e05df315ce2ed3e`。

最终根级 launcher 为 host/container 同一路径
`/mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh`，SHA-256
`5d54dacc5f5af26bd3e4847aad85ae4575b98d7072093aa21ad2ed550b4534ba`。脚本不再创建目录；
新运行产物使用 `04-runs/`、`05-tmp/`、`06-cache/`。为满足安全要求保留最小 8010 端口占用
检查；旧脚本备份可恢复地保存在 `01-environment/legacy-launchers/`。

本轮只完成适配与功能验证，未重跑 GPQA 或正式性能验收，不能据此把平台状态提升为
`optimized`；历史 accuracy 失败结论不变。

## 2026-09-11 适配阶段完成

用户明确要求将适配标记为完成。状态按能力边界收口为 `functional`，而不是 `optimized`：

- 2026-09-11 最终只读复核仍为 Plugin `db09b64`、FlagGems `4a3cba0`，两个 editable
  工作树 clean；vLLM 未修改。
- 容器 ID `bf3487115c28f4ac45b34667ce7f3853a3eaa9879b54715a6cde5e2bc81ca6b1`
  保持 running、restart 0；服务实例 `PPU-13:bf3487115c28:42996:175243105` 为
  health 200、16/16 worker。
- 最终 launcher 的 host/container 路径均为
  `/mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh`，SHA-256
  `5d54dacc5f5af26bd3e4847aad85ae4575b98d7072093aa21ad2ed550b4534ba`。
- 冷态 c8 保留首次 shape 编译/调优导致的性能失败；相同配置热态复测 8/8、零错误，
  153.28 tokens/s，满足固定 sanity 判据。
- 当前提交的全量 GPQA 已完成 198 个唯一题目：strict 172/198（86.87%），10 题均因达到
  60000 completion tokens 而被 runner 标记 `<TIMEOUT>`，不是 HTTP/RPC 计时超时。该结果
  未达 88% accuracy 门槛，因此 acceptance accuracy 保持 failed，不影响“模型服务和适配
  实现可用”的 functional 结论。

至此，源码所有权与 dispatch 设计、PPU 数值回归、真实 TP16 graph 服务、并发正确性、
最终启动脚本和完整负载稳定性均已验证，适配阶段完成；正式 accuracy、performance、
evidence 与 summary 仍属于后续验收工作。
