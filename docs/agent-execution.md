# 可恢复的 Agent 执行记录

借鉴 FlagScale-Agent 的执行前后 Guard 和反复失败复盘，将这些机制放在项目调用层。
`agent_step.py` 是可选的控制记录工具：不执行 shell/SSH、不启动或停止评测、不自动选 Skill，
也不写模型业务状态。正式结论继续来自原生验收器，Agent 负责依据返回结果推进工作。

## 具体执行必须委派

职责及直接执行例外以 [AGENTS.md 的 Subagent delegation](../AGENTS.md#subagent-delegation) 为主定义，
中文对应说明见 [子 Agent 委派](../AGENTS.zh-CN.md#子-agent-委派)。按[双端入口说明](agent-entrypoints.md)，
当前主机上的 Codex 或 dsh 客户端作为主控。
主 Agent 指协调者，负责规划、协调、观察、证据复核和验收；除明确例外外，可独立交付的分析、
实现和测试必须委派。执行者在明确派发边界内直接完成方法和交付证据，不递归委派；协调者的
直接执行例外不限制执行者完成已授权子任务，也不允许执行者自行扩大范围或承担最终整体验收。
使用当前主控已核实的内置子 Agent 能力。纯本地任务在本地委派，远端任务由执行者通过批准的项目
远程操作入口处理。缺少能力时暂停受影响的执行并重规划。
委派不执行未选阶段，不扩大 profile 可写组件或部署范围，也不改变适配容器持续运行、实际安装
组件修改、禁止导入覆盖、人工控制和原生验收要求。

### 执行前分配与阶段核查

- 每个选定阶段或有界工作单元执行前，在既有阶段计划或编号问题中记录工作单元、执行者、
  输入及已验证状态、预期产物、依赖/资源、时间预算、成功/停止条件和验收标准。任务绑定准确的
  model/platform/profile/phase、Host、容器、实际安装导入路径、批准工作根、文件/符号及读写权限；
  子任务必须读取适用规则/Skill，不得扩大范围、递归委派、提交或推送。
- 可委派工作先分配、派发再执行，不得由主 Agent 先完成后补派发。不能以
  只读、任务较小、顺手完成或执行器故障为由接管，也不得把连续执行拆成多个单步辅助操作。
- 派发和启动前先核[有效回执与在途工作](#优先复用有效回执)。同一所选阶段、同授权和写入边界内
  合并连续的判断型工作，一次写明执行范围、阶段检查点、前置门禁、停止条件和产物。仅在独立复核、
  审批/写入边界不同、真实依赖阻塞或有独立并行收益时拆分。派发按[委派上下文](agent-entrypoints.md#委派上下文)
  选择继承范围。同一工作单元可安全接续时，只向原执行者补发变化和缺口。
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

### 执行者收尾与交接

- 工作单元交付、达到停止条件，或已无可推进工作且需等待资源、依赖或决定时，执行者提交一次摘要并结束本轮。
  摘要记录任务绑定、结果及覆盖、证据位置及适用的 SHA、未完成项和已知在途进程及观察者。独立控制器仍有已授权
  任务在跑时，协调者核对归属并按[事件观察规则](#按事件观察)接续。
- 协调者有可执行的新输入、依赖已解除或定向验收发现具体缺口时，才续派尚可在原范围和剩余预算内完成的工作。
  同一已交付工作单元可为定向修正续派，说明缺口和完成条件。回执收取和状态核对使用现有记录或状态工具。
- 进入新阶段、变更授权或写入边界，或开展独立工作单元时，另行核定范围。后续需要委派时，按已核回执和剩余工作
  准备有界输入，使用新的执行会话。同一工作单元内，若历史主要是已交付工作，且剩余任务可凭检查点和原件独立
  完成，在下一个安全检查点用精简上下文交接。交接前核对旧执行和写入者、剩余预算及人工控制状态，复用有效产物和在途 run。
  同一工作单元的恢复或替换共用原预算。

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

## 优先复用有效回执

派发、启动和验收前查既有阶段记录、run 与原生回执。按所选 profile、model/platform/Host、
实际容器与服务/执行模式、安装组件和配置、评测任务/workload、校验器及覆盖范围核对绑定。
已有 journal 时可用 `agent_step.py check` 复核原依赖。正式结果仍需适用的原生校验器。

- **已有覆盖。** 引用已核回执及原始产物，保留原用途、实际绑定与覆盖。人工产物经同一原生验收后也可复用。
- **在途覆盖。** 复用原 run 与已分配的观察者，核对实际进程和覆盖，再等待原回执。
- **部分覆盖、失效或缺失。** 记录有效部分及具体缺口，只冻结并执行缺失的已授权检查。身份或配置改变时按
  所选 profile 重新绑定或建新 run。相同文件名、旧版本或旧服务状态不足以转用回执。

启动前优先复用已验证的采集入口与清单，按变化范围刷新证据。核对可复用的源码清单及相关
哈希，合并本次必须重取的现场信息（如容器、关联进程、设备占用、端口、控制模式）。只有
现有入口或清单无法满足当前覆盖时才补采，记录具体缺口；无法界定变更影响时重新采集所需
范围。交付引用同一份原始产物供适用的阶段使用，及时核对回执时效与覆盖。

同一 run 只计一次独立测量。保留原始失败与不完整项。先决阶段或验收子步骤缺失时，按所选阶段、
profile 的验收顺序和原授权处理，以原生验收和冻结契约判断该结果能支持的结论。

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

### 按事件观察

- 同一 run 保留一个观察者。先核真实启动或快速终态回执，记录观察入口、原生进度源和下个检查点。
  优先使用当前客户端的原生事件或既有后台/前台状态工具。多个独立 run 可合并等待和回收。
- 原生事件不可用时，由现有工具按有界退避查看状态、有效完成数或原始产物元数据。若工具不支持后台观察，
  在预计完成、软观察时限、停滞或总预算等已记节点定向核验。启动未确认时先核原任务身份。
- 有可推进的结果、依赖或资源释放、失败、需人工决定或约定检查点时才唤醒主 Agent，回传变更摘要和回执位置。
  保留用户明确要求的更新节奏，终态停用观察。人工暂停/接管期间只读观察，继续须遵守人工恢复规则。

## 执行中断与接续

- 远端长任务通过批准的项目入口启动，在批准的工作根内使用独立控制进程，保存冻结输入、运行身份、输出
  和检查点。启动确认丢失或 SSH 断开时，按原任务和尝试身份核对实际进程、关联子进程、部分改动及产物。
  核对 PID 时同时确认启动身份。
- 原任务仍在执行时，按[事件观察规则](#按事件观察)跟进同一 run。用产物、完成数或实际命令结果判断进展。
  已有产物先回收并进行原生校验。版本、配置或运行身份变化时按所选工作流重新绑定，保留原证据。
- 继续执行前核对授权和剩余预算，涉及适配工作区时同时核对 `framework.yml control.mode`。原执行和关联
  写入者已停止、检查点及绑定已核实且现有工具支持接续时，由一个责任人接续。瞬时故障的有限重试须确认
  无在途执行和无副作用。记录各次尝试，遵守根规则的恢复次数与总预算。预算耗尽时重规划。
- 需要重新派发时，按[执行者收尾与交接](#执行者收尾与交接)转交已验证状态和剩余工作。状态未知或
  存在旧写入者时先核验现场。精度、性能和其他验收失败依原流程保留并处理，由适用的原生校验器判定结果。

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
