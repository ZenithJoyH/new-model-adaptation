# 003：TP2 权重加载时 Triton 缓存临时目录清理失败

## 元数据

- 状态：`mitigated`（逐进程隔离的受控对照通过，文件系统竞态的底层根因仍是假设）；首次出现 2026-09-28，最后验证 2026-09-30
- Host / 容器：`H100-149` / `MinicpmV4.7-35B`
- 本文的 `<root>` 均指已核实宿主机与容器同路径的 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`。
- Plugin 基础 revision：`3a27a6fb2d514cdf55c00481bf813225dac63319`（现有未提交适配）；FlagGems `da6727e38f6f8eedef6cba43695a87b4996f9eca`；vLLM `0.24.0+cu129`
- 运行：`04-runs/eager-tp2-20260928/server.log`；GPU 4、5，TP=2，BF16，eager，`max_model_len=50000`，`TRITON_CACHE_DIR=<root>/06-cache/triton`

## 签名和首错

引擎已解析 4.7 Plugin 类并创建两个 TP worker；TP0 开始加载 safetensors。TP1 在 `vllm` vocab padding → `FlagGems` H100 `fill_scalar_` → Triton 编译的缓存写入路径首先抛出 `OSError: [Errno 16] Device or resource busy`。报错点是 `triton/runtime/cache.py:143` 对 `<root>/06-cache/triton/<key>/tmp.pid_1817_...` 执行 `os.removedirs`。该临时目录之后为空但残留；`/public` 挂载的文件系统是 `parastor`。后续 `WorkerProc initialization failed` 只是传播症状。

## 假设、对照和边界

两个 TP 进程在相同共享 Triton 缓存键下并发编译可能触发该文件系统的目录删除竞争。首次记录时尚未通过受控复现确认；该轮还纠正了 `enable_prefix_caching=False`，故不能把其成功单独归因于缓存隔离。后续 2026-09-30 的同参数对照见下文，支持逐进程隔离为有效缓解；具体文件系统或库的底层责任仍需最小双进程复现，不能认定为 FlagGems 或 Triton 产品缺陷。

缓存隔离放在本任务 `01-environment/` 运行配置，写入仍限于批准的 `06-cache/`；不更改 FlagGems、vLLM 或通用 Plugin 算子。若该轮仍失败，检查具体 `tmp.pid` 路径与最早错误，不能删除整个缓存树或掩盖报错。

## 服务处理与验证

首次服务由本任务 `docker exec -d` 启动，容器内 API PID 1580。因非性能测试应开启前缀缓存，先向确认命令行匹配的 PID 1580 发送 `SIGTERM`；其 EngineCore 已退为 zombie，但 API 未退出，随后对同一已核实 PID 发送 `SIGKILL`。两次操作均仅针对本任务服务，未停止容器或其他 vLLM 进程。之后 GPU 4、5 显存均回到约 4 MiB，原始日志保留。下一轮需记录启动命令、前缀缓存有效值、首错、GPU 占用和服务 readiness。

2026-09-30 对用户脚本（SHA-256 `b3bf5abd0353e7ad35747e822f43204684569c4bc17206ac5dc4978522998284`）做了更严格对照：均为 GPU 4/5、TP2、前缀缓存开启、`FULL_AND_PIECEWISE`、100,000 token，且均在不设置 `PYTHONPATH` 的已安装 Plugin 环境中启动。共享 `TRITON_CACHE_DIR` 的首次和全新目录重试分别在 `<root>/04-runs/user-script-8021-100k-20260930T135248Z/service.log`、`<root>/04-runs/user-script-8021-100k-fresh-cache-20260930T1408Z/service.log` 留下 `triton/runtime/cache.py:143` 的 `os.removedirs(tmp.pid_...)` → `Errno 16`，API 未就绪。仅将缓存改为逐进程目录后，`<root>/04-runs/user-script-8021-100k-pid-cache-20260930T1416Z/` 完成权重加载、图捕获和图文 6/6、十并发 10/10。此对照支持逐进程隔离作为当前栈的有效缓解，但没有证明 Parastor、Triton 或 FlagGems 中具体哪一方有产品缺陷。

为使该缓解在无 `PYTHONPATH` 的容器进程生效，已安装仅在 `MINICPM_TRITON_CACHE_BASE` 存在时运行的 `/usr/local/lib/python3.12/dist-packages/minicpm_triton_cache.pth`（SHA-256 `1bc91fb4822188496e394c12aa7039ffaa8300b23a1af05ae1445031deac1f5e`）；它执行 `<root>/01-environment/sitecustomize.py`，把 Triton 缓存指向 `<root>/06-cache/triton/<run-id>/pid-<pid>`。新 Python 进程核实 `PYTHONPATH=None` 且路径含自身 PID。2026-09-30 脚本 `<root>/start-model.sh`（SHA-256 `4e4982c7ef9c447c0e2759e569c46d31da9931e224a3aae675aeebe343a9ec51`）使用该变量启动，结果见[已安装 Plugin 的服务验证](../acceptance/service-validation-installed-plugin-2026-09-30.md)。2026-10-01 前一版精简脚本继续使用该变量并实际启动，见[精简验证](../acceptance/launcher-simplification-2026-10-01.md)。钩子属于当前容器运行环境，不进入 Plugin、vLLM 或 FlagGems 源码；容器重建后须重新安装并验证，前一版脚本会在钩子失效时拒绝启动。

2026-10-01 用户再次改写的当前脚本不设置该变量，直接启动后仍完成权重加载、图捕获与图文 6/6，见[新脚本验证](../acceptance/user-revised-launcher-validation-2026-10-01.md)。其 vLLM 编译缓存使用 `/root/.cache/vllm/`，与先前 Parastor 共享目录失败的文件系统条件不同；这不是对原签名或逐进程隔离缓解的反证，也不证明默认缓存位置符合工作区约束。

## 知识复用

目前无完整签名匹配的既有 troubleshooting 条目。本问题尚未验证根因，不推广到其他 Host，也不作为正式验收结论。
