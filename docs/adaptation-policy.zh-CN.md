# 模型适配细则

本文件承接 [仓库规则](../AGENTS.zh-CN.md) 中的适配要求，执行任一适配阶段前必读。
代码路径均相对仓库根目录。远端写入边界、目录编号和最终启动脚本的完整要求见
[远程操作细则](remote-operations.zh-CN.md)，进行远端操作或核验最终启动脚本时必须读取。
英文规范见 [adaptation-policy.md](adaptation-policy.md)。

## 新模型适配工作区

每次适配都有三个身份维度：**模型、硬件平台、framework profile**。进行框架相关的环境
变更、代码实现或验收前，必须先从 `framework-profiles/` 选择 active 或 experimental profile。现有直接位于
`models/<model>/<platform>/` 的记录按历史隐式 `vllm-plugin-fl` profile 解释，不得批量迁移。
draft/不完整 profile 只允许模型分析和只读调查；experimental 允许声明的适配和基础验证，
但不能完成正式整体验收或标记 optimized。Profile 可以收紧，
但不得削弱仓库通用安全与证据要求。

新模型适配工作区明确分为两个相互独立的部分：

1. **远端工作目录**：用户为一个准确“模型 × 平台 × framework profile”任务在每台目标
   主机批准的实际执行区域，供适配容器和远端命令存放
   运行配置、一次性诊断、运行结果、缓存及算子复现；它不是源码 checkout 或仓库镜像。
2. **本地工作目录**：当前管理仓库，用于保存精简的模型/平台/框架记录、可复用控制工具、模板
   以及远端证据引用，不作为远端运行产物的镜像。

本地记录必须引用准确的远端路径和 revision；不得把远端原始产物整批复制进本地工作目录，
也不得把本地已有记录视为远端写入授权。

### 本地工作目录

- 本仓库只记录已明确模型和平台的新模型跑通、平台验证及推理优化。不得记录无关运维、
  普通包安装、聊天、探索性输出或未经验证的结论；未经用户明确要求不得提交或推送。
- 使用 `./scripts/new-model <model-name>` 创建模型且不得覆盖已有目录。平台名称限定为
  `nvidia`、`ppu`、`metax`、`ascend`、`mthreads` 和 `hygon`。
- 使用 `./scripts/new-framework <model> <platform> <framework-id>` 创建显式框架工作区；不得
  手工复制 profile 或复用另一个框架的状态。
- `models/<model>/<platform>/` 根目录只保留 `README.md`、`platform.yml`、可选的
  `frameworks/` 以及历史直接记录。新任务放在
  `models/<model>/<platform>/frameworks/<framework-id>/`，其根目录只保留 `README.md`、
  `framework.yml`，以及三个目录：
  `environment/` 只放 Markdown 格式的环境/平台分析；
  `adaptation/` 仅作为带编号的 Markdown 问题台账；`acceptance/` 只放 Markdown 格式的
  验收计划、结果报告、总结和复盘。三个本地目录均不得建立子目录，也不得放脚本、
  Playbook、JSON/YAML 配置、原始输出、缓存或临时文件。
  模型级内容放 `architecture-and-inference.md` 与 `_shared/`；公共测试工具保留在 `test/`。
- `_shared/` 只保留 Markdown 索引和少量合并后的跨平台分析，确保便于阅读。上游原始
  元数据、复制模板、一次性检查脚本、JSON/YAML 快照和其他采集产物统一放在该 framework
  profile 已批准的远端
  根目录，不得保存在本地模型目录。
- `adaptation/` 不得放脚本、Playbook、补丁、源码或算子实现、复制测试、原始日志、运行
  JSON/YAML 或命令输出。Profile 声明可写的产品源码只放产品必需代码和可维护的局部测试；
  一次性过程代码放远端 `02-issues/` 或 `05-tmp/`，置于全部产品、框架和内核源码仓库之外
  且不得提交。可跨模型
  工具只有经用户批准后才能提升到仓库级 `scripts/`。
- 可执行的过程产物放在已批准远端根目录：环境采集与运行配置放 `01-environment/`，
  一次性诊断放 `02-issues/` 或 `05-tmp/`，验收包装与配置放 `03-acceptance/`，原始结果
  放 `04-runs/`。本地 Markdown 只总结可重复命令并记录准确 Host、远端路径、revision、
  引擎、镜像、参数、输入、日期、用途和验证结果；清理远端临时文件前保留最小必要证据。

### 状态与收尾

- 优化前建立正确性和性能基线，每次只改变一个实质变量，并保留对比。
- 按 profile 的图模式优先顺序逐级尝试；vLLM 使用
  `full` → `full-and-piecewise` → `decode-full` → `piecewise`。
  每个更高档位都要记录准确配置、可复现问题、定位、修复尝试、仍无法解决的阻塞、证据和
  恢复尝试条件，不能直接选择更容易跑通的低档位。性能与实际生效模式的检查按
  [通用工作流](model-adaptation-workflow.zh-CN.md)执行。完整回退链有证据后，piecewise
  可以验收；仅 eager 仍只用于诊断，不能算 graph 通过。后续验收和启动脚本绑定逐 Host
  最终验证模式。
- 正式全量精度评测只有一个数值通过标准：有效的完整评测回执中，每个在运行前冻结的指标
  都达到其配置阈值，即可把精度子步骤标记为 `passed` 或 `complete`。指标不必达到 `1.0`，
  因而允许存在少量答错的题目；“逐题全部正确”只属于前置小批量 sanity，不得用作正式
  精度完成条件。最终超时的请求必须保留为失败/错误样本，计入完整样本总数和指标分母，
  不得被丢弃、忽略或用重试掩盖；只要样本仍完整且所有冻结指标达到阈值，允许存在少量
  此类超时。缺失或无效样本、非超时的请求/执行错误、过期证据或任一指标低于阈值，仍按
  项目精度契约判定为失败或证据不完整。
- 完成前更新 framework 工作区 `README.md` 中的结果、问题、原因、方案、限制和下一步，
  并与 `framework.yml` 同步；历史隐式记录继续更新平台 `README.md` 与 `platform.yml`。
  同时核验远程操作细则要求的远端根目录顶层 `start-model.sh`；仅有文件不构成完成
  证据。最小推理通过后才能标记 `functional`；正确性回归和性能结果记录后
  才能标记 `optimized`。
- 不得提交权重、密钥、完整日志或大型原始 benchmark。

技术适配完成后、最终交付前，Agent 调用[镜像发布与部署 Skill](../skills/adaptation-deployment-guide/SKILL.md)
生成本地英文 `acceptance/deployment-guide.md`。除非任务已包含镜像发布/部署，否则只生成文档。
有明确请求时，同一 Skill 完成候选验证、推送及已发布镜像的全新容器部署，复用已验收启动
脚本且不停止适配源容器；发布状态与技术适配验收分开记录。模板在 Skill 内维护，权重下载仅写使用说明，
不执行下载。单独调用、草稿处理和阶段隔离见[完成交付](model-adaptation-workflow.zh-CN.md#完成交付英文部署文档)。

## 框架实现与 PR 质量

- vLLM/SGLang 插件从计划、实现、测试到 PR 准备均遵循用户提供的
  [开发规范 v1](inference-plugin-development-v1.md)。先读综述，再按任务索引读取全部适用条款；
  在已有计划/审查中记录条款编号、证据、未满足的【必须】及偏离【应该】的理由。新增数值实现
  放在 FlagGems 或框架专用算子库，通过公开 API 接入；框架 metadata 按 A3 保留在框架侧。
  这取代旧的“缺失数值 Triton kernel 放 Plugin 内”要求，不授权新增可写组件、未支持 profile
  或远端操作。
- 将修改按多模型、多平台框架的可维护贡献来设计。修改前阅读选定 profile、其工作流与验收
  文档，以及目标 checkout 的设计、贡献和测试规范。选择 `vllm-plugin-fl` 时还必须遵守
  [Plugin 修改与 PR 标准](plugin-contribution-policy.md)。
- 修改前在已有计划或问题记录中限定变更清单：已确认需求、负责组件、文件/符号、增改删、
  基线和回归测试。逐组件执行，包括声明可写时的 Plugin、FlagGems、FlagGems-vllm。
  删除须有调用方/注册/兼容性证据，不能仅凭当前模型未使用；不夹带无关清理、整层重写
  或跨组件重复 workaround。改中对照计划查看增量 diff；扩展前说明依据，超出任务边界
  的工作须另获授权。
- 在平台环境分析或对应的编号适配问题中说明职责归属、现有扩展点、接口契约、替代方案
  和受影响调用方。复用已有 dispatch/注册路径，模型语义放在模型适配层，硬件
  约束放在 vendor/能力路径；不得在公共执行代码散布模型名称或特定机器的例外。
- 保持作用域外的既有行为。验证适用的已有模型调用方、守卫未命中路径、可选依赖隔离和
  选定 profile 要求的全部执行模式（`vllm-plugin-fl` 为 eager/graph）。缺少硬件或未执行
  测试时明确限制，不能从一个模型跑通推断多平台支持。
- 适配收尾和准备 PR 时审查真实 diff，并把审查结论记录在相关编号问题和最终验收总结中。
  记录已确认的 PR base、当前 HEAD、dirty/新增文件、既有改动、影响矩阵、测试证据、
  workaround 退出条件及剩余风险。实质变更后更新审查；设计阻塞未解决不能标记适配完成。
  逐组件、逐 diff 块核对计划和所有增删；无法解释的改动或已知回归阻止源码审查通过。
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

- 精度与性能工作使用本仓库入口，能力 ID 为 `adaptation/accuracy`、
  `adaptation/performance`，要求调用方显式传入操作。Hub 或全局同名 Skill 不代表
  相同的原生证据生产者。
- 执行前读取 `docs/skills-project-contract.md` 中的项目方法及原生 runner 映射，
  不动态读取旁边可变的 Hub 工作区。切换实现必须显式比较接口与证据协议。
- 长任务需要恢复记录时遵循 `docs/agent-execution.md`：冻结 Skill 与输入身份，
  执行原生前后检查，重试前先检查既有 run。记录器不扩大远程权限，不替代框架业务状态；
  后续动作由调用方 Agent 决定。
- 对具备前缀缓存的框架，模型分析、环境分析、适配、执行模式、小批量与精度等非性能环节
  保持前缀缓存开启。本项目仅对性能测试增加一个强制前置条件：任何性能测试或
  Profiling 开始前，必须复用精度测试的最小 `start-model.sh`，仅选择其显式性能开关，遵循
  [统一服务启动入口](remote-operations.zh-CN.md#统一服务启动入口)，不得把关闭参数写入通用 graph
  配置；应使用选定 framework profile 声明的准确缓存关闭机制，并从实际生效的启动配置和
  启动证据核实其关闭状态，随后把证据引用绑定到正式性能回执。`vllm-plugin-fl` profile
  中仍必须在本轮被测实例加入准确参数 `--no-enable-prefix-caching`。
  客户端 workload 的随机前缀长度为 0 不能证明服务端前缀缓存已经关闭；无法核实该准确
  参数已生效且缓存处于关闭状态时，不得启动性能测试，也不得把 performance 子步骤标记
  为通过。后续如果继续进行任何非性能测试，必须恢复为开启前缀缓存的普通服务配置。

- 用户可以按编号或名称选择任意阶段：`architecture`（1）、`environment`（2）、
  `adaptation`（3）、`acceptance`（4）和 `retrospective`（5）。只执行所选阶段，多个阶段
  始终按 1→5 顺序执行；未选阶段只能作为前置条件检查，不得自动执行或重写。
- 步骤 2～5 必须指定 active 或 experimental framework profile 和准确 Host。新框架工作区使用
  `./scripts/new-framework` 创建，并用 `./scripts/audit-workspace` 检查本地结构；历史直接平台
  记录继续使用已有检查。前置身份、证据、状态或时效性缺失/冲突时，停止并报告准确阻塞，不得静默
  补跑其他阶段或只刷新哈希。
- 验收子步骤由 profile 的有序 `acceptance.steps` 决定。vllm-plugin-fl 使用
  execution-mode → sanity → accuracy → performance → evidence → summary；Torch-FL 使用
  device → operators → model-eager → 可选 wheel → summary。不得混用框架流程或跳过前置。
- 显式工作区用 `adapt-model --framework <id> --check-only` 核对前置，加 `--verify-records`
  校验所选步骤的完成证据。按 `docs/framework-evidence.md` 读取批准远端根下的原生回执，
  无法读取时不得以 Markdown 代替。
- 未带 `--framework` 的旧 `adapt-model` 实现仍包含结构化文件门禁。平台步骤 2～5 不得以创建模式运行该
  工具，也不得把它所需的旧 YAML/过程文件重新放回精简平台目录；这些阶段直接使用自然
  语言请求 Codex，并用 `audit-workspace` 检查本地布局，等待门禁迁移。步骤 1 的结构分析
  初始化仍可使用。
- 只有所选工作已经真实验证且证据仍然有效，才能更新当前 `framework.yml`；历史隐式记录
  继续更新 `platform.yml`。按
  `docs/skills-project-contract.md` 和 `docs/workflow-guide.md` 绑定阶段及验收回执，并在环境
  分析中记录和核实准确 Host 集合。原生回执名称、校验命令和失效规则只在项目契约中维护，
  不在本细则中重复。
- 使用 `./scripts/audit-workspace` 检查本地结构和历史状态；warning 需要人工复核，不能作为
  远端成功证据。

## 详细工作流程（执行前必读）

执行模型分析、环境分析、适配、验收或复盘前，必须读取
选定 profile 的 workflow 与 acceptance 文档，再读取
[详细五阶段工作流程](model-adaptation-workflow.zh-CN.md)，并按顺序执行所选阶段。
详细规则仍是强制要求；拆分文档不削弱任何安全边界或验收条件。
本地命令和证据绑定方法见 [工作流操作指南](workflow-guide.md)。

## 合同版本、人工交接与可复现交付

新工作区按 [v2 契约](evidence-contract-v2.md) 固定 profile 快照；文档措辞或当前 profile 更新
不会静默升级已有结果。人工接管后显式执行 `workspace-control upgrade`，保留旧回执并复核
受影响阶段。旧阶段 2～5 的创建入口已停用，只读检查仍保留。

任一阶段均可按[人工协作](human-collaboration.md)接管和交回。交接记录身份、工作根与进程，
不停止现有进程；交回核对变更和原生证据，同一验收器验证通过的人工新回执可以直接采用。

可将经脱敏的小型可复现交付放在独立 `deliveries/<model>/<platform>/<framework>/`：
启动脚本、配置、源码补丁或引用、依赖锁定与恢复说明。该例外不允许权重、密钥、原始日志、
结果与过程临时文件进入仓库；仍需用户要求才能提交/推送。记录文件哈希和镜像实际验证状态，
镜像 `pending` 不等于打包验证通过。
