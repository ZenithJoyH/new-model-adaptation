# 用户调整版启动脚本验证

- 日期：2026-09-30
- Host / 容器：`H100-149` / `MinicpmV4.7-1B-native`，单 GPU 0，TP1
- Host / 容器脚本：`/public/flagos/jinghao/MiniCPMV4.7-1B/native/start-model.sh`，映射及相同 SHA-256 已核对
- 当前脚本 SHA-256：`f4be3515cc079773a26465497fef7955355bf68e35201a2704d6e5883350a66b`
- 旧脚本回退副本：`01-environment/start-model.rollback-default-cache-20260930.sh`，SHA-256 `b08a779b7a86ba208647c953897947611a08717dfb6f80864ab7065953a52bcb`
- vLLM：容器安装版 0.24.0；模型路径 `/data/models/MiniCPM-V-4.7/weights/1b`，权重保持只读

## 当前参数和启动结果

用户脚本保留 `CUDA_VISIBLE_DEVICES=0`、`TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu`、显式前缀缓存及 `FULL_AND_PIECEWISE`；监听 `127.0.0.1:8000`，`--gpu-memory-utilization 0.85`，没有 `--max-model-len` 或 `--model-impl`。脚本以 `nohup ... &` 后台启动，输出重定向到根目录 `service.log`。缓存及临时文件使用容器默认路径。未修改用户脚本。

执行前确认端口 8000 空闲、`service.log` 不存在；仅停止此前由本任务启动并核对身份的 8307 API PID `15984` 及其 EngineCore `16590`，确认 GPU 0 释放且适配容器继续运行。Ansible 单 Host `--check --diff` 后，原样执行脚本。首次工具审批超时未执行；重试执行成功。API PID `17782`、EngineCore PID `18176`，有效命令行与脚本一致，健康端点 `/health` 返回 200。日志显示模型最大长度 `262144`、前缀缓存开启、mixed prefill/decode PIECEWISE 51/51 与 decode FULL 51/51 捕获完成；无 ERROR、Traceback 或 Exception。GPU 0 约使用 68,341 / 81,559 MiB，余量约 12,739 MiB。最后一次独立只读检查仍得到相同脚本 SHA-256、进程命令行和 `/health=200`。

十并发变输入基本推理覆盖文本、单图、双图和两帧视频，10/10 返回 HTTP 200、`finish_reason=stop`，并命中简单预期；耗时 2.698 秒。原始结果位于 `04-runs/user-launcher-20260930/`，摘要 `04-runs/user-launcher-20260930/concurrent-summary.json` 的 SHA-256 为 `f82d4a17225b6ff4dd4ce66f19eb6a7d994d71234596453ad4f72e3101e7d022`。

## 边界

这证明当前配置可启动并完成短输入的基本多模态推理，不是 262144 token 长上下文、正式准确率或性能验收。`nohup ... &` 使脚本在服务就绪前返回，子进程稍后失败时脚本退出码仍可能为 0；没有端口或 GPU 占用检查，重复执行的行为未验证。每次启动以 `>` 覆盖同一个 `service.log`，且日志不在项目规定的 `04-runs/`。端口由旧版 8307 改为 8000，下游客户端需使用当前端口。`framework.yml` 中旧执行模式回执及部署身份未随本次脚本变更刷新，不能据此认定当前版本完成正式验收。
