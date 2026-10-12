# 026：FlagGems-vllm 分页索引打分在 full graph 捕获中执行 GPU 到 CPU 同步

## 元数据

- 状态：`hypothesis`（首错和局部修复已验证；整模复试先被另一条图预热路径阻断）
- 首次出现及最后验证：2026-09-24
- 模型、Host、容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-149`，`deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`
- 原模式：TP8、真实权重、`cudagraph_mode=FULL`、2048 token 上限、前缀缓存启用

## 问题与原因

第二十三轮整模 full graph 启动使用
`01-environment/h100149-plugin-20260923/start-diagnostic-full-graph.sh`
（SHA-256 `41324b102c16b6597d90afe4e05cda24554f8b0b3066bb150382975b42d5bd25`），
原始日志为 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-graph-full-20260924/service.log`。
09:40:27 的首错在 rank 5 的 full graph 捕获：Plugin
`nvidia/indexer.py:_run_decode()` 调用 FlagGems-vllm
`fp8_fp4_paged_mqa_logits()`，其 `_preprocess_kv_cache()` 对 GPU
`context_lens` 执行 `int(context_lens.max().item())`，报
`CUDA error: operation not permitted when stream is capturing`。其余 rank
出现同一首错；后续 `cudaErrorStreamCaptureInvalidated` 和进程退出时的
`captures_underway.empty()` 是捕获失败的连带报错，不是独立根因。服务未开放
8012 端口。只对本次经 PID、模型命令和参数核对的残留 API 进程执行停止：
SIGTERM 60 秒未退出后对同一 PID 发送 SIGKILL；确认容器仍运行且无目标服务。

## 受控修复与证据

FlagGems-vllm 当前公开函数没有可传入的静态最大上下文长度参数；其底层
`_mqa_logits_kernel` 已按每行实际 `ctx_len` 遮罩多余 tile。Plugin 仅在
`torch.cuda.is_current_stream_capturing()` 为真时，用配置的
`max_model_len` 作为静态启动上界，复用现有 FlagGems-vllm Triton 内核和
tile 选择；非捕获路径保持调用原公开算子。FlagGems-vllm、FlagGems 和
锁定版 vLLM 均未修改。此为根因修复候选，尚待第二十四轮整模确认。

补丁保存在 `H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/h100149-graphsafe-mqa-20260924/integration.patch`
（SHA-256 `9e860a26f41a4fce8fb6a93999bc227dbb1d6c050c84de5c7c497f7f5dd17fcc`）。
应用前确认服务已退出；源码 SHA-256 从
`5f9a6317b36626fb15f4f8f44ad78eff8002d517ba7504719953502dd82d3370`
变为 `e3377625c4f385e8e1dadd25bd8777e603d7de13889512bd0e409ef0fe807c02`。
`git apply --check --whitespace=error`、Ansible `--check --diff` 和语法检查通过。
同目录 `test.py` 用两组变动的 Q/上下文长度对比 FlagGems-vllm 公开算子，
三次比较的最大绝对误差均为 0；CUDA Graph 捕获及变输入重放通过。
第二十四轮以同 TP8 参数、仅更换该 Plugin 源码的 full graph 服务使用
`01-environment/h100149-plugin-20260923/start-diagnostic-full-graph-graphsafe.sh`
（SHA-256 `7be1e6b2c6d75aa4e0505e8796b81926be5654efede5ec849ea46716f6438858`），
日志位于 `04-runs/h100149-graph-full-graphsafe-20260924/service.log`。这次在
10:00:50、权重加载前因每卡只剩约 9 GiB 可用显存而失败；检查发现第二十三轮
EngineCore 及其 8 个 worker 在 API PID 退出后仍存活并占用每卡约 70 GiB。
逐一核对这些 rank 的容器 PID、父子关系以及宿主机 `nvidia-smi` 计算进程 PID，
仅向这一组旧 EngineCore 和 worker 发送 SIGTERM；确认 GPU 显存回到 0 MiB、
目标容器继续运行且 8012 空闲。这次资源预检失败不评价 graph 修复。
第三次以同参数及源码重启，独立日志为
`04-runs/h100149-graph-full-graphsafe-retry-20260924/service.log`，启动脚本
`01-environment/h100149-plugin-20260923/start-diagnostic-full-graph-graphsafe-retry.sh`
的 SHA-256 为 `9223415184a8f9c83f126eebbdf2f4d544767ecdba8955371c1437d33f99ccdf`；
真实权重加载完成，图捕获在到达分页 MQA 前被 FlagGems `linear` 的首次
Triton 编译阻断，详见[问题 027](027-v41-indexer-graph-warmup-divergence.md)。
所以这轮不能证明分页 MQA 的整模图修复已通过。Plugin 后续把非捕获和捕获
decode 路径统一为同一 FlagGems-vllm 底层内核，补丁和源码哈希见问题 027。
Plugin 定向回归测试 `tests/models/deepseek_v4_1/test_graphsafe_paged_mqa.py`
已加入，变输入数值和 CUDA Graph 重放通过；与候选块测试合计 4 个通过。

## 限制与下一步

- 静态上界会启动额外的空 tile，性能影响未测；后续应比较实际上下文分布和解码速度。
- Plugin 当前依赖 FlagGems-vllm 的私有底层内核接口；上游公开函数若增加 graph-safe 静态上界参数，应退出此包装并改用公开接口。
- 局部图测试不代表整模 full graph、候选块长上下文或视觉路径通过。先完成候选块真实上下文，再以统一预热路径复试 graph 和最小生成。
