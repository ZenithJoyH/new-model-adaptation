# Torch-FL PPU 简单适配工作流

本 profile 继承仓库通用五阶段、安全、远端目录和证据规则。首版只覆盖 PPU，详细构建与
部署依据见 [Torch-FL PPU 适配与部署流程](../../docs/Torch-FL_PPU适配与部署流程.md)。文档中的
路径和版本都是示例；必须以目标容器内实际 Torch-FL revision、源码和厂商环境为准。

## 适配边界

- 允许修改且仅允许修改已核实 Git 根、revision、工作树归属和 editable/build source 身份的
  Torch-FL 源码。厂商 PyTorch/libtorch、官方 CPU PyTorch、PPU SDK/Driver/Runtime、模型源码
  和权重默认只读。
- 优先使用 Torch-FL 现有 `PrivateUse1`、`flagos`、dispatch、backend 配置和项目构建入口接入；
  不得通过修改厂商库、全局 `LD_LIBRARY_PATH` 或复制未知动态库掩盖版本与符号问题。
- 一次性探测、构建包装和诊断代码放在批准远端工作根的 `01-environment/`、`02-issues/` 或
  `05-tmp/`。只有必要产品代码和可维护测试进入 Torch-FL 源码树。
- 直接集成模式用于最初 bring-up 和定位；自包含 wheel 模式用于验证可部署产物。两套 Python
  环境必须隔离，不得在同一环境交替覆盖安装官方 CPU torch 与厂商 torch。

## 五阶段映射

### 1. 模型结构与推理链路分析

用中文记录模型整体结构、输入输出、推理主链路、dtype、shape/layout、设备放置、关键 ATen
算子和可能的复合算子。把这些算子映射到 Torch-FL 的 `flagos/PrivateUse1` dispatch、CUDA
boxing、已有后端或缺失路径，并明确最小推理入口和参考结果来源。

### 2. 推理环境分析

先做只读核实并记录：Torch-FL Git 根与 commit、当前构建接口、Python ABI、厂商 torch wheel
及 `torch/lib` 绝对路径、官方 CPU torch 版本、C++ ABI、PPU SDK/Driver/Runtime、设备状态、
容器映射、模型入口和依赖。必须从当前 commit 的 `setup.py`、`CMakeLists.txt`、项目文档和脚本
判断使用 `FLAGOS_ACCELERATOR=ppu` 还是旧接口，不得混用。

### 3. 进行适配

1. 在厂商 torch 环境中先建立设备、代表性算子和模型最小 eager 推理基线。
2. 核对失败算子的实际 dispatch 路由。优先补齐 Torch-FL 现有配置、生成 binding 或 backend；
   不得把 CPU fallback 当作已适配，除非其正确性、数据搬运和性能影响被明确接受并记录。
3. 每次只改变一个关键变量，并为新增或修复的路径补充数值、dtype、shape、layout、设备与
   eager 测试。Torch-FL 或厂商算子问题使用远端 `07-bugs/` 中的最小复现保存证据。
4. 直接集成模式通过后，如任务需要可部署 wheel，再建立独立 CPU torch 构建环境，使用当前
   revision 提供的 bundle/build 流程打包厂商 libtorch。不得以手工复制 `.so` 代替项目脚本，
   除非当前 revision 确无入口且 SONAME、符号链接、RPATH 和间接依赖已被单独审查。
5. 在独立的干净验证环境安装官方 CPU torch 和生成的 Torch-FL wheel；禁止安装厂商 torch
   Python 包，并排除 `PYTHONPATH`、系统 site-packages 和全局库路径造成的假阳性。

### 4. 适配验收

按本 profile 的 [验收要求](acceptance.md)执行。当前只定义 eager Python API、直接集成和
自包含 wheel 的基础验收，不得据此声称 graph、正式模型精度或性能已经通过。

### 5. 适配复盘

总结模型/算子缺口、dispatch 或动态库问题、最终修改位置、两种部署模式的适用边界、版本
兼容矩阵、残余 CPU fallback、未验证能力和可复用经验。只有跨模型且经过复验的结论才能提升
到仓库通用 troubleshooting 文档。

## experimental 与 active

当前为 experimental：可以创建独立工作区，完成环境分析、源码适配和明确的基础验证，
无需先通过正式模型验收。实施顺序为直接集成 → dispatch/算子修复 → eager 模型验证；
需要自包含交付时再构建 wheel 并在干净环境验证。验收子步骤为
`device → operators → model-eager → [wheel] → summary`，`wheel` 按交付范围选择。
实验结果可以标为 `functional` 并进行复盘；完整 acceptance 与 `optimized` 保持未完成。
不强制引入 vLLM、graph 服务、FlagEval 或并发请求。

升级为 active 需要补齐以下能力；这是扩展正式验收的条件，不阻止已有实验步骤：

新增正式 runner 时需同时实现对应的证据 validator 和 adapter 注册，再更新 profile；
当前仅已实现的 vLLM 服务适配器不得冒充 Torch-FL 的 Python API 验收入口。

- 为目标模型类型定义可重复的最小推理和正式精度 runner、输入集与阈值回执。
- 定义正式性能 runner、指标、warmup/并发规则，并明确该执行栈是否存在前缀缓存；若存在，
  给出只用于性能测试的可验证关闭方式。
- 明确 graph/compile 是否属于必需模式；如属于，补充 capture/compile、replay 和回退验收。
- 定义适配完成时的最终运行入口；若模型以服务方式运行，补充协议、健康检查和最小
  `start-model.sh` 契约。
- 在真实 PPU 环境至少完成一次端到端试运行，并将验证后的 revision 与限制写回本 profile。
