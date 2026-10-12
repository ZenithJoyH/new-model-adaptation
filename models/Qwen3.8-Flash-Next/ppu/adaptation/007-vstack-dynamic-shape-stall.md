# 007：GPQA c64 混合 prefill/decode 停滞与 vstack 动态特化

## 元数据

- 状态：`partially-verified`（`vstack` 动态调优基数已修复；长输出停滞仍可复现）
- 首次出现时间：2026-09-11 13:34:45 +08:00
- 最后验证时间：2026-09-11
- 模型：Qwen3.8-Flash-Next，BF16，served model `Qwen3.8-Flash-Next`
- 平台与 Host 别名：T-Head PPU，`PPU-01`，仅使用 PPU 8–15
- 容器名称与镜像：`qwen3.8-flash`；
  `glm5.3-flash-ppu13-snapshot:20260904-215131@sha256:7755ef5656bd33703eb7c3c81fb6b2099b154284ba582488861f5ec99e3f7b30`
- Plugin / FlagGems / vLLM revision：Plugin
  `939600b323c02c21916f1f76bfb4cd8c2b02578d`；FlagGems 基线
  `7ba32ded1365d3ce6d3b7e28f41af7ddc7ff095c`，修复
  `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：TP8、`FULL_DECODE_ONLY` graph、max model len 65536、服务端
  max 32 sequences / 4096 batched tokens；GPQA Diamond 198 题、客户端并发 64、
  `max_gen_toks=60000`

## 问题现象

- 第一轮正式评测完成 100/198 后停止生成；停滞时 32 running、32 waiting，八个 worker
  仍存活且 CPU 忙等，PPU 8–15 利用率为 0%。
- 13:34:45 后没有新 token；每 60 秒记录 shared-memory broadcast 无可用 block。已配置
  `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=1800`，14:04:32 最终报
  `TimeoutError: RPC call to sample_tokens timed out`，EngineCore 与 API 退出，剩余 98 个请求
  返回 HTTP 500。
- 未见 OOM、worker Python 异常或 collective work 序号分叉。`sample_tokens` 是超时暴露点，
  不能据此直接认定采样算子为根因。
- 受服务故障污染的 receipt 为 failed：100 条真实响应、98 条失败，strict 70/198；该分数
  不是可接受的模型精度结果。
- 原始运行：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/Qwen3.8-Flash-Next-7ba32ded-graph-c64-maxgen60000/gpqa-full-c64-maxgen60000-7ba32ded-20260911-v2/`；
  服务日志：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/execution-mode-graph-7ba32ded-20260911/service.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| Qwen 003 sample_tokens timeout | TP worker 不返回后经 RPC timeout 终止；均发生在混合 prefill/decode | 本轮 timeout 已是 1800 秒，且有明确动态 kernel 缓存增长线索 | 高 | 不再增大 timeout；继续定位停滞前最后一个动态算子 |
| Hy4 018 及 `support-hy4-preview` 的 topk 修复 | 长评测中全局 FlagGems 算子按输入长度生成大量特化，随后模型步不返回 | Qwen 当前默认 T-Head blacklist 已包含 `topk`，本轮无 `topk` Triton 缓存 | 中 | 排除“同一个 topk 算子”；验证同类动态特化机制 |

## 诊断与假设

已验证事实：当前 T-Head 默认 blacklist 包含 `topk`、`stack` 和 `cat`；本轮没有生成
FlagGems `topk` kernel。因此 HY4 的全局 `topk(N,k)` 实现不是本轮的直接调用方。

Plugin 模型文件的 `_short_conv_dilated_dispatch` 在混合 decode/prefill 分支调用
`torch.vstack(non_spec_parts)`。FlagGems 全局注册了 `vstack`，其 Triton autotune key 为
`max_tile_elems`；该值随本批新 prefill 的 token 行数变化。第一轮正式评测期间，缓存中生成了
110 个 `vstack_kernel.autotune.json`，停滞前仍在为新长度写入，且没有同期 `topk` kernel。

当前高可信假设：`vstack` 的无界动态 shape autotune/特化与 HY4 的 `topk` 属于同类机制，
在持续混入不同 prompt 长度时令某个 TP worker 的模型步不返回。缓存时间相关性本身不足以证明
因果；需要保持模型、服务、并发和数据不变，只令 `vstack` 回退 ATen 的负向对照。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 无，只读对照 HY4 topk | GPQA c64 在 100/198 后停滞 | 比较当前 blacklist、调用点、Triton cache 与 HY4 修复 | 远程只读诊断；基线日志见上 | `topk` 已回退且无缓存；定位到 110 个动态 `vstack` autotune 缓存 | 排除同一个 topk；保留同类动态特化假设 |
| 2 | 仅增加 `vstack` 回退 | `_conv_depthwise2d,index` | `_conv_depthwise2d,index,vstack` | `/mnt/nfs/users/jinghao/qwen3.8-flash/02-issues/vstack-dynamic-shape-ab-20260911/start-model-vstack-blacklist.sh` | 198/198 HTTP 200、非 200 为 0；20 分 16 秒完成；服务健康，0 running/0 waiting；`vstack` cache 110→110；致命错误 0 | 在相同 198 个 prompt 和 c64 混合队列上，回退 `vstack` 消除了动态缓存增长并越过基线停滞点；支持因果假设 |
| 3 | FlagGems `vstack` autotune key 分桶 | 精确 `max_tile_elems` | 下一个 2 的幂 `max_tile_elems_bucket` | FlagGems `src/flag_gems/ops/vstack.py`，提交 `2aacb2ed` | 恢复 FlagGems 加速路径后 198/198 HTTP 200、非 200 为 0；约 20 分 16 秒完成；cache 110→115 后保持不变；致命错误 0 | 通用分桶修复保持数值正确并限制动态调优基数，验证其为底层根因修复 |

## 根因

- 已验证根因：直接终止原因是一个 TP 模型步超过 1800 秒不返回，随后
  `sample_tokens` RPC timeout 使 EngineCore/API 退出。
- 已验证局部根因：FlagGems `vstack` 将随 prompt 行数变化的精确 `max_tile_elems` 作为
  autotune key，导致长时混合 prefill/decode 负载持续生成新调优实例。原生 `vstack` 负向对照与
  恢复加速路径后的分桶修复均完成 198 条 max2048 诊断，证明该动态调优问题及修复成立。
- 该结论不能解释全部长输出停滞。修复后的正式 v3 在 `vstack` cache 保持 115、停滞前 8 分钟
  没有新 Triton cache 文件的情况下再次卡死；因此“`vstack` 是 60K 正式轮唯一底层根因”的原结论
  被反例否定。新的 PCCL/graph→eager 边界问题单独记录在
  [008：PCCL graph→eager collective work FIFO 停滞](008-pccl-graph-eager-collective-stall.md)。

## 解决方法或 Workaround

- 已在 FlagGems 通用 `vstack` 中将 autotune key 从精确元素数改为下一个 2 的幂 bucket；
  Plugin、vLLM 与根 `start-model.sh` 均无需增加模型名或 `vstack` 回退例外。
- 修复已作为独立通用算子提交 `2aacb2ed` 推送到
  `ZenithJoyH/FlagGems: support-qwen3.8-flash`；作者和提交者均为
  `ZenithJoyH <1355922182@qq.com>`。其父提交仍是单独的 Qwen 适配提交 `7ba32ded`。
- 诊断脚本和配置只位于远程批准根 `02-issues/vstack-dynamic-shape-ab-20260911/`；原始运行写入
  `04-runs/`，缓存位于 `06-cache/`。
- 基线服务失败后只终止本任务遗留的八个 orphan worker；确认它们退出、PPU 8–15 释放且容器
  始终运行。A/B 服务使用 PPU 8–15；PPU 0–7 的其他任务未操作。
- vLLM 工作树未修改。

## FlagGems 证据

- checkout：`/workspace/FlagGems`，clean
  `support-qwen3.8-flash@2aacb2ed7b116baee0acc147cdc770b4176a6cdd`，远端分支已核对同一 HEAD。
- 已有算子：`src/flag_gems/ops/vstack.py`；全局注册，autotune key 为
  `max_tile_elems`。这不是 Qwen 专属新增算子。
- 数值/调优 reproducer：21 个动态行数、BF16、hidden size 10240 全部逐元素匹配；精确 shape
  被压缩为 4 个 2 的幂 bucket。既有 `tests/test_vstack.py` 为 20 passed，Qwen FlagGems PPU
  算子回归为 97 passed。

## 验证结果

- A/B preflight：离线 GPQA Diamond 198 条、模型端点 200、并发 64，已通过；证据：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/gpqa-vstack-ab-c64-maxgen2048-20260911-preflight.log`；
  SHA-256 `7ad49a934fdd8c3c3d94708a054fdc82e021b8e41f30321a1495bb1c2a5943cd`。
- A/B：198/198 个 API 请求均为 HTTP 200，非 200 为 0；服务最终 0 running/0 waiting、health
  200；EngineCore/RPC timeout、OOM 和 Python traceback 均为 0。既有 `vstack` autotune cache
  保持 110，晚于新服务日志的文件为 0。
- 该轮将生成上限故意设为 2048，只用于覆盖全部 198 个不同 prompt 的动态 prefill 与 c64
  队列稳定性。121 个回答因推理达到 2048 且正文为空，被验收 runner 标成 `<TIMEOUT>`，所以
  runner 返回 1；它们均已有 HTTP 200，不是传输或服务超时。本轮分数不作为 accuracy。
- FlagGems 分桶修复恢复加速路径后，第二轮相同 198 prompt/c64/max2048 压力测试在约
  20 分 16 秒内得到 198/198 HTTP 200、0 非 200、0 EngineCore/RPC/OOM/traceback；`vstack`
  cache 从 110 增到 115 后不再增长。124 条回答因诊断用 2048 上限产生 HTTP 200 length finish
  并被 runner 标记 `<TIMEOUT>`，不属于传输或服务超时，诊断分数不用于 accuracy。

## 限制与下一步

- 发布后 clean `2aacb2ed` 的 c64/max60000 正式 v3 已失败：113 条返回、85 条服务失败，strict
  86/198；该分数受服务退出污染，不能作为模型精度。失败时 `vstack` cache 没有增长。
- 本问题只关闭 `vstack` 动态 shape 调优基数；完整 accuracy 仍未通过，后续诊断转入 008。

## 经验沉淀

- 是否可跨模型或平台复用：动态 shape autotune key 无界增长的诊断方法可跨模型复用；具体
  `vstack` 结论仍限 T-Head PPU 当前 revision。
- 知识库处理状态：`candidate-verified-on-qwen-ppu`
- 候选知识库条目：动态 shape Triton autotune 在长时混合 prefill/decode 下的缓存增长与 TP
  无返回诊断。
