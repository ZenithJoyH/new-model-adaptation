# Hy4-preview 当前栈执行模式与 graph sanity

## 范围与身份

- 日期、Host、容器：2026-09-07，`PPU-07`，`hy4`（container ID
  `550e93f0ba4c3109f05002d3a39c55d10c42eee13d661f3062757d9505535ca2`）。
- 模型服务：served model `hy4`，TP16，端口 8010，最大上下文 100,000。
- vLLM / FlagGems / Plugin revision：
  `ee0da84ab9e04ac7610e28580af62c365e898389` /
  `717a9ef60d38b559d8b4424488ca5cad2fe61a59` /
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`。
- Plugin 工作区仍保留用户原有未提交差异，diff SHA-256 为
  `d2a01df0f5d9b85bbb51d3111bde7ceeafef9f563f6be1b151cbfd9616a3943d`；本轮未覆盖它。
- 服务运行时使用问题 016 记录的安全 T-Head blacklist（Plugin HEAD 默认集合加 `index`），
  启动器为远端
  `/mnt/nfs/users/jinghao/hy4-preview/02-environment/hy4-safe-blacklist-runtime-20260907/start.sh`。

## execution-mode

先在相同镜像、模型、TP 和 blacklist 下启动 `--enforce-eager` 服务，再切回 graph 服务；只停止
本任务的精确 API/EngineCore/worker 进程，容器未停止、重启或删除。

- eager：健康检查 200；固定请求 `17 + 25` 返回 `42`，`finish_reason=stop`。
- graph：完成 `FULL_DECODE_ONLY` 51/51 capture；相同请求返回 `42`，
  `finish_reason=stop`。
- 当前 graph API 实例：`PPU-07:550e93f0ba4c:2468847:151120760`。
- eager 原始证据：
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/execution-mode-hy4-safe-20260907/eager-probe-result.json`，
  SHA-256 `2916f815f03678dcf95c1ada21609309a2abff3969dea88494917d7917746db7`。
- graph 原始证据：
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/execution-mode-hy4-safe-20260907/graph-probe-result.json`，
  SHA-256 `bb2dd359e336e922b2f04867fbc227b8ae51a6cc5addcbf11fe669035cf70c8b`。
- 生命周期记录：同一目录的 `eager-to-graph-lifecycle.txt`；eager 首次启动脚本因 SDK
  `envsetup.sh` 读取位置参数而与 `set -u` 冲突，已仅调整启动器的 `set -u` 时序并成功复验，
  记录为 `eager-launch-recovery.txt`。

结论：当前栈的 eager 与 graph 完整模型执行模式均通过。`reasoning_effort` 省略时接口行为正常；
API 对 `none` / `no_think` 的校验与 parser 约定不一致，但不影响正式 GPQA 使用的 `high`。

## graph 并发 8 sanity

graph 实例完成 capture 后，使用 8 个并发确定性算术请求：`i + 17`（`i=1..8`），
`temperature=0`、`seed=42`、最多 128 tokens。

- 结果：8/8 内容正确，全部 `finish_reason=stop`，总耗时 24.9877 秒。
- 服务状态：健康检查 200，16 个 TP worker 保持运行，
  `vllm:num_preemptions_total=0`，日志无 `Traceback`、EngineCore fatal、HTTP 500 或设备断言。
- 原始证据：
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/execution-mode-hy4-safe-20260907/graph-sanity-result.json`，
  SHA-256 `2e501d733f6f4ae602a4d86d40ea834980efce908bc28746b688e1031995aa52`。
- 可执行 sanity 工具：
  `/mnt/nfs/users/jinghao/hy4-preview/04-acceptance/hy4-safe-20260907/graph_sanity.py`。

结论：当前 graph 实例通过正式 accuracy 前置的并发 8 正确性 sanity；该耗时只作轻量预检，
不是正式性能结论。

## 下一步

在同一 graph 服务实例上执行 GPQA Diamond 全量 198 题、并发 32、
`reasoning_effort=high`、`max_gen_toks=40000`。完整 result/sample、日志、配置和缓存继续留在
批准的远端 `04-acceptance/`、`05-runs/` 与 `07-cache/`；本地只更新 Markdown 结论。
