# 002：FlagGems clone 的 Autograd 注册污染 CPU 权重加载

2026-10-23，状态：clone 注册及完整权重加载修复已验证；整模型数值另行定位。范围为 PPU-01、新容器 `minicpm-jev-vllm`、FlagGems `722854072a3329c6c33ea2850afe368c9b4f63bc`、Plugin `06014201f8ea8cd7092a56a945d8fc7998c5a46c`、vLLM `0.24.0+empty`，BF16/eager pooling/classify。原 `minicpm-ocr` 容器不受修改影响。

## 现象与已验证根因

解决 IPC 地址长度后，EngineCore1184 进入 checkpoint 加载。原生 vLLM `models/adapters.py` 为缓存权重调用 `loaded_weight.clone()`，CPU tensor 进入 FlagGems GPU clone，报 `ValueError: Expected a cuda device, but got: cpu`。日志在工作根 `04-runs/eager-abstract-ipc-20261023/server.log`。

最新 FlagGems `src/flag_gems/__init__.py` 的 clone 配置把 `(AUTOGRAD_DISPATCH_KEY, fallthrough_kernel)` 作为额外 dispatch key 序列，registrar 却要求单个 `(key, implementation)` pair 再包一层序列。结果全局 Autograd alias 错误绑定 clone 本体；后续把函数当 dispatch key 的登记错误又被 registrar 的既有错误处理收集。GPU clone 被用于 CPU checkpoint 复制，不是模型权重损坏。

独立复现 `07-bugs/clone-registration-20261023/repro.py` 只对 clone 启用 gems，不依赖 vLLM/完整模型，修复前复现同一 CPU device 异常。没有使用 CPU 回退重试掩盖 GPU 内核错误。

## 修复与边界

仅修改实际 editable FlagGems 的 clone 注册条目：使用正确嵌套 pair，将 fallthrough 限定为 `Autograd + backend_info.dispatch_key`。不修改公共 registrar，不把 clone 注册到所有设备的 Autograd alias，不给 CPU 添加伪 GPU 实现。CPU 继续使用原生 PyTorch clone/梯度，PPU CUDA clone 继续进入已有 FlagGems 内核及自定义 Autograd Function。

产品文件：`/workspace/FlagGems/src/flag_gems/__init__.py`。维护测试：`/workspace/FlagGems/tests/test_clone_registration.py`。没有 Plugin 模型名/路径特例，没有修改 vLLM；不会将该修复加入原 OCR 容器。其他硬件未实测，不宣称跨平台验收。

## 验证

- 同一独立复现修复后通过：CPU clone 及梯度、PPU FP32/BF16、连续/转置布局、独立存储，以及两次变输入 graph replay。
- pytest 标准入口：`python -m pytest -q tests/test_clone_registration.py`，3 passed。覆盖 CPU Autograd 隔离、GPU 梯度、布局与图重放。
- 原始 before/after 日志、退出码和 JUnit XML 均在工作根 `07-bugs/clone-registration-20261023/`。
- 整模型相同参数复测进程 PID3675，启动 tick544281586；`04-runs/eager-clone-fix-20261023/` 已验证完整权重加载、GDN warmup 和服务就绪，随后真实请求暴露独立的 worker 异步协议问题，见 003。修复 003 后 eager 及实际 PIECEWISE 均完成 12 样例两轮，无 clone/device 加载回归。概率误差在 004 单独保留，不能以本算子修复通过替代数值验收。

## 设计审查

该改动归属 FlagGems 的算子注册协议，修复所有相同注册入口中的 clone，而非复制 vLLM 模型或绕过 Plugin。正向覆盖 PPU eager/graph，守卫未命中覆盖 CPU 正常数值与梯度；没有异常吞掉、全局禁用或精度容差放宽。当前可作为声明范围内修复候选，但完整模型/graph 回归仍需完成；没有提交、推送或创建 PR。

知识库状态：local-only。移除条件：上游修正 clone 的 tuple 结构与设备专用 Autograd 注册，并以同一复现验证。
