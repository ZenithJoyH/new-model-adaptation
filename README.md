# 新模型适配：远程运维控制仓库

这个仓库把 Codex 所在的本机作为控制端，通过现有 SSH 别名管理远程服务器。远程服务器不需要安装 Codex CLI。

## 模型适配工作区

模型适配工作区分为两部分，二者用途不同，不做整目录镜像：

- **远端工作目录**：用户为一个“模型 × 平台 × framework profile”适配任务在目标服务器上
  明确指定的绝对目录，使用 `01-environment/` 至
  `07-bugs/` 的带序号目录保存环境采集、临时诊断、运行日志、缓存、
  验收结果和算子复现；适配完成后在根目录顶层保留最终 `start-model.sh`。涉及容器时还要
  核实该脚本及各子目录对应的容器绝对路径与挂载关系。最终脚本只保留已验收配置必需的
  参数和设置，不复制诊断或测试命令，不包含性能测试专用参数；能依赖稳定默认值时不显式
  传入，每个最终保留的显式项都要有可追溯的必要性依据。
- **容器内源码**：远端工作目录不创建源码仓库子目录或源码副本。允许修改的组件和位置由
  当前 [framework profile](framework-profiles/README.md) 明确声明，未声明组件默认只读。
  `vllm-plugin-fl` profile 仍要求修改 editable-install Plugin、保持 vLLM 只读，并只使用
  容器内已核实且获准同步的 FlagGems checkout。
- **本地工作目录**：当前 Git 仓库，保存 `models/` 下精简、可追溯的模型/平台/框架记录，以及
  `scripts/`、`test/`、`templates/` 和 `docs/` 中的通用工具与规范。本地只记录准确远端路径、
  revision、命令和结论，不复制完整远端日志、缓存或临时文件。

新编号从新写入和新运行计划开始生效。既有适配记录中的旧编号路径仍表示真实历史位置，
不会在远端目录尚未迁移和复核时仅为统一文本而改写。

本地模型记录统一放在 `models/<model-name>/<platform>/`；同一模型和平台存在多套推理框架
时，使用 `frameworks/<framework-id>/` 隔离。现有直接位于平台根目录的历史记录按隐式
`vllm-plugin-fl` profile 解释，不批量迁移。现有模型与状态入口：

- [GLM-5.3-Flash-BF16](models/GLM-5.3-Flash-BF16/README.md)
- [Hy4-preview](models/Hy4-preview/README.md)
- [Qwen3.8-Flash-Next](models/Qwen3.8-Flash-Next/README.md)
- [XingChen4-29B-A4B](models/XingChen4-29B-A4B/README.md)

目录示例：

```text
models/<model-name>/
├── model.yml
├── _shared/
├── nvidia/
├── ppu/
│   └── frameworks/
│       ├── vllm-plugin-fl/
│       └── <future-framework>/
├── metax/
├── ascend/
├── mthreads/
└── hygon/
```

每个显式 framework 工作区分为三类材料：
- `environment/` 只保存 Markdown 环境与平台分析；
- `adaptation/` 只保存按问题编号的 Markdown 台账及其索引；
- `acceptance/` 只保存 Markdown 验收计划、结果报告、总结与复盘。三个目录均不保存脚本、
Playbook、JSON/YAML、原始日志、缓存或临时子目录。框架 profile 指定的产品代码仓库只保存
必要实现和可长期维护的回归测试。

一次性诊断、部署、日志分析、探针和试验代码放在用户批准的远端工作根目录，不得放入
任何产品源码仓库。问题台账只引用准确路径、revision、命令和结论。跨平台内容放在 `_shared`。
完整约定见 [models/README.md](models/README.md)。

公共的最终性能、精度和通信测试工具位于 [test/](test/README.md)。每次模型适配完成前，
应选择与目标平台适用的测试工具执行验证；模型专用可执行配置和原始结果留在远端工作根
目录，本地平台 `acceptance/` 只记录验收结论和准确证据路径。正式精度 runner 支持同一
FlagEval 镜像内的一个或多个 lm-eval task；GPQA 只是默认示例，每个数据集都必须单独冻结
完整样本数、指标键和验收阈值。

精度和性能使用项目内维护的评测入口，能力 ID 为 `adaptation/accuracy`、
`adaptation/performance`，保留原有目录路径。Hub 的公共能力可作为参考，但不得动态读取
未冻结的同名 Skill 来替代本项目的 runner 与原生回执。具体操作见
[评测 Skills](skills/README.md)，接口指纹、前后校验和长任务恢复见
[Agent 执行记录](docs/agent-execution.md)。

使用 `vllm-plugin-fl` profile 修改模型适配 Plugin 前，可参考
[vllm-plugin-FL 项目分析与新模型适配代码修改指南](docs/vllm-plugin-FL-analysis.md)，按模型注册、算子 dispatch、平台 backend、量化、attention/MoE 和 graph 执行链路选择最小改动面。

`vllm-plugin-fl` 的 Plugin 代码按 [修改与 PR 交付标准](docs/plugin-contribution-policy.md)
设计；其他框架按各自 profile 和目标源码规范执行。所有框架都要核对职责、已有模型/平台
行为、实际回归范围和最终 diff。设计审查结论写入对应编号适配问题和最终验收总结；文档
存在不代表代码已通过设计审查。

开始环境变更、适配实现或验收前，应先检索
[新模型适配故障知识库](docs/troubleshooting/README.md)。已有经验只能作为需要在当前模型、
平台、framework profile 和软件 revision 上重新验证的候选方案；新经验先记录在当前 framework
工作区 `adaptation/` 下对应的编号问题记录中，验证充分后再提升到仓库级知识库，并在复盘中审计。

创建下一个模型：

```bash
./scripts/new-model <model-name>
```

为模型和平台创建一套显式框架适配记录：

```bash
./scripts/new-framework <model-name> <platform> <framework-id>
```

当前可用 profile 及新增方式见 [framework-profiles/README.md](framework-profiles/README.md)。

## 在 Codex 中按步骤调用适配流程

日常操作入口和证据绑定方法见 [工作流操作指南](docs/workflow-guide.md)。
先运行 `./scripts/audit-workspace` 检查全仓库结构和历史状态；其中的 warning 表示待复核，
不能作为远端或阶段成功证据。
旧的一次性执行入口已按[停用清单与替代路径](docs/legacy-entrypoints.md)保留原文并拒绝重放；
不要把历史启动记录当作当前执行入口。

工作记录分为五个可单独调用或组合调用的阶段；每个框架的实际实施和验收步骤由 profile 独立定义：

1. 模型结构与推理链路分析（`architecture`）
2. 推理环境分析（`environment`）
3. 进行适配（`adaptation`）
4. 适配验收（`acceptance`）
5. 适配复盘（`retrospective`）

不需要使用特殊命令或斜杠指令。在本项目的 Codex 任务中直接说明模型、平台、目标机器和要执行的步骤即可。推荐使用下面的统一模板：

```text
模型：<模型名称>
平台：<nvidia|ppu|metax|ascend|mthreads|hygon>
推理框架：<framework profile ID；旧记录可写 vllm-plugin-fl>
目标机器：<SSH Host 别名；步骤 1 可不填写>
远端工作目录：<用户指定的宿主机绝对目录；多机逐一列出>
容器工作目录：<已有容器名及容器内对应绝对目录；须核实挂载关系>
执行步骤：<1 / 2 / 3 / 4 / 5，可指定一个或多个>
验收子步骤：<可选，仅执行步骤 4 中的指定项目>
参考文件：<路径，可选>
执行边界：只执行指定步骤；其他步骤只检查前置产物，不自动执行
完成条件：<完成后停止，或继续到下一个指定步骤>
```

未指定远端工作目录时，先确认目录再创建或写入远端文件。所有新增工作产物集中在该目录，不自动移动旧文件、修改挂载或在目录外创建临时脚本。规则及配置格式见[远端执行目录](docs/workflow-guide.md#3-远端执行目录)。

步骤 1 可以使用阶段工具初始化模型结构分析文档。显式框架工作区使用 `adapt-model --framework <id> --check-only` 检查前置，
使用 `--verify-records` 验证完成证据；具体操作仍可用自然语言调用。旧入口只用于历史记录，
不得把其旧 YAML/过程文件放回精简目录。命令及远端证据读取见 [框架证据契约](docs/framework-evidence.md)。

```bash
./scripts/adapt-model Qwen3.8-Flash-Next --steps architecture
```

步骤 2～5 的请求必须明确目标 Host，并由执行者核对其是否属于对应 inventory 组。实际运行
配置、采集脚本、验收包装和原始结果保存在用户为该 framework profile 批准的独立远端工作
根目录，本地模型目录只保留 Markdown 分析、问题记录和验收结论。适配容器保持运行；源码
修改边界、执行模式、服务协议和验收方式按选定 profile 执行。`vllm-plugin-fl` 仍要求 vLLM
只读以及 eager/graph 验收；graph 先尝试并优先采用覆盖 prefill 与 decode 的 `full` 全量图，
只有具备阻塞证据时才可降级到最低要求 `decode-full`，后续验收和最终启动脚本沿用已验收的
最高图级别。

只执行模型分析：

```text
对 Qwen3.8-Flash-Next 执行步骤 1：模型结构与推理链路分析。
只执行这一步，不进行环境分析或实际适配。
```

连续执行多个步骤：

```text
模型：Qwen3.8-Flash-Next
平台：ppu
推理框架：vllm-plugin-fl
目标机器：PPU-01
执行步骤：1、2
执行边界：只执行步骤 1 和步骤 2
完成条件：完成模型分析和环境分析后停止，不进入实际适配
```

基于已有材料从中间步骤继续：

```text
模型：Qwen3.8-Flash-Next
平台：ppu
推理框架：vllm-plugin-fl
目标机器：PPU-01
执行步骤：3
参考文件：使用该模型目录下已有的模型分析、PPU 环境分析和参考文件
执行边界：步骤 1 和步骤 2 只检查前置产物，不重新执行
完成条件：适配完成后停止，暂不进入验收
```

vllm-plugin-fl 的步骤 4 还可以只调用某个验收子步骤，包括执行模式验收、10 并发小批量精度与
性能验证、全量精度测试、正式性能测试、验收证据整理和最终适配总结。例如：

```text
模型：Qwen3.8-Flash-Next
平台：ppu
目标机器：PPU-01
执行步骤：4
验收子步骤：10 并发小批量精度与性能验证
执行边界：只执行指定验收子步骤，不启动全量精度和正式性能测试
```

也可以用同一套 Skill 语言明确评测深度，例如：

```text
模型：Qwen3.8-Flash-Next
平台：ppu
目标机器：PPU-01
使用 $inference-accuracy-evaluation，操作：formal-full
执行边界：只执行正式精度；已有执行模式和 sanity 仅做前置核验
```

```text
模型：Qwen3.8-Flash-Next
平台：ppu
目标机器：PPU-01
使用 $inference-performance-evaluation，模式：full-suite，目的：正式验收
执行边界：先以 gate-check 只读核验正式精度，再执行正式性能；不启动 profiling
```

每个步骤可以单独调用，但后续步骤仍有前置依赖。Codex 应先检查已有产物是否完整、有效并与当前模型、平台和环境一致；若前置条件缺失、失败或已经过期，应停止并报告，不得擅自补跑未指定的步骤。多个步骤即使按不同顺序写出，也必须按照1 到 5 的流程顺序执行。阶段文件的保存位置、完成标准和安全边界以[AGENTS.md](AGENTS.md) 为准。

## 当前管理范围

`managed` 总组当前包含 16 个具体主机别名（以本机 SSH 配置和 inventory 核对结果为准）：

| 子组 | 主机 |
|---|---|
| `nvidia` | `H100-145`、`H100-149` |
| `metax` | `mx-57`、`mx-58`、`mx-59`、`mx-60`、`mx-103`、`mx-104` |
| `mthreads` | `mthread-07`、`mthread-08` |
| `ascend` | `910C-120`、`910C-121` |
| `hygon` | 当前暂无 SSH 别名，已预留平台组 |
| `ppu` | `PPU-01`、`PPU-03`、`PPU-07`、`PPU-13` |

SSH 用户、端口、堡垒机和密钥继续由本机 `~/.ssh/config` 管理，仓库中不保存这些信息。

## 初始化控制端

### Codex 中的 Ansible 权限

本项目的 Ansible 2.21 控制端需要创建本地 Unix socket；Codex 默认文件沙箱会阻止该
socket。仓库已在 `.codex/rules/ansible.rules` 中配置分级放行：

- `./scripts/connectivity-check`、`./scripts/accelerator-check`、
  `./scripts/health-check` 和 `./scripts/inventory` 是参数已经收紧的只读入口，自动在沙箱外执行。
- `./scripts/ansible` 和 `./scripts/playbook` 可以在沙箱外执行，但由于参数能够产生任意
  远端变更，每条命令仍需审批。

首次加入或信任本项目后需重启 Codex，使项目级规则生效。调用时应以仓库根目录作为工作
目录，并保持上述相对路径写法；直接调用 `.venv/bin/ansible*`、通过 `bash` 包装、使用
绝对路径或复合命令不会匹配该规则。沙箱外执行只解决本地 RPC，目标主机确认、单机试运行、
`serial: 1`、容器保护和破坏性操作确认等安全要求仍然有效。

首次使用时安装本地 Ansible 环境：

```bash
./scripts/bootstrap-control-node
```

该命令只在本仓库的 `.venv` 中安装依赖，并自动选择 Python 3.12 或更新版本。本机需要手动指定解释器时可以使用：

```bash
PYTHON_BIN=/opt/homebrew/bin/python3.12 ./scripts/bootstrap-control-node
```

需要直接使用项目 Python 时激活虚拟环境：

```bash
source .venv/bin/activate
python --version
```

检查 inventory：

```bash
./scripts/inventory
```

检查 SSH/Ansible 连通性：

```bash
./scripts/connectivity-check
```

收集全部主机的只读健康信息：

```bash
./scripts/health-check
```

限制到一台服务器：

```bash
./scripts/health-check --limit PPU-01
```

也可以按硬件组限制范围：

```bash
./scripts/health-check --limit nvidia
./scripts/health-check --limit ascend
./scripts/health-check --limit ppu
```

## 查询加速卡

查询命令由硬件组自动选择，不应跨平台使用：

| 平台组 | 命令 |
|---|---|
| `nvidia` | `nvidia-smi` |
| `ascend` | `npu-smi info` |
| `ppu` | `ppu-smi` |
| `metax` | `mx-smi` |
| `hygon` | `hy-smi`；进程查询使用 `hy-smi --showpids` |
| `mthreads` | `mthreads-gmi` |

```bash
# 查询所有平台，自动选择正确命令
./scripts/accelerator-check

# 只查询某个平台
./scripts/accelerator-check --limit ascend
./scripts/accelerator-check --limit metax

# 查看某台机器的完整原始输出
./scripts/accelerator-check --limit H100-145 --full-output

# 海光平台查询加速卡进程
./scripts/accelerator-check --limit hygon --show-processes
```

`htop` 是交互式工具，需要通过 SSH 登录海光机器后使用，不由批量 Playbook
自动启动。平台命令不存在时检查会明确失败，不会回退到 `nvidia-smi`。

## 常用操作

```bash
# 查看所有机器磁盘（raw 不要求远端预装 Python）
./scripts/ansible managed -m ansible.builtin.raw -a 'df -h'

# 使用 PPU 平台对应的 ppu-smi 查询 PPU-03
./scripts/accelerator-check --limit PPU-03

# 检查 inventory 和所有 Playbook 语法
./scripts/syntax-check
```

执行修改前请遵循 [AGENTS.md](AGENTS.md) 中的安全边界。特别是批量变更、删除、重启、停止服务以及覆盖已有配置。

Torch-FL 当前为 experimental，可以创建工作区并进行 PPU 适配、算子路由和 eager 模型验证；
可选执行自包含 wheel 验证。它不强制使用 vLLM、graph 服务或 FlagEval，独立步骤通过不等于
完整正式验收。具体流程见 [Torch-FL](framework-profiles/torch-fl/workflow.md)。
