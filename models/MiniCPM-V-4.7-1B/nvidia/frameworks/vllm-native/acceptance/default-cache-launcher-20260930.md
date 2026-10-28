# 容器默认缓存与临时路径的根级启动脚本

- 日期：2026-09-30
- Host/容器：`H100-149` / `MinicpmV4.7-1B-native`
- Host/容器中的脚本：`/public/flagos/jinghao/MiniCPMV4.7-1B/native/start-model.sh`
- 当时 SHA-256：`b08a779b7a86ba208647c953897947611a08717dfb6f80864ab7065953a52bcb`；已由[用户调整版](user-launcher-validation-20260930.md)取代
- 前版备份：`02-issues/start-model.explicit-workspace-cache.20260930.sh`，SHA-256 `c5fce8aba2f93a66e9fc1a5a23a386900b05c2a5464d326750eabd723aaaa6df`

## 用户指定的精简范围

删除 `XDG_CACHE_HOME`、`TRITON_CACHE_DIR`、`PYTHONPYCACHEPREFIX`、
`TMPDIR` 的脚本设置，删除缓存及临时目录创建。容器进程环境已核对这些
变量以及 `HF_HOME`、`VLLM_CACHE_ROOT` 均未设置。容器当前默认的
Hugging Face 与 vLLM 缓存位置分别为 `/root/.cache/huggingface` 和
`/root/.cache/vllm`，临时目录为 `/tmp`；`/root/.triton` 已存在。
这些默认位置不属于批准工作根，是本次用户明确指定的运行配置；未对
已有默认路径内容执行删除、移动或清理。

保留 `TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu`，因为该镜像不设置时
Triton 查找 libcuda 失败，见适配问题 002；`CUDA_VISIBLE_DEVICES=0`
保持已核对的 GPU。日志仍只写 `04-runs/`，脚本只创建该目录。
多行 Python 端口检查改为 Bash 内建 `/dev/tcp` 检查；GPU 0 占用检查
缩为两行，仍拒绝替换已有服务或与未知进程共用设备。vLLM 命令保留
已验证所需的模型、接口、容量、显式前缀缓存和 `FULL_AND_PIECEWISE` 参数。

## 现场验证

Ansible 单 Host `--check --diff`、脚本 `bash -n`、Host/容器相同哈希与
端口被占用时拒绝替换均通过。只终止本任务核对后的 API PID `14562`，
复核 EngineCore PID `14966` 退出、GPU 0 显存释放、容器仍运行，随后
从当前根脚本启动。新日志为 `04-runs/service-20260930T145818-15984.log`；
当前 API PID `15984` 的进程环境没有上述缓存或临时目录变量，日志显示
前缀缓存启用，mixed prefill/decode PIECEWISE 51/51 和 decode FULL 51/51
均捕获完成，无 ERROR/Traceback/Exception，`/health=200`。

十并发文本、单图、双图与视频请求均 HTTP 200、`finish_reason=stop`
且命中简单预期（10/10）。摘要位于
`04-runs/default-cache-launcher-20260930/concurrent-summary.json`，SHA-256
`02a5a117311d69d11c54ab677fd1a0c067b99dedf9e34fd35831f263a05691f3`。
适配容器继续运行。此检查不是正式准确率或性能评测；先前
`framework.yml` 的部署身份与 execution-mode 回执仍绑定旧 decode-full
配置，不将其误记为当前脚本的原生验收。
