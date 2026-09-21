# 新模型适配项目：公共 Skills 项目契约

本文件只负责把 `skills-hub` 的公共方法映射到本仓库工具，不重新定义精度或性能测试方法。
具体步骤、并发、预热、指标、比较和三态判定以对应 Skill 包为准；本项目规则与用户指令可以
收紧执行范围，但不得降低其完整性要求。

## 项目标识与规则优先级

- 项目：新模型适配。
- 根目录标记：`AGENTS.md`、`inventory/hosts.yml`、`models/`、`test/`。
- 公共 Skill 来源：`skills-hub`；具体受支持 revision 在项目 README 或当前任务记录中冻结。
- 解析顺序：用户当前指令 → 本仓库 `AGENTS.md` → 本契约 → 公共 Skill 方法。

## 运行身份

模型、权重、tokenizer、Host、平台、设备拓扑、容器、服务实例、endpoint、engine、Plugin、
FlagGems、启动参数和执行模式必须来自当前远端取证以及当前模型平台记录。平台步骤的远端
工作根、容器根及映射按 `workspace.roots` 和现场核验确定，不能从历史路径猜测。

## 远程机器操作映射

- 清单和平台变量：`inventory/hosts.yml` 及 `inventory/group_vars/`。
- 只读入口：`./scripts/inventory`、`./scripts/connectivity-check`、
  `./scripts/health-check`、`./scripts/accelerator-check`。
- 通用 Ansible 入口：`./scripts/ansible`、`./scripts/playbook`，遵守仓库审批规则。
- 聚焦只读诊断可在 AGENTS 允许时使用直接 SSH；多机或重复变更使用 Ansible。
- 变更先单机试点、验证后 `serial: 1` 扩展；适配容器是受保护资源，不得停止、重启或删除。
- 逐 Host 保留 `unchanged`、`changed`、`failed`、`unreachable` 结论。

## 工作流顺序

五阶段及验收子步骤顺序由 `AGENTS.md` 和 `docs/model-adaptation-workflow.md` 维护。公共 Skill
只执行用户明确选择的操作；未选择步骤仅检查前置条件，不自动补跑。

## 框架与调用名

先读取 profile：以下服务精度/性能映射适用于 vllm-plugin-fl，Torch-FL experimental 使用
device/operators/model-eager/可选 wheel，不要求 FlagEval、graph 或并发请求。

公共方法来源由当前任务记录实际 skills-hub revision。本地 skills/ 仅保留转接入口，不能再
维护独立并发/超时/缓存规则。用户已经确定的 10 并发、超时计失败、性能关闭缓存优先于旧
公共示例。共享 runner 若不支持这些契约或原生格式不同，返回 incomplete，不能静默换工具。

旧调用名在调用前明确映射：baseline-sanity → service-sanity，formal-gate → formal-full；
minimal-regression 由框架定向测试承担，只有提供固定案例集时才调用 hard-case。
性能 baseline/targeted/checkpoint/formal 是调用方目的，实际操作为 single-scenario 或 full-suite，
由用户选定范围和场景 manifest 决定，不自动扩大测试范围。

## 精度评测映射

- 公共方法：`inference-accuracy-evaluation` Skill 包中的
  `references/accuracy-method.md`。
- `service-sanity`：在已经通过执行模式验收的 graph 服务上使用 10 个固定 GPQA 类问题，
  并发 10；逐题正确性、输出健康和明显性能异常按公共方法检查。固定题目 manifest、请求脚本
  和原始结果放在远端 `<host_root>/03-acceptance/` 与 `<host_root>/04-runs/<run_id>/`。
  当前仓库没有独立维护的通用 sanity runner；未提供已核实 manifest 和入口时返回
  `incomplete`，不得临时在本地模型目录造脚本。
- `formal-full` evaluator：目标机器上基于
  `harbor.baai.ac.cn/flageval/flageval-llmeval:v1` 或已核实的适用 arm64 镜像的评测容器。
- `formal-full` runner：`test/Accuracy_test/llmrun.py`。在容器内保持该文件与
  `acceptance_contract.py`、`score_progress.py` 同目录，先执行
  `python3 llmrun.py <frozen-config> --preflight-only`，再使用同一配置执行
  `python3 llmrun.py <frozen-config>`。
- 正式配置映射：graph、`limit=0`、并发至少 32、`allow_timeouts=true`，每个任务的
  metric/minimum 和完整样本数在运行前冻结。单 task 的 `expected_samples` 可为正整数；多
  task 必须为键集合与 `tasks` 完全一致的正整数映射。可用 `datasets` 为每个 task 配置
  `path`/`name`/`split` 并在 FlagEval 容器内预检；FlagEval 自带或 `include_path` 提供的 task
  仍必须通过最终样本完整性校验。GPQA Diamond 只是其中一个 198 题的配置，不是唯一支持
  的正式数据集。完整规则由公共方法拥有，本条仅声明本项目 runner 字段映射。
- 正式精度的完成判定按冻结阈值执行：有效完整结果中每个任务的指定 metric 达到对应
  minimum，即可将精度子步骤标记为 `passed` 或 `complete`。metric 不要求为 `1.0`，允许
  个别题目答错；`service-sanity` 的逐题正确要求不得替代正式精度的阈值判定。最终超时请求
  必须作为错误样本保留并计入分母，不得丢弃或用重试掩盖；样本完整且各 metric 达标时允许
  少量超时。样本或回执无效、非超时请求/执行错误、结果不完整或任一 metric 未达阈值时
  仍不得通过。
- 正式结果：runner 生成的 `acceptance-result.json`。通过
  `./scripts/adapt-model <model> --platform <platform> --framework vllm-plugin-fl --hosts <hosts> --steps acceptance --acceptance-substeps accuracy --check-only --verify-records --artifact-root <Host>=<可读根>`
  执行本项目绑定检查；不得用 Markdown、阶段分数、日志或退出码替代。
- `hard-case`：当前尚无仓库级固定清单和正式入口；用户未提供并冻结版本化 manifest 时返回
  `incomplete`。
- `gate-check`：使用
  `./scripts/adapt-model <model> --platform <platform> --framework vllm-plugin-fl --hosts <hosts> --steps acceptance --acceptance-substeps performance --check-only --artifact-root <Host>=<可读根>`
  只读核对当前正式精度前置及服务绑定；只要求检查时不得自动重跑精度。
- 远端配置和包装放 `03-acceptance/`，完整结果放 `04-runs/<run_id>/`，缓存放 `06-cache/`；
  本地平台 `acceptance/` 只保存 Markdown 摘要和准确路径、哈希、身份与结论。

## 性能评测映射

- 先读取当前 `framework.yml` 引用的 profile；profile 的
  `acceptance.performance_adapter` 决定可使用的正式 runner。旧直接平台记录按
  `vllm-plugin-fl` 处理。不得仅因某个 CLI 已安装就跨 profile 选择 runner。
- 公共方法：`inference-performance-evaluation` Skill 包中的
  `references/performance-method.md`。
- vLLM runner：`test/perf_test/vllm_perf.py`；SGLang runner：
  `test/perf_test/sglang_perf.py`；`all_perf.py` 仅在其文档支持范围内作为兼容入口。
- `single-scenario`：把冻结的单个场景映射为一个
  `--case INPUT,OUTPUT,CONCURRENCY,NUM_PROMPTS`；先执行相同命令加 `--dry-run`，核对后只移除
  `--dry-run`。必须提供匹配 baseline，结论仅覆盖该场景。
- `full-suite`：把版本化完整场景 manifest 中每项映射为重复的 `--case`；不得静默遗漏。
  `--model`、`--tokenizer`、`--max-model-len`、Host、端口和 endpoint 来自当前服务取证，且
  每个 `INPUT+OUTPUT` 不超过当前上下文预算。
- 测量与验证：按公共方法执行显式预热、多轮无 profiler 测量、请求/token/指标校验；项目
  原生报告为 `benchmark-result.json`，使用 `perf_common.validate_report` 完整校验。
- 正式回执：在完整远端报告旁执行
  `python3 test/perf_test/perf_acceptance.py --report <benchmark-result.json> --runtime-config <runtime.yml> --output <receipt.json> --model <model> --platform <platform> --deployment-fingerprint <sha256> --service-instance-id <id>`。
  后续工作流通过 `./scripts/adapt-model ... --framework vllm-plugin-fl --acceptance-substeps performance --check-only --verify-records --artifact-root <Host>=<可读根>` 核验。
- 正式性能只使用已通过 profile 执行模式验收的主模式服务（`vllm-plugin-fl` 为 graph），
  并要求当前精度 `gate-check` 已通过。profiler-on
  轮次和 trace 只属于诊断，不进入正式性能结果。
- 非性能测试保持前缀缓存开启。所有性能与 Profiling 轮次都必须切换到性能专用服务配置，
  使用 profile 声明的缓存关闭机制；`vllm-plugin-fl` 的准确参数为
  `--no-enable-prefix-caching`，不得将它写入普通 graph 参数。
  执行前核实本轮服务实例的生效启动配置和启动证据，在 runtime 的
  `service.prefix_caching.performance` 中记录 `enabled: false`、仅含准确参数的
  `launch_args` 和非空 `verification`。正式回执会校验 runtime、
  准确关闭参数、现场证据与服务实例绑定。benchmark 客户端不负责修改模型服务，
  `--random-prefix-len 0` 不能替代该证据。
- 性能计划/包装放 `03-acceptance/`，原始 JSON/CSV/stdout/stderr 放
  `04-runs/<run_id>/`，缓存放 `06-cache/`；本地只保存 Markdown 摘要与准确证据引用。

## 精度定位、Profiling 与算子分析

- 精度失败记录：当前模型平台的 `adaptation/` 编号问题；复现代码放远端 `02-issues/`、
  `05-tmp/` 或最小算子问题的 `07-bugs/`。
- Trace 和 profiling 入口、rank 覆盖及产物路径按当前任务远端工作根和项目工具文档映射。
- 产品修改只进入当前 profile 声明可写且已核实身份的源码；`vllm-plugin-fl` 仍只修改
  editable-installed Plugin，vLLM 只读。

## 产物与生命周期

完整日志、样本、JSON、CSV、Trace 和缓存留在批准的远端工作根。本地仓库只保存精简、可读
且可复核的 Markdown 记录。服务停止/重启、容器保护、源码边界和需确认操作继续遵守
`AGENTS.md`；公共 Skill 不扩大授权。

新工作区的绑定及完整原生产物校验见 [框架证据契约](framework-evidence.md)。legacy 快照
导出器不适用于新目录，禁止为了通过旧工具重新创建本地过程 YAML。
