# Qwen3.8-Flash-Next PPU 适配总结

> 当前状态：验收进行中。只有下列待完成项全部通过后才改为 complete。

## 范围与环境

- 模型：`/mnt/cpfs/models/Qwen3.8-Flash-Next`，配置 SHA256 `889658f2508e8c61d409b02e70e0d78d8d4452ec65aaafbe129805d213d2e74b`，BF16 文本路径。
- 平台与主机：PPU，`PPU-01`，8× PPU-ZW810E（卡 8–15）；卡 0–7 属于其他任务，未操作。
- 适配容器：`qwen3.8-flash`；基础镜像 `glm5.3-flash-ppu13-snapshot:20260904-215131@sha256:7755ef5656bd33703eb7c3c81fb6b2099b154284ba582488861f5ec99e3f7b30`。适配容器从未停止、重启或移除。
- vLLM：`0.24.0+empty`，`/workspace/vllm` revision `ee0da84ab9e04ac7610e28580af62c365e898389`；所有记录点均保持干净，未修改。
- 插件：最终集成工作树为 `/mnt/nfs/users/jinghao/qwen38-adaptation-20260904/01-repos/vllm-plugin-FL-qwen38-integration`；`support-qwen3.8-flash` 已推送并回读确认 revision `a5c6f0ca373afa606b68d2daa4bb4a9dcc1833c5`。旧 `/workspace/vllm-plugin-FL-qwen38-adaptation` 不作为最终 clean 证据。
- FlagGems：`/workspace/FlagGems` master 于 2026-09-07 再次按 fast-forward-only 从 clean `34bd6d68928c8b0039c42987840929da52aa6a62` 更新到 clean `dcd0cfeae8187dee691656c0616c1ed95899c2ae`。同步后的 slice、depthwise conv 和 index 路径仍需现场回退，均已在该 revision 重验。

## 架构和实现范围

架构分析覆盖 48 层 `[GDN,GDN,GDN,QSA]×12`、512 专家 top-10 MoE、PLE n-gram、QSA 稀疏分页缓存、GDN 状态和通信路径。插件分支提供 Qwen4Exp 注册、权重装载、QSA 六个插件 Triton 算子、PLE gather/scatter、packed GDN 和 common-slot mapping；这些模型专用 ABI 在同步后的 FlagGems 中没有兼容实现。其来源、约束、eager/graph 测试见 `environment/flaggems-operator-evidence.md`。

当前验收范围是 `--language-model-only` 的 BF16 文本推理；视觉、MTP、量化、EP 和 PP 没有纳入本轮验收，不能从文本结果推断支持。

## 运行配置

- TP=8、PP=1，`CUDA_VISIBLE_DEVICES=8,9,10,11,12,13,14,15`。
- 最终冒烟使用 `--max-model-len 65536`；模型配置支持 262144，没有因错误降低长度。
- `--max-num-seqs 32 --max-num-batched-tokens 4096 --gpu-memory-utilization 0.90 --disable-custom-all-reduce`。
- eager：`--enforce-eager`，`cudagraph_mode=NONE`。
- graph：mode 0，`cudagraph_mode=FULL_DECODE_ONLY`，捕获批大小 1/2/4/8/16/32；之后的 sanity、精度、性能和通信均使用该 graph 配置。
- TP RPC：`VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=1800`。默认300秒在正式并发下不足；该环境变量同时覆盖 `execute_model` 与 `sample_tokens` 的 TP RPC 等待。

## 已解决问题

|问题|根因|最终方案|证据|
|---|---|---|---|
|首次请求在调度元数据处 HTTP 500|FlagGems `slice` 明确拒绝 `torch.bool`；`discard_request_mask.copy_to_gpu` 需要布尔切片|插件 `thead.yaml` 精确排除 `slice`，恢复原生 view 语义|容器 `/bug/flaggems-slice-bool-20260904`；`failure-eager-baseline1-slice.json`、`slice-workaround-evidence.txt`|
|8 并发长输入时申请 7.79 GiB 并 OOM|PLE 深度卷积 `[7,10240,3644]` 每组输入通道为 1；FlagGems conv2d 为 Triton dot 将其逐组填充至 16，临时输入从 522,403,840 B 膨胀到 8,358,461,440 B|精确排除 `conv1d` 与真正的下层入口 `_conv_depthwise2d`，使用平台原生卷积；未降低上下文或并发|容器 `/bug/flaggems-depthwise-conv-padding-20260904`；`inspect_sanity_failure.json`、`inspect_nested_conv.json`、`conv-workaround-evidence.txt`|
|正式 GPQA 混合调度在生成计数17237处停滞并退出|vLLM TP8 `sample_tokens` RPC 超过默认300秒；各 rank 随后通信 work 序号分叉|保持全部服务参数，仅显式设置 `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=1800`；32并发混合预填充/解码压力40/40成功并严格生成22000 tokens|`accuracy-crash-evidence.json`、`execute-model-timeout-source.json`、`timeout1800-stress-progress.json`|
|延长超时后的正式评测首批32请求触发 `sqlite3.OperationalError: database is locked`|FlagGems `index` 在多个TP rank首次 autotune时共享SQLite benchmark数据库，提交路径只处理 `IntegrityError`，未处理数据库锁；生产形状为BF16 `[9,551,10240]` 和两组int64索引|插件精确排除 `index`，走原生索引；生产形状 eager、float32及graph变输入重放均通过；修复后32并发压力32/32成功|容器 `/bug/flaggems-index-autotune-sqlite-lock-20260906`；`timeout1800-autotune-failure.json`、`index-postfix-regression.txt`、`index-stress-progress.json`|

最终不覆盖 tracked `thead.yaml`；运行时通过 `VLLM_FL_FLAGOS_BLACKLIST_APPEND` 追加 `slice`、
`conv1d`、`_conv_depthwise2d`、`index`。三类算子测试覆盖 eager、graph capture/replay、变更输入、
布尔长度、深度卷积 decode/长 prefill、独立 FP32 参考、额外显存上限，以及 index 的生产
BF16/int64 形状。同步 FlagGems 和集成 HY4 后完整 Qwen 与 dispatch 回归为 410 passed、12 warnings，
证据位于 `05-runs/plugin-regression-dcd0cfe-20260907-1714/pytest.log`。

## 验收状态

- 执行模式：最终 revision 以 TP8、FULL_DECODE_ONLY、`max-model-len=65536` 在连续卡 8–15 启动；确定性请求返回 `2`、HTTP 200，响应后 health 仍为 200。证据位于 `05-runs/full-model-smoke-dcd0cfe-20260907-1740/`。
- 8 并发 sanity：最终 graph 配置固定用例8/8正确，3794输入/20输出tokens，总耗时96.477秒，峰值显存91941MiB，观测PPU利用率峰值100%，零错误/OOM/超时。
- 正式精度：历史完整 198 道 GPQA 最终 strict 166/198，另有 22 题达到生成上限；这些结果产生于旧 revision。提高 `max-model-len` 和 `max_new_tokens` 的诊断不能替代在最终 `a5c6f0c` + `dcd0cfe` 组合上的正式重跑，因此当前精度状态仍为 failed/pending rerun。
- 正式性能：未启动；必须等待完整精度满足标准后运行模型专用 `vllm_perf_qwen38.py`。
- 通信：未启动；PPU 专用 graph all-reduce wrapper 已准备，公共 `test/nccl_test` 仅有 MThreads 脚本，不会错用。

## 服务生命周期

只停止或清理过本任务的API与worker以切换模式或恢复运行时错误；每次均从本任务日志和进程树精确解析PID并验证退出。首次正式精度失败后仅清理了遗留的TP worker 350418–350425。未影响卡0–7、其他容器或无关服务；适配容器始终运行。

## 待完成

1. 在最终 Plugin/FlagGems revision 上重跑正式 GPQA，并执行 strict ≥90%、零超时、零错误和样本完整门禁。
2. 精度通过后运行正式性能与 PPU TP8 通信验证。
3. 补全正式 receipt 与指标，完成复盘；当前不得标记 optimized 或 complete。
