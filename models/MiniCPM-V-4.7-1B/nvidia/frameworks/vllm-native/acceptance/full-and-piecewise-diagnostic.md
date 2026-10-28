# 显式 FULL_AND_PIECEWISE 运行验证

- 日期：2026-09-28
- Host/容器：`H100-149` / `MinicpmV4.7-1B-native`，容器保持运行
- 模型：`/data/models/MiniCPM-V-4.7/weights/1b`
- 引擎：容器内 vLLM `0.24.0+cu129`，wheel 内 MiniCPM-V-4.7 adapter SHA-256 `e1bddd8ee92576ff8260ef8e5362a8a7fb7d47c3f4f70584e63944695c2cf86d`
- 设备和服务：GPU 0、TP1、BF16、`127.0.0.1:8307`、prefix caching 开启
- Host/容器工作根：`/public/flagos/jinghao/MiniCPMV4.7-1B/native`
- 专用脚本：`01-environment/start-minicpmv47-full-and-piecewise.sh`，SHA-256 `d1d01538232b50031e85726abe9135b289033637d24704d952756fda3a9b4a80`
- 参数：`--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}'`，其余容量与上一轮 decode-full 对照一致

## 过程与实测

切换前确认原服务 API PID `7712`、端口 `8307`、模型和
`FULL_DECODE_ONLY` 参数。仅向该 PID 发送 `TERM`；复核 API PID 与
EngineCore PID `8116` 均退出、GPU 0 显存释放、容器仍运行，其他 GPU
上的进程未处理。通过单 Host Ansible playbook 在原容器启动专用脚本。

`04-runs/native-full-and-piecewise-20260928/service.log` 显示生效配置为
`CUDAGraphMode.FULL_AND_PIECEWISE`，mixed prefill/decode 的 51 个 PIECEWISE
图和 decode 的 51 个 FULL 图均捕获完成；Graph capturing finished，
`/health` 返回 200。并发检查由
`03-acceptance/minicpmv47-hybrid-smoke.py` 发起 10 路变输入请求，包含纯文本、
单图、双图和两帧视频，全部为 HTTP 200、`finish_reason=stop` 且匹配预期；
整体用时 1.225 秒。原始响应和摘要位于
`04-runs/native-full-and-piecewise-20260928/`；
`concurrent-summary.json` SHA-256 为
`1d2c3eb3d61bd988a95057c602f72ea07ddce89950041db9ca6358afa572f48a`。
复核当前 API PID `9611` 的命令行仍明确指定该图模式。服务日志在这些请求后
未见 ERROR、Traceback 或 Exception。

## 边界

这是用户要求的显式混合图运行检查，不能把 PIECEWISE 的 prefill 记为
`full` 图通过。后续根级 `start-model.sh` 已按用户要求改为此模式，见
`acceptance/root-launcher-hybrid-update.md`；先前的
`FULL_DECODE_ONLY` 部署身份和原生执行模式回执作为历史证据保留，不作为新脚本的回执。
固定 sanity manifest、冻结阈值的正式准确率与性能评测仍待完成。
