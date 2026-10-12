# 010：Common slot graph replay 完成性导致 GDN 状态污染

## 元数据

- 状态：`partially-verified`；metadata 可见性修复已验证；设备级和当前流同步均在 full198 长负载中
  遇到同类 TP rank 分叉，说明超时是独立问题
- 首次出现时间：2026-09-13
- 最后验证时间：2026-09-14
- 模型：Qwen3.8-Flash-Next，BF16
- 平台与 Host 别名：T-Head PPU，`PPU-01`，仅使用 PPU 8–15
- 容器名称：`qwen3.8-flash`
- Plugin / FlagGems / vLLM revision：Plugin 基线
  `939600b323c02c21916f1f76bfb4cd8c2b02578d`；FlagGems
  `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：TP8、`FULL_AND_PIECEWISE`、max model len 65536、max seqs 32、
  max batched tokens 4096、capture sizes 1/2/4/8/16/32；正式 GPQA 为 198 题、c64、
  `max_gen_toks=60000`

## 问题现象

- full198 图模式得到 198/198 个 HTTP 200 且服务终态健康，但 strict 只有 114/198
  （57.58%）。样本中有 69 条 `timeout=true`/`<TIMEOUT>`，其中只有 19 条实际达到
  60000 token；其余 50 条在较短输出后 `content=None`。
- `<TIMEOUT>` 是评测器把 `message.content is None` 转换得到的标签，并非这些请求都发生了网络或
  服务超时。图模式的 `message.reasoning` 已出现重复、乱码、提前 EOS 或无界推理，最短异常只有
  12 token。
- 异常集中在后续请求波次。相同 198 个 prompt、target 与生成配置下，eager 的 159 个有效样本中
  153 个正确；图模式中大量 eager 正确样本变成空正文，符合请求槽位复用后 GDN/Mamba 状态被
  错误消费的表现。
- 原始 full198 样本位于
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/Qwen3.8-Flash-Next-2aacb2ed-fullpiecewise-normal-aten-c64-maxgen60000/gpqa-full-c64-maxgen60000-2aacb2ed-fullpiecewise-normal-aten-20260912/gpqa_diamond_generative_cot/attempt-1/Qwen3.8-Flash-Next/`；
  结果与 samples SHA-256 分别为 `532d9064865cc59e6df6cae68b60dbb88be6b315635688a95440ef999df3e0b0`
  和 `6b4953bc13fbb7df8fd921bb86fa4fe7d2305dab9d54bb8fc7264b021c0f51a9`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [005：GPQA 长推理达到生成上限](005-gpqa-generation-cap.md) | 都会形成空正文或 `<TIMEOUT>` | 本问题 50/69 未达到 60000 token，且 reasoning 已损坏 | 高 | 生成上限只能解释 19 条，不能解释主要精度下降 |
| [008：PCCL graph replay 后 collective work FIFO 停滞](008-pccl-graph-eager-collective-stall.md) | 都由 graph 路径触发 | 本轮 198/198 HTTP 完成、服务无 fatal，表现为输出状态污染 | 高 | 作为独立 graph 正确性问题处理 |
| Hy4 preview 的历史 `topk` 问题 | 都可能影响采样输出 | 当前 blacklist 已包含 `topk`，三组 A/B 使用完全相同采样参数 | 高 | 排除为本次必要变量 |

## 诊断与假设

已验证事实：

1. 评测器只读取 `choices.message.content`；`None` 被包装成 `<TIMEOUT>`，所以原统计把服务超时、
   达到 token 上限和推理状态损坏混在了一起。
2. 相同 9 个代表样本、c9、temperature 1、top-p 0.95、top-k 20、seed 1234、max tokens 2048
   下，原图模式出现 5 个 12–254 token 的异常提前结束、3 个 length、仅 1 个正常回答；纯 eager
   为 6 个正常回答、3 个 length。
3. 保留整模型 `FULL_AND_PIECEWISE`，只令 `CommonSlotMappingGraphRunner` 走 eager 后，结果恢复为
   6 个正常回答、3 个 length。该 runner 产生 72 个 cache group 的 slot mapping 与共享
   `num_computed_tokens`，下游直接用它选择 GDN/Mamba 初始状态。
4. 在生产服务中让原 graph replay 先运行，随后同步并用同一 FlagGems kernel eager 重算；前 128
   个 decode step、8 个 TP rank、72 个 cache group 的 slot mapping 逐元素差异均为 0，
   `num_computed_tokens` 差异也为 0。kernel 数值与捕获地址不是根因。
5. 只在 graph replay 返回后增加设备完成点，不再 eager 重算，9 个样本恢复为合理回答/长推理；
   将同一逻辑写入 Plugin 源码、移除所有诊断 import hook 后，9/9 再次完成，无短 token 乱码退出。
6. 同一当前流上图 A 生成 slot mapping、图 B 立即消费的 200 轮最小复现全部正确。因此不能把结论
   扩大为“PPU 所有图之间都不保序”；触发条件是实际模型执行中 common-slot 独立图与后续
   attention/model/collective 路径的完成可见性边界。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 模型执行模式 | 原 `FULL_AND_PIECEWISE` | `--enforce-eager` | `04-runs/accuracy-diagnosis-eager-replay-20260914/` | 代表样本由乱码/提前退出恢复为 6 stop + 3 length | graph 是必要变量 |
| 2 | common-slot 执行 | 整模型 graph | 仅 common-slot eager | `04-runs/accuracy-diagnosis-fullpiecewise-common-slot-eager-20260914/` | 6 stop + 3 length，服务健康 | 故障边界缩到 common-slot graph wrapper |
| 3 | graph 结果数值 | graph replay | 同步后 eager 重算逐元素对照 | `04-runs/accuracy-diagnosis-common-slot-graph-vs-eager-20260914/` | 128 step、72 group、8 rank 均 0 diff | 排除 kernel 数值、地址和 capture key 作为直接根因 |
| 4 | replay 完成点 | common-slot graph 无同步 | replay 后仅增加设备同步 | `04-runs/accuracy-diagnosis-common-slot-graph-sync-20260914/` | 6 stop + 3 length，无 eager 重算 | 缺失完成可见性是必要变量 |
| 5 | 实现载体 | `sitecustomize` 诊断 hook | Plugin 源码候选修复，无 hook | `04-runs/accuracy-diagnosis-source-fix-common-slot-sync-20260914/` | 7 stop + 2 length，无异常短输出，health 200 | 源码修复方向复验通过 |
| 6 | 同步范围 | T-Head replay 后 `device.synchronize()` | `current_stream().synchronize()`，其余源码和服务参数不变 | `04-runs/accuracy-diagnosis-current-stream-sync-20260914/` | 代表 9 题全部 HTTP 成功，7 stop + 2 length；没有异常短输出，服务健康 | 当前流同步足以保证 common-slot metadata 可见性，且避免显式等待无关 copy stream |
| 7 | 正式长负载 | 设备级同步候选 | full198/c64/60K | `04-runs/accuracy-diagnosis-source-fix-common-slot-sync-20260914/` | 最终保留 198 分母，但 110 条 timeout；严格 83/198。PG2 `_ALLGATHER_BASE` SeqNum 101524 超时，rank 1–7 已进入，rank 0 未进入 | 设备级同步没有解决独立 TP timeout；只凭该轮不能证明它导致 rank 分叉 |
| 8 | 正式长负载 | 设备级同步 | 当前流同步，其他参数不变 | `04-runs/accuracy-diagnosis-current-stream-flightrecorder-20260914/` | 198/198，99 timeout，strict 95/198（47.98%）；PG2 `_ALLGATHER_BASE` SeqNum 85169 仍为 rank 1–7 进入、rank 0 缺席 | 缩小同步范围没有消除超时；同步范围不是该 rank 分叉的根因 |

采样温度为 1，因此不同轮的具体 token 数和 stop/length 个数允许波动；判据是是否重新出现
12–254 token 的乱码/空正文提前结束，以及 reasoning 是否保持语义连续。

## 根因

- 已验证根因：T-Head PPU 上 `CommonSlotMappingGraphRunner` 的独立 graph replay 返回后，生产模型
  路径没有建立一个能覆盖后续 attention/model/collective 消费者的完成可见性点。下游可能读取
  尚未完成更新的 slot mapping / computed-token metadata，使复用请求槽关联到错误 GDN/Mamba
  状态，随后产生乱码、重复推理、提前 EOS 或无界推理。
- FlagGems `compute_common_slot_mapping` 的最终数值正确；问题位于 Plugin 的 graph 生命周期边界，
  不属于 Qwen 模型语义或 `topk` 算子。
- 简单双图同流复现未失败，说明底层更精确的厂商 runtime 条件仍涉及实际模型中的流/collective
  组合；当前修复只对已验证的 T-Head common-slot replay 边界增加完成点。

## 解决方法或 Workaround

- 在 `vllm_fl/worker/common_slot_mapping.py` 增加通用 replay helper：先 `graph.replay()`，仅当
  `current_platform.device_name == "thead"` 时同步当前执行流；其他平台保留原异步行为。
- 不含模型名、服务名或权重路径判断，不改变 dispatch 和 FlagGems kernel，也不修改 vLLM。
- 增加守卫两侧测试：T-Head 调用当前流同步，非 T-Head 不调用；原 PPU 变输入 capture/replay数值测试
  继续通过。定向结果为 4 passed。
- 当前 Plugin 工作树有且仅有两处候选修改：
  `vllm_fl/worker/common_slot_mapping.py` 与
  `tests/qwen3_8_flash_next/test_common_slot_mapping_graph.py`。未提交 diff SHA-256 为
  `86fab0c11bac4dba8ab414e8bef55e3a9923b54c0c3c920552af51687530d7e7`。
- 当前候选由 Plugin base、两文件 diff SHA-256 和远端运行目录绑定；正在进行的 no-async 长稳态
  对照及进程身份记录在问题 011。容器未停止、重启或删除。
- 同步是正确性修复候选；正式 full198 和性能回归完成前不宣称最终验收通过。若厂商 runtime 后续
  提供可靠的跨流 event 依赖，可将设备完成点替换为更细粒度等待。

## FlagGems 证据

- FlagGems 保持 clean `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`，本问题未修改算子。
- eager 与 graph 在同步后 72 个 cache group 的输出逐元素一致，证明无需把同步策略放进
  FlagGems 数值 kernel。
- 最小复现：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/07-bugs/common-slot-graph-ordering-20260914/graph_to_graph_ordering.py`，
  SHA-256 `c7f8810395cb1acd4646e4e17d8b5207aff45f89864011cf1d2176798e2136d0`；200/200 同流双图通过的
  receipt SHA-256 为 `19e65b7c07b03c72928d1ccd20c7dce3d25bd49a8b43d7b7e6621def133da8f7`。

## 验证结果

- 纯 eager 对照：6 stop + 3 length；JSONL SHA-256
  `e7d9bfb835e3d1b4226e55178c717fe9a97561aa68c012f75ac9c25712515c1e`。
- common-slot eager：9/9 完成，6 stop + 3 length；JSONL SHA-256
  `d31acc2c476e1dced4152c53eabdec1f7a64a08ebac073ae2942d092349fcd77`。
- graph-vs-eager 元数据：0 diff；256-token JSONL SHA-256
  `2ce79573e4083290568675f15cbe6fc2861fee9f2e3dfef5ed519949762d1899`。
- sync-only：9/9 完成，6 stop + 3 length；JSONL SHA-256
  `0b8b825209d2d47eb84d7438e61a28c9736da685b4706b09d435863b7673f082`。
- Plugin 源码候选修复：9/9 完成，7 stop + 2 length，无异常短输出；JSONL SHA-256
  `3f00be4bd0972c6edc2385c4fabd3be2042d0ffad80d89ee5ca7164d64582fdf`；服务日志 SHA-256
  `bc66ca6766434b66a414fa30e90d952df35b8c79525a85ff4d8ac230404c7f30`。
- 设备级同步 full198：198 个结果中 110 个 timeout，strict 83/198（41.92%）；PG2
  `_ALLGATHER_BASE` 输入 993280、输出 7946240，分别精确对应 batch 32 × 本地词表 31040 与
  batch 32 × 全词表 248320。rank 1–7 进入 SeqNum 101524，rank 0 未进入。
- 当前流同步代表 9 题：9/9 HTTP 成功，7 stop + 2 length，无异常短输出。正式运行
  `gpqa-full-c64-maxgen60000-currentstream-86fab0c-20260914` 覆盖 198/198，但因 99 timeout 得到
  strict 95/198（47.98%），未通过 88% 门槛。该结果不否定 common-slot metadata 可见性修复，
  但证明同步 helper 不是长稳态 TP 超时的修复。

## 限制与下一步

- 将 common-slot 输出污染和长稳态 TP timeout 分开验收；后者转到 011 继续定位，不能再通过调整
  common-slot 同步范围解释。
- 在同配置下记录同步前后的吞吐与时延，确认每 decode step 设备同步的性能成本；若成本不可接受，
  再以厂商 event/wait 能力替换粗粒度同步。
- 完成目标 Plugin base/HEAD/diff 与共享 graph 调用方影响审查后，才提交和推送候选修复。

## 经验沉淀

- 是否可跨模型或平台复用：诊断方法适用于所有“graph 服务健康但有状态模型在槽位复用后输出
  损坏”的场景；修复本身目前只在 T-Head PPU 的 common-slot 路径验证。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：独立 metadata graph replay 与有状态模型消费者之间的完成可见性诊断。
