# 远程操作说明

## 管理范围

- 本仓库通过 `inventory/hosts.yml` 管理操作者 SSH 配置中的所有具体主机别名。SSH别名新增或删除时，必须同步更新 `managed` 组。
- 对可重复操作或多主机变更使用 Ansible。仅针对明确目标开展只读诊断时，可以直接使用 SSH。
- Codex 调用 Ansible 时，必须把工作目录设为仓库根目录，并使用准确的相对入口：
  `./scripts/ansible`、`./scripts/playbook`、`./scripts/connectivity-check`、
  `./scripts/accelerator-check`、`./scripts/health-check` 或 `./scripts/inventory`。
  项目规则会让四个已经收紧参数的只读包装脚本自动在沙箱外执行；两个通用入口因参数可能
  产生任意远端变更，仍需逐次审批。不得改用 `.venv/bin/*`、`bash`/`sh` 包装、绝对路径或
  复合命令绕过规则。
- 不得硬编码 IP 地址、SSH 用户、堡垒机信息、密码、令牌或私钥路径。SSH 连接信息应保存在操作者的 `~/.ssh/config` 中。

## 安全要求

- 状态检查、日志查看、inventory 列举、磁盘检查、进程查看和版本查询均视为只读操作。
- 修改服务器前，先检查当前状态并明确目标主机。
- 会产生变更的 playbook 必须先在一台主机上执行，验证成功后才能扩展到主机组。
  对任何硬件组执行变更时使用 `serial: 1`。
- 相关模块支持检查模式时，使用 `--check --diff`。
- 不得使用范围过大的破坏性命令、关闭 SSH 主机密钥检查、覆盖非预期文件或掩盖验证
  失败。
- 删除数据、替换本仓库之外已有配置、重启机器，或停止当前模型适配范围之外的服务前，
  必须取得用户明确确认。在正在进行的模型适配中，对于由 Agent 为当前任务启动，或由
  用户明确纳入本次适配范围的推理服务或相关进程，Agent 可以按需停止或重启，无需每次
  重复请求确认。适配容器本身必须保持运行，禁止停止、重启或删除。操作前必须准确确认
  服务或进程，不得影响共享或无关负载，并记录原因、命令和验证结果。
- 优先使用具备幂等性的 Ansible 模块，而不是 shell 命令。确需使用命令时，应有意识
  地定义 `changed_when` 和 `failed_when`。

## 加速卡查询

- 不得假设所有主机都使用 NVIDIA 工具。应使用平台组变量和
  `./scripts/accelerator-check`。
- NVIDIA：`nvidia-smi`。
- 华为昇腾：`npu-smi info`。
- 平头哥 PPU：`ppu-smi`。
- 沐曦：`mx-smi`。
- 海光：`hy-smi`；查看进程详情时使用 `hy-smi --showpids`。`htop` 仅用于交互式
  SSH 会话。
- 摩尔线程：`mthreads-gmi`。
- 如果配置的命令不存在，应明确报告，不得静默改用其他厂商的命令。

## 新模型适配工作区

新模型适配工作区明确分为两个相互独立的部分：

1. **远端工作目录**：用户为每台目标主机批准的实际执行区域，供适配容器和远端命令存放
   源码 checkout、一次性诊断、运行结果、缓存及算子复现。
2. **本地工作目录**：当前管理仓库，用于保存精简的模型/平台记录、可复用控制工具、模板
   以及远端证据引用，不作为远端运行产物的镜像。

本地记录必须引用准确的远端路径和 revision；不得把远端原始产物整批复制进本地工作目录，
也不得把本地已有记录视为远端写入授权。

### 远端工作目录

- 任何远端写入前，取得准确的 SSH Host 别名和绝对 `host_root`；涉及容器时再核实绝对
  `container_root` 及映射。确认前仅做只读检查。`workspace.roots` 必须为
  `target.hosts` 中每台主机记录一项 `{host_alias, host_root, container_root}`；映射只对
  指定容器有效，配置声明本身不等于已经核实。
- 所有新增远端写入统一放在已批准根目录，并使用带序号的目录名：`01-repos/` 放源码，
  `02-environment/` 放环境采集和运行配置，`03-issues/` 放一次性诊断，`04-acceptance/`
  放验收工具与配置，`05-runs/` 放每轮输出，`06-tmp/` 和 `07-cache/` 放临时或隐式写入，
  `08-bugs/` 放最小算子复现。复现用例在 `08-bugs/` 中通过已核实的容器对应路径原地执行，
  不再复制到 `/bug`；只有必要工具或上游流程明确要求 `/bug` 时，才可将同一个 `08-bugs/`
  目录以已批准且核实的映射暴露为 `/bug`，或使用明确批准的目录外例外。逐个核实参与容器
  的对应映射；工具无法限制在该范围内时暂停并取得授权。
- 每条远端命令显式指定 `cwd`/`workdir`，`cd` 失败立即停止，并核实 symlink、bind mount
  的真实落盘位置。根目录外已有权重、数据集、依赖和源码默认只读；写入、搬迁或修改挂载
  需单独授权，不得为安排目录而停止或重启适配容器。
### 本地工作目录

- 本仓库只记录已明确模型和平台的新模型跑通、平台验证及推理优化。不得记录无关运维、
  普通包安装、聊天、探索性输出或未经验证的结论；未经用户明确要求不得提交或推送。
- 使用 `./scripts/new-model <model-name>` 创建模型且不得覆盖已有目录。平台名称限定为
  `nvidia`、`ppu`、`metax`、`ascend`、`mthreads` 和 `hygon`。
- `models/<model>/<platform>/` 根目录只保留 `README.md`、`platform.yml`，以及三个目录：
  `environment/` 只放 Markdown 格式的环境/平台分析；
  `adaptation/` 仅作为带编号的 Markdown 问题台账；`acceptance/` 只放 Markdown 格式的
  验收计划、结果报告、总结和复盘。三个本地目录均不得建立子目录，也不得放脚本、
  Playbook、JSON/YAML 配置、原始输出、缓存或临时文件。
  模型级内容放 `architecture-and-inference.md` 与 `_shared/`；公共测试工具保留在 `test/`。
- `_shared/` 只保留 Markdown 索引和少量合并后的跨平台分析，确保便于阅读。上游原始
  元数据、复制模板、一次性检查脚本、JSON/YAML 快照和其他采集产物统一放在已批准远端
  根目录，不得保存在本地模型目录。
- `adaptation/` 不得放脚本、Playbook、补丁、源码或算子实现、复制测试、原始日志、运行
  JSON/YAML 或命令输出。Plugin 仓库只放产品必需代码和可维护的局部测试；一次性过程代码
  放远端 `03-issues/` 或 `06-tmp/`，置于 Plugin、vLLM 和 FlagGems 仓库之外且不得提交。可跨模型
  工具只有经用户批准后才能提升到仓库级 `scripts/`。
- 可执行的过程产物放在已批准远端根目录：环境采集与运行配置放 `02-environment/`，
  一次性诊断放 `03-issues/` 或 `06-tmp/`，验收包装与配置放 `04-acceptance/`，原始结果
  放 `05-runs/`。本地 Markdown 只总结可重复命令并记录准确 Host、远端路径、revision、
  引擎、镜像、参数、输入、日期、用途和验证结果；清理远端临时文件前保留最小必要证据。

### 状态与收尾

- 优化前建立正确性和性能基线，每次只改变一个实质变量，并保留对比。
- 完成前更新平台 `README.md` 中的结果、问题、原因、方案、限制和下一步，并与
  `platform.yml` 同步。最小推理通过后才能标记 `functional`；正确性回归和性能结果记录后
  才能标记 `optimized`。
- 不得提交权重、密钥、完整日志或大型原始 benchmark。

## Plugin 设计与 PR 质量

- 将插件修改按多模型、多平台框架的可维护贡献来设计。修改前阅读目标 checkout 的设计、
  贡献和测试规范，并遵守 [Plugin 修改与 PR 标准](docs/plugin-contribution-policy.md)。
- 在平台环境分析或对应的编号适配问题中说明职责归属、现有扩展点、接口契约、替代方案
  和受影响调用方。复用已有 dispatch/注册路径，模型语义放在模型适配层，硬件
  约束放在 vendor/能力路径；不得在公共执行代码散布模型名称或特定机器的例外。
- 保持作用域外的既有行为。验证适用的已有模型调用方、守卫未命中路径、可选依赖隔离和
  eager/graph 行为。缺少硬件或未执行测试时明确限制，不能从一个模型跑通推断多平台支持。
- 适配收尾和准备 PR 时审查真实 diff，并把审查结论记录在相关编号问题和最终验收总结中。
  记录已确认的 PR base、当前 HEAD、dirty/新增文件、既有改动、影响矩阵、测试证据、
  workaround 退出条件及剩余风险。实质变更后更新审查；设计阻塞未解决不能标记适配完成。
  设计审查与完整验收分别记录。
- 修改保持主题集中、面向产品实现；不夹带无关重构，不用宽泛 fallback 隐藏失败。
  不得仅为完成审查而提交、推送或创建 PR；这些动作仍需用户明确要求。

## 适配经验积累与复用

- 环境变更、适配实现或验收前，先检索 `docs/troubleshooting/`、相关复盘及相近模型/平台的
  问题记录。已有经验只作为候选假设，不自动证明根因，也不扩大操作授权。
- 按完整故障特征和上下文匹配：症状顺序、最先失败的 rank/组件、模型结构、平台、软件
  revision、dtype/shape、并行拓扑、负载及 `eager`/`graph` 模式。仅关键词相同不算匹配。
- 每个新的实质问题都使用 `templates/adaptation/issue-record.md` 记录到当前平台带编号的
  `adaptation/` 台账。在受控对比验证前保持 `hypothesis`；每次只改变一个实质变量，保留
  前后证据，并区分诊断、临时规避、缓解措施和根因修复。
- 只有可复用且已经验证的结论才提升到 `docs/troubleshooting/`。知识条目必须包含故障签名、
  适用范围和可信度、revision、诊断顺序、安全动作、停止/回退条件、验证结果、性能影响、
  `eager`/`graph` 覆盖及来源记录；不得包含密钥、权重、完整日志或无证据结论。复盘时明确
  标记候选经验为已提升、拒绝、已替代或待验证。
- 复用条目时，在当前编号问题中引用它，记录本次与原场景的相同点和差异，并在当前软件栈
  重新验证。补充复验结果和日期；出现反例时缩小适用范围、降低可信度或标记废弃。
- 已知例：仅当故障完整表现为“`sample_tokens` 超过 300 秒、各 rank work 序号随后分叉、
  EngineCore 最终因 RPC 超时退出”时，参考
  `docs/troubleshooting/distributed-sample-tokens-timeout.md`。只有 worker 仍存活并持续推进时，
  才可把调大 `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS` 作为受控诊断或缓解；出现 rank 异常、
  OOM、集合通信分叉或死锁时应停止加时，转而定位最早失败的 rank。

## 工作流调用与阶段隔离

- 用户可以按编号或名称选择任意阶段：`architecture`（1）、`environment`（2）、
  `adaptation`（3）、`acceptance`（4）和 `retrospective`（5）。只执行所选阶段，多个阶段
  始终按 1→5 顺序执行；未选阶段只能作为前置条件检查，不得自动执行或重写。
- 进入所选阶段前，运行对应的 `./scripts/adapt-model ... --check-only`；步骤 2～5 必须提供
  准确 Host。前置身份、证据、状态或时效性缺失/冲突时，停止并报告准确阻塞，不得静默
  补跑其他阶段或只刷新哈希。
- 验收子步骤可以单独选择，但顺序固定为：`execution-mode` → `sanity` → `accuracy` →
  `performance` → `evidence` → `summary`。不得执行未选择的子步骤，也不得跳过未完成的
  前置验收条件。
- 当前 `adapt-model` 实现仍包含旧版结构化文件门禁。平台步骤 2～5 不得以创建模式运行该
  工具，也不得把它所需的旧 YAML/过程文件重新放回精简平台目录；这些阶段直接使用自然
  语言请求 Codex，并用 `audit-workspace` 检查本地布局，等待门禁迁移。步骤 1 的结构分析
  初始化仍可使用。
- 只有所选工作已经真实验证且证据仍然有效，才能更新 `platform.yml`。按
  `docs/workflow-guide.md` 绑定阶段及验收回执，并在环境分析中记录和核实准确 Host 集合。
  正式精度必须有通过的
  `acceptance-result.json`；正式性能必须使用 `test/perf_test/perf_acceptance.py` 导出的
  回执，不能用 Markdown/CSV 成功标签代替。
- 使用 `./scripts/audit-workspace` 检查本地结构和历史状态；warning 需要人工复核，不能作为
  远端成功证据。

## 详细工作流程（执行前必读）

执行模型分析、环境分析、适配、验收或复盘前，必须读取
[详细五阶段工作流程](docs/model-adaptation-workflow.zh-CN.md)，并按顺序执行所选阶段。
详细规则仍是强制要求；拆分文档不削弱任何安全边界或验收条件。
本地命令和证据绑定方法见 [工作流操作指南](docs/workflow-guide.md)。

## 验证与报告

- 修改 inventory 或组变量后，运行 `./scripts/inventory`。
- 修改 inventory、变量或 playbook 后，运行 `./scripts/syntax-check`。
- 对多主机操作，应逐台报告结果，并区分未变化、已变化、失败和不可达状态。
- 对未连接或未验证的主机，不得声称操作成功。
- 使用 `./scripts/connectivity-check`，不能只依赖 SSH 退出码；堡垒机可能在报告找不到
  资产的同时返回退出码 0。

## 密钥与敏感信息

- 不得提交密钥。SSH 密钥使用 SSH agent/keychain，其他凭据使用 Ansible Vault 或经
  批准的密钥管理器。
- 包含敏感信息的 Ansible 任务必须设置 `no_log: true`。
