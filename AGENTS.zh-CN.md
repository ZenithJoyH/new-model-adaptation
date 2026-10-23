# 新模型适配说明

本仓库用于指定模型、硬件平台与 framework profile 的模型跑通和推理优化。
[AGENTS.md](AGENTS.md) 是供 Agent 使用的英文规则，本文是面向人的中文版。

## 任务范围与基本边界

- 只执行用户要求的任务。本地文档、代码审查和仓库维护不自动启动远端操作或新一轮适配；
  机器出现在 inventory 中不代表已授权操作全部机器。
- 模型记录只保存已验证的适配内容。保留无关改动，不在模型目录加入聊天、无关运维、
  原始日志、缓存或一次性脚本；提交、推送和创建 PR 仍需用户明确要求。
- 人工可在任一阶段接管。先读取 `control.mode`；人工持有期间停止后续 Agent 变更，
  保留现有进程。交回后核对变更及证据，只复核受影响阶段；人工结果使用相同验收器。
  操作见[人工协作](docs/human-collaboration.md)。
- 远端写入前明确准确主机和已批准的绝对工作根，逐个核实容器映射。产品修改只进入所选
  profile 声明且已核实的可写源码树；未声明的源码只读，`vllm-plugin-fl` 下 vLLM 保持只读。
- 直接修改容器实际安装的 FlagOS 组件，包括普通安装目录和 editable 源码；不得用
  `PYTHONPATH` 指向另一份代码或版本，仍按 profile 的可写组件清单执行。
- 代码按正式 PR 的质量标准修改，只解决有证据的适配需求。动手前限定组件、文件/符号和
  测试范围；增删代码须有依据，不夹带无关重构，最终逐块审查 diff。`vllm-plugin-fl` 下
  Plugin、FlagGems、FlagGems-vllm 的每个被改组件均遵守[贡献标准](docs/plugin-contribution-policy.md)。
- 最终服务脚本只保留必要启动指令与设置。必需代码、配置和脚本须在镜像打包后仍位于
  容器内路径；宿主机 bind mount 可访问不等于内容已进入镜像。
- 适配容器必须持续运行。适配期间只允许按需停启当前任务负责的推理服务或相关进程。
  删除数据、替换仓库外已有配置、重启主机和停止无关服务仍需用户明确确认。
- 连接信息保存在操作者的 SSH 配置中。不得提交密钥、权重、完整日志或大型原始测试产物；
  保留命令审批和主机密钥校验，不得绕过执行限制。
- 只报告准确范围内已验证的结果。缺失、过期或不可访问的证据不能作为通过依据；
  如实保留失败和未测试范围。

## 按任务读取规则

执行前读取匹配的入口。链接细则在对应范围内仍为强制要求，拆分不降低原有要求。
只有用户扩展任务时才加载无关工作流。

| 当前任务 | 必须读取的入口 |
| --- | --- |
| 本地文档、代码审查或控制工具维护 | 相关文件及其测试/契约；只有涉及下列范围时才追加对应规则。 |
| 远端检查/变更，或 inventory、组变量、Ansible 入口、playbook 维护 | [远程操作 Skill](skills/remote-operations/SKILL.md) 及其引用细则；中文版为[远程操作细则](docs/remote-operations.zh-CN.md)。 |
| 任一选定模型适配阶段 | [适配细则](docs/adaptation-policy.zh-CN.md)、所选 profile 的 workflow/acceptance 文档，再读[详细五阶段流程](docs/model-adaptation-workflow.zh-CN.md)。 |
| 适配中涉及远端操作 | 首次远端操作前追加读取远程操作 Skill。 |
| 精度或性能评测 | 追加读取[项目契约](docs/skills-project-contract.md)及其仓库内 Skill，明确选择操作。 |
| 需要恢复记录的长任务 | 追加读取[执行记录](docs/agent-execution.md)。 |
| 框架代码实现或 PR 审查 | 追加读取目标源码规范；`vllm-plugin-fl` 还需读取[Plugin 贡献标准](docs/plugin-contribution-policy.md)。 |

远程 Skill 是按路径读取的项目内入口。用自然语言说明主机与操作即可使用，
无需安装全局 Skill；纯本地任务不会自动启动远端检查。

## 适配核心要求

- 五阶段为模型分析（1）、环境分析（2）、进行适配（3）、适配验收（4）、适配复盘（5）。
  只执行所选阶段，始终按 1→5 顺序进行；未选前置阶段只检查，不自动补跑或重写。
- 框架相关工作前先选择 profile，阶段 2～5 还需准确 Host。draft/不完整 profile 仅允许
  模型分析和只读调查；experimental 可执行声明的验证，但不能完成正式整体验收或标记
  `optimized`。
- 按各框架自己的实现与验收流程执行，不把 vLLM 服务门禁套在 Torch-FL Python API 上；
  profile 不得削弱通用规则。
- 模型结构和推理链路分析使用中文。本地 environment、adaptation、acceptance 目录仅放
  精简 Markdown 记录；可执行过程产物和原生证据保留在批准的远端根目录。
  目录布局、证据、经验复用和完成条件的完整要求见细则。
- vLLM profile 按 `full` → `full-and-piecewise` → `decode-full` → `piecewise` 尝试，
  每级完成定位/修复尝试并记录仍无法解决的阻塞后才回退一级，不得跳级。
  以实测性能为目标，后续验收和启动脚本绑定逐 Host 最终验证的模式。精度、性能、最终
  启动脚本和总结要求继续生效，单项成功不代表
  整个适配完成。
- 新工作区使用固定 profile 快照和 [v2 证据契约](docs/evidence-contract-v2.md)。升级需显式执行，
  保留旧回执；`optimized` 必须满足运行前冻结的性能目标。
- 验证后才能更新 `framework.yml`（历史记录为 `platform.yml`）。
  `./scripts/audit-workspace` 用于本地布局检查，warning 不能证明远端成功；
  使用旧版门禁前先读适配细则。
