# 新模型适配：远程运维控制仓库

这个仓库把 Codex 所在的本机作为控制端，通过现有 SSH 别名管理远程服务器。远程服务器不需要安装 Codex CLI。

## 模型适配工作区

模型相关工作统一放在 `models/<model-name>/<platform>/`。现有模型与状态入口：

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
├── metax/
├── ascend/
├── mthreads/
└── hygon/
```

每个平台目录分为三类材料：
- `environment/` 保存环境分析、平台适配计划、结构化运行
配置和服务状态；
- `adaptation/` 只保存按问题编号的 Markdown 台账及其索引；
- `acceptance/` 保存验收配置、简要证据、总结与复盘。Plugin 仓库只保存必要的产品实现和
可长期维护的回归测试；

一次性诊断、部署、日志分析、探针和试验代码放在适配容器中独立的临时工作目录，不得放入 Plugin 仓库。问题台账只引用准确路径、revision、命令和结论。跨平台内容放在 `_shared`。完整约定见 [models/README.md](models/README.md)。

公共的最终性能、精度和通信测试工具位于 [test/](test/README.md)。每次模型适配完成前，应选择与目标平台适用的测试工具执行验证，并把模型专用配置和简要结果记录在对应的平台目录中。

修改模型适配 plugin 代码前，可参考
[vllm-plugin-FL 项目分析与新模型适配代码修改指南](docs/vllm-plugin-FL-analysis.md)，按模型注册、算子 dispatch、平台 backend、量化、attention/MoE 和 graph 执行链路选择最小改动面。

插件代码按 [修改与 PR 交付标准](docs/plugin-contribution-policy.md) 设计，重点核对框架职责、已有模型/平台行为、实际回归范围和最终 diff。阶段 3 会准备 `environment/plugin-change-review.md`，适配收尾时填写真实审查结论；模板存在不代表代码已通过设计审查。

开始环境变更、适配实现或验收前，应先检索
[新模型适配故障知识库](docs/troubleshooting/README.md)。已有经验只能作为需要在当前模型、平台和软件 revision 上重新验证的候选方案；新经验先记录在当前模型平台`adaptation/` 下对应的编号问题记录中，并登记到 `adaptation/README.md`，验证充分后再提升到仓库级知识库，并在复盘中审计。

创建下一个模型：

```bash
./scripts/new-model <model-name>
```

## 在 Codex 中按步骤调用适配流程

日常操作入口和证据绑定方法见 [工作流操作指南](docs/workflow-guide.md)。
先运行 `./scripts/audit-workspace` 检查全仓库结构和历史状态；正式进入下一阶段时，
运行对应的 `adapt-model --check-only`。前者的 warning 表示待复核，不能替代后者的门禁。
本轮目录治理、备份与已知待复核项见 [治理记录](docs/workspace-maintenance.md)。
旧的一次性执行入口已按[停用清单与替代路径](docs/legacy-entrypoints.md)保留原文并拒绝重放；
不要把历史启动记录当作当前执行入口。

完整的新模型适配流程分为五个可单独调用或组合调用的步骤：

1. 模型结构与推理链路分析（`architecture`）
2. 推理环境分析（`environment`）
3. 进行适配（`adaptation`）
4. 适配验收（`acceptance`）
5. 适配复盘（`retrospective`）

不需要使用特殊命令或斜杠指令。在本项目的 Codex 任务中直接说明模型、平台、目标机器和要执行的步骤即可。推荐使用下面的统一模板：

```text
模型：<模型名称>
平台：<nvidia|ppu|metax|ascend|mthreads|hygon>
目标机器：<SSH Host 别名；步骤 1 可不填写>
远端工作目录：<用户指定的宿主机绝对目录；多机逐一列出>
容器工作目录：<已有容器名及容器内对应绝对目录；须核实挂载关系>
执行步骤：<1 / 2 / 3 / 4 / 5，可指定一个或多个>
验收子步骤：<可选，仅执行步骤 4 中的指定项目>
参考文件：<路径，可选>
执行边界：只执行指定步骤；其他步骤只检查前置产物，不自动执行
完成条件：<完成后停止，或继续到下一个指定步骤>
```

未指定远端工作目录时，先确认目录再创建或写入远端文件。所有新增工作产物集中在该目录，不自动移动旧文件、修改挂载或在目录外创建临时脚本。规则及配置格式见[远端工作目录约束](docs/workflow-guide.md#远端工作目录约束)。

也可以先使用阶段工具初始化所选步骤的缺失文件、检查结构化前置条件，并生成上述Codex 调用文本。该工具本身不执行远程命令，也不会修改阶段状态：

```bash
# 步骤 1 不要求平台
./scripts/adapt-model Qwen3.8-Flash-Next --steps architecture

# 多个步骤始终按 1 到 5 的顺序解析
./scripts/adapt-model Qwen3.8-Flash-Next --platform ppu \
  --hosts PPU-01 --steps architecture,environment,adaptation

# 步骤 3 已通过后，只准备指定验收子步骤
./scripts/adapt-model Qwen3.8-Flash-Next --platform ppu \
  --hosts PPU-01 --steps acceptance --acceptance-substeps execution-mode,sanity

# 只检查，不创建任何文件
./scripts/adapt-model Qwen3.8-Flash-Next --platform ppu \
  --hosts PPU-01 --steps adaptation --check-only
```

首次为某个平台调用阶段工具时，它会在需要的阶段内从 `templates/adaptation/` 创建缺失文件，但不会覆盖已有记录。旧模型的 `platform.yml` 如果尚无五阶段状态结构，非`--check-only` 模式只补充缺失字段，不改写已有字段。

进入步骤 3 或步骤 4 前，需要填写平台 `environment/runtime-config.yml`。工具会检查目标 Host是否属于对应 inventory 组、是否误存敏感连接字段、vLLM 只读和容器保持运行边界、软件 revision、`eager`/`graph` 配置、模型长度计算规则，以及所选验收子步骤需要的graph 服务、FlagEval 镜像和测试配置。配置不完整时只报告缺项，不会绕过门禁。

只执行模型分析：

```text
对 Qwen3.8-Flash-Next 执行步骤 1：模型结构与推理链路分析。
只执行这一步，不进行环境分析或实际适配。
```

连续执行多个步骤：

```text
模型：Qwen3.8-Flash-Next
平台：ppu
目标机器：PPU-01
执行步骤：1、2
执行边界：只执行步骤 1 和步骤 2
完成条件：完成模型分析和环境分析后停止，不进入实际适配
```

基于已有材料从中间步骤继续：

```text
模型：Qwen3.8-Flash-Next
平台：ppu
目标机器：PPU-01
执行步骤：3
参考文件：使用该模型目录下已有的模型分析、PPU 环境分析和参考文件
执行边界：步骤 1 和步骤 2 只检查前置产物，不重新执行
完成条件：适配完成后停止，暂不进入验收
```

步骤 4 还可以只调用某个验收子步骤，包括执行模式验收、8 并发小批量精度与
性能验证、全量精度测试、正式性能测试、验收证据整理和最终适配总结。例如：

```text
模型：Qwen3.8-Flash-Next
平台：ppu
目标机器：PPU-01
执行步骤：4
验收子步骤：8 并发小批量精度与性能验证
执行边界：只执行指定验收子步骤，不启动全量精度和正式性能测试
```

每个步骤可以单独调用，但后续步骤仍有前置依赖。Codex 应先检查已有产物是否完整、有效并与当前模型、平台和环境一致；若前置条件缺失、失败或已经过期，应停止并报告，不得擅自补跑未指定的步骤。多个步骤即使按不同顺序写出，也必须按照1 到 5 的流程顺序执行。阶段文件的保存位置、完成标准和安全边界以[AGENTS.md](AGENTS.md) 为准。

## 当前管理范围

`managed` 总组当前包含 13 个具体主机别名：

| 子组 | 主机 |
|---|---|
| `nvidia` | `H100-145`、`H100-149`、`H100-205` |
| `metax` | `mx-103`、`mx-104` |
| `mthreads` | `mthread-07`、`mthread-08` |
| `ascend` | `910C-120`、`910C-121` |
| `hygon` | 当前暂无 SSH 别名，已预留平台组 |
| `ppu` | `PPU-01`、`PPU-03`、`PPU-07`、`PPU-13` |

SSH 用户、端口、堡垒机和密钥继续由本机 `~/.ssh/config` 管理，仓库中不保存这些信息。

## 初始化控制端

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
./scripts/accelerator-check --limit H100-145 -e full_output=true

# 海光平台查询加速卡进程
./scripts/accelerator-check --limit hygon -e show_processes=true
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
