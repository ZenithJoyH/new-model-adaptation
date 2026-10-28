# 006：精度负载下 GDN 索引 JIT 非法显存访问

## 元数据

- 状态：`hypothesis`；首次出现及最后只读验证：2026-10-01。
- 模型：MiniCPM-V-4.7-1B；平台/Host：T-Head PPU、`PPU-13`；容器：`minicpmV4.7-1B`。
- Plugin HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`；FlagGems checkout `80d0000d93dad55320df06687eb088a5b6dad07d`，运行包先前记录为 5.3.5；vLLM 运行日志为 0.24.0。此次只读诊断未修改产品源码、权重或容器。
- 当时脚本 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/start-model.sh` SHA-256 `0bb6618fa01fe65536fea9c407dca9c92b85d737325d6fb62af069ee418c0f12`：PPU2、`0.0.0.0:8000`、TP1/BF16、默认最大上下文 262144、前缀缓存开启、`FULL_AND_PIECEWISE`、`VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy`。脚本由用户在上次验证后修改，本次未运行该脚本。

## 问题现象与证据

原始日志为 Host 工作根 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/service.log`，容器路径相同，2026-10-01 只读 SHA-256 `de10cd90eeaa224b1a570fe56057cc64eb36bfb04b41b9079c4ded1c519a99cf`。API PID `297698` 于 13:23:03 启动，EngineCore PID `298178`；约 14:47 开始记录高并发请求。16:45:14 仍有 32 个运行请求、0 等待，生成吞吐约 1907 tokens/s、KV 缓存使用 3.3%。

16:45:22 的**首个设备故障**是 PPU 驱动 `Exception invalid page`，指令落在 `_index_jit_function` 的 `vmem.st.b32x4` 显存写入（日志约 870–911 行）。其后 EngineCore 才打印调度输入并报 `torch.AcceleratorError: CUDA error: an illegal memory access was encountered`，接着 API 多个请求返回 HTTP 500、EngineCore/API 退出。此顺序排除了把 HTTP 500 或 `EngineDeadError` 当作首因。

故障调度快照有 32 个运行请求、0 等待、KV 使用率 3.54%；其中一个新请求 prompt 1242 tokens、`max_tokens=28000`，另有 31 个缓存中的解码请求，最长输出已达 27850 tokens。该请求上限与先前冻结的 GPQA 配置 `max_gen_toks=2048` 不同，本次未核对用户评测完整配置，不沿用旧回执。故障发生在 mixed prefill/decode 与长输出并发负载，尚不证明任何单一参数导致错误。未见 OOM，故障后 PPU2 空闲 `1/98304 MiB`，服务端口不再监听。未停止、重启或移除适配容器；未自行重启模型服务或评测。

## 已有经验匹配与代码定位

- [003](003-gdn-full-graph.md) 同为 GDN 与混合图，但其签名是 `FULL` 降级为 PIECEWISE，未包含运行期 invalid page，不能直接套用其结论。
- [分布式 sample_tokens 超时](../../../../../../docs/troubleshooting/distributed-sample-tokens-timeout.md) 要求首故障为 TP rank `sample_tokens` 超时、序列分叉、RPC timeout；本次 TP1 且首故障为设备非法页，故不适用超时缓解。
- vLLM 的 GDN `_forward_core` 在 `initial_state = ssm_state[prefill_state_indices]` 后执行 `initial_state[~prefill_has_initial_state, ...] = 0`。Python 报错栈显示后者经 FlagGems `index_put_ → nonzero → copy_`；但 CUDA/PPU 错误可能异步报告，不应据此断言 `copy_` 是原始写坏位置。
- 当前 FlagGems 安装包的 `ops/index.py` 使用 `_index_jit_function` 实现 `aten.index.Tensor`，其生成代码含 `tl.store(out_ptr + out_offset, ...)`；设备 PC 的函数名和 store 指令与此实现吻合。`ops/index_put.py`、`ops/nonzero.py` 也处于故障堆栈。尚未取得该次 `ssm_state`、`prefill_state_indices` 的实际张量值/shape 或最小复现，无法区分索引越界、JIT mask/shape 缺陷、graph replay 地址问题和更早异步内存破坏。
- Plugin 把 `VLLM_FL_FLAGOS_BLACKLIST` 传给 `flag_gems.enable(unused=...)`。本次值仅为 `nonzero_numpy`；FlagGems 注册表把 `nonzero`、`nonzero_numpy`、`index.Tensor` 分别列为不同项，因此这个设置不屏蔽故障函数 `index` 或堆栈中的普通 `nonzero`。vLLM 对该变量发出 `Unknown vLLM environment variable` 提示，但 Plugin 源码会读取它；不能仅凭该提示说变量完全无效。

## 诊断结论与下一步

已验证的直接原因是**PPU 上发生非法页/非法显存写入，导致 EngineCore 崩溃，API 随之失败**。目前最强定位是 FlagGems `index` JIT 在 GDN mixed prefill/decode 步骤中的写入；导致非法地址的上游条件仍为假设。32 并发、接近 28k 的输出和 mixed 图是当时条件，不是已证实的独立根因；KV 使用率很低，不能归因于 KV 缓存耗尽。此前文本/图片各一次的启动检查只覆盖低负载，不能证明长时高并发稳定。

2026-10-01 后续诊断：在已核对 Host/容器同路径映射的工作根新增 `07-bugs/gdn-index-invalid-page/repro.py`，SHA-256 `663f31b96218110d6b26efb0f24866d907e2c44f9bc870faa542bda2a5e9c783`。仅在空闲 PPU2 上运行 BF16 连续状态 `[64,16,128,128]` 与单个 int64 索引的受限对照；原生/FlagGems 各自 eager 100 次、CUDA graph replay 100 次，逐次同步和校验，四组均通过。原始输出在 `04-runs/gdn-index-repro-20261001/{native-eager,flaggems-eager,native-graph,flaggems-graph}.log`。这**未**复现故障，不能排除真实 GDN 形状/索引、mixed 调度、graph 内存生命周期或更早异步写入。未启动完整精度评测、模型服务，未修改产品源码或容器。当前用户再次修改的启动脚本 SHA-256 为 `79b9a5ff47deff6127c37cc88513e7aea205aa779631f9d2b5a485e7ecc3b255`，其 blacklist 已与故障时配置不同；复现时应以原始故障配置为准，并避免覆盖原始 `service.log`。

已向 FlagGems 提交 [issue #6846](https://github.com/flagos-ai/FlagGems/issues/6846)，包含脱敏环境、故障先后顺序、32 并发长解码与新 prefill 条件、独立标准库负载脚本，以及小型算子对照未复现的限制。公开脚本是待验证的端到端复现流程，不应记作确定性复现。下一步若需定位，可先获得真实 GDN 状态形状和索引，再在独立服务中一次只改一个变量（如仅排除 `index`）重放受限 mixed 负载；核对原生索引的数值后再扩大。必要时用 `CUDA_LAUNCH_BLOCKING=1` 定位异步报错。不能把 blacklist、降并发或改图模式称为已验证修复；不要直接重跑完整精度并覆盖既有样本。

知识库处理状态：`needs-validation`，暂无可推广的跨模型修复结论。
