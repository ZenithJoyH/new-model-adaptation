# H100-149 TP2 历史脚本服务验证（2026-09-30）

> 之后用户改写并再次精简了同一路径的 `start-model.sh`。2026-09-30 后继脚本
> SHA-256 为 `4e4982c7ef9c447c0e2759e569c46d31da9931e224a3aae675aeebe343a9ec51`；
> 2026-10-01 后继精简脚本见[精简验证](launcher-simplification-2026-10-01.md)，当前用户再改脚本见[新脚本验证](user-revised-launcher-validation-2026-10-01.md)。
> 本页的启动和图文通过结果只绑定下文 SHA-256 为 `0dcb41a752dcfcc43fa07837791b74ca95db26ffbca5332f679e68040458239c` 的历史脚本；
> 2026-09-30 后继文件的实际启动结果见[已安装 Plugin 的服务验证](service-validation-installed-plugin-2026-09-30.md)，变更过程见[问题 007](../adaptation/007-user-edited-launcher-self-containment.md)。

## 身份与范围

- Host：`H100-149`；容器：`MinicpmV4.7-35B`；镜像：`sha256:36fe2dcc73d074f6a35e7111f5bc597d7830ae4ba44e0e436623cb71ad44ddeb`。
- 宿主机和容器工作根均为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`。精简后的 `start-model.sh` 两侧设备号 `45`、inode `213641374989` 一致。
- 权重：`/data/models/MiniCPM-V-4.7/weights/35b-a3b`；H100 GPU 4、5；TP2；BF16；vLLM `0.24.0+cu129`。
- Plugin 基础 HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`，仅 `vllm_fl/__init__.py` 修改和新 `vllm_fl/models/minicpmv4_7.py` 未提交；后者 SHA-256 `2e96de24dc2aa003ed21b146e602102bf9ee30ca075dfe6a8986cb45b006213e`。FlagGems HEAD `da6727e38f6f8eedef6cba43695a87b4996f9eca` 且工作树干净。只读 vLLM 4.6 视觉适配文件 SHA-256 `fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`。

## 用户选定的图模式和结果

显式 `cudagraph_mode=FULL_AND_PIECEWISE`，保留前缀缓存。精简版脚本启动后的日志确认 mixed prefill/decode `PIECEWISE` 捕获 5/5、decode `FULL` 捕获 4/4，随后 `Application startup complete`；`GET /health` 和 `GET /v1/models` 均返回 HTTP 200。当时进程 PID `29991`，实际参数含 TP2、GPU 4/5、50,000 token、`max_num_seqs=10`、端口 8019 与显式图模式。该任务服务后来在核实空闲与进程身份后停止，以验证新脚本；本页保留历史回执。

精简版原始结果均在 `H100-149:/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/service-full-piecewise-tp2-20260930T095238Z-29991/`：

| 证据 | 结果 | SHA-256 |
| --- | --- | --- |
| `server.log` | 图捕获、模型加载与 API 就绪 | 保留原始日志，未复制到本地 |
| `minimal-service-check.json` | 文本 2、红蓝图 2、变输入 replay 2，6/6 正确且均 `finish_reason=stop` | `89cc6be6efba4e7e4d23bdc71500a5d4f35e3a6fb0a2efeda2743de6e774d5dd` |
| `sanity10-no-thinking.json` | 五道算术题与五道纯色图题，10/10 正确、零请求错误；客户端十并发，观测引擎运行峰值 9、等待峰值 0；耗时 15.635 秒 | `8b5b34bf79335f9bd0ddfa731a404d91ff1e22c821b5ba92f9fcb918ec00ab28` |

小批量短答案请求冻结 `chat_template_kwargs: {enable_thinking: false}`、`max_tokens=256`、`temperature=0`；该设置避免默认 thinking 在短题中耗尽输出长度。15.635 秒是这一次已预热功能回归的墙钟时间；前缀缓存开启，不是正式性能回执。视频、正式精度与性能未测。

## 当时的根目录启动脚本

宿主机与容器路径均为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/start-model.sh`；权限 `0755`；精简版 SHA-256 `0dcb41a752dcfcc43fa07837791b74ca95db26ffbca5332f679e68040458239c`。`bash -n` 通过，未含代理或其他密钥。已实际运行精简版并核实上面的图捕获、API、结果与两张 GPU 的模型占用。脚本把日志放在 `04-runs/` 唯一目录，缓存定向至 `06-cache/`，不会停止或重启容器。端口 8019 已被占用时验证过会拒绝启动，且没有创建新运行目录；GPU 4/5 上已有计算进程时也会拒绝共享。

用户要求删去非必要设置后，删除了 `HF_HOME`、`HF_MODULES_CACHE`、`VLLM_CACHE_ROOT`、重复的 `PYTHONDONTWRITEBYTECODE=1` 和无实际用途的运行目录打印。实测只设置 `XDG_CACHE_HOME=.../06-cache` 时，Hugging Face、Transformers 和 vLLM 分别推导至 `06-cache/huggingface`、`06-cache/huggingface/modules` 与 `06-cache/vllm`；该历史服务日志实际使用 `06-cache/vllm/torch_compile_cache`。容器本身继承 `PYTHONDONTWRITEBYTECODE=1`，精简版进程环境核实未设置上述三个冗余缓存变量。`TORCHINDUCTOR_CACHE_DIR` 与 `MINICPM_TRITON_CACHE_BASE` 当时显式保留，以确保前者不落入默认临时目录、后者按 PID 隔离 Triton 缓存。

保留的显式设置及理由：

| 设置 | 理由 |
| --- | --- |
| `PYTHONPATH`、`VLLM_PLUGINS=fl`、`--model-impl vllm` | 选用已核实的 editable Plugin 和模型注册路径，避开镜像旧 namespace 遮蔽。 |
| `CUDA_VISIBLE_DEVICES=4,5`、TP2、`--gpu-memory-utilization 0.8`、`--max-num-seqs 10` | 锁定实测设备与并行/资源上限，避开其他 GPU 的服务。 |
| 模型路径、服务名、`--trust-remote-code`、BF16、50,000 token | 锁定权重、checkpoint 自带处理逻辑和已验证的推理配置。 |
| loopback 端口 8019 | 与本轮验证一致；避免把尚未正式验收的服务直接暴露到外部。 |
| `--mm-processor-cache-gb 0` | canvas M-RoPE 需要未缓存的图像/视频目标尺寸。 |
| `--enable-prefix-caching` | 非性能服务的 profile 约束；性能专用禁用参数未进入最终脚本。 |
| `FULL_AND_PIECEWISE` | 用户明确选定，并由当前 GDN backend 的实际图捕获验证。 |
| SDPA 黑名单追加两项 | 排除本模型视觉路径上已复现的 CUDA 非法地址算子；见问题 004。 |
| `XDG_CACHE_HOME`、`TORCHINDUCTOR_CACHE_DIR`、`MINICPM_TRITON_CACHE_BASE` | 集中常规缓存于 `06-cache/`，使 TorchInductor 不使用默认临时目录，并隔离各进程 Triton 缓存。 |

## 切换过程、源码审查与限制

首次切换前核实旧服务 PID `24553` 的模型、端口、TP2、图模式和进程树，metrics 显示运行/等待均为 0；仅对该任务进程发送 SIGTERM。复查整棵进程树退出、端口关闭，GPU 4/5 为 0 MiB，随后通过根目录脚本启动 PID `27353`。精简脚本时再次核实该进程配置和空闲状态，仅对 PID `27353` 发送 SIGTERM；复查 API、EngineCore、两名 TP worker 全部退出，端口关闭且 GPU 4/5 无计算进程，随后通过精简脚本启动 PID `29991`。两次切换均未停止或重启容器，前一版运行目录 `04-runs/service-full-piecewise-tp2-20260930T062344Z-27353/` 作为历史证据保留。

实际源码差异范围只有 Plugin 注册 9 行和新 129 行模型适配；`git diff --check`、适配文件 AST 解析均通过。共享 vLLM 与 FlagGems 未修改；该验证仅覆盖 H100、当前 wheel、TP2 的文本与图片路径，不能推断视频或其他平台。SDPA 黑名单是运行缓解，退出条件是两条实现的根因修复及同配置视觉/图回归；GDN 全 mixed 图阻断和退出条件见[问题 005](../adaptation/005-gdn-full-graph-limit.md)。未提交、推送或创建 PR。

此运行配置满足用户选定的服务验证；`FULL_AND_PIECEWISE` 的 mixed prefill 是分段图。现行 active profile 明确规定分段/可断图不能通过正式 execution-mode，后续正式 accuracy、performance、evidence、summary 也未执行；不得把本功能验证记为正式验收或 `optimized`。当前 vLLM 还提示 Mamba `align` 模式下的前缀缓存支持属实验性，须在正式精度回归中重点核对重复请求与长上下文。
