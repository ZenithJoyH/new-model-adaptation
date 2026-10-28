# MiniCPM-V-4.7-1B / H100-149 功能与服务验证

验证日期：2026-09-28、2026-09-30（Asia/Shanghai）。目标 Host `H100-149`、容器
`MinicpmV4.7-1B`（ID `4642fce472209069ab927e6bf6af7bc1ccb3443f2fa85d4a6f76b65e92a5c637`）、
权重 `/data/models/MiniCPM-V-4.7/weights/1b`，工作根 Host/容器均为
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`。容器镜像为
`harbor.baai.ac.cn/flagos-inner-models-release/xingchen4-nvidia003-gems5.3.5-tree0.6.2-cxnone-plugin0.0.0-vllm0.24.0-cp312-pt211-cu129-x64-580.105.08:202609070901`，
image ID `sha256:d0af16489bc171d5434fc225c7afd89d32da7946af53655b9ad6dc7b50c745ca`。
Plugin `main@3a27a6fb2d514cdf55c00481bf813225dac63319` 加当前未提交差异；
FlagGems `master@da6727e38f6f8eedef6cba43695a87b4996f9eca`；
vLLM wheel `0.24.0+cu129`，未修改。

## 结果与可复核证据

| 检查 | 结果 | Host/容器同路径原始证据（工作根相对路径） |
|---|---|---|
| eager 文本 | 目标权重加载并生成中文；前缀缓存启用 | `04-runs/eager-text-cudnn-filter-v8-20260928/run.log`，SHA-256 `1b95f296504fd43822c6f7d521c4582c2ca15ff95baf13e43862387683e2cd55` |
| eager 单图 | 224×224 红图识别为红色 | `04-runs/eager-image-v1-20260928/run.log`，SHA-256 `63d1856d2897e7d4efccae9d0fa058ec55ff081b6ea75c35c75ff7e648ef2d17` |
| full graph 优先尝试 | 显式请求 `FULL`，GDN backend 自动降为 mixed `PIECEWISE` + decode `FULL`，不判通过 full | `04-runs/full-graph-v1-20260928/run.log`，SHA-256 `269ae025284d0062d7ffb0741aeb9c071fb0eac8bc4da3a5b6f581efe16f4808` |
| decode-full 回归 | 修正 canvas decode delta 后，显式 `FULL_DECODE_ONLY` 捕获 2/2；文本与单图完成 | `04-runs/decode-full-v2-delta-fix-20260928/run.log`，SHA-256 `de2430de7b9def2938388a3cc5ed859d929112077360615d0e9a9cad33277a94` |
| 多图与视频 | 红/蓝双图、红/蓝双帧视频答案均按顺序命中，`stop` | `04-runs/decode-full-mm-variants-v1-20260928/run.log`，SHA-256 `6f551c3f26763d1c63babfd3663c6670e6238b3a4c004677ec31531d0302211f` |
| Plugin 契约测试 | canvas delta 与纯文本路径，2/2 通过；4.7 注册命中、4.6 保留、4.8 未命中 | `04-runs/plugin-unit-delta-20260928/pytest.log`，SHA-256 `863bdf2648cbe42c254e95516805bdaf9ae5e52196317161489e8b280bd4d661`；注册检查 2026-09-28 实时执行 |
| OpenAI API | `/v1/models` 身份正确；文本 42 与红图回复均为 HTTP 200、`stop` | `04-runs/service-smoke-v1-20260928/run.log`，SHA-256 `f1b5b2a41a3734e25ba26521f5cc7066eb236efc7e598d8802229cd7e9a27cad` |
| 固定十并发功能检查 | 10/10 逐条正确、HTTP 200、`stop`；客户端请求时间重叠，无 timeout | `04-runs/ten-concurrent-v1-20260928/run.json`，SHA-256 `bd1c4bb390bd59de06e24af31606223b75931b935153a0740fba6a849933beb9` |
| 初次根级脚本实启 | 初次 `FULL_DECODE_ONLY` 启动；decode FULL 捕获 7/7、API 就绪；文本/图片再次通过 | `04-runs/model-service/service.log`、`04-runs/final-launcher-smoke-20260928/run.log`；后者 SHA-256 `4c5386fb8f562fc89ef48e9ba82f90b57a302318f9ca73a69dd9a8e9958d6ba3` |
| 更新后根级脚本实启 | 显式 `FULL_AND_PIECEWISE`，prefill PIECEWISE 11/11、decode FULL 7/7；API 就绪，文本/红图完成 | `04-runs/model-service/service.log` 的 14:23 新启动段；`04-runs/full-and-piecewise-root-launcher-smoke-20260928/run.log`，后者 SHA-256 `2a3dc0a63be5f4c9cb0939803d1f113ef3d90a07df8212f5d68f9c41747b4cd5` |
| 2026-09-30 根级脚本精简 | CLI 参数保持必要配置；结构 48→33 行。实启后缓存开启、图模式不变，文本/红图再次通过 | `04-runs/model-service/service.log` 的 EngineCore PID 13398 启动段；`04-runs/simplified-launcher-smoke-20260930/run.log`，后者 SHA-256 `9ef6aa116ae3461604ceb228dae6815894c63b2d9d5474a536fd81abc97d6216` |
| 2026-09-30 冗余缓存变量删除 | 脚本进一步缩至 30 行；有效前缀缓存仍开启，prefill PIECEWISE 11/11、decode FULL 7/7，文本/红图再次通过 | `04-runs/model-service/service.log` 的 EngineCore PID 14063 启动段；`04-runs/minimal-env-launcher-smoke-20260930/run.log`，后者 SHA-256 `7729ceaed78e973c4af17c04f53834a5ff3248aa94e674dd1970a5da03ab6281` |
| 2026-09-30 当轮 29 行脚本 | 仅预建日志和临时目录；前缀缓存开启、prefill PIECEWISE 11/11、decode FULL 7/7；明确回执中的文本/红图均通过 | `04-runs/model-service/service.log` 的 EngineCore PID 14629 启动段；`04-runs/minimal-final-launcher-confirmed-20260930/run.log`，后者 SHA-256 `027ed73d7e699218a1c64821208b5d4affa7551dd7f77d6c4558bb28735de1be` |
| 2026-09-30 Plugin 重装及 28 行脚本 | 不设 `PYTHONPATH` 的新服务激活 Plugin；前缀缓存开启、prefill PIECEWISE 11/11、decode FULL 7/7，文本/红图通过 | `04-runs/plugin-install-compat-20260930/pip.log`，SHA-256 `5676018e1fd9b234d602cdc8a41c64583fbd49cd22274be3beddb0e50ee6becf`；`04-runs/installed-plugin-launcher-smoke-20260930/run.log`，SHA-256 `c0c1aed7564bc52113a4973ecdf87d3761319ca2e03f41264ae14d5d278028b2` |
| 2026-09-30 用户修改后的根级脚本 | `bash -n` 通过；端口预检、运行目录约束和已验收 API 身份已改变，未安全实启，不将旧服务结果计入新脚本 | 当前 `start-model.sh` SHA-256 `db435de265683fc6ea849b3c01a528762df0f560c3881516a5d01ed1c2e2193b`；问题见 [005](../adaptation/005-launcher-minimality.md#2026-09-30-用户修改后的当前脚本核查) |

十并发请求用固定的文本、红/蓝/绿单图和红蓝双图构成，并逐条检查最终回答，
客户端并发度为 10、时间窗口重叠；36.257 秒完成，延迟中位数 32.350 秒，
记录的 GPU1 前/后显存为 47015/47275 MiB。这是功能及粗略性能健康检查，
不是正式 benchmark 或 GPQA sanity manifest；其图像请求延迟仍需单独分析，
不得由此宣称性能已优化。

## 服务与启动脚本

本报告首次验证时的服务由根级
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/start-model.sh` 在同路径容器内启动。
文件 SHA-256 `ca544ac90cacb1c6b7fccf82e8585490af10d8c4c91e7e1a8ddf68bc79531ae8`；
Host/容器设备号:inode 均为 `45:232989235970`，权限 0755，`bash -n` 通过。
端口 `127.0.0.1:8308`，served model `minicpm-v-4.7-1b-fl`，物理 GPU1、TP1，
服务 API PID 10413、EngineCore PID 10625（启动后现场记录；PID 会随再次启动变化）。
脚本在端口被占用时确实拒绝启动，不停止或替换其他服务。
切换前仅对本任务此前启动且已核实模型/端口的 API PID 9736 发出
`docker exec MinicpmV4.7-1B kill -TERM 9736`；8308 关闭、PID 9736/9948 消失、
GPU1 释放、适配容器始终 `Up` 后，才用根级脚本启动。服务就绪与身份已再次核对。

同日用户要求显式开启 `FULL_AND_PIECEWISE` 后，先以
`01-environment/start-service-full-and-piecewise-20260928.sh`（API PID 11048）
独立验证。其有效配置、图捕获、文本/图片 API 冒烟结果和切换过程见
[004 问题记录](../adaptation/004-gdn-full-graph.md#2026-09-28-显式-full_and_piecewise-服务验证)。
用户随后要求根级启动脚本也采用此模式；实际只修改一行 graph 参数，
通过 `--check --diff`、哈希、语法和实启验证。当时服务由更新后的
`start-model.sh` 启动，API PID 11580、EngineCore PID 11792。
脚本 Host/容器同路径、同设备号:inode `45:232998688002`、权限 0755，
SHA-256 `b7221238606a5f193a8ec0153332328e6e1b9ecedf7cf7da28c99ca45eb729b6`。
原适配容器保持运行，仅停止/重启本任务模型服务；命令、原因及结果详见
[004 的根级脚本记录](../adaptation/004-gdn-full-graph.md#2026-09-28-根级启动脚本同步)。

2026-09-30 应用户要求复核最小启动参数。省略 `--enable-prefix-caching` 的
单变量诊断使本模型 EngineCore 的有效值变为 `False`，故立即恢复并实启确认
`True`。随后先精简端口保护和目录创建代码，再删去由其他根目录变量覆盖的
`HF_HOME`、`VLLM_CACHE_ROOT`、`TORCHINDUCTOR_CACHE_DIR`，最后删去缓存目录预建；
按用户要求，随后在容器内从原 checkout 用兼容模式 editable 重装适配后 Plugin，
并从脚本移除 `PYTHONPATH`。当轮已实启根级脚本 SHA-256
`14f1019d4378e09f5c52e54933487cd2ea612c6ab4208e0e7cbf49a21487c651`，
Host/容器设备号:inode 均为 `45:221917417992`，权限 0755，验证日期 2026-09-30。
现存 API PID 15252、EngineCore PID 15464；当轮负载、资源上限、前缀缓存、
`FULL_AND_PIECEWISE` 和日志/缓存边界均未改变。脚本拒绝被占用的 8308 端口，
随后在端口释放后实启成功。问题诊断、差异与恢复过程见
[001](../adaptation/001-editable-import-shadowing.md) 和
[005](../adaptation/005-launcher-minimality.md)。
29 行脚本冒烟的首轮 Ansible SSH 返回通道中断；保留其日志后，经连通性检查，
在新目录重跑并取得 `ok=4, failed=0, unreachable=0` 的完整回执。

同日用户在原路径修改了启动脚本，当前文件 SHA-256 为
`db435de265683fc6ea849b3c01a528762df0f560c3881516a5d01ed1c2e2193b`。
旧服务仍正常运行，但其进程参数属于前述 28 行脚本；本次只做语法、映射、
现有服务和写入边界检查，未执行新脚本。当前文件不能继承上述实启或功能回执，
具体阻塞见 [005](../adaptation/005-launcher-minimality.md#2026-09-30-用户修改后的当前脚本核查)。

脚本保留的参数依据：`--model-impl vllm` 固定 Plugin 适配路径，
`--trust-remote-code` 读取权重内目标模型与处理器，`--max-model-len 50000`
遵守本 profile 的首次运行长度，`--max-num-seqs 32` 为并发容量上限，
`--gpu-memory-utilization 0.65` 限制 GPU1 占用，
`--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}'` 固定用户要求且
实启验证的运行模式，`--enable-prefix-caching` 固定非性能服务要求；host/port/model name
固定服务暴露范围及 API 身份。`CUDA_VISIBLE_DEVICES=1` 固定空闲设备；
Plugin 已直接以兼容模式 editable 安装到容器，不需要在脚本设置 `PYTHONPATH`；
`VLLM_FL_FLAGOS_BLACKLIST_APPEND` 仅过滤已定位引发 CUDA 错误的两个 attention
注册函数，其根因及退出条件见 [003](../adaptation/003-flaggems-cudnn-attention.md)。
`XDG_CACHE_HOME`、`TRITON_CACHE_DIR`、`TMPDIR` 将运行写入限制在
`06-cache/` 和 `05-tmp/`，其中 Hugging Face、vLLM 与 TorchInductor
分别沿用上述根目录变量导出的默认路径；vLLM 与 Triton 自行创建缓存目录。
`PYTHONDONTWRITEBYTECODE=1` 防止 Python 在只读源码和权重目录写缓存；
日志在 `04-runs/model-service/`。脚本无密钥，未携带诊断/性能专用开关，
尤其没有 `--no-enable-prefix-caching`，也不会停止或重启容器。

## 当前结论和剩余工作

服务与上述最小功能验证通过；正式验收可用的最低图级别为 `decode-full`。
现存服务按用户要求运行显式 `FULL_AND_PIECEWISE`，其中 prefill 为
PIECEWISE、decode 为 FULL；不能将这次运行计作全量图通过。
用户本轮要求先完成服务与功能验证，正式精度数据集/阈值尚未冻结；
未运行 FlagEval 全量精度或无缓存性能评测，不标记正式 acceptance 通过或
`optimized`。项目原生 framework-check 回执和部署指纹尚未生成，
因此 `framework.yml` 暂不把阶段/子步骤写成 passed；后续补齐冻结配置和
原生证据后再更新正式状态。FlagGems cuDNN attention 的最小独立复现、
高分辨率/长上下文、TP>1 和其他硬件平台仍未验证。

## 实际差异审查

2026-09-28 确认 Plugin 的 PR base `origin/main` 与当前 `HEAD` 同为
`3a27a6fb2d514cdf55c00481bf813225dac63319`，开始前工作树干净，
无继承差异。当前只有 `vllm_fl/__init__.py` 的 4.7 懒注册改动，
以及模型专用 shim 和聚焦测试两个未跟踪文件；未暂存、提交或推送。
`git diff --check` 通过。逐文件设计、调用方影响、源文件哈希与未覆盖范围
记录在 [002 问题审查](../adaptation/002-v47-model-integration.md#2026-09-28-实际差异设计审查)。
4.6 注册路径经检查保持可用；未知 4.8 未命中。其他模型的整模运行、
其他平台与 TP>1 均不在本轮实测范围内。
