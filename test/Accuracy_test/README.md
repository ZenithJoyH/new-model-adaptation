# 精度评测工具

本目录保存可复用的多数据集评测工具和通用配置示例。模型名称、输出路径、任务/数据集、生成参数和验收阈值放在
`models/<model>/<platform>/acceptance/` 的专用配置中，不修改公共配置承载一次评测。

## 正式入口

正式验收仍使用 `llmrun.py`，在目标主机的 FlagEval v1 或 arm64 镜像容器内执行。
部署时将 `llmrun.py`、`acceptance_contract.py`、`score_progress.py` 一起复制到同一目录。
需要 `lm_eval`、`datasets`、已缓存的数据集和可访问的模型服务。

先复制公共 `llm_config.json`，再填写：

- `eval_model`：本轮输出标签；`model_name`：服务 /v1/models 返回的精确模型 ID。
- `base_url`：完整的 Chat Completions 地址；`service_mode` 固定为 graph。
- `gen_kwargs`：根据模型约定明确设置；公共示例值不代表所有模型的推荐值。
- `tasks`：FlagEval 镜像内 `lm_eval` 可识别的一个或多个 task ID。
- `expected_samples`：单 task 可使用正整数；多 task 必须使用 `{task: 完整样本数}` 映射。
- `datasets`：可选的 task 级数据集预检映射，每项包含 `path`、可空的 `name` 和 `split`。
  对 FlagEval 自带或 `include_path` 提供且无法独立 `load_dataset` 的 task，可省略该映射，
  但最终样本完整性仍由 `expected_samples` 强制校验。
- `acceptance_criteria`：每个 task 的精确指标键和事先确定的准确率下限（0 到 1）。

多数据集配置的核心结构如下；task ID、数据集标识、样本数、指标键和阈值必须在运行前
根据当前 FlagEval 镜像实际能力冻结，不得照抄占位符：

```json
{
  "tasks": ["<task-a>", "<task-b>"],
  "expected_samples": {"<task-a>": 100, "<task-b>": 200},
  "datasets": {
    "<task-a>": {"path": "<dataset-a>", "name": null, "split": "test"},
    "<task-b>": {"path": "<dataset-b>", "name": "<subset>", "split": "validation"}
  },
  "acceptance_criteria": {
    "<task-a>": {"metric": "<metric-a>", "minimum": 0.8},
    "<task-b>": {"metric": "<metric-b>", "minimum": 0.7}
  }
}
```

同一个配置中的 task 共用模型服务、并发和生成参数；如果不同数据集需要不同的
`gen_kwargs`、聊天模板或超时，应拆成多份冻结配置和独立 run，不得用一套参数勉强混跑。

### FlagEval task 配置边界

FlagEval 镜像中的 task YAML 才是数据集语义的来源：它定义 `dataset_path`、`dataset_name`、
split、prompt、few-shot、生成参数、filter 和 metric。模型专用 JSON 负责选择 task、连接服务、
冻结完整样本数和验收阈值；其中的 `datasets` 只用于提前验证数据集及样本数，不会替换 task
YAML。更换 FlagEval 镜像或 task revision 后，必须重新核对这些字段。

在既有 FlagEval v1 环境中核对到的代表性配置如下。它们用于说明配置形态，不提供可直接
照抄的样本数或阈值：

| task 形态 | task YAML 中的数据源 | 主要差异 |
|---|---|---|
| `gsm8k_cot_zeroshot` | `gsm8k` / `main` / `test` | 生成式 exact-match，包含 `strict-match` 与 `flexible-extract` filter |
| `mmlu_pro_<subject>` | `TIGER-Lab/MMLU-Pro` / `test` | 各学科为叶子 task，使用 `custom-extract`；`mmlu_pro` 本身是聚合 group |
| `ifeval` | `google/IFEval` / `train` | 同时产生 prompt/指令级 strict/loose 多个指标 |
| `math_500` | task YAML 引用本地 JSONL | 依赖 `LMEVAL_DATASET_DOWNLOAD_PATH`，数据文件由 task YAML 的 `data_files` 解析 |
| `humaneval_instruct` | `openai/openai_humaneval` / `test` | task 标记 `unsafe_code: true`，会执行生成代码，不属于默认安全评测路径 |

正式配置应优先列出叶子 task。对于 `mmlu_pro` 这类 group，应先展开并冻结实际参与验收的
叶子 task、各自完整样本数和指标，不能只用 group 名掩盖子任务缺失。对于 `math_500` 这类
由 task YAML 解析本地文件的数据集，可以省略 `datasets` 预检映射，但必须在容器内验证环境
变量、文件路径和最终完整样本数。HumanEval 等执行模型生成代码的 task，只有在隔离执行环境、
明确启用危险代码评测并获得用户授权后才能接入；当前通用 runner 不默认启用该能力。

公共示例故意留空模型名和阈值，直接运行会失败，避免无意启动错误任务。
`llmrun.py` 必须显式接收配置路径：

```bash
python3 llmrun.py <模型专用配置路径> --preflight-only
python3 llmrun.py <模型专用配置路径>
```

预检校验配置、任务数据集和服务模型 ID，不发起正式评测。正式配置要求：

| 字段 | 要求 |
|---|---|
| formal_acceptance | true |
| service_mode | graph |
| limit | 0，全量 |
| num_concurrent | 至少 32 |
| expected_samples | 单 task 为正整数；多 task 为键集合完全一致的正整数映射 |
| allow_timeouts | true（最终超时样本按错误答案计入分母） |
| acceptance_criteria | 每个 task 都有 metric、minimum |
| datasets | 可选；提供时必须为每个 task 配置 path/name/split |

十并发只用于前置 sanity，不用于正式全量精度验收。
正式精度按 `acceptance_criteria` 中每个 task 的 `metric`/`minimum` 判定：有效完整结果的
指标达到阈值即可标记该精度测试通过或完成，指标不要求等于 1.0，也不要求每道题全部
答对。前置 sanity 的逐题正确要求不得替代这里的阈值判定。错误答案会体现在精度指标中；
最终超时请求作为错误答案保留并计入分母；样本完整且指标达到阈值时允许少量超时。缺失或
无效样本、非超时请求/执行错误、结果不完整或指标低于阈值仍不能通过。
完整流程及证据绑定见 [工作流指南](../../docs/workflow-guide.md)。

## 结果和退出码

输出保存在 `<output_root>/<eval_model>/<run_id>/`：

```text
source_config.json
effective_config.json
acceptance-result.json
<task>/
  lm_eval.log
  progress_score.log
  attempt-1/results_*.json
  attempt-1/samples_*.jsonl
```

正式模式会检查精确指标阈值、完整样本数、有效 doc_id、有效回复及错误；最终超时回复必须
保留为错误样本。
支持单文档单行，以及 FlagEval 的单 filter 或多 filter 行格式。
filter 格式要求 `(doc_id, filter)` 唯一、每题 filter 覆盖一致，验收指标指定的 filter 必须
存在，且跨 filter 的原始输入、响应和
已有哈希一致；不接受把真正重复、冲突记录或混合 schema 静默去重。
配置只读取一次：解析与 `source_config_sha256` 使用同一份原始 bytes，
`source_config.json` 保留该原文，`effective_config.json` 保存补齐默认值、解析路径后的有效配置。
生成终态报告时复核两个 snapshot；内容变化或丢失都不能生成 passed。
源配置路径之后的修改不会改变已启动任务的 snapshot，也不会被错误绑定为本轮配置。

失败返回非零；已有 run 目录且存储可用时，正常失败、可处理异常和中断会生成 failed 报告。
成功报告包含 passed、运行 ID、task 列表、数据集描述、task 级完整样本数、阈值、配置哈希、结果/样本路径及 SHA256，新增
`config_artifacts`、`task_attempts` 和 `errors` 用于追踪配置、各次尝试及终止原因。
报告保持原有 schema_version=1 和 passed/failed 字段，以临时文件完整写入后独占发布，
不会覆盖已有 `acceptance-result.json`；成功重试只绑定最终通过 attempt 的产物。
可将本轮报告复制到模型平台 acceptance/ 作为 accuracy 证据。

这不是“任何异常必有报告”的保证：创建 run 目录之前的预检失败、SIGKILL、断电、
存储不可写/不支持所需原子发布操作等可能没有终态文件。文件缺失、残缺或退出非零必须
按未完成/失败处理，不能自动回退到其他目录的历史 passed 报告。

报告只知道配置并发；实际有效并发、吞吐、耗时、利用率和显存必须另行观测。
不得用早期完成样本的阶段得分代替全量结果：短题往往先完成，阶段得分不是随机抽样。

```bash
tail -F <本轮输出目录>/<task>/progress_score.log
```

通用诊断可以不启用 formal_acceptance，并使用小样本、低并发或明确允许超时；
这种模式的成功退出只表示评测完成，不代表正式验收通过。

## 缓存、重试和等待

响应缓存位于容器本地 `<cache_root>/<eval_model>/<run_id>/<task>/<identity>/responses.sqlite_rank0.db`，
通用 runner 的旧默认在 /tmp，不是新远端任务可以直接沿用的目录授权；下述新后台入口
要求显式配置本轮目录内缓存。应核实存储的 SQLite/锁语义，不把响应缓存放到未经验证的
NFS。大结果和数据集不提交到本仓库。
identity 绑定完整有效配置、runner 源码和本次调用的随机 nonce；即使换输出根后复用运行标签，
也不会命中上一次服务的缓存。同一进程内重试仍复用同一身份，不自动跨进程恢复。

直接使用通用 runner 时 `run_id=auto` 每轮生成新目录；下述新后台入口拒绝 `auto`，要求
配置与运行计划有相同的显式 ID。已经存在的输出目录会被拒绝，当前 runner 没有跨进程
恢复旧输出目录的接口。进程内 eval_max_retries 重试可以复用同轮响应缓存，结果文件按
attempt-N 隔离，当前尝试缺失结果时不会用旧文件充数。
损坏 JSON、结果结构错误或 samples 验证失败会消耗本次尝试，并按配置重试；耗尽后失败。
子进程回收失败则立即中止，不在上一轮 worker 可能仍存活时启动重试。
模型权重、服务参数、生成参数或任务模板变化后必须开启新轮次。

`wait_for_service=true` 时可等待服务，service_poll_interval 控制轮询间隔，
service_wait_timeout=0 表示无总等待上限。API timeout 与服务等待超时不同。
formal 模式允许最终超时样本存在，但会将其判为错误答案；只有包含这些失败样本后的指标仍
达到冻结阈值，整个精度评测才可通过。

## 子进程生命周期

两个 runner 共用 `llmrun.py` 的本地进程监督代码，不增加独立部署依赖。
每个 lm_eval 和阶段计分 sidecar 都由本次调用新建专属 POSIX session；正常完成、
sidecar 启动失败、输出异常及可处理的 SIGINT/SIGTERM 路径会回收这些进程组。
SIGINT/SIGTERM 分别非零退出 130/143；parallel 的 silent worker 和重试等待能响应取消，
progress monitor 在异常时也会停止。工具不按名称扫描进程，不触碰旧服务或其他任务。

当前 lm_eval 子进程使用 `close_fds=True`。仅 runner 被 SIGKILL，或子进程主动
setsid/daemonize 逃离本次进程组时，supervisor 可能无法清理残留后代。后台运行必须由
实际 worker 管理完整生命周期，不能把短暂 launcher 的退出视为任务结束。

本轮真实本地用例验证正常父子进程组、sidecar、静默客户端取消和 SIGTERM 失败报告。
macOS 在 leader 已退出的 orphan group 上可能在 TERM 后对 KILL 返回 EPERM，生产代码仍
按回收失败中止，不忽略权限错误；该特殊用例仅在 Linux 运行，当前没有 Linux 实测证据。

## 多服务和多 shard

`llmrun_parallel.py` 仅用于用户明确指定的多服务、多 shard 场景，不能替代默认正式入口。
它保留通用评测语义，不输出上述正式验收契约报告。公共 llm_parallel_config.json 中
api_list 故意留空，复制到模型 acceptance/ 并填写真实服务后使用：

```bash
python3 llmrun_parallel.py <模型专用并行配置> --preflight-only
python3 llmrun_parallel.py <模型专用并行配置>
```

num_concurrent 是每 shard 并发，data_parallel_size / shards 定义完整分片范围。
仅全部分片完成且合并结果通过检查后才能报告完整结果；部分分片不能代表全量。

并行部署需要 `llmrun_parallel.py` 及上述三个公共文件。输出位于
`<output_root>/<eval_model>/<task>/<run_id>/`，包含不可变 `run-manifest.json`；
首次创建时保存该调用的 `source_config.json` 与 `effective_config.json`，后续分片调用不覆写；
跨调用的一致性以排除 shards/merge_only 操作选择项后的 manifest 为准。
`shard-N/attempt-M/` 按尝试隔离，成功分片的 `shard-result.json` 绑定结果与样本哈希。
merge 只接受同一 manifest 下完整分片的有效 receipt，并检查文档不重叠、总量正确，
不递归吸收未列入 receipt 的历史文件。已存在的分片目录不会被覆写或自动重跑。
分片样本必须保留全局 `doc_id`；若某个 evaluator 使用分片内局部编号，应先提供经过验证的
schema 适配，不自动猜测编号映射。此轮只验证了本地合成分片，未执行远端多服务评测。
分批运行时保留同一 run_id、服务列表与评测设置，只改变 shards；`merge_only=true` 必须
指定已有 run_id。旧版无 manifest 的目录仅供历史取证，不能自动迁移为新正式结果。

## 阶段计分与部署边界

阶段计分仅适配 `flageval-gpqa-v1-top-k-numeric` 请求 schema（可通过
`progress_score_cache_schema` 显式指定），识别已验证的 `top_k=-1` / `-1.0` 两种缓存编码，
不修改正式请求或缓存。未知键、重复文档编码或无法读取的缓存显示 `UNAVAILABLE`，
空缓存显示 `PENDING`，都不解释为 0 分；最终成绩仍以 lm-eval 全量产物为准。

### Hy4 新后台准入与部署

Hy4 fixed c32/c64 的 prepare/start 使用同目录 `hy4_accuracy_tasks.yml`，要求控制端本轮
`run_plan_src`，不再按日期文件名复制旧配置。完整声明、字段来源和 prepare/start
命令模板见[新后台入口](../../docs/workflow-guide.md#hy4-新后台精度入口)。

计划必须为 schema 5，包含模型、平台、主机、服务端口、新 `run_id`，以及严格的
`workspace: {host_root, container_root, evaluator_container, evaluator_root}`。runtime target
必须恰好为该主机；前两个路径绑定 runtime workspace，另行确认评测容器到同一宿主根目录
的映射。公共 helper 仍由模型 wrapper 显式提供 `expected_scope`。
实际评测镜像还须匹配 manifest 的 `evaluator_image`；当前两个 wrapper 使用本机 8010
端口，只支持两个容器均为 host network，不猜测 bridge/代理映射，也不自动改网络。

运行目录固定为宿主 `host_root/04-runs/run_id`、评测容器
`evaluator_root/04-runs/run_id`。
配置只能来自当前 runtime `acceptance.accuracy_config` 的原始字节，必须已有同一显式
`run_id`，`output_root`、`cache_root` 和 `hf_datasets_cache` 均在本轮容器运行目录内，
后者必须是绝对路径。不会改旧配置、迁移旧结果或自动复用旧缓存。

新准入要求 `service-state.yml` 中实际 API 监听进程的 `service.pid`（不是 EngineCore）和严格四项
`service.process_identity: {container_id, boot_id, start_ticks, cmdline_sha256}`；分别来自只读
容器 inspect、Linux boot ID、该 PID 的 `/proc/<pid>/stat` 启动 ticks 和原始 cmdline 字节
摘要。缺失即拒绝，不从历史 PID 或旧通过标签回填。

prepare 先在控制端执行原 canonical accuracy gate，再核实实际 bind/真实路径，独占创建
新 run，部署三件精度公共文件、`background_worker.py`、模型 wrapper 和唯一源
`scripts/{remote_workspace,accuracy_admission,service_observation}.py`。
所需 canonical gate 源码、配置与绑定证据的原字节放到 `run/workflow/`，另存 manifest 和
原运行计划，核验完整 hash/导入及 `--check-plan`。PyYAML 缺失会拒绝，不自动安装。
快照不是一个 `passed` 标签，也不是远端实时证明；start 必须重新导出当前快照比对已有
manifest/bundle/config，不更新它们，任何差异都须保留旧 run 并重新准备。

prepare `--check --diff` 只有本地 gate 和远端只读映射检查，不创建 run。实际 prepare
也不运行 runner preflight 或发 HTTP。start `--check --diff` 检查已有部署，不派发或观察
服务；标准 Ansible 模块的临时文件仅在已核实的 `host_run_dir/tmp/ansible` 内。正常 start
才派发 worker 并配对运行宿主观察器，宿主/容器命令分别指定 cwd / `--workdir`。

worker 重跑 canonical 快照 gate，发出随机 nonce challenge，由 start
配对的宿主观察器读取并核对精确服务进程身份，响应绑定本次 nonce；之后才执行
preflight、健康/忙闲检查和评测。直接 detached wrapper 没有观察器时，会限时失败，不发
正式请求。`launch.json: dispatched` 只表示派发；`worker-started.json` 表示准入后开始，
`exit-status.json` 是退出状态，均不能替代本轮 `acceptance-result.json`。
观察器同时核对该 PID 的 fd 与服务端口 LISTEN socket 的归属；这只是启动前瞬时观察，
不能保证整个评测期间服务身份不变或阻止非协作方替换服务。
监听检查仅支持 IPv4 localhost，同端口存在 IPv6 listener 时拒绝；具体地址与全部 socket
归属要求见[支持边界](../../docs/workflow-guide.md#hy4-新后台精度入口)。

支持的客户端缓存、临时文件与输出留在本轮目录，但不重配现有推理服务日志、FlagGems
数据库或其他服务端外部写入；不是 OS sandbox。上文 SIGKILL 等
生命周期边界仍有效。历史远端副本与结果不自动迁移，没有新增远端部署或评测验证。
