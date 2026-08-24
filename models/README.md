# 模型适配工作区

每个模型使用一个独立目录，目录名采用模型的稳定短名称。平台目录名与
Ansible inventory 组保持一致。

```text
models/<model-name>/
├── README.md                 # 总体目标、状态矩阵、关键结论
├── model.yml                 # 模型来源、规模和共享参数
├── _shared/README.md         # 跨平台下载、Tokenizer、补丁和共性问题
├── nvidia/
├── ppu/
├── metax/
├── ascend/
├── mthreads/
└── hygon/
```

每个平台目录初始包含：

- `README.md`：适配步骤、操作记录、问题和结论。
- `platform.yml`：目标 inventory 组、查询命令、推理引擎、版本和状态。
- `runbook.md`：按顺序记录前置检查、启动、验证、优化和回滚操作。

适配过程中按需新增：

- `prepare.sh`：依赖安装、镜像准备或代码构建。
- `serve.sh`：推理服务启动命令。
- `stop.sh`：可重复、安全的停止命令。
- `smoke-test.sh`：最小功能验证。
- `benchmark.sh`：吞吐、时延和显存测试。
- `configs/`：引擎配置、服务配置和模型配置覆盖。
- `patches/`：上游或插件补丁。
- `results/summary.md`：可提交的小型结果摘要。

不要把权重、完整日志、性能原始数据或密钥提交到 Git。权重位置只记录为
远端绝对路径。

## 状态约定

- `not_started`：尚未开始。
- `environment_ready`：依赖和硬件环境可用。
- `model_loading`：模型能加载，推理尚未验证。
- `functional`：最小推理正确。
- `optimized`：完成目标性能优化和回归验证。
- `blocked`：存在明确阻塞，并在平台 README 中记录原因。

## 创建新模型

```bash
./scripts/new-model <model-name>
```

脚本从 `models/_template` 复制完整平台骨架，若目标已存在会拒绝覆盖。创建后
先填写 `model.yml`，再确定每个平台的目标主机和推理引擎。
