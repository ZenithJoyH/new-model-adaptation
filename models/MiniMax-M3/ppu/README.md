# MiniMax-M3 / ppu

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)

当前 framework 记录：
- [vllm-plugin-fl](frameworks/vllm-plugin-fl/README.md)（v2；历史结论不自动成为新门禁通过）。

旧平台阶段记录按原位置保留（不作为新增执行入口）：
- [环境与设计](environment)。
- [问题台账](adaptation/README.md)。
- [验收记录](acceptance/README.md)。

## 整理前平台说明（历史原文）

> 2026-09-21 状态复核：当前状态为 `blocked`。本地审计发现历史验证缺失或上下文失效，
> 原始适配结果保留供追溯；它们不代表当前部署验收已通过。本次未操作远端或重新评测。
> 具体阻塞见 `platform.yml`，重新核实原生证据后才能恢复通过状态。

- Inventory group: `ppu`
- Hardware query: `ppu-smi`
- Target: `PPU-13` / container `minimaxM3`
- Approved host/container root: `/mnt/nfs/users/jinghao/minimaxM3`
- Current state: `functional`；Plugin 已移除 index-topk monkey patch，当前 TP16 graph 服务 PID `2153450` 通过 `FLAGTREE_AABS=0` 使用原生 vLLM `index_topk`，在 `max_model_len=65536` 下完成 59/59 加载、6/6 capture、health 200 和真实 sparse-prefill 请求，请求后 API/EngineCore 均存活且无原静态断言。此前 patch 配置的固定前十题为 10/10、GPQA Diamond c64 为 177/198（89.39%）；这些精度结果尚未在 no-patch + AABS0 配置重跑。容器与 GitHub `support-minimax-m3` 均为单一适配提交 `7e412e6f8b6d8a5e4350e0237e1a8548dfaf7b94`。

平台根目录只保留本索引与 `platform.yml`。运行 `scripts/adapt-model` 后，环境材料、
适配过程和验收证据分别放入 `environment/`、`adaptation/` 和 `acceptance/`。
容器没有暴露 `ppu-smi` 时必须记录为环境阻塞，不得回退到其他平台命令。

当前证据入口：

- 模型结构：`../architecture-and-inference.md`
- 环境分析：`environment/environment-analysis.md`
- 适配问题索引：`adaptation/README.md`
- GPQA sanity：`acceptance/sanity-results.md`（当前 redesign，10/10，0 timeout）
- GPQA Diamond 全量精度：`acceptance/accuracy-results.md`（当前 redesign c64 177/198，89.39%，passed）
- 验收总结：`acceptance/adaptation-summary.md`
- 最新 dispatch redesign：`adaptation/008-flaggems-dispatch-reclassification.md`（最终 Plugin `7e412e6`；无 `_C` ABI 合成；focused 15/15、其余 dispatch 277/277）
- 无 index-topk patch 负对照日志：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/graph-no-thead-index-topk-patch-20260915/server.log`
- 恢复补丁后的 65K 服务日志：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/graph-restored-index-topk-patch-65k-20260915/server.log`
- no-patch + `FLAGTREE_AABS=0` 65K graph 服务及真实请求证据：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/index-topk-aabs0-no-patch-graph-65k-20260916-01/`
- 最终启动脚本：host/container `/mnt/nfs/users/jinghao/minimaxM3/start-model.sh`，32 行，SHA-256 `e65ba3a1b01d2d8196d9a754e8c3b4c82cbfa35c6d1dba683e05fa4ff63c7326`；只保留重复服务/端口保护、必要缓存落盘、`FLAGTREE_AABS=0` 和已验证的 vLLM 启动命令。2026-09-16 已通过语法、容器映射、重复服务拒绝与现有服务 health 200 验证。
