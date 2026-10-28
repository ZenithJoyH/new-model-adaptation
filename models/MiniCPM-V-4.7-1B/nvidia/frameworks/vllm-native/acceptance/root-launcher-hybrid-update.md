# 根级启动脚本切换为 FULL_AND_PIECEWISE

- 日期：2026-09-28
- Host/容器：`H100-149` / `MinicpmV4.7-1B-native`
- Host 与容器中的同一路径：`/public/flagos/jinghao/MiniCPMV4.7-1B/native/start-model.sh`
- 旧 SHA-256：`d21322e696819ea953c54f609fabf89c1494ee32e73fae9410419eec870a4926`
- 新 SHA-256：`0e94c30ed5c460b354ea6a3c0e38966ff32b24a7e56f566c5012396d1e9b2e53`
- 旧脚本备份：`02-issues/start-model.decode-full.20260928.sh`，哈希与旧脚本一致

## 修改与验证

基于已核对哈希的旧根脚本，仅将 `cudagraph_mode` 从
`FULL_DECODE_ONLY` 改成 `FULL_AND_PIECEWISE`。仍使用 GPU 0、TP1、
本机 `8307` 端口、前缀缓存开启、`max_model_len=2048`、
`gpu_memory_utilization=0.35`；日志、缓存和临时文件仍留在批准工作根的
`04-runs/`、`06-cache/` 和 `05-tmp/`。启动时检查端口和 GPU 0 占用，
不停止或替换已有服务。旧文件身份断言与 Ansible `--check --diff` 均通过。

Host 和容器内的脚本 SHA-256 相同，`bash -n` 在两侧通过。原混合图
服务占用端口时，从根脚本试启动按预期拒绝替换。随后只停止已确认属于
本任务的 API PID `9611`，复核 EngineCore PID `10010` 退出、GPU 0
显存释放、容器仍运行，再从新根脚本启动服务。新日志为
`04-runs/service-20260928T142341-10982.log`：有效配置是
`CUDAGraphMode.FULL_AND_PIECEWISE`，51 个 mixed prefill/decode PIECEWISE 图
和 51 个 decode FULL 图捕获完成，API `/health` 返回 200。

十并发文本、单图、双图和视频复测写往
`04-runs/root-launcher-hybrid-20260928/concurrent-summary.json`。2026-09-30
连接恢复后已核验：10/10 HTTP 200、`stop` 且匹配简单预期；摘要 SHA-256
`7ee89329ed703415a5bf2af5350f6f38498e22def3e72231f417f36e5041e4ba`。
该版本随后被 2026-09-30 精简版替换，见
`acceptance/launcher-simplification-20260930.md`。

## 验收边界

先前 `01-environment/deployment-identity.json` 和 `framework.yml` 中的
deployment fingerprint、execution-mode 原生回执绑定的是旧 decode-full
脚本。保留原始证据；新脚本的正式身份和原生回执尚未重建，不将历史
`passed` 视为本次混合图启动模式的正式验收。PIECEWISE prefill 也不等于
mixed FULL graph。
