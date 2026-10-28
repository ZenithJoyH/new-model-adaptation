# 009：GPQA 全量评测后半段输出乱码

## 元数据

- 状态：`hypothesis`；分析、独立算子对照及新黑名单全量复测日期：
  2026-10-02–03。
- 模型/Host/容器：MiniCPM-V-4.7-35B-A3B、`PPU-13`、
  `minicpmV4.7-35B`；TP2，PPU 0、1，`FULL_AND_PIECEWISE` 七种捕获尺寸，
  前缀缓存开启。
- 当前根级启动脚本：`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh`，
  SHA-256 `36a661b067a072e8d3f7d0689fc05f8e7b2cf0c156ce15db8d61d376f6621e01`。
  用户在先前 SHA-256
  `62d97f6ec4b9be9bcd7ebefbaa37aa08b6685fabac9b683ba859be3f422806b7`
  版本的黑名单后增加 `copy_`、`_index_put_impl_` 并重启服务。
- 用户提供的原始文件：`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/gpqa_cpm35B_ptg.jsonl`，
  SHA-256 `136303924883ae3e3be7db6bfa84fe9773b785b698be262dfeb33d3c0096db3b`，
  文件修改时间 2026-10-02 23:22:50 +08:00。未取得该文件的独立运行配置、
  进程日志及采样时间线，因此不能仅凭复制时间将具体请求绑定到服务日志行。

## 问题现象与证据

用户文件有 GPQA Diamond 198 个唯一题号、396 行（严格与宽松各 198），
题目、prompt、target 哈希逐题与 NV 参考及先前 PPU 32 并发全量结果一致。
严格匹配 88/198（44.44%）、宽松匹配 79/198；0 timeout，但严格提取中
85 题为 `[invalid]`。按两份旧参考文件可重建的宽松答案提取式重新计分仍为
88/198，未改变一题的正确性，因此本次下降不能靠改答案提取规则解释。

样本 0–96：严格正确 76/97、无无效提取、97 题均有 `</think>`。
样本 97–197：严格正确 12/101、85 题无效，仅 16 题含 `</think>`；
15 题用满 `max_gen_toks=18000`。首个异常题 97 的原始回复从 `First` 后即出现
阿拉伯字母、汉字和重复英文碎片，题 98、99、101 等同样从开头乱码并提前结束；
这些不是正常答案格式差异。85 个无效样本中位完成 token 数为 287，
其中 15 个达到 18000。该文件第 0 与 97 题记录的生成参数一致。

先前同一 PPU 服务的 32 并发全量结果为 146/198（严格），后 101 题
73/101、5 题无效、1 题达到 18000。NV 参考严格 152/198，后 101 题
75/101、0 无效。对照文件分别为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/04-runs/MiniCPM-V-4.7-35B-A3B/gpqa-32c-restarted-20261002-1820/gpqa_diamond_generative_cot/attempt-1/MiniCPM-V-4.7-35B-A3B/samples_gpqa_diamond_generative_cot_2026-10-02T10-42-23.695288.jsonl`
和 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/gpqa_cpm-35B_nv.jsonl`。

首次只读分析时根级 `service.log` SHA-256
`dddba60d87e8e86d0579b7877328e30a4745a0282497a8fcb019d7ce8e48410b`，
最后修改于 21:39:18；该日志没有 Python 异常、非法访存或 RPC timeout，
HTTP 请求仍返回 200，服务 `/health` 仍为 200。后续诊断向同一日志追加了记录；
2026-10-03 00:14:32 的 SHA-256 为
`4e0359ec5f2b52242773e3bef1932b0aed37fb57d7b6d0e51c558118414ca098`。

关键补充：宿主机内核日志 `journalctl -k --since '2026-10-02 21:33:09'
--until '2026-10-02 21:33:11'` 在用户低分运行中记录两张卡同时发生
`Xid 1155 / L1 Invalid page`：PPU0 地址 `0xa467f6000`、PID `1718880`，
PPU1 地址 `0xa467f8000`、PID `1718881`。`ps` 与 `docker top` 将它们明确映射
到当前 35B 容器的 `VLLM::Worker_TP0/TP1`，不是同 Host 的 1B 服务。
服务日志此轮 21:28:34–21:39:14 共完成 198 次 HTTP 200 响应、最高
`Running: 32`；内核事件发生于 21:33:10。按日志行累计，21:28:34 前有
598 次，21:33:04 前有 758 次，21:33:14 前有 763 次，21:39:14 前有
796 次。因此 Xid 出现在本轮约第 160–165 次完成响应之间，之后至多
还有 38 次响应。该轮 85 题无效，即使这 38 次全部无效，仍至少有 47 题
在 Xid 前已经返回无效答案。这个计数以此时间窗口的 198 次 POST 均属于
用户提供的同轮结果为前提；计数吻合，原始样本却无请求 ID/时间戳可逐题
交叉验证。**Xid 不能作为首次乱码的起点**，可能是更早错误的后续表现，
也可能是独立的同时事件；现有证据无法判别。

## 已有经验与假设

- [007：GPQA 解码口径差异](007-gpqa-decoding-mismatch.md)：以前的 7 题差异可由
  提取式解释；本次旧式重算仍为 88，故不是同一故障。
- [008：GDN 非法页](008-gdn-index-invalid-page.md)：同模型/设备/图模式，
  但先前崩溃为 `Xid 896 / Shader invalid page`，Python 明确报
  `_index_jit_function` 非法访存并导致 EngineCore 退出；本轮为
  `Xid 1155 / L1 Invalid page`，无 Python 异常且服务继续 200。两者都涉及
  设备页故障，但签名不同，不可把先前定位直接套用到本轮。
- 本次有客观的设备页故障，低分不是评测提取式或普通单题模型能力下降。
  长负载下内存访问/状态污染是最强候选机制；具体首错算子、是否图 replay、
  缓存或 FlagGems 内核触发仍未验证。
- 当前黑名单按 FlagGems 注册函数名精确过滤；现有值包含 `copy`、
  `index_put_`，但注册表与当前 Worker `/tmp/flaggems_enable_oplist.txt`
  仍可见 `copy_`、`_index_put_impl_` 路径。黑名单没有覆盖这两个不同函数名；
  这说明现有配置不能证明所有相关索引/复制路径均已退回原生实现，
  但不能据此认定它们导致本次 Xid。

### 排除：GDN 状态的 32 位块偏移溢出

2026-10-03 只读核对运行中的安装包与 vLLM 源码后，发现 FlagGems
`ops/index_put.py` 生成的 `_index_put_jit_function` 使用
`cur_index * input_stride`，没有显式转换为 64 位。GDN 元数据的块索引为
`int32`，因此最初怀疑高编号块产生超过 `2^31` 个元素的偏移。

此怀疑不符合当前服务的显存上界。模型 40 层中 30 层是 GDN；TP2 时每层
SSM 状态每块为 `16 × 128 × 128` 个 FP32 元素，约 1 MiB，另有卷积状态。
仅按 PPU0/1 各约 92,026 MiB 的**全部**占用显存计算，30 层状态合计最多
约 3,000 块；实际还要扣除权重、注意力缓存和运行时，块数更小。
vLLM 的 `MambaSpec` 每块还含卷积状态和 1.49% 的页填充，因此 SSM
张量第 0 维 stride 略大于 262,144 个 FP32 元素；在约 3,000 块内最大
偏移仍远小于 `2^31`。服务日志的“5,007,595 tokens”是混合缓存的
**等效 token 容量**，不能直接除以 544 推断 GDN 独立块数；此前据此
估算超过 9,000 块是错误的。本轮没有理由用这个具体溢出机制解释乱码。
FlagGems 其他索引语义或图重放错误仍未排除。

原始样本自身的 `usage.prompt_tokens` 可校验前缀命中假设：85 个无效答案的
prompt 长度 213–540 token，中位数 331，全部短于本实例 544-token
注意力缓存块。198 题中 187 题的 prompt 也短于一块。因此这 85 个
请求在 prefill 时没有可恢复的完整前缀块，无法由“各坏题直接命中坏的
前缀状态”解释。先前长请求导致共享状态或块管理损坏的间接可能性尚未排除；
外部 GDN/align 模式问题的触发条件不能直接套用到本轮。
参考 vLLM 上游问题 [#55766](https://github.com/vllm-project/vllm/issues/55766)
和 [#56736](https://github.com/vllm-project/vllm/issues/56736)：前者需要
可复用的完整前缀块并报告 NaN logits，后者涉及推测解码和数万 token
上下文，均与本轮短 prompt、无推测解码、HTTP 200 且乱码先于 Xid
的完整签名不同。它们只提示应检查 GDN 状态管理，不作为当前根因证据。

### 进一步核对：故障签名与解码路径

宿主机 `journalctl -k` 复核故障窗口 21:30–21:36，只有 21:33:10
双卡同秒 `Xid 1155 / L1 Invalid page`，涉及当前服务 TP0/TP1；
后续到 2026-10-03 08:45 未见新 Xid。vLLM 普通 GDN decode 路径把
`non_spec_state_indices_tensor[:num_actual_tokens]` 传给卷积更新和
`fused_recurrent_gated_delta_rule_packed_decode`。但 FULL graph 构建器注明
`m.num_actual_tokens` 可含图填充 token；它将多余请求槽的状态索引填为
`NULL_BLOCK_ID`，源码实际常量是 **0**，不是 `-1`。因此仅看到这个
切片不能证明填充槽未被卷积 kernel 处理；索引 0 也不是直接越界地址。
继续核查实际 Triton 实现：`causal_conv1d_update` 在状态索引等于
`NULL_BLOCK_ID` 时提前返回；普通和 packed recurrent kernel 也在
状态索引小于等于 0 时跳过状态读写。因此“图填充槽直接向 null block 0
写入并污染后续请求”不符合这些代码路径。仍需故障时的真实块索引、
图 batch 尺寸、实际选择的分支及首个错误 kernel，才能定位其他状态污染。

## 受控尝试与当前处理

没有修改评测生成参数、服务脚本或产品代码，也没有重启服务/容器。
在原服务上以用户文件记录的请求内容和生成参数重放：

| 诊断 | 并发/样本 | 结果 | 原始证据 |
|---|---:|---|---|
| 首个异常题 97 | 1/1 | 18.22 秒，HTTP 200、答案 A、`</think>` 完整 | `04-runs/gpqa-garble-20261002/doc-97-single.json` |
| 异常区间 97–128 | 32/32 | 169.52 秒，0 API 错误、0 乱码/无答案 | `04-runs/gpqa-garble-20261002/batch32-97-128/summary.json` |
| 全题 0–197 | 32/198 | 576.69 秒，198/198 返回，0 乱码、0 新 Xid，1 题用满 18000 token 且无可提取答案；历史提取式 144/198 | `04-runs/gpqa-garble-20261002/batch32-0-197/summary.json`，SHA-256 `8c5e2dd3c2a3bd1ac12c8a37b685ae66e5756a87d59ed93f674f702215c89dc9` |

诊断脚本位于 Host/评测容器同路径
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/02-issues/gpqa-garble-20261002/`，
`replay.py` SHA-256 `549404ac3c2008bad39938bb1ec6d1405860eecba62fe729b28b2a0c46e12b25`，
`replay_batch.py` SHA-256 `ca0cc3407d3127898eb9f23814c6880fe422b7ee749cc8927954785ff825018b`。
198 题复现时间 2026-10-03 00:03:40–00:13:17；该窗口内核日志没有
`Xid / Invalid page`，服务终态 `/health` HTTP 200。诊断客户端不是
FlagEval 原生 runner，144/198 仅用于输出健康对照，不是正式精度分数。
相同 32 并发未稳定复现，暂不能用单轮比较验证任何修复。

2026-10-03 在 `PPU-13` 的空闲 PPU3 上单独运行
`07-bugs/gdn-copy-graph-20261003/repro.py`（SHA-256
`8dba15ec5032ed68cfb42fa0d8026dd20112a6312ce7bc9347c0d98ff1ac6f07`）。
Host/35B 容器工作根均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，
设备号:inode 均为 `41:14016406509`；运行前 PPU3 仅占 1 MiB，
没有已有计算进程。脚本模拟从二维块表第 0 列取得步长 512 的非连续
`int32` 索引，再拷入连续图输入缓冲区；逐次对照直接调用的 FlagGems
`copy_` 与原生 `Tensor.copy_`。对 batch 1、2、4、8、16、32、64，
每种各 100 次 eager 与 100 次 CUDA graph replay，均 0 次不一致、
0 次图捕获错误。原始结果：
`04-runs/gpqa-garble-20261002/gdn-copy-graph/result.json`，SHA-256
`c1d68ceddbbfbcc972dd62f55136e98823dbb0474f86b2fa3b3307f85fa83ecb`。
诊断后原 35B 服务 `/health` HTTP 200，诊断窗口未出现新的 Xid。
这只排除了该小规模、单算子、单设备拷贝模式的稳定差异；不证明
`copy_` 在真实混合批次和长时间服务下安全，也不支持直接改生产黑名单。

同设备另运行 `07-bugs/gdn-copy-graph-20261003/index_put.py`（SHA-256
`983be71003247976a545d6b24f5be87683d92e1489e73902480f2a34b731dc85`），
模拟 GDN SSM 张量形状 `[64,16,128,128]`、带页填充的 stride
`[272288,16384,128,1]` 和 `int32` 块索引。直接调用 FlagGems
`_index_put_impl_`，与原生 ATen 写回逐次比较；batch 1、32 各 20 次
eager 和 20 次 graph replay 均 0 不一致、0 捕获错误。结果为
`04-runs/gpqa-garble-20261002/gdn-copy-graph/index-put-result.json`，
SHA-256 `468405423029a14024c9f9d1d1aee17137ba4497ad47df4e7deba2e3010326d2`。
运行后服务 `/health` HTTP 200，诊断窗口无 Xid。此试验覆盖单层、
固定状态布局的写回，不覆盖真实服务的缓存复用、多层与混合批次，
也未重现故障；它不能证明该算子是根因或已经安全。

### 用户扩展黑名单后的两轮全量 GPQA

2026-10-03，核对 `PPU-13` 新服务 API PID `3065077` 的进程环境后，
确认完整黑名单为
`nonzero_numpy,index_put,nonzero,copy,index_put_,index,copy_,_index_put_impl_`。
在这个实例上依次以 32、64 并发运行原生 FlagEval GPQA Diamond 全量
198 题；生成参数、超时、重试、数据集与前次原生 32 并发诊断一致，
两份新配置仅改变并发、运行 ID 和隔离缓存目录。两轮配置、preflight、
原始文件路径及 SHA-256 见
[复测报告](../acceptance/gpqa-blacklist-expanded-32-64-20261003.md)。
EngineCore/TP Worker 的 `/proc` 初始环境未显示黑名单；运行期
`flaggems_enable_oplist.txt` 快照未列出两个新增算子，但不是逐 Worker
分派证明，因此新增条目在每个实际推理 Worker 的生效状态尚未严格闭环。

32 并发严格正确 142/198、11 个无效答案、2 题缺 `</think>`；
64 并发严格正确 136/198、12 个无效答案、1 题缺 `</think>`。
两轮均 198/198 返回、0 timeout、0 请求错误，服务日志实际 `Running`
峰值分别为 32、64。后 101 题的无效答案分别仅 8、5 题，
没有再现异常文件的 85 题集中失效。最终 `/health` 为 HTTP 200，
评测窗口无新 Xid，服务 PID 未改变。这是**未复现**的受控复测，
不是 `copy_` 或 `_index_put_impl_` 致因、修复或长期稳定性的证明：
旧黑名单服务此前 32 并发全量重放也曾正常，尚缺故障可稳定触发的
前后对照。64 并发原生分数低于 32 并发 6 题，仅两轮不能判断
是否为并发效应，且没有后半段状态污染的同一签名。

下一次故障需同步保存评测客户端每题开始/结束时间、请求 ID 与服务调度信息，
以及首个 Xid 前后的设备/Worker 日志；再针对完整故障签名做一个变量的
算子或 graph 对照。正式精度验收不能用 88/198 的文件标记通过。

## 限制与下一步

- 用户文件不含逐请求时间线；文件复制时间不是请求发生时间，
  因而本轮 Xid 与首次乱码只能建立同次运行关联，不能确定因果先后。
- 当前仍没有证明扩展后的 `VLLM_FL_FLAGOS_BLACKLIST` 能稳定防止本次
  无报错乱码；定位需故障首次发生时的逐请求时间线及 Worker/设备状态。
- 经验沉淀：`needs-validation`，暂不推广为跨模型方案。
