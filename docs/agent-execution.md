# 可恢复的 Agent 执行记录

借鉴 FlagScale-Agent 的执行前后 Guard 和反复失败复盘，将这些机制放在项目调用层。
`agent_step.py` 是可选的控制记录工具：不执行 shell/SSH、不启动或停止评测、不自动选 Skill，
也不写模型业务状态。正式结论继续来自原生验收器，Agent 负责依据返回结果推进工作。

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
工具另外冻结自身、校验器源码及相关项目规则。Skill/配置/校验代码发生变化后返回复查要求，
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
journal 自己不写 `framework.yml`。不要把该可变文件放在 begin 的 context_files：finish 时会冻结
它作为完成记录，之后该文件任何改动都会让旧 journal 需要复查。冻结的运行配置和请求 manifest
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
