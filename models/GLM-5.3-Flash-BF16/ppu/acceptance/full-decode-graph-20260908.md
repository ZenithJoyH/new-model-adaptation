# 无 breakable 的 decode FULL 执行模式与 sanity

日期：2026-09-08。本轮只验证 adaptation 所需的 graph 执行模式和小规模正确性，不是新的
正式 accuracy/performance 轮；历史 GPQA strict 83.84% 失败结论不刷新。

- 主机/容器/服务：`PPU-13` / `glm5.3-flash` / 服务实例
  `PPU-13:bf3487115c28:2893015:159690393`；16/16 worker，health 200，容器 running、
  RestartCount 0。
- 参数：TP16、65,536 context、32 sequences、`FULL_DECODE_ONLY`。prefill eager，decode
  使用 FULL graph；进程环境中没有 `VLLM_USE_BREAKABLE_CUDAGRAPH`。
- 当前启动段完成 7/7 `Capturing CUDA graphs (decode, FULL)`，没有 PIECEWISE capture；
  服务日志无 EngineCore/worker/illegal-memory-access 故障签名。
- 最终结果：
  `/mnt/nfs/users/jinghao/glm5.3-flash/05-runs/023-full-decode-graph/final-cache-root-c8-r2.json`。
  两轮各 8 并发，共 16/16 通过、16/16 `finish_reason=stop`；两轮输出均为
  `9、0、巴黎、56、H₂O、东京、25、蓝色`，没有 `!` 重复。
- 根级 launcher host/container 路径均为
  `/mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh`，SHA-256
  `031923efe0f33a5ce4052f69cc076b48eaad9e8559b4b7e28ba37f759320740f`；脚本运行中端口
  拒绝检查返回 1 且没有替换 PID。
- `VLLM_CACHE_ROOT` 实际生效为 `07-cache/service/vllm`；新目录首次编译耗时 145.75 秒，
  整体 engine init 205.67 秒。该耗时包含首次 NFS cache 构建，不作正式性能结论。
- 实现、逐轮负对照、RLock 归属和 diff 审查见
  [023](../adaptation/023-full-decode-graph-without-breakable-20260908.md)。

本轮 evidence-info receipt 未写入 `platform.yml`：绑定工具在计算 context 时发现历史
`environment/deployment-identity.yml` 的 `runtime_config_sha256` 与当前 legacy
`runtime-config.yml` 不一致。按工作区规则没有通过刷新旧哈希绕过门禁；该记录只陈述已直接
核验的现场结果，不伪装成已完成正式 receipt。
