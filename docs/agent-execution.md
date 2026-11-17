# 可恢复的 Agent 执行记录

借鉴 FlagScale-Agent 的执行前后 Guard 和反复失败复盘，将这些机制放在项目调用层。
`agent_step.py` 是可选的控制记录工具：不执行 shell/SSH、不启动或停止评测、不自动选 Skill，
也不写模型业务状态。正式结论继续来自原生验收器，Agent 负责依据返回结果推进工作。

## 具体执行必须委派

职责及直接执行例外以 [AGENTS.md 的 Subagent delegation](../AGENTS.md#subagent-delegation) 为主定义，
中文对应说明见 [子 Agent 委派](../AGENTS.zh-CN.md#子-agent-委派)。按[双端入口说明](agent-entrypoints.md)，
当前主机上的 Codex 或 dsh 客户端作为主控，本机不依赖 `dsh headless`。
主 Agent 指协调者，负责规划、协调、观察、证据复核和验收；除明确例外外，可独立交付的分析、
实现和测试必须委派。执行者在明确派发边界内直接完成方法和交付证据，不递归委派；协调者的
直接执行例外不限制执行者完成已授权子任务，也不允许执行者自行扩大范围或承担最终整体验收。
优先使用当前主控实际提供且已核实的委派能力；纯本地任务在本地委派，不新增远端授权。
仅明确选用远端 `dsh headless` 时核实该目标入口和权限，并适用下文恢复流程；内置子 Agent
回退仅在当前主控实际提供且能力、路径及权限已核实后使用。缺少能力时暂停受影响执行并重规划。
委派不执行未选阶段，不扩大 profile 可写组件或部署范围，也不改变适配容器持续运行、实际安装
组件修改、禁止导入覆盖、人工控制和原生验收要求。

### 执行前分配与阶段核查

- 每个选定阶段或有界工作单元执行前，在既有阶段计划或编号问题中记录工作单元、执行者、
  输入及已验证状态、预期产物、依赖/资源、时间预算、成功/停止条件和验收标准。任务绑定准确的
  model/platform/profile/phase、Host、容器、实际安装导入路径、批准工作根、文件/符号及读写权限；
  子任务必须读取适用规则/Skill，不得扩大范围、递归委派、提交或推送。
- 可委派工作先分配、派发再执行，不得由主 Agent 先完成后补派发。小任务可合并派发，不能以
  只读、任务较小、顺手完成或执行器故障为由接管，也不得把连续执行拆成多个单步辅助操作。
- 同一源码/服务上的写入及共享设备测量按既有规则协调和串行，只有独立且资源不冲突的工作可并行。
  更换主控客户端不改变资源归属；下文的 journal 目录锁只保护记录调用，不防止跨 run 的源码或服务双写。
  主 Agent 验收实际 diff、执行路径、原始产物和原生回执；子 Agent 自述完成或退出码 0 不能替代
  所选 profile 的数值、执行模式/graph、sanity、精度、性能及交付门禁。
- 阶段结束时在同一记录中汇总已交付/未完成工作、产物位置、主 Agent 直接执行例外及验收结果，
  保留失败和证据缺口。按独立产物核查分工，不以调用次数、命令数或 token 数代替贡献，不为指标
  重复执行，不把完整适配一次性交给无人阶段复核的执行者。
- 分配与例外使用既有 Markdown 计划、编号问题和总结；控制输入/事件继续留在批准的外部产物根。
  不新增模型业务账本、过程目录或必填 YAML schema，也不要求启用可选的 `agent_step.py`。
  文档要求不表示旧控制器已自动强制分工；历史事实和有效证据不为补委派记录而改写或重跑。

### 主 Agent 直接执行的限制

直接操作仅限根规则列明的规则/上下文读取、最小只读预检、派发与观察、产物回收、验收复核、
纯本地规则/文档/记录维护、已授权的紧急控制及符合条件的单步辅助操作。每次简述例外类别、原因
和范围，写入已有任务/阶段/问题记录；纯本地规则维护可在当前任务说明中记录。例外不新增审批，
也不能放宽原有授权、命令审批、共享环境保护或 `framework.yml control.mode`。

最小预检不包括大范围源码搜索、完整日志扫描、trace 解析或批量统计；派发命令不得夹带由主 Agent
编写的产品实现或实验脚本替代委派。验收可针对性核对实际 diff、执行路径与原始证据，调用不启动
新 workload 的现成原生校验器；深入分析、修改和测试/评测重跑必须委派，不以验收或维护名义重做
具体执行。纯本地规则/文档维护例外不包含产品代码、实验脚本或评测/控制工具实现。

## 先冻结接口，再执行

`interface.json` 声明能力 ID、接口版本、显式操作集合及结果契约。
`scripts/skill_bundle.py inspect --skill-dir /absolute/skill --capability-id ID --selection MODE \
--interface-version VERSION --result-contract CONTRACT`
验证身份和操作，并输出完整文件 SHA 集合；缺少模式、资源或身份不匹配返回 `incomplete`。
路径相同和 Git HEAD 相同都不能证明内容相同。缓存文件不参与指纹，bundle 内不允许符号链接。
项目入口不是可独立安装的公共 bundle：项目外部依赖由下面的 context/source 校验冻结。

`skill_bundle.py` 初始实现与本轮 Hub 的同名工具保持一致，现由本项目维护，不运行时 import Hub。
`agent_step.py` 在适配和优化项目初始同版，`project_gates.py` 各自拥有原生校验映射。
任何后续同步都须显式比较和运行回归，不能自动跟随另一个工作区。

## 一个操作对应一个唯一 run

调用方准备 JSON spec，下方给出本项目示例。所有路径必须换成已核实且批准的绝对路径；
不要把示例路径直接作为生产目标。`context_files` 只列本轮冻结输入，不列会持续增长的日志。
工具另外冻结自身、参与验证的控制代码、精度/性能实现以及所选 Skill bundle。
文档措辞和未选 profile 不参与新 journal 的源码指纹；结构化 profile 和运行计划单独绑定。
所选 Skill、配置或校验代码发生变化后返回复查要求，
不能通过改写旧哈希继续声称是同一轮。

```sh
python3 scripts/agent_step.py begin --spec /approved/case/step-spec.json --run-dir /approved/case/control-run-001
python3 scripts/agent_step.py observe --run-dir /approved/case/control-run-001 --evidence /approved/case/progress-snapshot.txt --completed 32
python3 scripts/agent_step.py check --run-dir /approved/case/control-run-001
python3 scripts/agent_step.py finish --run-dir /approved/case/control-run-001
```

`begin` 验证接口、冻结内容并执行前置检查；通过后仅为 `ready/incomplete`。
调用方随后按原有项目流程启动所选工作。`observe` 记录真实进度快照及单调递增完成数；日志变长
不等于有效进度，不要用重复行数或重试数冒充已完成样本。
`finish` 重新核对身份并执行原生完成校验，只有通过才成为 `verified/passed`，同时冻结完成回执。
`check` 不发起新评测；即便已完成，也会重读回执和原生依赖，发现删除、替换或篡改返回 `incomplete`。
旧进度快照只是观察记录，不能作为正式通过证据。

`begin` 初始化及同一 run 的后续操作使用目录锁，取得锁后才读取、校验和更新 journal。
已有调用尚未结束时，另一调用立即返回 `incomplete` 和 `run is busy`，不覆盖记录或等待重试。
核实原调用结束后再调用；工具会重读最新状态，已完成 run 不能被较早的进度快照改回运行中。
这只协调 journal 入口，不阻止绕过工具直接编辑文件，也不暂停实际评测或服务。

CLI 的退出码 0 表示控制操作成功，**不等于验收通过**；必须读取 JSON `status`。
复查原因或校验错误返回 2。工具异常同样失败关闭，不通过模型自评或宽松兜底来通过 gate。
原生校验结果只证明读取到的证据绑定，不代替现场进程、容器和设备取证。

## 时间、错误与恢复

- `budget_seconds` 是本轮预算；`stall_seconds` 从最近一次完成数增长开始计时。0 表示不设置。
- 超预算、长期不增长、连续两次相同 `error_signature` 返回明确复查原因。长期运行但持续增长
  不会仅因总耗时被标成停滞；超预算仍单独提示。
- 这些值是调用方检查时计算的决策信号，**不是后台 watchdog**。调用方决定是否停止准确的
  客户端、缩小同配置实验、证伪一个假设或修改方法，不能无条件重试，也不能自动停止模型服务。
- 接手已有任务先 `check`，核验当前服务/进程/证据与记录对应，再观察或结束原 run；不要重放启动命令。
- 失败可执行 `fail --note '实际失败原因'`。此操作只关闭记录，不声称远端进程已停止。

## dsh 恢复与回退

本节落实中英文 `AGENTS.md` 的子任务委派要求。主 Agent 依据现场证据编排恢复；
仅在明确选用远端 `dsh headless` 时使用该执行器的恢复路径；dsh 客户端作为本机主控不表示
已启动 headless 任务，也不需要因本机没有 headless 而触发回退。
`scripts/dsh_recovery.py` 是本项目维护的独立决策工具，不从其他工作区导入或自动同步。
它只读取调用方核验的快照并建议下一步，不执行 SSH、不停止/恢复进程、不写业务状态，
也不替代 `agent_step.py` 或原生验收器。旧控制器不会因文档更新自动改变行为。

执行器故障不自动允许主 Agent 接管。不可恢复或恢复次数耗尽后，核实旧执行及关联写入者已停止、
交接范围和剩余预算，再把剩余工作转交当前主控实际提供且已核实能力、路径和权限的内置子 Agent；
总预算耗尽先重规划，副作用未知先核验，不能借回退重置预算或绕过门禁。主控未提供该能力或
内置子 Agent 也无法承担时，记录能力缺口，暂停受影响执行并调整计划；主 Agent 只能执行根规则
明确例外内的操作，不自动安装工具或扩大权限，不假定 dsh 客户端具有 Codex 的工具 API。

### 按失败层次处理

| 已核验的状态 | 下一步 |
| --- | --- |
| SSH 断开、远端状态未知 | 重连核实原任务；客户端退出不等于 dsh 退出，不立即派发第二份任务。 |
| 远端仍在执行 | 观察同一任务；超过软时限且有实质进展时，在总预算内继续；无进展先定位等待原因。 |
| 整个子任务的总预算耗尽 | 按授权准确停止该任务并核验子进程，保留证据后重规划；不能用恢复或 fallback 重置预算。 |
| 执行已结束，已有产物 | 先回收并核验；缺少最终文字或 SSH 后续断开不要求重新计算。异常退出仍如实记录。 |
| 瞬时故障，未启动或已终止且无副作用 | 在总预算内有界退避后重试，同一 task-id、独立 attempt-id，不并发重放。 |
| 执行已结束，有有效 session 和检查点 | 核实当前安装实际支持恢复，再在不变上下文中接续；检查点不等于验收通过。 |
| 所选远端执行器未安装、配置/权限错误或无法恢复 | 报告原因，确认旧执行和写入者停止后，仅向当前主控实际可用且已核实的内置后端回退；无后端则记录缺口并重规划，不自动安装或放宽权限。 |
| 测试失败、精度不达标或验收证据无效 | 按原定位和验收流程返回失败/未完成，不能通过更换执行者抹掉失败或绕过门槛。 |

必须区分 dsh 自发退出和控制器主动终止。即使退出码为 0，若存在 error 事件或
controller timeout，也不能判定成功；终止后的 closed-handle 等清理错误不能单独证明
最初失败原因。调用方先独立核验真实产物，再决定能否复用、继续或回退。

### 派发与接续边界

- 远端长任务使用已批准远程工作根内的独立控制进程和唯一产物路径，SSH 只负责启动与观察。
  输入从已保存的任务文件读取，stdout/stderr 保存到文件，不依赖交互终端或可能随连接关闭的管道。
  启动确认丢失时，按 task-id/attempt-id 查已有执行和产物，不能立即重发；不引入共享服务或修改系统配置。
- 按可交付产物拆分任务，例如源码契约核对、确定性统计、归因和独立复核。大文件扫描及重复计算
  优先用参数化解析器，避免模型反复输出整份源码/trace。只读任务在获准的控制产物目录保存日志、
  中间统计不等于取得源码写权限；若任务明确禁止写文件，则由控制器回收 stdout。
- 启动前冻结软观察时限、无实质进展时限与总预算；所有尝试、session 恢复和内置回退共用总预算。
  软时限只触发检查，不直接 kill；日志增长、模型思考和 token 消耗不单独算进展，须核对完成的
  文件/阶段、命令结果或中间产物。预算不足时缩小或重规划剩余工作，保留旧记录，不静默重置计时。
- 保存 task-id、attempt-id、model/platform/framework/Host、容器与实际导入路径、工作目录、任务/规则/
  源码/运行契约指纹、PID/PGID 与启动身份、session-id、权限及产物路径。每次决策重新核验现场，
  不把过期快照默认视为已验证；PID 存在不证明未被复用。恢复时确认模型、profile、源码、workload、
  评测配置和产物绑定不变；变化时沿用原工作流创建新绑定/run，不刷新旧证据哈希。
- 同一 session 只允许一个恢复者。原 dsh 已退出但 pytest/benchmark 等任务子进程仍在工作时，
  继续观察或按授权准确停止，不再启动第二份。写入范围未知先核验；已验证的部分修改可交接，
  不能重放有副作用的步骤。产品源码仍只可修改所选 profile 声明、容器实际安装的可写组件，
  不通过 `PYTHONPATH` 切换副本；适配容器保持运行，恢复不授权停止无关服务或扩大组件范围。
- 自动恢复最多 2 次；同一错误连续 2 次停止机械重试。已存在 session 却没有核验检查点时，
  先检查原 session/产物，不新开任务；入口缺失、配置/权限错误不盲目重试。只有旧执行和
  关联写入者均已停止，且当前主控确有可用、能力/路径/权限已核实的内置子 Agent，才能在恢复无效或
  次数耗尽后自动交接剩余工作；没有该能力则记录缺口并重规划，不由主 Agent 接管。
- 先检查 `framework.yml control.mode` 并服从人工暂停/接管。暂停、总预算耗尽和副作用未知不能
  通过 fallback 绕过；每个 attempt 保留失败及证据，不把替代执行者成功改写成原 dsh 成功，
  不由控制工具直接将 `framework.yml` 标成通过。

### 本地决策入口

```sh
python3 scripts/dsh_recovery.py --help
python3 scripts/dsh_recovery.py --snapshot /absolute/control/dsh-snapshot.json
```

帮助中提供 schema 1 的完整 JSON 示例。每个字段均须显式提供，未知、缺失、重复或类型不合法的
字段拒绝处理。`automation_allowed` 来自当前人工控制状态，`binding_verified` 包含上述模型/profile/
运行契约绑定，`observation_verified` 表示调用方已重新核验现场；它们不是工具自行得出的事实。
快照和决策回执放在批准的外部控制产物目录，不进入模型业务记录，不新增第二套历史账本。

输出 `observe/continue_within_budget` 表示继续观察，`reconcile` 表示先核验，
`collect_existing_result` 表示回收原产物；`resume_existing/retry_launch/fallback` 只是建议，
由主 Agent 按当前主控实际能力、权限和证据边界编排、交接及验收；具体执行仍须委派，主 Agent
直接操作仅限明确例外。执行者直接完成已派发工作；工具的 `fallback` 建议不证明存在可用后端。
工具退出码 0 不等于任务通过，`accept` 也只表示调用方已核验
完成状态，不能替代本项目 sanity、accuracy、performance 或完整验收的原生检查。

## 产物位置

spec、run.json 和进度快照放在批准的控制/外部 case 目录，不放入 `models/`。
既有业务记录只引用所选操作结果、证据路径和必要哈希；不创建第二套模型阶段或历史目录。
工具不改变项目既有远程操作、服务生命周期与审批边界。

## 本项目原生 gate 与示例

`framework` 调用现有 `framework_evidence.check_command`，等价于框架路径的
`adapt-model --framework ... --check-only`；不会启动工作。`before` 必须是 prerequisites-only，
`after` 必须开启 `verify_records`，并且前后 model/platform/framework/Hosts/steps/产物根完全一致。

当前支持新 `frameworks/<framework>/framework.yml` 布局中的正式 accuracy/performance 验收；
分别仅允许 `acceptance/accuracy` 与 `acceptance/performance`。accuracy 支持 formal-full/gate-check。
此处 gate-check 对已完成 accuracy 原生记录做只读重验；不自动跑精度。
spec `run_id` 必须与所验原生回执的 run ID 完全一致。新评测使用其新 run ID；
gate-check 使用待复验的旧 run ID，不得用新名称包装旧回执。
legacy 直接平台布局、sanity/hard-case、Torch-FL 实验子步骤尚未接入这个 journal 的完成映射，
继续使用原工作流，不能用其他阶段的通过来代替。框架不支持该子步骤时由原生检查拒绝。

本轮工作完成后，调用方按既有规则先完成真实业务记录及 receipt 绑定，再调用 `finish` 复核；
journal 自己不写 `framework.yml`。不要把该可变文件放在 begin 的 context_files：finish 仅冻结
本轮阶段的状态、verification 和实际回执；后续正常推进其他阶段不使旧 journal 失效。
人工接管时 begin/check/finish 暂停推进；交回后重新核对，操作见[人工协作](human-collaboration.md)。
冻结的运行配置和请求 manifest
放 context_files；精度必须包含回执实际引用的 config；性能必须包含实际 runtime 和
与 `acceptance_plan.performance_request_sha256` 一致的完整 request manifest。`begin` 另外冻结
当时的 profile、target、workspace、deployment 和 acceptance plan，但允许后续正常写入工作流状态与回执。`finish`
会通过 artifact root 反查该文件，与 begin 冻结路径不一致时拒绝通过。全部大产物仍按批准的
远端路径保存，artifact_roots 仅映射真实可读证据。

```json
{
  "schema_version": 1,
  "run_id": "performance-001",
  "owner": "current-task",
  "capability_id": "adaptation/performance",
  "selection": "single-scenario",
  "scope": {
    "model": "Example",
    "platform": "ppu",
    "framework": "vllm-plugin-fl",
    "hosts": [
      "HOST-01"
    ]
  },
  "skill_dir": "/absolute/project/skills/inference-performance-evaluation",
  "context_files": [
    "/approved/case/frozen-runtime.yml",
    "/approved/case/frozen-request.json"
  ],
  "before": [
    {
      "kind": "framework",
      "model": "Example",
      "platform": "ppu",
      "framework": "vllm-plugin-fl",
      "hosts": [
        "HOST-01"
      ],
      "steps": [
        "acceptance"
      ],
      "acceptance_substeps": [
        "performance"
      ],
      "verify_records": false,
      "artifact_roots": {
        "HOST-01": "/approved/readable-artifacts"
      }
    }
  ],
  "after": [
    {
      "kind": "framework",
      "model": "Example",
      "platform": "ppu",
      "framework": "vllm-plugin-fl",
      "hosts": [
        "HOST-01"
      ],
      "steps": [
        "acceptance"
      ],
      "acceptance_substeps": [
        "performance"
      ],
      "verify_records": true,
      "artifact_roots": {
        "HOST-01": "/approved/readable-artifacts"
      }
    }
  ],
  "budget_seconds": 1800,
  "stall_seconds": 600
}
```
