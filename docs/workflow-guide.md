# 工作流操作指南

安全边界和完整五阶段规则以 [AGENTS.md](../AGENTS.md) 为准。本页说明执行入口，
不改变阶段隔离、容器保持运行、vLLM 只读和先精度后性能的要求。

## 每次开始

1. 明确模型、平台、SSH Host 别名、本次阶段及用户指定的远端工作目录；先看对应平台 README。
2. 运行 `./scripts/audit-workspace`。error 是结构错误；warning 是历史证据或状态待复核，
   不等于通过。`--strict` 将两者都作为失败；`--json` 提供结构化报告。
3. 使用阶段工具初始化缺失材料；正式执行前用同一命令加 `--check-only` 检查。
4. 在所属文档记录远程命令，按规则核实现场后执行所选阶段；不补跑未选阶段。

```bash
./scripts/adapt-model Qwen3.8-Flash-Next --platform ppu --hosts PPU-01 \
  --steps acceptance --acceptance-substeps accuracy --check-only
```

工具递归验证未选的所有前置阶段和验收子步骤。同次选择的前置步骤按顺序执行，
初始化成功只表示已准备任务，不代表其中任一步通过。组合选择不是一次性通行证：
完成每个前置步骤、写入真实证据后，下一验收子步骤必须单独执行 `--check-only`。

## 工作目录划分

每次适配同时涉及两个不同的工作目录：

| 工作目录 | 所在位置 | 主要内容 | 不应存放 |
|---|---|---|---|
| 远端工作目录 | 用户指定的目标主机 `host_root` 及已核实的容器 `container_root` | 带序号的实际 checkout、环境采集、一次性诊断、运行日志/结果、缓存、验收程序和 `08-bugs/` 复现 | 本地仓库的长期知识索引；未经授权的目录外写入 |
| 本地工作目录 | 当前“新模型适配”Git 仓库 | `models/` 精简记录、`docs/` 规范与知识库、`scripts/` 控制工具、`test/` 公共测试、`templates/` 模板 | 完整远端日志、缓存、临时脚本、模型权重和运行目录镜像 |

本地记录通过准确 Host、远端绝对路径、容器对应路径、revision、命令和精简结果引用远端
事实。文件出现在本地不代表远端路径或挂载已经核实，也不构成远端写入、搬迁或清理授权。

## 远端工作目录约束

每次远端任务先取得用户指定的 Host 别名和宿主绝对目录；使用已有适配容器时，再确认容器名
及容器内对应路径。只有路径文本还不够：只读检查实际目录、symlink、挂载、写权限、已有文件
及其他任务归属后才能准备新工作。未指定时不以 `/tmp`、`/root` 或某个源码仓库代替。

环境阶段在 `environment/environment-analysis.md` 记录用户要求和核实证据；进入适配/验收时
填写已存在或按所选阶段初始化的 `environment/runtime-config.yml`，例如：

```yaml
workspace:
  roots:
    - host_alias: PPU-01
      host_root: /operator-assigned/tasks/model-a
      container_root: /mounted/tasks/model-a
    - host_alias: PPU-07
      host_root: /operator-assigned/tasks/model-b
      container_root: /mounted/tasks/model-b
```

这些是格式占位示例，不是已选目录或默认值。列表必须精确覆盖 `target.hosts`，每台主机恰好
一项；路径为规范 POSIX 绝对目录，不能包含 `..` 或用 `/` 指整个文件系统。不要用控制端的
`Path.resolve()` 冒充远端真实路径验证。更改该声明会改变 runtime 摘要及相关证据上下文，
不能自动重签旧通过状态；本次规则更新不回填具体模型的历史目录。

这里的 `container_root` 只对应 `target.container_name`。另一个评测容器如使用不同路径，
须在环境分析中另行记录并核实其到同一宿主工作目录的映射，不能把一份声明当成所有容器都
已验证。没有相应挂载时停止该容器内的新写入，不自行改挂载或为省事在其他位置另建产物目录。

工作根目录内的建议布局如下，按当前任务实际需要创建，不一次性生成无关阶段内容：

```text
<work-root>/
├── 01-repos/                    # 经批准的新源码 checkout；只放正常产品代码和测试
├── 02-environment/              # 环境采集、准备配置
├── 03-issues/                   # 远端诊断材料，不是本地 adaptation/ Markdown 台账
├── 04-acceptance/               # 验收程序及配置
├── 05-runs/<run-id>/            # 各轮日志、PID/状态、结果、profile
├── 06-tmp/<issue-or-run-id>/    # 一次性脚本/临时文件，不能散落到源码树
├── 07-cache/                    # 本任务可控的下载、编译和评测缓存
└── 08-bugs/                     # 算子复现；已有用例不再复制到容器 /bug
```

执行时显式使用该目录内的 cwd、Ansible `chdir` 或容器 `--workdir`，`cd` 失败立即停止；
所有脚本、子进程和后台实际 worker 都必须设置正确输出参数。根据已安装版本确认并设置
TMPDIR、编译/评测缓存、日志和结果目录，不能假设改变 cwd 就改变库的默认缓存位置。
重定向用绝对目标，参数按 argv 或正确引用传入，不拼接未经引用的路径。

已有权重、系统库和依赖可在目录外只读引用。要修改已有外部源码、安装位置或共享缓存时，
先明确路径及影响并获得用户单独授权，或经批准在工作目录准备独立副本；不自动搬迁、复制
大权重、替换 symlink/挂载或重启适配容器。复现用例已能通过容器对应的工作目录路径访问时，
直接在 `08-bugs/` 原地执行，不再复制到 `/bug`。只有必要工具明确要求 `/bug` 时，才使用
指向同一 `08-bugs/` 的已批准、已核实映射或明确例外；不得维护第二份副本。

单独的目录声明、配置门禁和生成请求**不是文件系统沙箱**，不自动创建目录、切换远端 cwd、
设置环境变量或限制任意命令的写路径。下述 Hy4 新后台入口已显式接入这些检查与路径设置；
其他直接 SSH、历史副本和后台 worker 仍须逐一检查，不能仅填两个路径就声称都已迁移。
此控制仓库继续保留精简适配记录与证据引用，
远端原始日志和缓存留在工作目录，不把“所有文件集中”误解为搬进本地 `adaptation/`。

## 本地工作目录约束

本地模型记录按 `models/<model>/<platform>/` 组织：平台根目录只保留 `README.md`、
`platform.yml`、`environment/`、`adaptation/` 和 `acceptance/`；模型级结构分析及跨平台材料
放在模型根目录和 `_shared/`。`adaptation/` 仅保存编号 Markdown 问题台账，不接收脚本、
源码、补丁、原始日志或运行 JSON/YAML。公共且经过验证的工具才进入仓库级 `scripts/`、
`test/` 或 `templates/`。

远端一次性脚本、原始结果和缓存继续留在远端工作目录。本地只保存能够复核结论的精简证据
与准确引用；不得因为整理本地目录而自动移动、删除或改写远端文件。只有当前任务确实属于
新模型适配、平台验证或推理优化时，才更新本地模型适配记录。

## 证据与状态

模型元数据 `model.yml.name` 必须与目录名一致。步骤 2 初始化独立的
`environment/environment-target.yml`，只声明本次模型、平台和具体 Host 别名；声明不代表环境已验证。
环境收据绑定该文件，步骤 3 及后续复用环境结论时还会核对当前目标 Host 集合，不能把同一平台
另一台机器的环境证据直接复用。目标记录不包含后续推理调参，避免普通服务参数调整无谓改变环境摘要。
旧记录缺该文件时需要现场复核，不自动从当前 runtime 回填历史目标或刷新通过绑定。

`platform.yml` 中的阶段状态保持原有语义，新增 `failed` 表示已经执行且明确失败。
`passed` / `complete` 必须有证据绑定：

- 阶段：放在 `workflow.<phase>.verification`。
- 验收子步骤：放在 `workflow.acceptance.records.<substep>`；`substeps` 仍保存状态字符串。
- 字段：`run_id`、`last_verified`、`evidence`、`evidence_sha256`、`context_sha256`。
- `evidence` 相对平台目录；必须指向当前模型目录内的非空文件。

先完成并审查实际试验、保存证据，再生成绑定信息：

```bash
./scripts/adapt-model Qwen3.8-Flash-Next --platform ppu --steps acceptance \
  --evidence-info sanity --evidence acceptance/sanity.md --run-id <实际运行标识> \
  --service-instance-id <证据所属服务实例> --verified-on <实际验证日期>
```

该命令只打印信息，不写文件、不执行试验、不更新通过状态。核对证据里的真实运行标识与
日期后再写入 `platform.yml`；回填历史证据时必须用其实际验证日期，不能冒充当天新验证。
主阶段的 `evidence` 应与 `verification.evidence` 一致。

模型元数据、环境分析、运行配置或证据内容变化时，下游旧绑定失效。新版上下文绑定
部署身份及前置验证收据，重新验证 adaptation 不会恢复旧 execution-mode/sanity 的效力。
正式精度及之后的步骤还绑定模型专用精度配置。历史没有绑定的通过状态保留为历史记录，门禁要求复核，
不会为消除告警自动签发绑定。哈希只检测已记录文件的变化，不能发现未记录的远端变更；
每次仍需核对真实模型、源码 revision / dirty diff、容器镜像、启动参数及服务身份。

### 部署身份与当前服务

新适配初始化会创建 [deployment-identity.yml 模板](../templates/adaptation/deployment-identity.yml)。
在实际环境核实后填写 `environment/deployment-identity.yml`：模型 snapshot revision、镜像
不可变 digest、运行配置 SHA-256，以及 vLLM/plugin/FlagGems 各自完整 HEAD、tracked diff
和 untracked 文件内容摘要。只记录 HEAD 不足以识别同一 checkout 上的未提交修改。
没有 Git 元数据的 wheel/distribution 安装使用 `source_kind=installed_distribution`，记录包名、
实际安装版本、实际 import 路径及安装代码文件内容摘要；不能编造 Git HEAD，也不能只散列未修改的原始 wheel。
散列算法见模板注释；未跟踪文件摘要使用按相对路径排序的 `[路径, 内容 SHA-256]` 列表，
JSON 使用 `ensure_ascii=False, separators=(',', ':')` 的 UTF-8 字节。子模块、忽略的运行时代码、
安装产物与实际 import 路径仍需现场另行核对，不能把 Git 摘要当作整个容器的证明。
这里只记录摘要，不在 plugin 仓库加入采集脚本或快照。

```bash
./scripts/adapt-model <model> --platform <platform> --steps adaptation --deployment-info
```

该只读命令校验已有记录并输出 `deployment_fingerprint`，不采集远端、不写入状态。
描述性 notes 和采集时间不进入该指纹，运行配置与代码身份会进入。

[service-state.yml v2 模板](../templates/adaptation/service-state.yml) 区分标准化的 `mode=eager/graph`、
`readiness_result=passed/failed/unknown` 与自由描述 `graph_detail`。填写实际 host/container/PID/port、
进程生命周期内稳定的 `instance_id`、带时区的启动/观察时间，以及该实例**实际加载**的部署指纹；
不能因工作树已更新就认定旧进程已加载新代码。新执行要求 ready，通过的 readiness 记录不得
超过 24 小时（本地防陈旧上限，不保证进程仍活着；发起请求前仍须重新检查现场）。
sanity/accuracy/performance 要求 graph，前置验收收据必须属于当前 service instance。
组合选择包含 execution-mode 时允许从 ready eager 开始；sanity 前必须单独复核 graph。

`--evidence-info` 为四个实际执行子步骤要求显式 `--service-instance-id`，必须从实际运行证据中取得，
不会从当前服务自动推断。历史补录用 `--verified-on` 填真实日期，绑定入口本身不要求服务运行；
如果现有代码/配置已不同于历史运行，不得将旧结果绑定到新上下文，需保留旧记录并复核。
仅做 evidence/summary/
retrospective 不要求服务仍运行，停止服务不会删除或改写历史结果。旧版 service-state
和缺失部署身份只在审计中标记待复核，但不能用于新执行；本地工具不自动迁移、猜测字段
或重新签发通过收据。`architecture` 允许模型级证据，其余收据必须属于当前平台，避免跨平台误用。

## 执行与部署边界

阶段检查不占用或预留设备、端口、容器与源码目录。执行前必须现场核实目标 Host、设备、
服务监听、容器映射、源码身份和其他负载；发现冲突时停止并报告，不得终止或覆盖无关任务。
后台评测由实际 worker/supervisor 管理完整生命周期，短命 launcher 不能代表任务已开始、
已准入或已完成。目录门禁、进程身份和服务观察也不等于资源预留。

### Hy4 新后台精度入口

Hy4 / PPU 的 fixed c32、c64 prepare/start 已接入当前工作流，文件名保留历史日期不表示
复用历史任务。入口只面向 `PPU-07` 的单主机新运行；操作前仍须获得用户指定的工作目录，
完成当前阶段所需的现场核实和证据绑定，不从旧命令、PID 或目录名推断授权。

控制端 `run_plan_src` 必须是本轮运行计划 JSON 的绝对文件路径。计划采用
`schema_version: 4`，保留 `model`、`platform`、`host_alias`、`service_port`、显式新
`run_id`，以及严格的
`workspace: {host_root, container_root, evaluator_container, evaluator_root}`。
runtime `target.hosts` 必须恰好为该一个 Host；前两个 workspace 路径必须等于 runtime
的对应声明。`container_root` 对应
`target.container_name`，评测容器的名字和 `evaluator_root` 是另外显式核实的映射。
两容器必须都在运行，目录经可写 bind 映射到同一已存在的 `host_root`；入口拒绝 symlink、
含糊 volume 或根目录内的子挂载，不自动建根目录、改挂载、搬迁文件或停止容器。
实际评测镜像必须与当前准入 manifest 的 `evaluator_image` 一致。两个 Hy4 包装器使用
`127.0.0.1:8010`，当前入口因此要求两个容器均为 `HostConfig.NetworkMode=host`；不支持
通过 bridge、代理或猜测端口映射复用这条链路，不自动修改容器网络。

宿主运行目录固定为 `host_root/05-runs/run_id`，评测容器内为
`evaluator_root/05-runs/run_id`，
不能假设两侧路径相同。原始配置取自当前 runtime 的 `acceptance.accuracy_config`，必须
已有明确且相同的 `run_id`，`output_root`、`cache_root`、`hf_datasets_cache` 均在本轮容器
运行目录内（后者必须为绝对路径）。prepare 复制已绑定配置的原始字节，不自动修改旧配置、
把 `auto` 换成新 ID 或复用旧响应缓存；离线数据缓存没有准备好时也不能跳过预检。

新后台准入还要求 `environment/service-state.yml` 的 `service.pid` 为实际 API 监听进程，
不能填写 EngineCore 或其他仅参与推理的进程。该 PID 和
`service.process_identity` 有实际现场值；后者严格包含以下四项：

| 字段 | 只读核实来源 |
|---|---|
| `container_id` | 当前服务容器 `docker inspect` 的完整 `Id`，不是名字或镜像 tag |
| `boot_id` | 该容器内 `/proc/sys/kernel/random/boot_id` |
| `start_ticks` | 该服务 PID 的 `/proc/<pid>/stat` 第 22 字段 `starttime`，正整数 |
| `cmdline_sha256` | 同一 PID 的 `/proc/<pid>/cmdline` 原始字节 SHA256，保留 NUL 分隔 |

记录时确认 PID 未在采集中被替换，只保存必要身份与摘要，不记录秘密命令行。缺任何现场值
就拒绝新准入，不从历史 PID/`instance_id` 或当前文件自动回填；添加身份也不自动重签旧证据。

控制端先由 `scripts/accuracy_admission.py` 运行原 canonical accuracy gate，再部署所需
源码、当前配置和已绑定证据的原字节到 `run/workflow/`，保存 `workflow-manifest.json` 与
原始 `run-plan.json`。快照绑定文件集/摘要、runtime、部署、服务和计划，不是复制一个
`passed` 标签；它是可信记录的快照，不是远端实时证明或签名。start 重新导出当前快照并
比对已有 manifest、配置和完整 bundle，变更即拒绝，不刷新旧摘要、不覆盖或升级旧 run。

| 操作 | 执行边界 |
|---|---|
| prepare `--check --diff` | 控制端 gate 加远端只读映射检查；不创建 run、不部署、不发 HTTP |
| prepare | 映射通过后独占创建新 run，部署并验 hash、导入和 `--check-plan`；不运行评测 preflight、不发 HTTP |
| start `--check --diff` | 检查当前 gate、现有映射和已部署字节；不派发、不发服务 challenge 或 HTTP |
| start | 完成相同核验后派发 worker，并配对执行宿主观察器；派发不等于准入或验收通过 |

首次映射检查与新 run 创建使用不部署模块的受控命令；之后 Ansible 临时目录固定在
`host_run_dir/tmp/ansible`，包括 start 的检查模式可能使用的临时文件。宿主命令有显式
cwd，容器命令有显式 `--workdir`；评测客户端的临时文件、支持的缓存和结果路由到本轮
目录。为确保本地请求命中已核实的监听进程，客户端环境的 `NO_PROXY`/`no_proxy` 均补入
loopback 地址并保留其他已有条目。控制端及评测容器需具备 PyYAML，缺失时拒绝，不自动安装。

以下是命令模板，`<控制端本轮计划JSON绝对路径>` 必须替换为已确认文件；远端根目录由
用户明确指定并记录在计划/runtime 中，不由这些示例默认选择。核对检查结果后，只有当前
任务授权实际执行时才去掉 `--check --diff`：

```bash
./scripts/playbook models/Hy4-preview/ppu/acceptance/prepare-ppu07-fixed-c32-20260906.yml \
  --limit PPU-07 --check --diff -e 'run_plan_src=<控制端本轮计划JSON绝对路径>'
./scripts/playbook models/Hy4-preview/ppu/acceptance/start-ppu07-fixed-c32-20260906.yml \
  --limit PPU-07 --check --diff -e 'run_plan_src=<控制端本轮计划JSON绝对路径>'
```

c64 使用对应的 `prepare-ppu07-fixed-c64.yml` / `start-ppu07-fixed-c64.yml`，其当前配置
并发必须为 64；c32 为 32。二者都不能因文件名而选取历史配置。

实际 worker 重跑快照 gate，创建随机 nonce challenge 并等待 start
在宿主读取当前容器/PID/启动时间/boot/命令摘要，返回同一 challenge 的身份观察。身份不符、
观察失败或限时未收到响应都会拒绝；直接运行 detached wrapper 却没有配对观察器，即使
快照检查通过也会等待超时失败。派发时绑定 manifest 与配置/程序摘要，worker 在首次门禁前后
以及预检结束后复核同一摘要，防止混用不同版本的门禁与观察结果。身份核实后才进行 runner preflight、健康/忙闲检查
和正式评测。`launch.json: dispatched`、`worker-started.json`、`exit-status.json` 分别表示
派发、准入后开始与退出；正式精度仍须核验本轮 `acceptance-result.json`。
观察器还核实该 PID 的文件描述符拥有计划服务端口的 LISTEN socket，避免把同容器内
无关进程的身份当作请求目标。当前仅支持 IPv4 localhost：可命中的 IPv4 listener 地址
必须为 `127.0.0.1` 或 `0.0.0.0`，所有可命中该端口的 IPv4 socket 都必须由记录的 PID
持有。同端口若还有 IPv6 listener 则拒绝，不猜测 `IPV6_V6ONLY` 或双栈转发行为。
它是启动前的瞬时核实，不保证进程和监听关系在整个评测
期间不变，也不能阻止非协作方随后重启或替换服务。

此轮只约束新客户端/部署产物，不迁移或覆盖历史结果、现有服务日志和 FlagGems 数据库，
也不重配已有推理进程的外部写入。容器挂载核实不是 OS sandbox；
强杀 runner 等生命周期边界仍见[公共工具说明](../test/Accuracy_test/README.md#子进程生命周期)。
没有新增远端部署或评测结论，不修改历史 `platform.yml` 状态。

## Plugin 设计审查与 PR 准备

修改 plugin 前阅读 [修改与 PR 标准](plugin-contribution-policy.md) 和目标 checkout 的现行设计
规范。阶段 3 的初始化会创建 `environment/plugin-change-review.md`；只选择其他阶段不会
自动创建或回填它。准备时在平台计划中明确职责层级、共享调用方、默认行为及回归矩阵。

适配收尾时以实际 PR base、HEAD 和 dirty/新增文件差异检查设计与证据，并更新审查记录。
模板存在不等于审查通过；审查由 agent/审查者基于实际代码完成，本地脚手架不自动判断
架构合理性。设计阻塞未解决不能标记阶段 3 完成；设计候选状态和完整验收状态分别记录。
阶段 3 的 `context_sha256` 同时绑定审查记录；文件缺失或内容变化时旧的适配验证绑定失效，
应重新核对受影响的设计结论和证据，不能只刷新哈希。
PR base 未确认、硬件不可用或其他模型未验证时明确记录限制，不推断支持。

最终提供给用户的材料应解释问题与前后行为、设计理由、跨模型/平台影响、验证结果及
workaround 退出条件。代码变化后重新核对受影响部分；用户明确要求后才提交或创建 PR。

## 正式精度验收

将 `test/Accuracy_test/llm_config.json` 复制到当前模型平台的 `acceptance/`，填写模型名、
真实服务地址、生成参数及事先确定的准确率阈值。公共示例中的模型名和阈值有意留空，
不能直接运行，也不能凭示例推断一个模型应该达到的准确率。

正式配置必须指定 `formal_acceptance=true`、`service_mode=graph`、`limit=0`、
`num_concurrent>=32`、正的 `expected_samples`、`allow_timeouts=false`，以及每个 task 的
`acceptance_criteria: {<task>: {metric: <精确指标键>, minimum: <0到1的准确率阈值>}}`。
执行环境和镜像要求不变，入口仍是 `llmrun.py`：

```bash
python3 test/Accuracy_test/llmrun.py <模型专用配置路径> --preflight-only
python3 test/Accuracy_test/llmrun.py <模型专用配置路径>
```

部署 runner 时同时复制 `acceptance_contract.py` 和 `score_progress.py`，保持同目录。
正式结果会生成 `acceptance-result.json`，包含通过/失败、运行 ID、配置哈希、阈值和
结果/样本文件哈希。准确率不达标、重复/缺失样本 ID、空回复、超时或错误都不能通过。
将简短的报告保存到当前 `acceptance/`，以它作为 accuracy 子步骤的绑定证据；大型结果和
样本文件留在远端。实际有效并发、吞吐、耗时及监控证据仍需从服务/客户端观测另行记录，
不能把 configured_concurrency 当作 observed_concurrency。

通用诊断可以不启用 `formal_acceptance`，但不能据此将正式 accuracy 标记为通过。
历史远端评测未自动换用新 runner，需按已有证据完成本轮判断，后续受控评测使用新契约。

## 正式性能证据

性能通过不能绑定任意 Markdown、CSV 或只有 `status` 标签的文件。公共性能入口先生成
`benchmark-result.json`，在原始 CSV、stdout/stderr、profile trace 均可访问的环境执行
`perf_common.validate_report`，通过后才可导出平台目录需要的精简回执：

```bash
python3 test/perf_test/perf_acceptance.py \
  --report <本轮benchmark-result.json> --runtime-config <本轮运行时留存的runtime-config.yml> \
  --model <模型目录名> --platform <平台> \
  --deployment-fingerprint <本轮实际部署指纹> --service-instance-id <本轮实际服务实例ID> \
  --output <performance-acceptance.json输出路径>
```

导出器只读验证既有结果，不启动模型、不发请求；需要同目录的 `perf_common.py` 和
PyYAML。输出文件必须不存在。运行身份来自该次试验留存的记录，**不能把当前 runtime、
当前部署指纹或重启后的实例 ID 自动贴给历史报告**。

模型专用的离线复核不能替代此导出。例如 Qwen 的 `finalize_performance.py` 生成
`kind: model-performance-review`，只记录额外的模型/服务证据检查，不是可绑定的
`formal_performance` 回执；复核后仍须在原始工件可访问的环境执行上述共享导出器。

只把生成的 `performance-acceptance.json` 放入当前平台 `acceptance/`；原始报告、完整
日志和 trace 留在远端。回执保存原报告路径与 SHA256、producer/validator 摘要、实际
`run_id`、完整请求参数、服务/模型/平台/部署范围、已验证数量及分开的普通/profile 摘要。
后续按相同 run ID、实际验证日期和实例 ID 绑定 performance 收据。

本地门禁验证精简回执的类型、通过状态、覆盖数量、有限指标和固定输出预算，并检查
模型名、graph API 地址、部署/运行配置指纹和服务实例。服务预算优先取已明确记录的
`service.max_model_len.current`，否则取 `initial`；不得靠更改声明掩盖超预算工况。
若明确配置了 `service.tokenizer`，也检查 tokenizer 一致性。当前公共客户端以
host/port 构造 HTTP 请求，不把 HTTPS 服务误判为同一地址。
vLLM 地址保留代理前缀，已有 `/v1` 不再追加第二个 `/v1`；SGLang 原生客户端将同一
服务的 `/v1` 基地址对应到 `/generate`，但当前客户端不支持带代理前缀的原生路由，
不会通过丢弃前缀将其误判为同一个 API。

这是一份**可信来源的完整验证回执**，不是签名，也不代表本地再次读取了远端原始工件。
需要追查时用其路径和摘要在原始环境重验；不能手工拼装通过标签、盲刷哈希或把旧失败
CSV 升级成正式通过证据。缺少回执会阻止后续新验收门禁，不自动改写历史平台状态。

## 维护检查

```bash
./scripts/syntax-check
./scripts/audit-workspace --strict
```

语法检查涵盖公共 Playbook、工作流/验收回归和仓库结构。未完成适配的历史复核告警会
明确显示，但不会伪装成代码测试失败；严格审计适合阶段交接。不要通过补写 passed 或
删除失败记录来消除告警。
