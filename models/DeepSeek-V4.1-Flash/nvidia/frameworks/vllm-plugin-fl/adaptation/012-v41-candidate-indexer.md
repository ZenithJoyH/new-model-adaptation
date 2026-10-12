# 012：锁定版稀疏索引器缺少 V4.1 压缩比与候选块协议

- 状态：`verified`（候选块算子、定向 CUDA 回归及修正 Q 语义后的 17K eager 整模通过；graph 待另验）
- 首次出现：2026-09-23；最后验证：2026-09-24
- Host / 容器：`H100-149` / `deepseek-v41-plugin-adapt-20260923`
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、eager、前缀缓存启用、`max_model_len=2048`

第六轮整模启动越过 MoE 构造后，8 个 worker 在
`SparseAttnIndexer.__init__()` 报 `unexpected keyword argument 'compress_ratio'`。
原始日志为 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`
中 20:04:12 的 traceback，尚未进入权重加载。

锁定版 CUDA indexer 没有 V4.1 的 `compress_ratio`、`candidate_blocks`、
`candidate_block_size`、`candidate_write` 参数；压缩长度已由 Plugin indexer
在构造时除以比例，并由缓存 metadata 提供给旧 CUDA op。模型配置的候选筛选
为 2048 块、每块 8 个压缩位置，合计覆盖 16384 位置。当前诊断限定最大
2048 token，所有可见压缩位置都落在候选预算内，因此候选筛选对 top-k 无影响。
Plugin 现在仅在这个有数学等价保证的范围使用无候选过滤的 indexer；超过预算或
候选块大小无效时显式报错，不静默退化。第七轮 TP8 复试越过参数检查后，
发现锁定版 CUDA indexer 强制依赖缺失的 DeepGEMM；后续处理见问题 013。

H100-149 上已按原生 V4.1 的块分数、最新块固定入选和候选掩码协议制作
Plugin 集成补丁，但当前整模服务尚在复试，未应用到运行中的 Plugin。
一份独立算子原型与测试保留在
`/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-candidate-20260923/`。
2 行边界/填充数值测试、32K 压缩位置宽度的 2048 块选择与掩码、
掩码后 FlagGems-vllm top-k 仅选入保留位置，以及 CUDA graph 捕获/重放
均通过；`integration.patch` 的 `git apply --check`
也通过。上述证据只验证候选算子及补丁可应用，不等于整模长上下文通过。
后续 SWA Q 量化修复改变了 `attention.py` 上下文，原 `integration.patch`
不再直接应用；2026-09-24 在已核对的 `attention.py` SHA-256
`9da289ab77886ad8713af403d2c15e3e79dad6a40751eac3cda4e97e832ce889`
上重排为 `02-issues/h100149-candidate-20260923/integration-rebased.patch`
（SHA-256 `a2a3f7522e25dbd2198407433999dc2152f927e2258db04f3a3129acccd33424`）。
`git apply --check` 对完整补丁通过；full-graph 诊断服务仍在运行，未修改产品源码。
此后图捕获修复又改变了索引器调用处，见[问题 026](026-v41-paged-indexer-full-graph-capture.md)。
已在该修复后的索引器 SHA-256
`e3377625c4f385e8e1dadd25bd8777e603d7de13889512bd0e409ef0fe807c02`
上再次重排为同目录的 `integration-graphsafe-rebased.patch`（SHA-256
`aee4b5f640fb8ad68141ee43ce5150a52e5d5d58823d85659252e6b27266971c`）；
完整补丁通过 `git apply --check --whitespace=error`。第二十四轮整模图服务
结束后，在无运行服务、8 张 GPU 均释放的状态下应用该补丁及
`candidate-test.patch`，未修改锁定版 vLLM 或 FlagGems 库。应用后
`attention.py`、`nvidia/indexer.py`、新增 `nvidia/candidate_blocks.py`
SHA-256 依次为 `76766ae612c184f09baf471890f7395ece6e2700a85b3712c3994b69939167d6`、
`97b01d56232f43f3e59201e509483215ef0fdf665f148ece5e762b51b8354840`、
`0d53e4e6a60a37995713bf792089d645b07db1af3e55e36dcc49542705a5db9c`。
Plugin 测试 `tests/models/deepseek_v4_1/test_candidate_blocks.py`
的数值边界、32K 宽度及变输入图重放 3 个测试通过；分页 MQA 测试 1 个亦通过。
本轮 18K eager 服务使用
`01-environment/h100149-plugin-20260923/start-candidate-eager.sh`
（SHA-256 `4538bee5c1795255bb93ce917393ca7b553e296f26713437258bd19171b40d0c`），
日志为 `04-runs/h100149-candidate-eager-20260924/service.log`。

首次真实长请求使用 `"测试。" × 8500` 加末尾算术问题，模型服务处理了
17015 个 prompt token，HTTP 成功且无算子异常，但生成的 16 token 全是
`测试。`，以 `length` 结束，未答对。原始回执为同一 run 目录的
`long-context-smoke-v2.json`。控制实验只把重复次数改为 7500，prompt 为
15015 token、低于 16384 候选覆盖预算；它同样输出 16 token 的
`测试。` 并以 `length` 结束，回执 `short-control-smoke.json`。两次仅改变
提示长度，低于阈值也复现相同退化，所以不能把该症状独立归因于候选掩码；
也不能因此认定 >16K 的语义正确性通过。随后换成多样记录、普通词语及数字
填充；长请求仍失败，而且约 190-token prompt 已复现错误，远低于候选预算。
因此当前整模语义阻断另记为[问题 028](028-v41-short-context-semantic-regression.md)，
不能将长请求退化归因于候选块掩码。18K eager 服务已结束，512-token 全覆盖
索引对照正在加载权重；候选块的 >16K 真实语义验证仍未完成。

2026-09-24 再次检索 `FlagGems-vllm/src/flaggems_vllm` 和
`FlagGems/src/flag_gems` 的候选块相关符号，未找到对应的 H100 候选块索引
实现；Plugin 的新 Triton 实现只负责块分数、固定最新块、候选标记和掩码，
仍调用 FlagGems-vllm 的现有 logits/top-k。短上下文诊断 workaround 已由
实现替代，但还不能认定长上下文整模可用；退出条件是 Plugin indexer
在 `max_model_len > 16384` 的实际配置下通过数值、真实请求和 graph 回归。

变更前 `attention.py` SHA-256
`c6ba3566c77811098583920b2a1fb883502ffcdffd138712b4e79b9000c0a06b`；
补丁在远端 `02-issues/h100145-ring-20260923/v41-indexer-bounded-h100149.patch`，
`git apply --check` 通过。vLLM 未修改；在该轮补丁时，整模长上下文、图与精度仍待验证。
知识库处理状态：`needs-validation`。

2026-09-24 的受控后续：问题 028 已证明旧 FlagGems-vllm V4 融合算子对
V4.1 Q 多做 RMSNorm，并在 Plugin H100/FP8 SWA 路径修正。
`01-environment/h100149-plugin-20260923/start-skip-qnorm-18k.sh`
（SHA-256 `f10b83e63f2b18679f28d91ceb4ffd42fd3c42892aaee12f9da4908e0e29a948`）
以 TP8 eager、FP8 KV、前缀缓存启用、`max_model_len=18000`、
`max_num_batched_tokens=512` 启动。四个旧错误提示及四个 1024/1800-token
提示均严格返回 `2`；保留原多样记录生成逻辑的 17,037-prompt-token
请求也返回 `2` 且 `finish_reason=stop`，原始回执为
`04-runs/h100149-plugin-skip-qnorm-18k-20260924/long-varied-smoke.json`
（SHA-256 `7e4a0321b67a0b171b5fec0fcc5ad0bdf81bd371016ccc4782e41cf3c20f3744`）。
该请求超过 16,384-token 候选覆盖预算，证明当前 Plugin 候选路径在这一个
真实长提示上可工作；不证明任意长上下文、图模式或正式精度。服务 PID
`96049` 在九份回执核对后停止，8 卡显存归零，容器保持运行。旧的
`测试。` 重复提示即使低于预算也失败，现由问题 028 的 Q 语义差异解释；
此前不能据其失败否定候选块算子。当前 full graph 复试已另起服务，待记录。
