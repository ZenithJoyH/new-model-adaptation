# 模型适配工作区

本目录属于**本地工作目录**，只保存精简、可追溯的模型与平台记录；实际源码 checkout、
一次性诊断、日志、缓存、运行结果和 `08-bugs/` 复现保存在用户指定的**远端工作目录**。
本地记录通过准确 Host、远端绝对路径、容器对应路径和 revision 引用远端事实，不复制完整
远端运行目录。

本地每个模型使用一个独立目录，目录名采用模型的稳定短名称。平台目录名与 Ansible
inventory 组保持一致。

```text
models/<model-name>/
├── README.md                 # 总体目标、状态矩阵、关键结论
├── model.yml                 # 模型来源、规模和共享参数
├── architecture-and-inference.md # 中文模型结构与推理链路分析（步骤 1 创建）
├── _shared/README.md         # 跨平台下载、Tokenizer、补丁和共性问题
├── nvidia/
├── ppu/
├── metax/
├── ascend/
├── mthreads/
└── hygon/
```

每个平台根目录初始只包含：

- `README.md`：平台索引和约定。
- `platform.yml`：平台信息、五阶段状态、验收子步骤状态和证据路径。

为用户指定的平台执行阶段准备后，按需新增：

- `environment/`：环境分析及采集文件、平台适配计划、结构化运行配置、服务状态和
  `plugin-change-review.md` 设计审查；`README.md` 导航当前材料与历史分析。
- `adaptation/`：仅保存适配问题索引 `README.md` 和按问题编号的 Markdown 记录；每条
  记录聚焦问题现象、诊断、尝试、根因、解决方法、验证结论与限制。
- `acceptance/`：验收计划、精度与性能证据、最终总结和适配复盘；`README.md` 区分正式轮次、
  历史失败与诊断子集，文件存在不代表已执行或通过。

`adaptation/` 不存放脚本、配置、源码、补丁、测试文件、原始日志、JSON/YAML 或临时
输出。Plugin 仓库只保存必要的产品实现和可长期维护的回归测试；一次性过程脚本与代码
放在适配容器中、各源码仓库之外的 `06-tmp/` 或 `03-issues/`，且不得提交。FlagGems 复现保留在
已批准工作根目录的 `08-bugs/`，并通过已核实的容器对应路径原地执行；如果已在工作目录中，
不得再复制到 `/bug/`。只有必要工具明确要求时，才使用指向同一目录的已批准映射或明确
例外。问题记录通过准确路径、revision/commit、复现命令和结果引用这些材料。新问题使用
`templates/adaptation/issue-record.md`，按出现顺序命名为 `NNN-short-title.md`。

使用阶段入口初始化指定步骤并生成 Codex 调用文本：

```bash
./scripts/adapt-model <model-name> --steps architecture
./scripts/adapt-model <model-name> --platform ppu --hosts PPU-01 \
  --steps architecture,environment,adaptation
./scripts/adapt-model <model-name> --platform ppu --hosts PPU-01 --steps acceptance \
  --acceptance-substeps execution-mode,sanity
```

使用 `--check-only` 时不会创建文件，只检查所选步骤的目录、前置状态和配置。

不要把权重、完整日志、性能原始数据或密钥提交到 Git。权重位置只记录为
远端绝对路径。

## 当前已启动目录

只整理已有工作，不为未启动平台新增计划、审查或验收材料。这里提供导航，不重复维护动态分数。

| 模型 / 平台 | 平台概览 | 环境与设计 | 问题台账 | 验收轮次 |
|---|---|---|---|---|
| GLM-5.3-Flash-BF16 / PPU | [概览](GLM-5.3-Flash-BF16/ppu/README.md) | [环境](GLM-5.3-Flash-BF16/ppu/environment/README.md) | [问题](GLM-5.3-Flash-BF16/ppu/adaptation/README.md) | [验收](GLM-5.3-Flash-BF16/ppu/acceptance/README.md) |
| Hy4-preview / PPU | [概览](Hy4-preview/ppu/README.md) | [环境](Hy4-preview/ppu/environment/README.md) | [问题](Hy4-preview/ppu/adaptation/README.md) | [验收](Hy4-preview/ppu/acceptance/README.md) |
| Qwen3.8-Flash-Next / PPU | [概览](Qwen3.8-Flash-Next/ppu/README.md) | [环境](Qwen3.8-Flash-Next/ppu/environment/README.md) | [问题](Qwen3.8-Flash-Next/ppu/adaptation/README.md) | [验收](Qwen3.8-Flash-Next/ppu/acceptance/README.md) |
| XingChen4-29B-A4B / NVIDIA | [概览](XingChen4-29B-A4B/nvidia/README.md) | [环境](XingChen4-29B-A4B/nvidia/environment/README.md) | [问题](XingChen4-29B-A4B/nvidia/adaptation/README.md) | [验收](XingChen4-29B-A4B/nvidia/acceptance/README.md) |
| XingChen4-29B-A4B / PPU | [概览](XingChen4-29B-A4B/ppu/README.md) | [环境](XingChen4-29B-A4B/ppu/environment/README.md) | [问题](XingChen4-29B-A4B/ppu/adaptation/README.md) | [验收](XingChen4-29B-A4B/ppu/acceptance/README.md) |

## 状态约定

`platform.yml` 顶层 `status` 表示平台总体成熟度：

- `not_started`：尚未开始。
- `environment_ready`：依赖和硬件环境可用。
- `model_loading`：模型能加载，推理尚未验证。
- `functional`：最小推理正确。
- `optimized`：完成目标性能优化和回归验证。
- `blocked`：存在明确阻塞，并在平台 README 中记录原因。

`workflow.<phase>.status` 和验收子步骤状态使用：

- `not_started`：尚未开始。
- `in_progress`：正在执行。
- `blocked`：存在明确且已记录的阻塞。
- `failed`：已经执行验证且失败，保留失败证据。
- `passed`：阶段已经通过并具有对应证据。
- `complete`：复盘或需要收尾的阶段已经完整关闭。

通过状态必须同时具有与当前输入一致的证据绑定；历史无绑定的状态不能自动作为下一
阶段的前置通过依据。字段和校验入口见 [工作流指南](../docs/workflow-guide.md)。

## 创建新模型

```bash
./scripts/new-model <model-name>
```

脚本从 `models/_template` 复制平台根目录骨架，若目标已存在会拒绝覆盖。创建后
先填写 `model.yml`，再使用 `scripts/adapt-model` 只初始化实际请求的阶段和平台。
