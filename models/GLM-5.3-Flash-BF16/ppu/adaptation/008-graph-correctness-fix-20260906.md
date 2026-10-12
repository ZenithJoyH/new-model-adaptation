# 2026-09-06 graph 并发正确性修复

## 对象与边界

- 主机/容器：`PPU-13` / `glm5.3-flash`；容器始终保持运行。
- 正确权重：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`，BF16，120/120 分片。
- 插件：`/workspace/vllm-plugin-FL-glm53-hy4-adaptation`，基于 ZenithJoyH
  `support-hy4-preview@5329cb1293f397fd194852496cfcc710c35f1bfc`。
- vLLM：`/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389`，全程 clean，未修改。
- FlagGems / FlagGems-vllm 已从 clean tracked branch 以 ff-only 同步至
  `34bd6d68928c8b0039c42987840929da52aa6a62` / `255ab5601b8002b32044fa3632e63eb1b3d45f4e`。

## 症状与定位

eager 服务对固定 8 题连续两轮均 8/8；graph 服务则可复现静默错误：FULL graph
曾使 `12-3` 生成 256 个重复 `!`，PIECEWISE 将重复乱码消除，但同一批中的 `9-9`
会偶发输出 `3` 或 `6`。请求没有 HTTP 错误或超时，说明不能靠增大超时解决。

将捕获规模由 `[1,2,4,8,16,32]` 扩大到每个整数 1–32 后仍以 29.68 tokens/s
复现 `9-9 -> 6`，因此批次补齐不是根因。移除 `VLLM_USE_BREAKABLE_CUDAGRAPH`
会在启动期使 Dynamo 编译进入插件 dispatch 的 `RLock`，报 unsupported context
manager，因此该环境变量是插件动态 dispatch 的必要配置，不能删除。

正确性与 eager/graph 的唯一稳定差异落在有状态 sparse indexer：它会在每个 decode
step 读写压缩 index K cache 和四 token tail cache。该函数原本作为自定义算子整体进入
capture/replay，状态更新和动态 metadata 组合会在 graph 批处理下污染单个请求的索引结果。

## 最小修复

仅在插件 `vllm_fl/kernels/glm5_next/sparse_attn_indexer_kpool.py` 的
`sparse_attn_indexer_kpool` 函数上增加现有 `@eager_break_during_capture`。这让有状态
indexer 作为 breakable graph 的 eager 边界执行，模型其余 PIECEWISE graph 段仍被捕获。
补丁为 `patches/glm53-sparse-indexer-breakable-graph.patch`；应用与服务生命周期命令为
`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/apply-ppu13-glm53-sparse-indexer-graph-break.yml`。

已证伪的 1–32 捕获列表从最终启动脚本删除，最终只保留
`--compilation-config '{"cudagraph_mode":"PIECEWISE"}'`。插件自带的
`vllm_fl/dispatch/config/thead.yaml` 自动读取；主启动脚本没有 `runtime_dir` 或
`VLLM_FL_CONFIG`。宿主机 wrapper 仅负责防重复、PID 和日志生命周期。

## 验证

- 聚焦插件回归：`tests/unit_tests/test_glm5_support.py`、`tests/unit_tests/dispatch`、
  `tests/dispatch/test_vendor_bootstrap.py` 全部通过；`git diff --check` 通过。
- 精确规模实验下，修复后并发 8 两轮均 8/8，34.05 / 47.78 tokens/s。
- 删除实验捕获列表后的最终服务 PID `770859` 完成默认 11/11 graph 捕获并健康。
- 最小请求正确；最终并发 8 两轮均 8/8、零错误/超时，27.84 / 47.72 tokens/s，
  最大延迟 15.04 / 8.77 秒。详细 job 与资源数据见 `../acceptance/graph-sanity-results.md`。
- eager 结果在修复前已连续两轮 8/8；该装饰器不改变非 capture 执行语义。

## 正式精度状态

新运行目录 `/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-indexer-break`。
FlagEval v1 的 `test/Accuracy_test/llmrun.py` preflight 已确认 GPQA Diamond 198 题、
服务 HTTP 200、客户端并发 64。响应缓存与 2026-09-04 历史失败轮隔离；正式运行于
2026-09-06 11:11（UTC+8）启动。通过条件为 198 个唯一题、零超时且原始
`exact_match,strict-match >= 0.88`。正式结果完成前不启动性能验收。
