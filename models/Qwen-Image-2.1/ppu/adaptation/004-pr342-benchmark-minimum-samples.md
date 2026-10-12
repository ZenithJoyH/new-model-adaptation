# 004：PR #342 慢负载 benchmark 未保证两个正式样本

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-18
- 最后验证时间：2026-09-18
- 模型：Qwen-Image-2.1
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器：`qwen-image`
- Plugin revision：PR #342 head `229386dcb4734334bd695c6aabe24a35b8b491d2` + 本地未提交修复
- 负载：Diffusers eager，1024x1024，40 步，batch 4，`flagos:0`

## 问题现象

- PR 文档与终端提示声明正式测量“至少两次”，但 batch-4 单次约 146 秒，`blocked_autorange(min_run_time=60)` 只产生 1 个 timed sample。
- JSON 写入 `protocol.runs=1`、latency/phase `runs=1`、`std=0`，但摘要误报 `determinism two calls agreed`。
- 原始证据：`04-runs/pr342-declared-cases-20260918-01/flagos/bench-batch4.json`。

## 根因

- `blocked_autorange` 的最小时间不等于最小调用次数；一次调用已超过目标时间时，它合法地只返回一个 sample。
- 旧代码直接使用 autorange 返回的次数，未实现文档声明的两次下限。单样本时 `hashes[0] == hashes[-1]` 必然为真，不能证明确定性。

## 解决方法

- 新增 `ensure_minimum_measured_calls`：autorange 样本少于 2 时，显式补足 timed call。
- 每个 measurement 结束后立即截取对应的 phase、peak memory 和 image hash，避免 Timer 未计时的校准/probe 混入 receipt。
- 合并各 measurement 的 latency sample，并在 notes 记录补测事实。
- 修复路径：`tests/manual/qwen_image_21/bench.py`；回归：`tests/unit/test_qwen_image_21_manual_flow.py`。
- 过程补丁：`/mnt/nfs/users/jinghao/qwen-image/05-tmp/pr342-bench-min-two.patch`。

## 验证结果

- 单元回归：与 manual flow、PPU route、device guard 合计 `7 passed`。
- 修复前 batch-4：`runs=1`，36.49 s/image，0.0274 images/s，std 0.000 s，确定性结论无效。
- 修复后 batch-4：`runs=2`，中位数 36.41 s/image，std 0.001 s，0.0275 images/s，峰值分配显存 56.52 GiB，两次正式输出一致。
- 正式证据：`/mnt/nfs/users/jinghao/qwen-image/04-runs/pr342-declared-cases-20260918-01/flagos/bench-batch4-fixed.json`，SHA-256 `7c6305cd5e4fdca58e00606b4185d07992b7130a0a792a1faea01a8b99202ae8`。
- 性能表：同运行根 `bench-table.md`，SHA-256 `4fcc49580cfc60b28da682b6f0e9bcf98222f9a05312eb35816ba6d1a0e47455`。
- Diffusers 边界：本轮不使用 vLLM 服务，因此 `--no-enable-prefix-caching` 要求不适用。

## 限制与下一步

- 补测使用 `Timer.timeit`，其内部校准会增加额外墙钟时间，但不进入 receipt。可后续改为明确的两次外层计时以降低工具开销，不影响当前数据正确性。
- 分支修复仍未 commit、未 push。

## 经验沉淀

- `min_run_time` 不能代替 minimum sample count；确定性必须确认至少两个独立正式样本。
- 知识库处理状态：`needs-validation`
