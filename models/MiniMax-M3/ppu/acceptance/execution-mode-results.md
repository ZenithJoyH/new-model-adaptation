# MiniMax-M3 / PPU 执行模式验收

## 结论

`passed`。2026-09-15 在 `PPU-13` / `minimaxM3` 上，当前 Plugin redesign 工作树分别完成 TP16 eager 与 graph 整模启动、warmup、health 和两组 changed-input 推理。两种模式均使用 `max_model_len=65536`、BF16、block size 128、prefix caching 开启；本结论不替代固定十题 sanity 或正式精度结果。

## 当前源码身份

- 服务启动时 Plugin 为 `support-minimax-m3@86ec92fda1e7d329448f477a717e42e6a8d4f171` 加 redesign 工作树，tracked diff SHA-256 为 `99f53622dce770eced3cedb69f45a3b4b70d8017c44a6eb3e584461189d4085e`。2026-09-16 在不改变工作树字节的前提下移除旧提交并重新提交为 `aee54f38580e0b8b3db5ed433663ed5359ca308b`（tree `6fac31e4cdf13f6d31cf4e37b23e1f88ef38d2c0`）。
- 最终 graph 身份收据保存了当时的 working-tree status，以及包括新增实现 `vllm_fl/dispatch/backends/flaggems/impl/minimax_m3.py`、`vllm_fl/patches/minimax_m3_thead.py` 在内的推理相关文件 SHA-256；后续 Git 提交仅固定相同字节，不重启服务，因此原执行模式证据继续绑定同一实现。
- 四个既有 `.orig` 未跟踪文件保留，未纳入产品实现或修改。

## Eager

- run root：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/execution-mode-eager-65k-restored-patch-20260915-01/`。
- 结果：59/59 权重加载；FlagGems autotune 因 PPU Triton backend 没有 replay benchmarker 而回退 event timing，profile/KV cache/warmup 共耗时 `620.72s`，随后 health 200。
- changed-input：北京问答与 GPQA 风格火星选择题均经真实模型链路返回语义正确结果；后者的 32-token smoke 输出在思考阶段截断，但已明确给出 `Mars`，不作为 exact-match 证据。
- 收据 SHA-256：`smoke-receipt.txt` 为 `cf5f3853dd4fa09566908ad51f185d4b89fdbe9a74fb2afd38d32a68470773ca`；原始响应为 `36a64f6f946c1cbd61f89f57c326a03aa0e44b8f269ce251359f38c81c7572c6`。
- 服务切换：仅向本任务 API PID `1338419` 发送 TERM；进程和 8013 端口释放，容器保持运行且未重启，记录在同一 run 的 `termination-record.txt`。

## Graph

- run root：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/execution-mode-graph-65k-restored-patch-20260915-02/`。
- 配置：`FULL_DECODE_ONLY`，capture sizes `1,2,4,8,16,32`；6/6 capture 完成，GPU KV cache `672,384` tokens，profile/create-cache/warmup 共耗时 `680.02s`，health 200。
- changed-input：与 eager 相同的两组变更输入均语义正确；日志无 `CompileTimeAssertionFailure`、EngineCore failure 或 traceback。
- 当前服务实例：`ppu13-minimaxM3-7ffdd70d-boot-e0f88877-pid1551482-start219575444-cmd4735fa06`。
- 身份收据：`service-identity.json` SHA-256 `bd8ee8232f855ff7cb5cb751ab6dd41cb8843aa0e851ebf20f763f25b5b40fa5`；graph smoke receipt `3237ca4500c2262edec07e71ce1b7a4ae7ff9129f89a5b4455f34115c70f09b3`；原始响应 `e975ea525b49e29942939af1c2fdf94574b0dc183411e5d23e941f7ae2351c3f`。

## 历史证据边界

此前 `eager-service-run5` / `graph-service-run2` 对应提交态 Plugin，仍作为历史证据保留，但不再代表当前 redesign。固定前十题和全量 GPQA 的旧结果也必须在上述当前 graph 服务实例上重跑后才能恢复为当前验收结论。
