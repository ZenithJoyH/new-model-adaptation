# 017：GPQA temperature=0 触发长输出、抢占与近停滞

## 元数据

- 状态：`root-cause-fix-branch-published-awaiting-service-validation`
- 首次出现时间：2026-09-08 00:00 +08:00
- 最后验证时间：2026-09-08
- 模型：Hy4-preview W8A8 linear MoE，served model `hy4`
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器名称与镜像：`hy4`，镜像 ID
  `sha256:f22202780fa6a2b9b31e20702609582930f745544804e89ff18e53e3cc5c52c1`
- Plugin / FlagGems / vLLM revision：
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8` /
  `717a9ef60d38b559d8b4424488ca5cad2fe61a59` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：`FULL_DECODE_ONLY` graph、TP16、GPQA Diamond 198 题、客户端并发 32、
  `reasoning_effort=high`、`max_gen_toks=40000`

## 问题现象

- 症状：首次正式全量轮显式使用 `temperature=0.0`。已完成缓存的 12 个响应中，9 个达到
  40,000 tokens 并以 `finish_reason=length` 结束，只有 3 个形成有效答案。恢复模型默认
  `temperature=0.9` 后问题仍复现：首批 16 个缓存响应中又有 9 个 length。
- 发生顺序：并发请求持续占满 KV cache，服务累计 23 次 preemption；被抢占请求恢复时需要
  重算 KV，重算比例由约 4.5% 增至约 33%，输出吞吐降到约 0.0–0.3 token/s，并反复出现
  `No available shared memory broadcast block found in 60 seconds`。未见 EngineCore fatal、worker
  退出、OOM 或 HTTP 500。
- 影响范围：按该速度与截断比例继续运行不能形成可信的 198 题结果，因此只终止本任务评测进程，
  发布失败 receipt 后换新 run；旧 run 不覆盖、不续跑。
- 失败 run：远端
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/gpqa-full-safe-c32-high40k-20260907-2350/`。
- 失败 receipt：输出树内 `acceptance-result.json`，状态 `failed`，错误
  `RunInterrupted: signal15`，SHA-256
  `9778c137df7bf38e0860c42fd80ad92e4a30722a3451d7926d8b98b8bae2946d`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| `distributed-sample-tokens-timeout.md` | 并发生成阶段出现 shared-memory 等待且吞吐显著下降 | 本轮 worker 全部存活并持续进展，没有 `sample_tokens` 超过 300 秒、rank 分歧或 RPC timeout | 低 | 不增加执行超时；先处理造成超长序列的采样配置 |
| 既往 Hy4 40K GPQA 运行记录 | 同模型、同题集与最大输出长度 | 本轮显式 `temperature=0.0`，历史轮不是同一配置且仅少量 length | 中 | 将模型默认采样作为受控对照，不直接复用历史结论 |

## 诊断与假设

已验证事实：服务启动日志明确声明模型 `generation_config.json` 默认覆盖为
`temperature=0.9, top_k=-1, top_p=1`；首次正式轮又通过评测参数显式覆盖成 `temperature=0.0`。
终止评测客户端前 worker 均存活、服务健康、请求仍有缓慢进展，故不是 016 的 bool slice 崩溃复发。

当前假设：贪心解码显著增加该 reasoning 模型陷入长循环并触达 40K 上限的概率；32 条长序列进一步
制造 KV cache 抢占和重算，导致系统接近停滞。该因果关系需由仅恢复 `temperature=0.9` 的完整对照
验证，当前不标为根因修复。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 采样温度 | 模型默认 0.9 | 显式 0.0 | `05-runs/gpqa-full-safe-c32-high40k-20260907-2350/` | 12 个缓存响应中 9 个 length；23 次抢占，吞吐近停滞 | 该配置不可继续作为正式全量轮 |
| 2 | 采样温度 | 轮次 1 | 0.9；其余保持 c32、high、40K、graph | `05-runs/gpqa-full-safe-c32-high40k-t09-20260908-0315/` | 前 16 个缓存响应中 9 个 length；24 次抢占、23 个等待；失败 receipt SHA-256 `6b05b75ef30b7dae10b49c83adc12ded22e9bfce9eb31d01daebd93371c3796e` | 模型默认温度不足以消除问题，排除“仅 temperature=0 导致” |
| 3 | 客户端并发 | 轮次 2 的 c32 | c8；保持 0.9、high、40K、graph | 待新 run | 待执行 | 验证抢占/重算是否放大长输出问题 |

## 根因

- 已验证根因：`temperature=0.0` 不是充分根因；恢复模型默认 0.9 后仍有 9/16 响应达到 40K。
- 当前假设与缺失证据：c32 下长序列占满 KV 后的 preemption/recompute 明显降低吞吐，并可能放大
  生成退化；需在同一服务配置上以 c8、0.9、high、40K 做单变量对照。历史 2026-09-06 c32
  完整轮仅 6/198 无效，与当前 9/16 差异显著，但其 FlagGems/Plugin 状态和当前栈不等价。

## 解决方法或 Workaround

- 修改思路：第一步保留 graph、TP16、客户端并发、reasoning effort 和 40K 输出上限，只把采样
  温度恢复为模型发布配置的 0.9；复现后第二步保持温度与生成语义，仅把评测客户端并发从 32
  降为 8，避免同时让 32 条最长 40K 序列竞争 KV。
- 层级与职责：采样语义属于评测配置，不应通过 vLLM 或 Plugin 代码兜底；本轮未改源码。
- 远端过程路径：服务生命周期与旧日志保存在
  `/mnt/nfs/users/jinghao/hy4-preview/03-issues/017-gpqa-temp0-preemption-20260908/`；修正后的不可变
  runner 输入在
  `/mnt/nfs/users/jinghao/hy4-preview/04-acceptance/gpqa-full-safe-c32-high40k-t09-20260908-0315/`。
- 服务停启：终止评测后发现 32 个孤立服务请求不能由已退出客户端取消；为清空精确请求状态，
  仅向 API PID `2468847` 及其子进程发送 TERM，确认退出后使用已验证 launcher 启动新 API PID
  `2509597`。服务实例为 `PPU-07:550e93f0ba4c:2509597:152307561`；`hy4` 容器全程未停止、
  重启或删除。
- vLLM 未修改：HEAD 保持如元数据且工作树为空；Plugin 用户已有差异继续保留，二进制 diff SHA-256
  为 `d2a01df0f5d9b85bbb51d3111bde7ceeafef9f563f6be1b151cbfd9616a3943d`。
- workaround 退出条件：c8 对照能显著减少 length、保持 0 preemption，并完整产生 198 题结果；
  由于正式验收契约要求 c32，c8 结果只能满足本次诊断/全量评分，不能标记正式 accuracy passed。

## FlagGems 证据

- 本问题未发现新的 FlagGems 算子异常；安全黑名单仍为 016 已验证的运行时集合。
- 当前 clean revision：`717a9ef60d38b559d8b4424488ca5cad2fe61a59`。
- 016 的 bool slice 最小复现仍位于
  `/mnt/nfs/users/jinghao/hy4-preview/08-bugs/flaggems-slice-bool-20260907/`；本轮无需新增算子复现。

## 验证结果

- 最小回归：新服务 health 200、16 个 TP worker、0 preemption。
- `eager`：服务重启未改变执行配置；沿用 016 后已验证结果。
- `graph` capture/replay：新服务完成 `FULL_DECODE_ONLY` 51/51；单题确定性探针返回 `42`；c8
  sanity 为 8/8，耗时 20.66 秒，之后服务健康且 0 preemption。
- 正式全量：`temperature=0.9`、c32 轮已受控终止并发布失败 receipt；前 16 个缓存响应中 9 个
  length、累计 24 次抢占，未产生 result/sample 文件。下一轮 c8 仅是诊断性全量，不属于正式
  c32 accuracy acceptance。

## 限制与下一步

- 尚存限制：两轮 c32/high/40K 都无法形成完整结果；不能声称精度通过或优化完成。
- 后续动作：持续检查响应缓存、finish reason、吞吐、抢占和首个错误；终态核验正式 receipt、198 个
  唯一样本与 strict/flexible 指标。
- 设计审查：当前仅修正评测采样配置，无 Plugin PR 范围影响。

## 经验沉淀

- 是否可跨模型或平台复用：只适用于默认依赖采样的 reasoning 模型；跨模型结论尚未验证。
- 知识库处理状态：`local-only`
- 候选知识库条目：暂不提升，等待完整对照。

## 2026-09-08：c32/c8 差异确认与修复分支交付

后续单变量对照否定了“仅采样温度或 KV 抢占导致”的假设。同一评测器固定
`seed=1234`，c32 与 c8 有 12 个相同请求键；c32 中 4 个请求未形成字符串，多个响应膨胀至
约 1.4 万至 8.8 万字符，而 c8 的 19 个缓存响应全部为 395 至 1741 字符、无 length、服务
累计 0 preemption。对照原始结果位于：

- `/mnt/nfs/users/jinghao/hy4-preview/03-issues/017-gpqa-temp0-preemption-20260908/c32-c8-comparison.json`
- SHA-256：`d0483b5a8b9b04744da105266914dee54407eb10f0633f0066df702936201ce0`

当前 `sparse-mla-opt@717a9ef60d38b559d8b4424488ca5cad2fe61a59` 未包含
`051f303a6178d9c898cad1c8b20ada6202482af2` 的 INT8 W8A8 dtype 分类修复。当前栈独立复现
显示 BF16 W8A8 在 M=32、4095 通过，在 M=4096、8192 失败，后两者几乎 100% 元素错误；
`_get_config_dtype_str` 同时拒绝 `use_int8_w8a8` 参数。根因是 W8A8 被误分类为 plain BF16，
M>=4096 时进入不正确应用 INT8 scale 的 large-M fast path。c32 更容易把 prefill 聚合到该
阈值，c8 通常不触发；长输出与抢占是错误数值的后续放大。

已从 `origin/sparse-mla-opt@717a9ef60` 创建
`sparse-mla-opt-w8a8-moe-fix`，完整合入
`origin/fix-w8a8-moe-config@8f7fccc6`，再与官方上游默认主线
`upstream/master@6e9839ec` 对齐。官方仓库不存在 `main` ref，其默认主线为 `master`。
最终提交为 `bca444b8569294e7d4e4deff7ddfec7f05682033`，已非强制推送至：

- `https://github.com/ZenithJoyH/FlagGems/tree/sparse-mla-opt-w8a8-moe-fix`

本地与远端 ahead/behind 为 0，FlagGems 工作树为空；vLLM 保持 clean，Plugin 的既有
`PROVENANCE.md` 删除和 `thead.yaml` 修改原样保留。容器 editable 安装已刷新为
`flag_gems 0.0+gbca444b85`。合入后的 42 项 W8A8 回归全部通过，覆盖 FP16/BF16、
eager/graph、M=32/4095/4096/4097/8192；日志及哈希：

- `/mnt/nfs/users/jinghao/hy4-preview/08-bugs/flaggems-w8a8-large-m-current-20260908/evidence/upstream-aligned-full.stdout.log`
- SHA-256：`595abe63148b911e3eb836269f3cc4962976b4c42f4cfd35fdd2ce3963fa8d80`
- 分支合并、upstream 对齐与 push 证据：
  `/mnt/nfs/users/jinghao/hy4-preview/03-issues/017-gpqa-temp0-preemption-20260908/branch-merge-20260908/`

模型服务在 09:39 因 016 已知的 `slice: unsupported dtype torch.bool` 退出；这发生在 upstream
合并前且与 Git 操作无关。容器未停止或重启，GPQA 未恢复。下一步必须先确保新服务继续使用
016 的安全 blacklist，完成最小 eager/graph 与 c8/c32 小规模对照；在用户明确恢复前不重启
全量 GPQA。
