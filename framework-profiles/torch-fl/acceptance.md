# Torch-FL PPU 初始验收要求

本文件定义 `experimental` 阶段可执行的基础验证，不构成完整模型适配通过标准。任何未列出的
graph、服务协议、正式精度或性能能力都视为未验证。

## 1. 身份与版本

- 记录 Torch-FL commit、工作树状态、实际导入路径和构建接口。
- 记录厂商 torch wheel/版本/来源/SHA-256、官方 CPU torch 精确版本、Python 与 C++ ABI、
  PPU SDK/Driver/Runtime 版本和构建镜像标识。
- 证明厂商 `torch/lib` 输入来自已记录的绝对路径，而不是 CPU torch 构建环境。

## 2. 直接集成 eager 验证

- `import torch_fl` 后能够发现 `flagos` 设备。
- 至少完成设备 Tensor 分配、代表性矩阵算子、激活算子和结果回传 CPU，并与 CPU 参考结果
  比较到任务声明的容差。
- 用 dispatch 日志证明路径符合预期；所有 CPU fallback 必须逐项解释，不能静默接受。
- 使用目标模型的最小输入完成一次确定性的 eager 推理，并保存输入摘要、参数、结果和参考
  对比证据。仅算子 smoke test 不能代替模型最小推理。

## 3. 自包含 wheel 验证（任务选择该交付模式时）

- wheel 名称带可识别的平台/SDK 标识，记录 SHA-256，并检查 `lib_ppu`、构建配置、符号链接、
  SONAME、RPATH/RUNPATH 和所有间接依赖。
- 干净验证环境只安装匹配的官方 CPU torch 与待测 Torch-FL wheel，不安装厂商 torch 包。
- 先导入 Torch-FL，再重复设备、代表性算子、CPU 回传和模型最小 eager 推理。
- 用 `ldd`/`readelf` 证明关键库解析到 wheel 内 `lib_ppu` 或预期 PPU Runtime，不得依赖构建
  主环境中的厂商 site-packages、`PYTHONPATH` 或偶然的全局 loader 路径。

## 4. 当前不能通过的正式子步骤

- 使用 `device`、`operators`、`model-eager` 和可选 `wheel`，形成对应基础证据；不声明 graph/compile 已通过。
- `sanity`、`accuracy` 和 `performance` 尚无统一模型 runner、数据契约和原生回执，因此不能
  标记正式通过；不得套用 vLLM/OpenAI 服务入口或 FlagEval 配置进行推断。
- 前缀缓存是否适用尚未确定。在具体模型 runner 定义并验证前，不运行或通过正式性能测试。
- 尚未定义通用服务启动命令，不能生成猜测性的 `start-model.sh` 或标记整个模型适配完成。

现在即可用 `new-framework <model> ppu torch-fl` 创建实验适配工作区，按上述独立子步骤
执行和验证。满足 `workflow.md` 的 active 条件后才开放完整正式验收。
