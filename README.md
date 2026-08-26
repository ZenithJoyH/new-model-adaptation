# 新模型适配：远程运维控制仓库

这个仓库把 Codex 所在的本机作为控制端，通过现有 SSH 别名管理远程
服务器。远程服务器不需要安装 Codex CLI。

## 模型适配工作区

模型相关工作统一放在 `models/<model-name>/<platform>/`。当前首个模型是
[Qwen3.5-397B-A17B](models/Qwen3.5-397B-A17B/README.md)：

```text
models/Qwen3.5-397B-A17B/
├── model.yml
├── _shared/
├── nvidia/
├── ppu/
├── metax/
├── ascend/
├── mthreads/
└── hygon/
```

每个平台目录保存自己的环境信息、启动/停止命令、配置、补丁、正确性用例和
性能结果，跨平台内容放在 `_shared`。完整约定见 [models/README.md](models/README.md)。

公共的最终性能、精度和通信测试工具位于 [test/](test/README.md)。每次模型适配完成
前，应选择与目标平台适用的测试工具执行验证，并把模型专用配置和简要结果记录在对应
的平台目录中。

创建下一个模型：

```bash
./scripts/new-model <model-name>
```

## 当前管理范围

`managed` 总组当前包含 12 个具体主机别名：

| 子组 | 主机 |
|---|---|
| `nvidia` | `H20-141`、`H100-205` |
| `metax` | `mx-103`、`mx-104` |
| `mthreads` | `mthread-07`、`mthread-08` |
| `ascend` | `910C-120`、`910C-121` |
| `hygon` | 当前暂无 SSH 别名，已预留平台组 |
| `ppu` | `PPU-01`、`PPU-03`、`PPU-07`、`PPU-13` |

SSH 用户、端口、堡垒机和密钥继续由本机 `~/.ssh/config` 管理，仓库中不
保存这些信息。

## 初始化控制端

首次使用时安装本地 Ansible 环境：

```bash
./scripts/bootstrap-control-node
```

该命令只在本仓库的 `.venv` 中安装依赖，并自动选择 Python 3.12 或更新
版本。本机需要手动指定解释器时可以使用：

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
./scripts/accelerator-check --limit H20-141 -e full_output=true

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

执行修改前请遵循 [AGENTS.md](AGENTS.md) 中的安全边界。特别是批量变更、
删除、重启、停止服务以及覆盖已有配置。
