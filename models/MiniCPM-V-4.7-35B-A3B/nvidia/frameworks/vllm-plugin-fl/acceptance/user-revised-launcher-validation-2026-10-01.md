# 用户再次改写的 TP2 启动脚本验证（2026-10-01）

## 身份与操作

- Host：`H100-149`；容器：`MinicpmV4.7-35B`；模型：`/data/models/MiniCPM-V-4.7/weights/35b-a3b`。已核实宿主机和容器工作根映射为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`。
- 用户当前脚本两侧路径均为 `<root>/start-model.sh`，模式 `0755`，宿主机/容器设备号与 inode 同为 `45:213775686669`，SHA-256 `88ff63628fbdb5f0c863e46bc36a962b070b756346a475c0e2ff64244d284bb1`；本轮没有修改脚本。`bash -n` 返回 0。
- 启动前端口 8021 被上轮任务 API PID `41096` 占用，GPU 4/5 上只有该任务的计算进程。核实其模型、端口、TP2、图模式和 metrics 中运行/排队请求均为 0 后，仅向该 PID 发送 `SIGTERM`；复查端口关闭、GPU 4/5 无计算进程、旧 PID 退出。容器保持运行。
- 从容器内工作根执行 `bash ./start-model.sh`，没有注入 `PYTHONPATH` 或缓存环境变量。脚本启动新 API PID `43939`；进程命令行与脚本相符，`CUDA_VISIBLE_DEVICES=4,5`，`PYTHONPATH` 不存在。
- 脚本将日志写到根目录 `./service.log`。启动后将该新日志原 inode 移至 `<root>/04-runs/user-current-script-20261001T002902Z-43939/service.log`，核实 `/proc/43939/fd/1` 仍指向该文件，根目录没有留下 `service.log`；本次结果和脚本哈希也写入同一运行目录。

## 实测结果

| 检查 | 结果 |
| --- | --- |
| 模型与有效配置 | Plugin 注册自动激活，解析为 `MiniCPMV4_7ForConditionalGeneration`；BF16、GPU 4/5、TP2、`--gpu-memory-utilization 0.8`、前缀缓存开启、`--mm-processor-cache-gb 0`、`FULL_AND_PIECEWISE`。脚本省略 `--max-model-len`，日志与 `/v1/models` 均显示默认 `262144`，不再是上轮的 `100000`。 |
| 图捕获 | mixed prefill/decode 的 `PIECEWISE` 51/51，decode 的 `FULL` 51/51；日志中未出现本轮 Triton `Errno 16`。 |
| 就绪 | `/health` 与 `/v1/models` 均为 HTTP 200；后者返回模型名 `MiniCPMV4.7-35B` 和 `max_model_len=262144`。 |
| 最小请求 | 文本两项、红蓝单图及两次图片 replay 共 6/6 PASS；`<run>/minimal-service-check.json` SHA-256 `cf78944c2849a132071675327cd5892ad8398b84fbea014c49bc8e598543cb51`。 |
| 服务保留 | 验证后 API PID `43939` 存活；GPU 4/5 分别约占 65,016/65,018 MiB。 |

## 脚本边界

这份脚本**可以实际启动并完成最小图文推理**，但 `nohup ... &` 的 shell 返回码先于服务就绪，单看脚本退出码不足以证明成功。它没有端口或 GPU 占用检查；本轮依靠执行前的人工核实避免覆盖其他服务。`./service.log` 在原脚本中位于工作根，重复运行会截断已有同名日志；本轮只因启动前确认该文件不存在才直接执行，随后将新日志归档。

脚本不再设置 `MINICPM_TRITON_CACHE_BASE`、`XDG_CACHE_HOME`、`TORCHINDUCTOR_CACHE_DIR`、`TMPDIR` 或 `FLAGGEMS_ENABLE_OPLIST_PATH`。实际日志显示 vLLM 编译缓存写入 `/root/.cache/vllm/`；FlagGems oplist 实际写在 `/tmp/flaggems_enable_oplist.txt`（本轮时间戳 2026-10-01 00:34:48 UTC），都未按工作区要求限制在 `06-cache/` 或 `04-runs/`。本轮成功不证明在原 Parastor 共享 Triton 缓存条件下的并发问题已经消失。若要把当前文件作为可重复的最终启动器，仍需补上资源占用保护、日志/缓存目录和就绪验证；不能把这次短请求回归当作 262,144 token 长上下文、视频、正式精度或性能结果。mixed prefill/decode 仍为分段图，未满足 active profile 的正式 full graph 验收条件，`framework.yml` 保持 `environment_ready`。
