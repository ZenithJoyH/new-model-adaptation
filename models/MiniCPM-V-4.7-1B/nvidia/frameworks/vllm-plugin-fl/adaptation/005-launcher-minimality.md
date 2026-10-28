# 005：服务脚本精简与前缀缓存默认值

## 元数据

- 状态：`launcher-regression-open`（28 行脚本的历史验证仍有效；用户后续修改的当前脚本仅通过静态检查）
- 首次出现/最后验证：2026-09-30
- 模型/平台/Host/容器：`/data/models/MiniCPM-V-4.7/weights/1b` / NVIDIA H100 / `H100-149` / `MinicpmV4.7-1B`
- Plugin / FlagGems / vLLM：Plugin `3a27a6fb2d514cdf55c00481bf813225dac63319` 加本模型未提交差异 / FlagGems `da6727e38f6f8eedef6cba43695a87b4996f9eca` / wheel `0.24.0+cu129`
- 模式：物理 GPU1、TP1、`FULL_AND_PIECEWISE`、OpenAI API `127.0.0.1:8308`

## 问题现象

用户要求根级 `start-model.sh` 只保留必要参数。当时脚本的
`--enable-prefix-caching` 看似可由 vLLM 默认值替代；实际受控删除后，
EngineCore 的有效配置从 `enable_prefix_caching=True` 变为 `False`，
不符合本 profile 的非性能服务要求。API 虽然就绪，不能把这轮配置当作
普通服务的正确启动配置。原始证据为 Host/容器同路径
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/04-runs/model-service/service.log`
中 EngineCore PID `12374` 的 2026-09-30 14:18 启动段。

## 已有经验匹配

| 来源 | 相同点 | 差异 | 可信度 | 本次决定 |
|---|---|---|---|---|
| `framework-profiles/vllm-plugin-fl/profile.yml` 的 prefix-caching 规则 | 非性能运行必须启用 | 不规定 vLLM 当前版本的默认值 | 高 | 实测有效配置，保留显式开关 |
| vLLM `engine/arg_utils.py` 与 `config/cache.py` | 缓存配置存在默认逻辑 | `CacheConfig` 字段默认 `True` 不等于此模型的 EngineArgs 最终默认 | 高 | 以 EngineCore 最终配置为准 |

## 诊断与假设

已验证：`EngineArgs.enable_prefix_caching` 初始默认是 `None`，源码从模型能力
计算 `default_prefix_caching`。此目标栈省略 CLI 开关时，最终 EngineCore
确认为 `False`；恢复开关后确认为 `True`。具体是哪一个模型能力判断返回
`False` 未单独做数值检查，不把通用 `CacheConfig` 字段值当作服务默认值。
`--model-impl vllm` 保留，因为默认 `auto` 在注册未命中时可进入
Transformers fallback；服务需固定已验证的 Plugin 实现。

## 受控尝试

| 轮次 | 唯一实质变量 | 脚本 SHA-256 | 结果与原始证据 |
|---|---|---|---|
| 基线 | 显式 `--enable-prefix-caching` | `b7221238606a5f193a8ec0153332328e6e1b9ecedf7cf7da28c99ca45eb729b6` | 先前 EngineCore `True`，API 和文本/图像通过；见 [功能报告](../acceptance/functional-validation.md) |
| 默认值诊断 | 仅删除缓存开关 | `7f6596d970cabf7ea7d51de058957956b903821cb12f978658aeacd1d4355d3f` | EngineCore PID `12374` 为 `False`，图模式仍为 `FULL_AND_PIECEWISE`；立即判为不合格配置 |
| 恢复 | 只还原缓存开关 | `b7221238606a5f193a8ec0153332328e6e1b9ecedf7cf7da28c99ca45eb729b6` | EngineCore PID `12880` 为 `True`，API 就绪 |
| 结构精简 | CLI 参数和环境变量均不变，仅合并端口检查与目录准备代码 | `b475f6b1d3daf4e60c4e38696bd79aa091d8436080e6dc4db25c026c966f608a` | EngineCore PID `13398` 为 `True`，`FULL_AND_PIECEWISE`，文本/红图通过 |
| 环境变量精简 | 删除 `HF_HOME`、`VLLM_CACHE_ROOT`、`TORCHINDUCTOR_CACHE_DIR`，缩减对应 `mkdir` | `a74f642df4c2f767e9d7f97eca280b5ec99c90699e9d234c5f6d453a4e9a3806` | EngineCore PID `14063` 为 `True`，`FULL_AND_PIECEWISE`，文本/红图通过；缓存仍在工作根 |
| 目录准备精简 | 仅从 `mkdir` 中删除由 vLLM 和 Triton 自行创建的缓存目录 | `f64b3cad59a8c4f237f7ff2701d31c8dfb63a47209fc1235d295efb268007904` | EngineCore PID `14629` 为 `True`，图捕获和 API/文本/红图通过；缓存路径未改变 |
| 容器内安装 Plugin | 兼容模式 editable 重装后只删去 `PYTHONPATH` | `14f1019d4378e09f5c52e54933487cd2ea612c6ab4208e0e7cbf49a21487c651` | EngineCore PID `15464` 为 `True`，Plugin 激活、图捕获和文本/红图通过；见 [001](001-editable-import-shadowing.md) |

所有轮次沿用同一权重、Plugin revision、GPU1、资源上限和正常缓存目录。
每次脚本改动均通过 Ansible `--check --diff` 预览，文件写入前核对旧哈希。

## 根因与解决方法

当前栈的模型相关默认值使省略 `--enable-prefix-caching` 后有效值为 `False`；
对普通服务必须显式保留该开关。其他 CLI 参数也各有具体理由：
host/port/model name 固定本任务 API 边界和身份；`--model-impl vllm` 固定
Plugin 路径；`--trust-remote-code` 解析目标代码；`--max-model-len 50000`、
`--max-num-seqs 32`、`--gpu-memory-utilization 0.65` 固定已验证的长度、
并发容量和 GPU1 占用；`--compilation-config` 保留用户要求的图模式。
`XDG_CACHE_HOME` 使 Hugging Face 默认到 `06-cache/xdg/huggingface`、vLLM
默认到 `06-cache/xdg/vllm`；已在目标容器中解除对应显式变量后实测两路径。
`TMPDIR` 使 TorchInductor 默认到 `05-tmp/torchinductor_root`，实测目录已创建。
独立 Triton 的默认目录是 `~/.triton/cache`，所以继续显式设置
`TRITON_CACHE_DIR=06-cache/triton`。兼容模式 editable 安装已使 Plugin 在
不设 `PYTHONPATH` 时正确导入，因此删去该变量；
`PYTHONDONTWRITEBYTECODE=1` 避免在源码或权重目录生成 `.pyc`；
`TMPDIR` 与 `XDG_CACHE_HOME` 保证其他临时文件和通用缓存的写入边界。
端口绑定检查用于拒绝覆盖其他监听者；当前 vLLM 0.24 的
`entrypoints/openai/api_server.py:create_server_socket` 设置 `SO_REUSEPORT=1`，
不能仅凭 vLLM 自身绑定来保证排斥已有监听者。`mkdir` 必须先准备日志目录
（重定向的目标）和 `05-tmp`（否则 Python 可能回退到根外 `/tmp`）；
当前 vLLM 的 `compilation/backends.py` 和 Triton 的 `runtime/cache.py`
都会递归创建各自缓存目录。进程级 attention 过滤仍是
[003](003-flaggems-cudnn-attention.md) 记录的启动前提。

当轮已验证脚本在同一根路径从 48 行缩为 28 行：保留拒绝替换其他监听者的行为，
不改变模型、资源、前缀缓存或图参数。
没有修改 Plugin、vLLM、FlagGems 或权重。独立排查和更新均未写入产品源码。

## 验证结果

结构精简当轮脚本 Host/容器同路径同设备号:inode `45:233208947458`，权限 0755；
`bash -n`、SHA-256、端口占用拒绝测试、根级脚本实启与 `/v1/models`
身份均通过。2026-09-30 新服务 API PID `13186`、EngineCore PID `13398`；
EngineCore 记录 `enable_prefix_caching=True`、`CUDAGraphMode.FULL_AND_PIECEWISE`，
mixed prefill-decode PIECEWISE 捕获 11/11、decode FULL 捕获 7/7；GPU1 承载
目标 EngineCore，其他服务未操作。复用 `03-acceptance/service_smoke.py`
的文本 42 和红图请求，两项回答正确、`finish_reason=stop`；
`04-runs/simplified-launcher-smoke-20260930/run.log` 的 SHA-256 为
`9ef6aa116ae3461604ceb228dae6815894c63b2d9d5474a536fd81abc97d6216`。
脚本不能停止、重启或删除适配容器；本次仅对核实且空闲的任务 API PID
`11580`、`12162`、`12668` 分别按验证轮次发送 `TERM`，等端口关闭后启动新实例。

2026-09-30 环境变量精简后，当轮脚本 Host/容器同路径同设备号:inode
`45:221881681416`，权限 0755，SHA-256
`a74f642df4c2f767e9d7f97eca280b5ec99c90699e9d234c5f6d453a4e9a3806`。
Ansible `--check --diff`、`bash -n`、端口占用拒绝、根级脚本实启、
`/v1/models` 身份均通过。先确认原服务运行/等待请求均为 0，再只对
本任务 API PID `13186` 执行 `kill -TERM 13186`；端口关闭后启动新服务，
适配容器始终运行。新 API PID `13844`、EngineCore PID `14063`，有效配置
`enable_prefix_caching=True`、`CUDAGraphMode.FULL_AND_PIECEWISE`；
mixed prefill-decode PIECEWISE 捕获 11/11，decode FULL 捕获 7/7。
新服务日志确认 vLLM 编译缓存位于 `06-cache/xdg/vllm`，进程环境中已无
上述三项删去的变量，Triton 与临时目录仍指向批准根下。复用
`03-acceptance/service_smoke.py` 的文本 42 与红图请求，均得到 HTTP 200、
`finish_reason=stop` 和正确回答。原始结果
`04-runs/minimal-env-launcher-smoke-20260930/run.log` 的 SHA-256 为
`7729ceaed78e973c4af17c04f53834a5ff3248aa94e674dd1970a5da03ab6281`。

2026-09-30 目录准备进一步精简后，当轮根级脚本 Host/容器同路径同
设备号:inode `45:233225679362`，权限 0755，SHA-256
`f64b3cad59a8c4f237f7ff2701d31c8dfb63a47209fc1235d295efb268007904`。
Ansible `--check --diff`、两侧哈希、`bash -n`、端口占用拒绝和实启身份通过。
先核实原服务没有运行/等待请求，再仅对本任务 API PID `13844` 执行
`kill -TERM 13844`；端口关闭后重启，容器保持运行。当轮 API PID `14417`、
EngineCore PID `14629`，有效前缀缓存为 `True`，显式图模式
`FULL_AND_PIECEWISE`，prefill PIECEWISE 捕获 11/11、decode FULL 捕获 7/7；
vLLM 编译缓存仍在 `06-cache/xdg/vllm`，Triton 与 TorchInductor 缓存分别
在 `06-cache/triton`、`05-tmp/torchinductor_root`。第一次冒烟的 Ansible
SSH 返回通道中断，虽留下完整日志 `04-runs/minimal-final-launcher-smoke-20260930/run.log`
（SHA-256 `aa0eac2c431438d4f4cb8119becd152f223f4fa9f0d9b0136989205cb01c96ce`），
仍按未完成回执处理。`./scripts/connectivity-check --limit H100-149` 通过后，
在新目录重跑并获得 Ansible `ok=4, failed=0, unreachable=0`；文本 42 和
红图均为 HTTP 200、`finish_reason=stop` 且答案正确。有效原始结果
`04-runs/minimal-final-launcher-confirmed-20260930/run.log` 的 SHA-256 为
`027ed73d7e699218a1c64821208b5d4affa7551dd7f77d6c4558bb28735de1be`。
结束时服务模型身份正确、运行与等待请求均为 0。

2026-09-30 按用户要求重装适配后 Plugin（命令和安装回执见 [001](001-editable-import-shadowing.md)）
并删去 `PYTHONPATH` 后，当轮根级脚本 Host/容器同路径同设备号:inode
`45:221917417992`，权限 0755，SHA-256
`14f1019d4378e09f5c52e54933487cd2ea612c6ab4208e0e7cbf49a21487c651`。
Ansible `--check --diff`、两侧哈希、`bash -n`、端口占用拒绝均通过。
确认旧服务请求运行/等待数均为 0，且 API PID `14417` 的命令是本任务权重、
8308 端口和 `FULL_AND_PIECEWISE` 后，只对该 PID 执行 `kill -TERM 14417`，
端口关闭后用新脚本启动；适配容器始终运行。启动后的 API PID `15252`、
EngineCore PID `15464`，进程环境无 `PYTHONPATH`，Plugin 平台激活；有效配置
`enable_prefix_caching=True`，prefill PIECEWISE 捕获 11/11、decode FULL
捕获 7/7，vLLM 编译缓存仍位于 `06-cache/xdg/vllm`。`/v1/models`
返回正确模型和权重；`03-acceptance/service_smoke.py` 的文本 42、红图请求
均为 HTTP 200、`finish_reason=stop` 且答案正确，Ansible 回执
`ok=4, failed=0, unreachable=0`。原始结果
`04-runs/installed-plugin-launcher-smoke-20260930/run.log` 的 SHA-256 为
`c0c1aed7564bc52113a4973ecdf87d3761319ca2e03f41264ae14d5d278028b2`。
结束时服务运行与等待请求数均为 0。

## 2026-09-30 用户修改后的当前脚本核查

用户在同一 Host/容器路径原地修改 `start-model.sh`。当前文件 Host/容器同
设备号:inode `45:221917417992`、权限 0755、SHA-256
`db435de265683fc6ea849b3c01a528762df0f560c3881516a5d01ed1c2e2193b`；
`bash -n` 通过。此文件尚未实启。现存 API PID `15252`、EngineCore PID
`15464` 仍使用上一轮已实启的 `minicpm-v-4.7-1b-fl`、
`--model-impl vllm`、`--max-model-len 50000`、`--max-num-seqs 32` 和
`--gpu-memory-utilization 0.65`，因此旧服务 `/v1/models` 正常不能验证新脚本。

当前脚本去掉端口预检，并以 `nohup ... &` 后台启动，shell 可在模型就绪或
失败前返回。安装中的 vLLM 0.24 `create_server_socket` 设置
`SO_REUSEPORT=1`，直接在现有 8308 服务旁运行可能让两个模型进程共享端口；
不能以此执行占用端口测试。脚本把日志追加到工作根顶层 `./service.log`，
该文件当前不存在，若执行会产生不符合 `04-runs/` 边界的新文件。容器默认
`XDG_CACHE_HOME`、`TRITON_CACHE_DIR`、`TMPDIR` 均未设置；省略这三项会使
vLLM/Hugging Face、Triton 和 TorchInductor/临时文件的默认路径分别回到
`/root/.cache`、`/root/.triton/cache`、`/tmp`，不符合已批准的写入根。
容器级 `PYTHONDONTWRITEBYTECODE=1` 已设置，这一项从脚本删除本身可接受；
兼容模式 editable 安装后省略 `PYTHONPATH` 也已验证可用。

服务身份从 `minicpm-v-4.7-1b-fl` 改为 `minicpm-v-4.7-1B`，已有客户端与
`03-acceptance/service_smoke.py` 的模型 ID 不再匹配。GPU 内存比例由已验证的
`0.65` 升到 `0.85`；`--model-impl vllm`、50,000 长度和 32 并发上限均被移除。
这些值的当前有效配置与新脚本的资源占用尚未验证，不能沿用上一轮服务回执。
本次检查只读，没有执行新脚本、停止服务、修改容器或覆盖用户文件。
只有将端口排他、日志/缓存边界和服务身份等问题处理后，才能安全切换并做实启验证。

## 限制与经验沉淀

本次只验证服务启动与小规模功能，不构成正式精度、性能或 full graph 验收。
CLI 默认值取决于模型和 vLLM revision；以后若升级栈，可在相同输入上重新
比较有效 EngineCore 配置，再决定是否删除开关。知识库处理状态：`local-only`。
