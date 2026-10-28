# 已安装 Plugin 的 TP2 服务脚本验证（2026-09-30）

> 本页记录 2026-09-30 脚本的历史验证。PID `38060` 已于 2026-10-01 经空闲核实后停止；后继精简脚本见[精简验证](launcher-simplification-2026-10-01.md)，当前用户再改脚本见[新脚本验证](user-revised-launcher-validation-2026-10-01.md)。

## 身份与范围

- Host：`H100-149`；运行中的容器：`MinicpmV4.7-35B`；模型：`/data/models/MiniCPM-V-4.7/weights/35b-a3b`。
- 宿主机与容器工作根均为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`，其 bind mount 已核实。该次可执行脚本两侧路径均为 `<root>/start-model.sh`，模式 `0755`，SHA-256 `4e4982c7ef9c447c0e2759e569c46d31da9931e224a3aae675aeebe343a9ec51`。
- 该次服务运行目录：`<root>/04-runs/service-full-piecewise-tp2-20260930T144750Z-38048/`；PID 文件记载容器内 API PID `38060`。服务监听 `127.0.0.1:8021`，GPU 4/5，TP2，BF16，100,000 token 上限，`FULL_AND_PIECEWISE`，前缀缓存开启，多模态处理器缓存关闭。
- Plugin 基础 Git HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`，含本次未提交的 `vllm_fl/__init__.py` 与 `vllm_fl/models/minicpmv4_7.py` 适配；已在容器内通过 `pip install --no-index --no-deps --no-build-isolation --no-cache-dir --no-compile --force-reinstall --config-settings editable_mode=compat -e /vllm-workspace/vllm-plugin-FL` 安装。distribution `0.3.0rc2.post1+g3a27a6fb2.d20260930` 的 `direct_url.json` 指向该 editable 源码。vLLM `0.24.0+cu129`；FlagGems `da6727e38f6f8eedef6cba43695a87b4996f9eca`；容器镜像 `sha256:36fe2dcc73d074f6a35e7111f5bc597d7830ae4ba44e0e436623cb71ad44ddeb`。

## 运行与结果

| 检查 | 结果与原生证据 |
| --- | --- |
| 不依赖 `PYTHONPATH` 的安装 | 新容器进程中 `PYTHONPATH=None`，`vllm_fl` 与 4.7 adapter 均解析到 `/vllm-workspace/vllm-plugin-FL/`；服务进程 PID `38060` 的启动环境也没有 `PYTHONPATH`。 |
| 逐进程 Triton 缓存 | `/usr/local/lib/python3.12/dist-packages/minicpm_triton_cache.pth`（SHA-256 `1bc91fb4822188496e394c12aa7039ffaa8300b23a1af05ae1445031deac1f5e`）仅在设置 `MINICPM_TRITON_CACHE_BASE` 时加载 `<root>/01-environment/sitecustomize.py`。独立进程验证最终 `TRITON_CACHE_DIR` 包含自身 PID。缓存位于 `<root>/06-cache/`。见[问题 003](../adaptation/003-triton-cache-concurrency.md)。 |
| 脚本安全与语法 | `bash -n` 通过；在端口 8021 已占用时脚本拒绝启动；PID `34269` 空闲后只停止该任务服务，核实端口关闭和 GPU 4/5 无计算进程，再由该次脚本启动 PID `38060`。容器始终运行。 |
| 实际配置和图捕获 | `<run>/server.log` 与 `/proc/38060/cmdline` 证实 `--mm-processor-cache-gb 0`、前缀缓存开启、TP2、100,000 token 和 `FULL_AND_PIECEWISE`；mixed prefill/decode 的 `PIECEWISE` 51/51、decode 的 `FULL` 51/51 捕获完成。 |
| API 和最小图文 | `/health`、`/v1/models` 均返回 HTTP 200；两条文本、两张不同图片、两次重复图片请求 6/6 通过。原生结果 `<run>/minimal-service-check.json`，SHA-256 `949bcae3676abaef695bbb346fbf73b6831cc7cdbb327a63ad73889856fb9538`。 |
| 十并发混合请求 | 5 文本 + 5 图片 10/10 通过，客户端并发 10，指标最大同时运行 9、等待 0。原生结果 `<run>/sanity10-no-thinking.json`，SHA-256 `30aec853f3c90b5ecbb3fca44bea4e1b68f984b7d01d3ca3b028e379377e9827`。此为功能与并发 sanity，不是正式性能回执。 |
| 运行目录与设备 | `server.pid`、`server.log`、两份 JSON 结果和 FlagGems oplist 均在 `<run>/`；启动环境的临时文件与缓存分别在 `05-tmp/`、`06-cache/`。验证时 GPU 4/5 分别占用约 65,115/65,077 MiB。 |

最终启动脚本中保留的显式环境变量分别用于 GPU 4/5 放置、避开已知视觉 SDPA 问题实现、将临时文件与缓存约束在批准目录，以及逐进程 Triton 缓存隔离；`FLAGGEMS_ENABLE_OPLIST_PATH` 将实际生成的 oplist 留在运行目录。显式 vLLM 参数用于服务地址、TP2、精度、用户选定的 100,000 token 和图模式、显存上限、权重远程代码、前缀缓存与本模型的多模态处理器缓存约束。脚本不设 `PYTHONPATH` 或 `VLLM_PLUGINS`；安装后的 `fl` entry point 自动激活。

源码差异在安装后重新审查：Plugin 仍只有 `vllm_fl/__init__.py` 的 9 行注册变更和 SHA-256 `2e96de24dc2aa003ed21b146e602102bf9ee30ca075dfe6a8986cb45b006213e` 的新 129 行 `vllm_fl/models/minicpmv4_7.py`，AST 解析通过；安装没有增加源码改动。注册名仅针对 4.7，原有 4.6 与其他模型继续走既有路径；4.7 的 canvas M-RoPE 缺少多模态尺寸时显式报错。H100 TP2 的文本与单图已验证，视频、其他硬件和完整精度未覆盖。FlagGems 工作树干净，vLLM 未修改；无提交、推送或 PR。

## 限制与后续

本次只验证短文本、单图及十并发 sanity，没有提交 100,000 token 极限长上下文、视频、正式精度或按项目契约运行的正式性能结果。该图模式的 mixed prefill/decode 是分段图；根据当前 active profile，不能据此把正式 graph acceptance 标为通过。`deployment.fingerprint` 仍绑定较早候选，需要按原生证据契约重建后才能提升状态。该次脚本对应服务在验证后保持运行，随后于 2026-10-01 被精简脚本的任务服务接替；未改动 vLLM 或 FlagGems 源码，也未提交或推送。
