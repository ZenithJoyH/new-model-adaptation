# Codex 与 dsh 客户端入口

本说明提供共同规则的加载方式和角色约定。当前主机上启动的 Codex 或 dsh 客户端就是主控，
本机不需要安装 `dsh headless`，也不需要为使用其中一端而安装另一端。
本轮兼容范围为规则与文档入口，不新增执行适配层、自动派发工具或客户端专用配置。

> English summary: Codex and dsh are peer controllers. This guide defines roles and
> capability checks; both keep the same profiles, repository-local Skills and evidence
> contracts. Do not assume dsh reads `.codex/rules`. Keep restricted workspace access
> and per-command native approval for generic Ansible. The dsh parameter examples
> below have no recorded client version or reproducible runtime validation in this
> repository; verify the current tool schema before use. Existing authorization of
> the same full command and scope avoids an extra conversational confirmation, but
> does not waive native approval.

## 共同规则与角色

两端均读取仓库根 [AGENTS.md](../AGENTS.md)；[中文版](../AGENTS.zh-CN.md)供人阅读。
具体任务再按根规则加载相应 `docs/`、framework profile 和 [项目内 Skills](../skills/README.md)。
保留现有目录、接口和证据契约，不复制客户端专用的业务规则、Skill 正文或模型状态。

| 角色 | 进入方式 | 职责 |
| --- | --- | --- |
| 协调者（coordinator，原主 Agent） | 用户直接交给主控客户端的任务默认采用此角色；在当前任务说明中注明。 | 规划、分配有界子任务、协调资源、观察、复核及最终验收；具体执行须委派，直接操作仅限根规则明确例外。 |
| 执行者（worker，原子 Agent） | 协调者明确派发的有界任务，在任务输入中声明此角色和范围。 | 直接完成所分配的分析、实现或测试，交付改动及证据；不递归委派，不自行扩大授权、升级为协调者或宣布整体验收通过。 |

客户端名称不决定角色；dsh 客户端不等同于远端 `dsh headless` 执行器。执行者直接完成已派发
工作不属于协调者接管，也不再要求把同一任务委派一次。角色本身不授予源码、主机或进程权限。
边界不明确或能力不足时，执行者向协调者报告，暂停受影响操作；未受影响的已授权工作可继续。

## 能力与权限核对

由协调者在已有任务说明、阶段计划或编号问题中记录当前客户端、角色、所需能力及核对结果：

1. 核实当前工作目录为预期仓库，已读取根规则及适用任务入口。客户端未自动加载时，按下方
   启动提示显式读取；不要假定 dsh 自动发现 `AGENTS.md`、Skill 或 Codex 配置。
2. 优先使用当前主控实际提供且已核实的子任务委派能力；不要求两端具有同名工具或相同 API。
   仅核实本任务需要的能力，不因另一客户端或本机 `dsh headless` 缺失而判定当前入口不可用。
3. 核实所选执行路径的权限与可访问目录，并按客户端落实审批：
   - Codex 继续使用现有[命令规则](../.codex/rules/ansible.rules)及其原生审批；项目规则的
     加载受客户端信任设置约束。
   - dsh 保持受限工作区和需审批的策略。现有说明使用 `workspace-write` + `ask`，并以
     `sandbox_permissions: "danger-full-access"` 配合 `justification` 举例请求单次升级；
     仓库尚未记录这些参数对应的客户端版本、工具 schema 或可复核的实测摘要，审批卡是否
     包含完整命令参数也未有验证记录。上述内容是待现场核实的参数示例，不是已验证的通用接口。
     使用前核对当前客户端实际提供的配置、工具参数和审批行为，不直接套用到另一客户端。
   - 四个受限只读入口可先在现有沙箱内运行；若拒绝 `~/.ssh` 或本地 socket，再按已核实的
     客户端机制请求单次升级。通用 `./scripts/ansible`、`./scripts/playbook` 每次调用仍须
     经过原生审批；不得通过全局 `danger-full-access` + `never` 或等效设置关闭审批。
   - 执行前须在对话或审批请求中展示完整命令、目标 Host 和影响范围；审批卡缺少这些信息时，
     在对话中补充。用户已明确授权同一完整命令及范围时，不再额外要求相同的对话确认，
     但仍保留逐次原生审批。尚未授权时，展示后通过原生审批完成一次明确确认；若该机制无法
     明确关联所展示的命令，则取得一次对话确认，并仍履行原生审批。命令或范围变化时重新核对授权。
   - 两端都不得用 `.venv/bin/*`、`bash`/`sh` 包装、绝对路径或复合命令绕过上述入口；受限
     只读入口也不得扩大用户授权的目标或操作范围。
4. 纯本地任务只在本地委派。涉及远端时，先按[远程操作 Skill](../skills/remote-operations/SKILL.md)
   和原有规则确认准确 Host、绝对工作根、容器及已安装源码边界；本入口核对不授权远端探测。
   只有明确选用远端 `dsh headless` 时，才核实该目标实际安装的入口、版本、参数和权限。
5. 当前主控缺少可用委派或必要审批能力时，记录缺口，暂停受影响的执行并重规划；不以切换角色、
   自动安装、扩权、关闭审批或协调者接管来补足。恢复与回退须遵守
   [既有恢复规则](agent-execution.md#dsh-恢复与回退)，内置子 Agent 仅在当前主控确实提供且已核实后使用。

以上是人工/Agent 按规则进行的能力核对，不代表已有自动探测或执行适配器。
不向既有 journal spec、`framework.yml` 或证据回执增加客户端必填字段。

## 启动提示

在已打开本仓库的 Codex 或 dsh 客户端中发送协调者提示，再附上具体用户任务。
根规则已自动加载时无需重复粘贴正文：

```text
角色：协调者（coordinator）。当前客户端作为本机主控，本机不安装 dsh headless。
先读取仓库根 AGENTS.md 和 docs/agent-entrypoints.md，按任务读取所需 profile、规则和 Skill。
核实当前客户端实际可用的委派与审批能力，不假定另一客户端的工具存在。
按既有计划或编号问题分配有界任务；没有必要能力时记录缺口并重规划，不接管委派工作。
保留全部主机/容器/源码边界、人工接管、进程保护及原生验收要求。
本次任务：<具体工作；适配任务写明模型、平台、profile、Host、工作根及所选阶段>
```

协调者派发执行者时，使用下面的任务输入；这不是新的配置 schema。
填写经过核实的值，不适用项注明不适用，不以示例或历史路径替代现场核实：

```text
角色：执行者（worker）。直接完成本次有界任务，不递归委派，不提交或推送。
任务/问题 ID 与协调者：<已有记录标识及派发者>
共同规则：读取仓库根 AGENTS.md、docs/agent-entrypoints.md 及以下适用规则/Skill：<路径>
任务范围：<所选模型/平台/profile/阶段及分析、实现或测试目标；非适配任务注明不适用>
已验证输入与依赖：<当前状态、已有结果、适用契约和资源>
授权环境：<准确 Host、容器、工作根、实际安装导入路径；本地任务明确无远端授权>
读写边界与资源归属：<文件/符号、允许操作、只读或限定写入、需串行的资源>
预期产物与证据：<交付位置、原始结果/回执、变更和失败记录>
总预算及成功/停止条件：<与协调者记录一致；能力/边界不足时报告，不自行扩大范围>
验收：<所需原生检查及证据；由协调者复核，不自行宣布整体验收通过>
```

派发边界以用户已有任务授权为依据，模板不新增其他主机、组件或阶段的授权。
若所选执行方式会调用客户端 CLI，先核实实际安装的接口；本文不提供猜测的 dsh 启动参数。

## 接续与共同验收

- 同一工作单元及冲突资源的写入归属须明确。两端接续时先核对旧进程、子写入者、部分改动、
  现场绑定和有效证据；不因换客户端重复启动，不在同一源码或服务上并发写入。
- 两端均服从 `framework.yml control.mode` 的[人工接管](human-collaboration.md)。切换客户端
  不解除暂停、不重置预算、不扩大范围、不改写旧失败或刷新证据哈希。
- 两端共用原生 runner、验收器、业务记录及证据契约；退出码 0、子任务完成文字或客户端名称
  都不能替代正式通过证据。`agent_step.py` 仍是可选记录工具，`dsh_recovery.py` 仍只建议动作，
  不因本说明更新而成为执行器；journal 的完成映射继续限于其已声明支持的操作。

规则与文档变更通过本地链接、差异和一致性检查后，只能声称入口契约已整理。
实际客户端能力、权限及端到端运行须按具体环境另行核实；不能据此声称已完成模型适配或双端运行验收。
