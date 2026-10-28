# 根级模型启动脚本精简与验证

- 日期：2026-09-30
- Host/容器：`H100-149` / `MinicpmV4.7-1B-native`
- Host 与容器路径：`/public/flagos/jinghao/MiniCPMV4.7-1B/native/start-model.sh`
- 本轮脚本 SHA-256：`c5fce8aba2f93a66e9fc1a5a23a386900b05c2a5464d326750eabd723aaaa6df`；随后按用户要求改用容器默认缓存与临时路径，见 `default-cache-launcher-20260930.md`
- 前一版本备份：`02-issues/start-model.hybrid-before-minimal.20260930.sh`，SHA-256 `0e94c30ed5c460b354ea6a3c0e38966ff32b24a7e56f566c5012396d1e9b2e53`
- vLLM adapter / registry 哈希未变：`e1bddd8ee92576ff8260ef8e5362a8a7fb7d47c3f4f70584e63944695c2cf86d` / `58ea925cd79c7771b35455d48c5d991928fd019539d8e0e61e100af541d55d43`

## 精简结果

删去独立的 `HF_HOME`、`VLLM_CACHE_ROOT` 设置；已在此容器验证设置
`XDG_CACHE_HOME` 后，Hugging Face 与 vLLM 均把缓存放在批准的
`06-cache/` 下。将 `XDG_CACHE_HOME` 直接指向 `06-cache/`，缩短创建目录列表。
省略 `--enable-prefix-caching` 的尝试经同负载指标对照证实不满足本模型的
正常前缀缓存要求，已加回；详见 `adaptation/004-prefix-cache-default.md`。

最终脚本保留的显式设置及原因：

| 设置 | 保留原因 |
| --- | --- |
| `CUDA_VISIBLE_DEVICES=0`、GPU 占用检查 | 固定已核实的独占设备，拒绝与未知进程共享 |
| `XDG_CACHE_HOME`、`TRITON_CACHE_DIR`、`PYTHONPYCACHEPREFIX`、`TMPDIR` | 将 Hugging Face/vLLM/PyTorch、Triton、Python 和临时写入约束在批准工作根 |
| `TRITON_LIBCUDA_PATH` | 修复该镜像的 libcuda 查找失败，见适配问题 002 |
| `--host 127.0.0.1 --port 8307`、端口占用检查 | 固定已测接口且拒绝替换现有服务 |
| `--served-model-name` | 固定客户端请求所用模型 ID |
| `--trust-remote-code` | checkpoint 的配置和处理器使用 `auto_map` 自定义代码 |
| `--model-impl vllm` | 固定已适配的 vLLM 实现，阻止隐式 Transformers 回退 |
| `--enable-prefix-caching` | 当前模型省略时查询/命中均为零；显式启用后有实际命中 |
| `--max-model-len 2048`、`--gpu-memory-utilization 0.35` | 固定已验证的上下文范围及 GPU 内存配额 |
| `--compilation-config` 的 `FULL_AND_PIECEWISE` | 保持用户指定的 mixed PIECEWISE、decode FULL 模式 |

日志、缓存和临时文件分别保存在 `04-runs/`、`06-cache/`、`05-tmp/`。
脚本没有停启容器或其他 GPU 上的服务。`bash -n`、Host/容器相同哈希、
端口占用时拒绝替换均通过。仅停止本任务已核对的旧 API PID `10982`
与诊断 API PID `13222`；每次均复核退出和 GPU 0 释放后才重启。

## 当前服务实测

最终根脚本启动日志：`04-runs/service-20260930T142939-14562.log`。
本轮 API PID `14562` 命令行包含 `FULL_AND_PIECEWISE` 与
`--enable-prefix-caching`，mixed prefill/decode PIECEWISE 51/51 和 decode FULL
51/51 均捕获完成，`/health=200`，日志未见 ERROR/Traceback/Exception。
同一长前缀两次请求，缓存查询增加 1484 token、命中增加 576 token；
结果和 SHA-256 见问题 004。十并发文本、单图、双图和视频请求
10/10 HTTP 200、`stop` 且匹配简单预期，摘要位于
`04-runs/minimal-launcher-final-20260930/concurrent-summary.json`，SHA-256
`f5f51ec8b27f79107bbdae0b75d38419bb04c5efbbc115536be71024bd09394e`。
适配容器仍运行。该检查不是正式精度或性能评测。

先前 `framework.yml` 的 deployment fingerprint 和 execution-mode 回执仍绑定
decode-full 的历史启动配置；本次只修改启动脚本和本地分析记录，不刷新哈希
或将旧回执误记为新服务的正式验收。完整正式验收仍待完成。
