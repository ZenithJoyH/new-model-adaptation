# 027：索引器预热与 CUDA Graph 捕获走不同分支

## 元数据

- 状态：`hypothesis`（首错和路径差异已证实，整模图模式修复待复验）
- 首次出现及最后验证：2026-09-24／2026-09-28
- 模型、平台、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，NVIDIA H100，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- 镜像：`sha256:956bf9360f00d835c0b054c50ffc7f455f72972ccb7302f7c952afb3274385b7`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`
- 模式：TP8 真实权重，`cudagraph_mode=FULL`，`max_model_len=2048`，前缀缓存启用

## 问题现象与诊断

第三次 full graph 启动在 10:40:07 完成权重加载（1646.86 秒），10:44:31 进入图路径，10:45:15 的首错来自 rank 1。FlagGems `linear` 的 Triton kernel 首次编译发生在 CUDA stream capture 内，报 `operation not permitted when stream is capturing`。调用栈为 Plugin `attention.py:_wq_b_proj()` → 锁定版 `ReplicatedLinear` → `flag_gems.ops.linear` → Triton `libentry`。后续 rank 的图失效和退出异常为连带结果。原始证据：`H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-graph-full-graphsafe-retry-20260924/service.log`。此错误发生在前一问题 026 的分页 MQA 调用之前，不能据此判定该包装的整模结果。

Plugin 的短上下文捷径此前由当前请求 `max_seq_len` 和 `not torch.cuda.is_current_stream_capturing()` 决定。锁定版 runner 的图预热在非捕获流上运行，因此跳过 `wq_b` 与 FlagGems 索引器；真正捕获时则强制进入这些内核。`cudagraph_num_of_warmups=1` 无法预热未执行的分支。这是已核实的路径差异；修复后仍需整模证明没有其他首次编译。

已检索 `docs/troubleshooting/` 和相邻图问题 026；未找到与“短上下文捷径导致预热/捕获分歧、FlagGems linear 首编译在捕获内”完整签名相同的已验证知识条目。问题 026 同为 graph 捕获错误，但首错分别在 FlagGems-vllm GPU `.item()` 与 FlagGems `linear` 编译，不能直接复用其修复。

## 受控修复与证据

仅修改 Plugin。`attention.py` 现在用配置的压缩后 `max_model_len <= index_topk` 判断模型全域是否可跳过索引打分；2048/8=256，小于 top-k 512，预热和捕获均走原有全覆盖捷径。较长配置一律运行索引器，即使单次请求很短，保证预热和捕获的内核路径相同。这样保留短配置的快速路径，长配置的短请求可能增加索引器开销，待性能量化。

`nvidia/indexer.py` 的 decode 在非捕获与捕获时统一调用 Plugin 包装的 FlagGems-vllm `_mqa_logits_kernel`，避免又一次出现公开包装与私有内核的首次编译分歧。该包装已经对公开算子完成数值比较与变输入 CUDA Graph 测试，参见[问题 026](026-v41-paged-indexer-full-graph-capture.md)。FlagGems、FlagGems-vllm 和 vLLM 源码均未修改。上游公开算子提供 graph-safe 静态长度接口后，应退出私有内核包装。

准确补丁为 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-graphsafe-mqa-20260924/warmup-consistency-v2.patch`，SHA-256 `4e37e3feec7fc58401040f49e9df55af68672b53f2cff16541c42528aaa08f9e`。应用前 `attention.py` / `nvidia/indexer.py` SHA-256 分别为 `76766ae612c184f09baf471890f7395ece6e2700a85b3712c3994b69939167d6` / `97b01d56232f43f3e59201e509483215ef0fdf665f148ece5e762b51b8354840`，应用后为 `3c430d3e20882c65cc02cd519587af98d60f26efb4f3c098918c95b06be68866` / `b0d4b33f0a20ae87d7f6df8235e827eecac92a0d26bcad39e2f847fb7907756d`。`git apply --check --whitespace=error`、Ansible `--check --diff` 和 `git diff --check` 均通过；Plugin 中候选块与分页 MQA 定向 CUDA 测试共 4 个通过。此为局部回归，不代表整模图模式通过。

失败 API PID 58633 在 SIGTERM 60 秒未退出后按原命令再次核对并发送 SIGKILL；其后 EngineCore 58656 与 8 个 worker 58667/58672/58681/58694/58707/58720/58733/58746 按容器 PID、父子关系和 rank 名称分别核对后 SIGTERM。确认 8 张 GPU 均回到 0 MiB、8012 端口空闲且容器继续运行。未停止其他服务。

## 限制与下一步

- 18K eager 整模服务已通过固定短提示和 17,037-token 多样记录提示；同一源码的 TP8 graph 仍需分别核对短上下文与 >16K 请求。
- 锁定版 `/usr/local/lib/python3.12/dist-packages/vllm/v1/attention/backends/mla/indexer.py` 的 `DeepseekV32IndexerMetadataBuilder.get_cudagraph_support()` 返回 `AttentionCGSupport.UNIFORM_BATCH`；Plugin H100 indexer backend 继承了此 builder。第三轮 8 个 rank 的日志均明确把请求的 `FULL` 降为 `FULL_AND_PIECEWISE`。builder 在 `build()` 中按动态 prefill/decode 形状分支，未验证混合批次图重放，不能直接把能力声明改为 `ALWAYS`。即使服务可运行，也不等于完整 prefill/decode 图覆盖；已按 profile 准备显式 `FULL_DECODE_ONLY` 的后续受控验证，不能静默接受降级。
- 设计审查：静态判断属于 V4.1 模型索引器语义，decode 的 graph-safe 包装限定 NVIDIA/H100；现有其他平台未执行回归，不能声称支持。没有新增全局 FlagGems dispatch 或 vLLM 改动。
- 知识库处理状态：`needs-validation`；整模及跨上下文验证后再决定是否沉淀。

## 2026-09-24：Q 语义修正后的整模 FULL 复试

在问题 028 的 QNorm 修补后，以
`H100-149:/public/flagos/jinghao/deepseekV4.1/01-environment/h100149-plugin-20260923/start-skip-qnorm-full-graph.sh`
明确请求 `--compilation-config '{"cudagraph_mode":"FULL"}'`，保持 TP8、
FP8 KV、前缀缓存启用、`max_model_len=2048`、
`max_num_batched_tokens=512`。启动脚本 SHA-256 为
`32cdf8973606edcde14dddab055dfc11d6a70831ebf85eb2c111d4d39bbf6081`；
完整日志 `04-runs/h100149-plugin-skip-qnorm-full-graph-20260924/service.log`
在服务停止后 SHA-256 为
`3b95c519821308826bac9b2cce7599394f4f544052eef73f7d5e655fd95be611`。

8 个 rank 在 23:03:58 均报告：`CUDAGraphMode.FULL is not supported with
DeepseekV41FlagGemsIndexerBackend backend (support:
AttentionCGSupport.UNIFORM_BATCH); setting cudagraph_mode=FULL_AND_PIECEWISE`。
真实捕获日志随后显示 mixed prefill/decode 为 `PIECEWISE`、decode 为 `FULL`；
服务健康检查通过，四个固定 160/256-token 提示全部严格返回 `2`、
`finish_reason=stop`，原始回执在同一 run 目录 `probe/`。这证明先前的
FlagGems `linear` 首编译捕获错误在该图路径未复现，也确认当前 `FULL`
请求被能力声明强制降级，不能充当 full graph 验收。锁定版
`/usr/local/lib/python3.12/dist-packages/vllm/v1/attention/backends/mla/indexer.py`
的 `DeepseekV32IndexerMetadataBuilder.get_cudagraph_support()` 确实返回
`UNIFORM_BATCH`；Plugin 继承了它。该 builder 的 prefill `chunks` 和
动态切片尚无 `ALWAYS` 安全性的整模证据，不能只改声明以消除降级。
服务 PID `98850` 在四份响应和降级日志核对后停止；端口空闲、8 卡显存
归零，容器仍运行。后续已启动独立 `FULL_DECODE_ONLY` 服务验证 profile
允许的最低图级别，其结果需另记，不能由本次混合 piecewise 图推断。

## 2026-09-28：显式 decode-full 捕获与整模复试

9 月 24 日 23:11 启动的 2048-token `FULL_DECODE_ONLY` 服务在当日
23:46 完成 5 个 decode `FULL` 图捕获并启动 API，日志位于
`04-runs/h100149-plugin-skip-qnorm-decode-full-20260924/service.log`。
这个服务在四天内没有留下推理请求回执；9 月 28 日 09:33 EngineCore
意外退出，API 随后关闭。日志仅有 API 的 `EngineDeadError`，没有更早的
worker 堆栈；同时间内核日志没有相关条目，容器保持运行且 GPU 显存为零。
因此图捕获本身已有证据，但**图模式整模推理尚未证明**；不能把四天后的
退出归因于图算子，也不能将此次标记通过。

已核对 Plugin HEAD `fd5c727fcdb607bc4354cd11384761bb5d5ecfba`
和 Q/KV 修复文件 SHA-256 未变，在同一运行容器中启动新的 TP8、18K、
FP8 KV、前缀缓存启用、`FULL_DECODE_ONLY` 服务，加入 V4.1 reasoning
parser。启动脚本为
`01-environment/h100149-plugin-20260923/start-skip-qnorm-18k-decode-full-20260928.sh`，
SHA-256 `92180bac534cef3bf18df7907946c11c2e26f4028b3fb1587fe778bb8398cc5e`；
run 为 `04-runs/h100149-plugin-skip-qnorm-18k-decode-full-20260928/`，
精确 API PID `105185`。启动前确认旧服务退出、8012 端口空闲及 8 卡
显存为零；只启动新推理进程，未重启容器。拟在就绪后验证实际图级别、
短提示、17K 上下文、8 并发、视觉输入和 high 思考解析。结果另行补记。
