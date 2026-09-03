# 模型适配工作区

每个模型使用一个独立目录，目录名采用模型的稳定短名称。平台目录名与
Ansible inventory 组保持一致。

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

- `environment/`：环境分析及采集文件。
- `adaptation/`：适配计划、结构化配置、命令、补丁、测试、进度和服务状态。
- `acceptance/`：验收计划、精度与性能证据、最终总结和适配复盘。

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
- `passed`：阶段已经通过并具有对应证据。
- `complete`：复盘或需要收尾的阶段已经完整关闭。

## 创建新模型

```bash
./scripts/new-model <model-name>
```

脚本从 `models/_template` 复制平台根目录骨架，若目标已存在会拒绝覆盖。创建后
先填写 `model.yml`，再使用 `scripts/adapt-model` 只初始化实际请求的阶段和平台。
