# 016：FlagGems bool slice 导致 GPQA 首批请求击穿服务

## 元数据

- 状态：`workaround-verified`
- 首次出现时间：2026-09-07 22:05:07 +08:00
- 最后验证时间：2026-09-08
- 模型：Hy4-preview W8A8 linear MoE，served model `hy4`
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器名称与镜像：`hy4`，镜像 ID
  `sha256:f22202780fa6a2b9b31e20702609582930f745544804e89ff18e53e3cc5c52c1`
- Plugin / FlagGems / vLLM revision：
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8` /
  `717a9ef60d38b559d8b4424488ca5cad2fe61a59` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：`FULL_DECODE_ONLY` graph、TP16；GPQA Diamond 限定 32 题、并发 32、
  `max_gen_toks=512`

## 问题现象

- 错误签名：`AssertionError: slice: unsupported dtype torch.bool`。
- 发生顺序：32 个 FlagEval 请求开始后均收到 HTTP 500；所有 16 个 TP worker 在
  `_prepare_inputs → discard_request_mask.copy_to_gpu → aten.slice` 同一路径退出，随后
  EngineCore fatal，端口 8010 不再监听。
- 影响范围：诊断轮 32 个样本均未得到模型答案，不能计作精度结果；服务必须恢复后重跑。
- 原始结果：远端
  `/mnt/nfs/users/jinghao/hy4-preview/03-issues/016-index-blacklist-diagnostic-20260907/outputs/hy4-ppu07-index-blacklist-diagnostic-c32-20260907/diagnostic-c32-20260907-2151/`。
- 失败日志：同一问题目录下 `hy4-preview.bool-slice-failure.log`，SHA-256
  `b05177f1701a6f49c42efcf986db26c0986364c87b5e0d1c1189062d44365153`。

### 2026-09-08 再次复现

- 用户通过原始 `/mnt/nfs/users/jinghao/hy4-preview/start_hyv4-preview.sh` 启动服务后，
  `/mnt/nfs/users/jinghao/hy4-preview/hy4-preview.log` 于 09:39:45 再次出现同一首错。
- 当前 FlagGems 为分支 `sparse-mla-opt-w8a8-moe-fix`、revision
  `bca444b8569294e7d4e4deff7ddfec7f05682033`，安装模块来自
  `/workspace/FlagGems/src/flag_gems/__init__.py`。`ops/slice.py:199` 仍明确拒绝
  `torch.bool`。
- 本次启动脚本未设置 `VLLM_FL_FLAGOS_BLACKLIST`；Plugin 当前在途
  `thead.yaml` 仍只屏蔽 `to_copy`、`_to_copy`、`copy_`、`index`，不含 `slice`。
  因而此前验证的安全运行时 launcher 没有生效。
- 16 个 TP worker 均在
  `_prepare_inputs -> discard_request_mask.copy_to_gpu -> self.gpu[:n]` 进入 FlagGems
  `slice` 后断言退出。随后出现的 scheduler `KeyError`、`EngineDeadError`、HTTP 500 和资源泄漏
  warning 均为 EngineCore 失效后的连锁错误。
- 检查时容器仍存活，但无 vLLM 服务进程且 8010 未监听；评测容器中没有活动 GPQA/FlagEval
  进程，只有历史 defunct Python 进程。本次仅诊断和记录，未修改远端代码、配置或进程。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| Qwen3.8-Flash-Next / PPU `001-flaggems-slice-bool` | 同一 vLLM 请求准备路径、bool slice 断言、服务退出 | 模型、Plugin 与 FlagGems revision 不同；Hy4 为 TP16 graph | 高，但不能直接复用结论 | 在当前 revision 重新独立复现 eager/graph，并验证回退 |

## 诊断与假设

已验证事实：Plugin 的用户在途 `thead.yaml` 差异把历史默认黑名单中的大批算子移除，仅保留
`to_copy`、`_to_copy`、`copy_` 并新增 `index`；其中 `slice` 被移除。当前 FlagGems
`src/flag_gems/ops/slice.py:199` 明确拒绝 `torch.bool`。实际服务栈和独立复现都出现相同断言。

已排除方向：三份 FlagGems SQLite 数据库在请求前完整性检查通过，失败前后哈希不变；本轮没有
出现 `database is locked`。GPQA 数据集预检为 198 题，限定轮的 32 个 ID 唯一，因此不是输入
缺失或重复导致。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 让当前配置直接承载 GPQA 并发 | 服务空闲健康 | 32 题、c32、512 tokens | 上述诊断结果目录 | 32/32 HTTP 500，worker 全退 | 当前配置不可承载请求 |
| 2 | 当前 revision 独立复现 | 原生 aten slice | FlagGems bool slice | `08-bugs/flaggems-slice-bool-20260907/repro.py` | eager 与 graph capture 均稳定报同一断言 | 根因复现成立 |
| 3 | 仅排除 `slice` | FlagGems bool slice | 原生 slice 回退 | 同一复现脚本 | eager 与 graph replay 均返回 `[true,false,true]` | 黑名单回退在算子层成立 |
| 4 | 仅追加运行时 `slice` 黑名单 | 用户当前四项黑名单 | 五项黑名单 | `02-environment/hy4-slice-blacklist-runtime-20260907/start.sh` | 服务恢复、graph 51/51；随后进入轮次 5 | bool slice 崩溃消失，但策略仍不可用 |
| 5 | 保持其余算子放开，仅回退 `slice` | 五项运行时黑名单 | 同一 32 题、c32、512 tokens | `03-issues/016-slice-blacklist-rerun-20260907/` | 32/32 在 1,800 秒客户端边界超时；服务健康、16 worker 存活、新致命签名 0；TunedConfig 哈希变化 | 消除崩溃但不能形成可用服务，首次算子调优路径不可接受 |
| 6 | 恢复已验证的 T-Head 安全基线 | 五项运行时黑名单 | Plugin HEAD 默认黑名单完整集合并额外保留 `index` | `02-environment/hy4-safe-blacklist-runtime-20260907/start.sh` | graph 51/51；32 个请求均在约 295 秒返回，16 worker 存活、0 抢占、服务错误签名 0 | 服务级 workaround 通过；512-token 无最终答案不计精度 |

## 根因

- 已验证根因：FlagGems 当前 slice 实现不支持 bool；Plugin 用户在途配置移除了默认的
  `slice` 回退保护，使 vLLM 的 bool 请求掩码进入该实现并触发断言。仅补回 `slice` 后服务
  不再崩溃，但被同时放开的其他默认保护路径使首批 32 请求持续初始化超过 1,800 秒，不能作为
  GPQA 服务配置。
- 这是 FlagGems 能力边界与调度配置组合导致的确定故障，不是数据库锁或模型前向错误。

## 解决方法或 Workaround

- 修改思路：保留 Plugin 用户已有工作区差异，不直接写 `/workspace/vllm-plugin-FL`；先通过
  Plugin 已有 `VLLM_FL_FLAGOS_BLACKLIST` 扩展点做单变量 `slice` 对照。该对照证实崩溃消失但
  首批请求全部超时后，改为完整复述 Plugin HEAD 已验证的 T-Head 默认安全黑名单，并额外保留
  用户为当前栈加入的 `index`。
- 选定层级：这是已知不支持 dtype 的算子调度 workaround；原生 aten 已覆盖所需 view 语义。
  FlagGems 本身的根因修复应单独增加 bool 支持，不能在 vLLM 公共路径散布模型名判断。
- 受影响调用方：所有使用同一 T-Head 配置且可能对 bool tensor 执行 slice 的 vLLM 请求准备
  路径；环境变量仅作用于本次 Hy4 服务进程及其子进程，未改变其他容器或默认配置。
- Plugin 内实现/测试：本轮没有修改 Plugin 源码或新增仓内测试；外部 checkout 的用户改动原样
  保留。若将 workaround 固化为默认策略，应在 Plugin T-Head 配置与 dispatch 单测中完成，并
  独立评审当前大幅缩减默认黑名单的影响。
- 远端过程路径：单变量对照为
  `/mnt/nfs/users/jinghao/hy4-preview/02-environment/hy4-slice-blacklist-runtime-20260907/start.sh`；
  当前候选为
  `/mnt/nfs/users/jinghao/hy4-preview/02-environment/hy4-safe-blacklist-runtime-20260907/start.sh`；
  两者都不覆盖原始 `start_hyv4-preview.sh`。
- 服务停启：原 EngineCore 已因断言自行退出，确认无残留 vLLM PID、8010 未监听后，于
  2026-09-07 22:19 +08:00 只启动本任务 Hy4 服务；容器未停止、重启或删除。
- vLLM 未修改：启动前 clean，HEAD 如元数据；后续验证完成时再次核对。
- workaround 适用条件：FlagGems slice 仍拒绝 bool 且 vLLM 请求掩码会经过 slice。退出条件为
  FlagGems 在当前 PPU revision 上补齐 bool eager/graph 语义并通过同一复现后，方可去掉。

## FlagGems 证据

- 当前 clean revision：`717a9ef60d38b559d8b4424488ca5cad2fe61a59`。
- 实现证据：`/workspace/FlagGems/src/flag_gems/ops/slice.py:199` 的 dtype 断言。
- 当前任务复现根：
  `/mnt/nfs/users/jinghao/hy4-preview/08-bugs/flaggems-slice-bool-20260907/`。
- 容器内命令：在上述目录执行 `CUDA_VISIBLE_DEVICES=0 python3 ./repro.py`；结构化输出为
  `result.json`。未使用或复制 `/bug`。

## 验证结果

- 最小回归：原生 bool slice 通过；FlagGems 直调稳定失败；排除 `slice` 后结果正确。
- `eager`：算子级 workaround 通过；全模型当前栈执行模式验收随后单独执行。
- `graph` capture/replay：FlagGems 在 capture 阶段失败；排除后算子 capture/replay 通过。全模型
  graph 完成 51/51 capture；c32 共生成 16,384 tokens，全部 API 正常返回且服务保持健康。
- 数值、dtype、shape、layout、边界条件：当前最小用例覆盖 device bool 一维长度 4、切片
  `[0:3:1]`；这是实际请求掩码 dtype 的因果复现，不替代后续全模型覆盖。
- 最终通过标准：修复后同一 32 题 c32 诊断不再出现 HTTP 500/worker 退出，已满足。512-token
  诊断的 32 项因 `finish_reason=length`、`content=None` 被 runner 标作无答案，只验证服务稳定性，
  不作为精度分数。graph sanity 与全量 198 题 GPQA 属于后续验收。

## 限制与下一步

- 尚存限制：Plugin 工作区当前缩减默认黑名单的改动本身没有被覆盖或清理；当前服务依赖批准
  工作根中的运行时策略，重启时必须使用记录的 launcher。
- 上游跟踪：官方 FlagGems 已有同一根因 issue
  [#6049](https://github.com/flagos-ai/FlagGems/issues/6049)，PPU 独立复现证据已通过
  [补充评论](https://github.com/flagos-ai/FlagGems/issues/6049#issuecomment-5578303182) 提交；对应修复 PR 为
  [#6061](https://github.com/flagos-ai/FlagGems/pull/6061)。
- 后续动作：跟踪 #6061 最终 revision，在 PPU 上重新执行 bool slice eager/graph 最小回归和
  TP16 服务验证；通过后才能移除 `slice` workaround，并继续完整 GPQA。
- 设计审查：本轮只采用已有环境变量扩展点，未形成 Plugin PR。是否恢复默认 T-Head 黑名单需
  另行评估全部共享模型调用方，不能从单一 Hy4 成功外推。

## 经验沉淀

- 可跨模型/平台复用性：签名与 Qwen3.8/PPU 高度一致，PPU 上具有复用价值；其他平台未验证。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：FlagGems bool slice 请求准备失败及精确调度回退。
