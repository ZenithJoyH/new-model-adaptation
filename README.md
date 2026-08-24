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

创建下一个模型：

```bash
./scripts/new-model <model-name>
```

## 当前管理范围

`managed` 总组包含 SSH 配置中的全部 16 个具体主机别名：

| 子组 | 主机 |
|---|---|
| `nvidia` | `H20-141`、`H100-205` |
| `metax` | `mx-103`、`mx-104` |
| `mthreads` | `mthread-07`、`mthread-08` |
| `ascend` | `910C-120`、`910C-121` |
| `hygon` | 当前暂无 SSH 别名，已预留平台组 |
| `ppu` | `PPU-240`、`PPU-231`、`PPU-233`、`PPU-234`、`PPU-01`、`PPU-03`、`PPU-07`、`PPU-13` |

`modelscope_hosts` 是经过 Python 3.12/ModelScope 路径验证的专用组，目前包含
`PPU-01`、`PPU-03`、`PPU-07`、`PPU-13`。这能避免将其专用路径错误应用到
其他异构服务器。

截至 2026-08-24，`PPU-233`、`PPU-234` 的堡垒机配置会返回“未发现匹配的
资产”。它们仍保留在 inventory 中；`connectivity-check` 会将这种退出码为 0
的堡垒机伪成功识别为失败。

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

## 管理 ModelScope

先查看单机变更预览：

```bash
./scripts/playbook playbooks/install-modelscope.yml \
  --check --diff --limit PPU-01
```

在一台机器实际执行并验证：

```bash
./scripts/playbook playbooks/install-modelscope.yml --limit PPU-01
```

确认结果后，再逐台应用到已验证的 `modelscope_hosts` 组：

```bash
./scripts/playbook playbooks/install-modelscope.yml
```

该 Playbook 使用 `serial: 1`，不会同时修改多台机器。其他服务器必须先验证
Python、pip 和脚本路径，之后才能加入 `modelscope_hosts`。

## 启动大模型下载

下载 Playbook 强制要求一台明确的目标机器、模型 ID 和绝对目标路径。默认
至少需要 850 GiB 空闲空间。目标路径的父目录必须提前存在，以避免路径写错
时落到根盘。任务在远程后台运行，SSH/Codex 会话断开后仍会继续。

```bash
./scripts/playbook playbooks/download-model.yml \
  -e target=PPU-01 \
  -e model_id=Qwen/Qwen3.5-397B-A17B \
  -e model_local_dir=/models/Qwen3.5-397B-A17B
```

命令会返回 `ansible_job_id`。使用该 ID 查询进度：

```bash
./scripts/playbook playbooks/check-async-job.yml \
  -e target=PPU-01 \
  -e ansible_job_id=<job-id> \
  -e model_local_dir=/models/Qwen3.5-397B-A17B
```

任务完成后，查询 Playbook 会验证返回码和 `config.json`，并报告模型目录大小。

ModelScope 下载支持续传；同一个目标目录可以在失败修复后重新启动。

## 常用操作

### 准备 rsync 传输环境

`rsync_transfer_hosts` 当前只包含 `PPU-240` 和 `PPU-01`。安装 Playbook
使用 `serial: 1`，并根据操作系统分别使用 `apt` 或 `dnf`：

```bash
# 先在单机预演、安装并验证
./scripts/playbook playbooks/install-rsync.yml --check --diff --limit PPU-240
./scripts/playbook playbooks/install-rsync.yml --limit PPU-240

# 验证首台后，再处理第二台
./scripts/playbook playbooks/install-rsync.yml --check --diff --limit PPU-01
./scripts/playbook playbooks/install-rsync.yml --limit PPU-01
```

该 Playbook 只安装和验证 `rsync`，不会复制 SSH 配置、密钥，也不会启动数据
传输。服务器之间的 SSH 主机名解析和认证需要单独验证。

```bash
# 查看所有机器磁盘（raw 不要求远端预装 Python）
./scripts/ansible managed -m ansible.builtin.raw -a 'df -h'

# 主机安装了 NVIDIA 工具时查看 GPU；未安装时该命令会明确失败
./scripts/ansible PPU-03 -m ansible.builtin.command -a nvidia-smi

# 检查 inventory 和所有 Playbook 语法
./scripts/syntax-check
```

执行修改前请遵循 [AGENTS.md](AGENTS.md) 中的安全边界。特别是批量变更、
删除、重启、覆盖已有配置以及多机大文件下载。
