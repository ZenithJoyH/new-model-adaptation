# Torch-FL PPU 适配与部署流程

## 1. 文档目的

本文说明如何在已有平头哥 PPU 厂商 PyTorch 和 PPU SDK 的镜像中，构建一个面向 PPU 的 Torch-FL wheel，并在仅安装官方 CPU PyTorch 的独立虚拟环境中部署和验证。

本文重点描述两种使用模式：

1. **直接集成模式**：PPU 厂商 PyTorch 与 Torch-FL 在同一个 Python 环境中使用。
2. **自包含 wheel 模式**：构建阶段从 PPU 厂商 PyTorch 取得底层 `libtorch` 动态库，将其打包进 Torch-FL；部署阶段使用官方 CPU PyTorch、带 PPU 动态库的 Torch-FL wheel，以及宿主机上的 PPU Driver/Runtime。

自包含 wheel 模式适合需要统一部署入口、不希望在目标虚拟环境中额外安装厂商 PyTorch wheel 的场景。它并不会消除对 PPU SDK、Driver、Runtime 或厂商 `libtorch` 的依赖，而是把厂商 `libtorch` 从“单独安装的 Python 包”变成 Torch-FL wheel 的组成部分。

> 注意：Torch-FL 的 PPU 构建接口仍在演进。部分版本使用 `ACCELERATOR=cuda` 配合 `PPU_SDK` 自动检测，较新的构建代码使用 `FLAGOS_ACCELERATOR=ppu`。开始适配前必须以实际检出的 Torch-FL commit、`setup.py`、`CMakeLists.txt` 和 `docs/vendors/ppu/installation.md` 为准，不要混用不同版本的参数。

## 2. 工作原理

PPU 对 PyTorch 暴露 CUDA 兼容接口，并将厂商算子注册到 PyTorch 的 `CUDA` Dispatch Key。Torch-FL 将自己的统一设备注册为 `flagos`，其底层使用 PyTorch 的 `PrivateUse1` 扩展机制。

典型算子调用链如下：

```text
PyTorch ATen 算子，例如 aten::mm
        ↓
flagos / PrivateUse1 Dispatch
        ↓
Torch-FL 生成的算子包装函数
        ↓
按照 backends_*.conf 选择 CUDA boxing
        ↓
将 flagos Tensor 临时转换为同一存储上的 CUDA 视图
        ↓
重新进入 CUDA Dispatch Key
        ↓
PPU 版 libtorch_cuda.so 中注册的算子
        ↓
PPU CUDA 兼容 Runtime / 算子库
        ↓
PPU 硬件
```

这个过程的关键不是复制 Tensor 数据，而是在满足实现条件时对同一块设备存储进行元数据转换。因而，PPU 版 `libtorch_cuda.so`、`libc10_cuda.so` 及其依赖必须与 PyTorch、PPU SDK 和驱动版本匹配。

## 3. 两种使用模式

### 3.1 直接集成模式

环境组成：

```text
PPU 厂商镜像
├── PPU 厂商 torch
│   ├── torch Python 包
│   └── torch/lib/*.so
├── PPU SDK / Driver / Runtime
└── torch_fl
```

优点：

- 依赖关系直观；
- 厂商 torch 自带所需的 `libtorch_cuda.so` 和 CUDA 兼容运行时；
- 适合最初 bring-up 和问题定位。

限制：

- 每个运行环境都必须安装厂商 torch；
- 厂商 torch 的分发、Python 版本和依赖可能限制部署方式；
- 不利于验证 Torch-FL wheel 是否真正自包含厂商 `libtorch`。

### 3.2 自包含 wheel 模式

构建环境：

```text
PPU 厂商镜像
├── 主环境或已解压目录中的 PPU 厂商 torch/lib
├── PPU SDK / Driver / Runtime
└── 独立构建虚拟环境
    ├── 官方 CPU torch
    ├── CMake / Ninja / patchelf / wheel
    └── Torch-FL 源码
```

产物：

```text
torch_fl-<version>+ppu-<python>-<platform>.whl
└── torch_fl/lib_ppu/
    ├── libc10.so
    ├── libc10_cuda.so
    ├── libtorch.so
    ├── libtorch_cpu.so
    ├── libtorch_cuda.so
    ├── libtorch_cuda_linalg.so
    ├── libtorch_python.so
    └── 其他必要依赖
```

部署环境：

```text
目标环境
├── 官方 CPU torch（版本和 ABI 与厂商 torch 匹配）
├── 自包含 PPU Torch-FL wheel
└── 宿主机提供的 PPU Driver / Runtime
```

构建厂商 wheel 的环境和最终部署环境应相互独立。不要在同一个虚拟环境中交替安装 CPU torch 和厂商 torch，因为二者的 Python 包名均为 `torch`，后安装者会覆盖前者。

## 4. 前置条件

开始前准备并记录以下信息：

- Torch-FL Git 仓库 URL、分支和精确 commit；
- 厂商 torch wheel 名称、版本、Python ABI 和来源；
- 官方 CPU torch 的精确版本；
- PPU SDK 和 Driver 版本；
- Python 版本与平台架构；
- 厂商 torch 的 `torch/lib` 绝对路径；
- 目标机器是否具备可用的 PPU 设备节点和 Runtime；
- 最终 wheel 的版本标识，例如 `ppu_sdk_x.y`。

版本应至少满足：

```text
厂商 torch 与 CPU torch 的 PyTorch minor 版本一致
Python ABI 一致，例如均为 cp310 或均为 cp312
C++ ABI 一致
厂商 libtorch 与 PPU SDK/Driver 兼容
Torch-FL 生成的 ATen binding 与 PyTorch minor 版本一致
```

当前 Torch-FL 主线通常固定在某个 PyTorch minor 版本。构建前应检查：

```bash
rg -n "TORCH_PIN|requires-python|torch>=" setup.py pyproject.toml
```

## 5. 推荐目录与环境规划

以下路径仅为示例，应替换为镜像中的真实绝对路径：

```text
/opt/vendor/python/                 # 厂商 Python 主环境
/opt/vendor/python/.../torch/lib/   # 厂商 libtorch 来源
/usr/local/PPU_SDK/                 # PPU SDK
/opt/venvs/torch-fl-build/          # 构建虚拟环境
/opt/venvs/torch-fl-verify/         # 干净验证虚拟环境
/workspace/Torch-FL/                # Torch-FL 源码
/workspace/wheels/                  # 最终 wheel 输出目录
```

不要把示例路径直接当作真实路径。应先在目标镜像中进行只读探测。

## 6. 阶段一：确认厂商环境

### 6.1 获取厂商 torch 信息

在尚未激活 CPU torch 构建虚拟环境时执行：

```bash
python - <<'PY'
from pathlib import Path
import platform
import sys
import torch

torch_root = Path(torch.__file__).resolve().parent
print("python:", sys.version)
print("platform:", platform.platform())
print("torch version:", torch.__version__)
print("torch path:", torch_root)
print("torch lib:", torch_root / "lib")
print("torch.version.cuda:", torch.version.cuda)
print("torch.cuda.is_available:", torch.cuda.is_available())
print("torch.cuda.device_count:", torch.cuda.device_count())
PY
```

记录输出中的厂商 `torch/lib` 路径。后续不要依赖 `which python` 或模糊的 `site-packages` 推断。

### 6.2 检查关键动态库

```bash
VENDOR_TORCH_LIB=/absolute/path/to/vendor/torch/lib

find "$VENDOR_TORCH_LIB" -maxdepth 1 -type f -o -type l
```

重点确认以下库是否存在：

```text
libc10.so
libc10_cuda.so
libtorch.so
libtorch_cpu.so
libtorch_cuda.so
libtorch_cuda_linalg.so
libtorch_python.so
```

实际依赖集合可能更多，应由项目提供的 bundle 脚本和 `ldd` 结果决定，不要只手工复制上述文件。

### 6.3 检查 PPU SDK 和设备

```bash
export PPU_SDK=/usr/local/PPU_SDK
export CUDA_HOME="$PPU_SDK/CUDA_SDK"

test -f "$CUDA_HOME/include/cuda_runtime.h"
test -x "$CUDA_HOME/bin/nvcc"
ppu-smi
```

若镜像需要执行厂商提供的环境初始化脚本，应先检查脚本内容，再在当前 shell 中加载。

## 7. 阶段二：创建 CPU torch 构建环境

创建独立虚拟环境：

```bash
python3 -m venv /opt/venvs/torch-fl-build
source /opt/venvs/torch-fl-build/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install cmake ninja patchelf
```

安装与厂商 torch minor 版本及 Python ABI 匹配的官方 CPU torch。以下版本仅为示例：

```bash
python -m pip install 'torch==2.10.0+cpu' \
  --index-url https://download.pytorch.org/whl/cpu
```

验证当前环境确实是 CPU torch：

```bash
python - <<'PY'
import torch
print("torch path:", torch.__file__)
print("torch version:", torch.__version__)
print("torch.version.cuda:", torch.version.cuda)
print("torch.cuda.is_available:", torch.cuda.is_available())
PY
```

预期 CPU wheel 在尚未加载 Torch-FL 的情况下不会报告 PPU CUDA 可用。

## 8. 阶段三：准备 Torch-FL 源码

进入已确认的 Torch-FL 源码目录并记录状态：

```bash
cd /workspace/Torch-FL
git rev-parse --show-toplevel
git rev-parse HEAD
git status --short
```

检查当前 commit 使用哪套构建变量：

```bash
rg -n "FLAGOS_ACCELERATOR|ACCELERATOR|PPU_SDK|lib_ppu|FLAGOS_VENDOR_TORCH_LIB" \
  setup.py CMakeLists.txt torch_fl scripts docs
```

应根据检查结果选择一种接口：

```text
新接口：FLAGOS_ACCELERATOR=ppu
旧接口：ACCELERATOR=cuda，并通过 PPU_SDK/PPU_HOME 自动识别
```

不能同时假定两套接口都有效。

## 9. 阶段四：构建并打包 PPU 动态库

### 9.1 设置构建变量

示例：

```bash
export PPU_SDK=/usr/local/PPU_SDK
export CUDA_HOME="$PPU_SDK/CUDA_SDK"
export FLAGOS_VENDOR_TORCH_LIB=/absolute/path/to/vendor/torch/lib
export FLAGOS_WHEEL_LOCAL=ppu_sdk_version
```

其中 `FLAGOS_VENDOR_TORCH_LIB` 必须是阶段一记录的厂商 torch 库目录，不能指向当前虚拟环境中的 CPU torch。

### 9.2 使用项目提供的 bundle 脚本

优先使用仓库中对应 commit 提供的 PPU bundle 脚本，例如：

```text
scripts/vendor/bundle_ppu_libtorch.sh
```

先查看脚本帮助和内容：

```bash
bash scripts/vendor/bundle_ppu_libtorch.sh --help
sed -n '1,240p' scripts/vendor/bundle_ppu_libtorch.sh
```

确认脚本的输入路径、输出目录、RPATH 修改和依赖检查后再执行。不要用手工 `cp` 替代脚本，除非当前 commit 明确没有该脚本，并且复制集合、符号链接、SONAME、RPATH 和验证步骤都已经单独审查。

预期 bundle 目录为：

```text
torch_fl/lib_ppu/
```

### 9.3 构建 wheel

新接口的示例命令：

```bash
FLAGOS_ACCELERATOR=ppu \
FLAGOS_VENDOR_TORCH_LIB="$FLAGOS_VENDOR_TORCH_LIB" \
FLAGOS_WHEEL_LOCAL="$FLAGOS_WHEEL_LOCAL" \
python setup.py bdist_wheel
```

若项目要求使用 pip/PEP 517，则按当前文档改用：

```bash
FLAGOS_ACCELERATOR=ppu \
FLAGOS_VENDOR_TORCH_LIB="$FLAGOS_VENDOR_TORCH_LIB" \
FLAGOS_WHEEL_LOCAL="$FLAGOS_WHEEL_LOCAL" \
python -m pip wheel . --no-build-isolation --no-deps -w /workspace/wheels
```

`--no-build-isolation` 的目的是让构建系统看到当前虚拟环境中已经确认的 CPU torch 头文件和 CMake 配置。

某些 commit 的流程是“先构建原生扩展，再 bundle 厂商 libtorch，最后重新打包 wheel”。若对应 PPU 文档或脚本要求该顺序，应严格遵循，不要只执行一次 `bdist_wheel` 就假定 `lib_ppu` 已经进入产物。

## 10. 阶段五：检查 wheel 内容

列出生成的 wheel：

```bash
find dist /workspace/wheels -maxdepth 1 -name 'torch_fl*.whl' -print 2>/dev/null
```

检查 wheel 是否包含 PPU 动态库：

```bash
python -m zipfile -l /path/to/torch_fl-0.1.0+ppu-*.whl \
  | rg 'torch_fl/lib_ppu/.*\.so'
```

至少检查：

- wheel 文件名是否带有可识别的 PPU/SDK 本地版本标记；
- `_build_config.py` 是否记录了预期 accelerator 和 kernel 集合；
- `torch_fl/lib_ppu/` 是否包含完整依赖集合；
- wheel 中是否意外混入 NVIDIA `nvidia-*-cu12` 组件；
- 是否遗漏符号链接目标；
- PPU 动态库 RPATH 是否指向预期的 `$ORIGIN` 相对目录和允许的系统 Runtime 路径。

可将 wheel 解压到临时目录后检查：

```bash
TMP_WHEEL_DIR="$(mktemp -d)"
python -m zipfile -e /path/to/torch_fl-0.1.0+ppu-*.whl "$TMP_WHEEL_DIR"

find "$TMP_WHEEL_DIR/torch_fl/lib_ppu" -maxdepth 1 -type f -o -type l
readelf -d "$TMP_WHEEL_DIR/torch_fl/lib_ppu/libtorch_cuda.so" | rg 'NEEDED|RPATH|RUNPATH'
```

不要删除或覆盖未知目录；这里只使用 `mktemp -d` 创建的临时目录。

## 11. 阶段六：干净部署验证

这是证明自包含 wheel 有效的必要步骤。验证环境中不能安装 PPU 厂商 torch wheel。

### 11.1 创建验证环境

```bash
python3 -m venv /opt/venvs/torch-fl-verify
source /opt/venvs/torch-fl-verify/bin/activate

python -m pip install --upgrade pip
python -m pip install 'torch==2.10.0+cpu' \
  --index-url https://download.pytorch.org/whl/cpu
python -m pip install /path/to/torch_fl-0.1.0+ppu-*.whl
```

验证安装列表中没有厂商 torch：

```bash
python -m pip list | rg 'torch|torch-fl|torch_fl'
python -m pip show torch torch-fl
```

### 11.2 检查打包后的库

```bash
python - <<'PY'
from pathlib import Path
import importlib.util

spec = importlib.util.find_spec("torch_fl")
if spec is None or spec.origin is None:
    raise SystemExit("torch_fl is not installed")

root = Path(spec.origin).resolve().parent
print("torch_fl root:", root)
print("PPU libraries:")
for path in sorted((root / "lib_ppu").glob("*.so*")):
    print(" ", path.name)
PY
```

### 11.3 最小功能验证

厂商 libtorch 需要在 PyTorch 初始化之前装载或重链接，因此自包含模式通常要求先导入 Torch-FL：

```bash
python - <<'PY'
import torch_fl
import torch

from torch_fl import _build_config

print("torch path:", torch.__file__)
print("torch version:", torch.__version__)
print("build accelerator:", _build_config.ACCELERATOR)
print("compiled kernels:", getattr(_build_config, "KERNELS", None))
print("torch.version.cuda:", torch.version.cuda)
print("torch.cuda.is_available:", torch.cuda.is_available())
print("flagos available:", torch.flagos.is_available())
print("flagos device count:", torch.flagos.device_count())

x = torch.randn(4, 4, device="flagos:0")
y = torch.relu(x @ x)
print("result:", y.cpu())
PY
```

验证不能只检查 `import torch_fl` 成功，还必须至少执行一次设备分配、一个代表性算子和回传 CPU。

### 11.4 确认动态库来源

获取 Torch-FL 原生扩展和关键库的位置，再使用 `ldd` 检查实际解析结果：

```bash
python - <<'PY'
from pathlib import Path
import torch_fl

root = Path(torch_fl.__file__).resolve().parent
for pattern in ("_C*.so", "lib/libtorch_fl.so", "lib_ppu/libtorch_cuda.so"):
    for path in root.glob(pattern):
        print(path)
PY
```

对输出的绝对路径逐一执行：

```bash
ldd /absolute/path/to/library.so
```

确认关键依赖解析到了 `torch_fl/lib_ppu/` 或预期的 PPU SDK/Driver 路径，而不是主环境中的厂商 `site-packages`。如果验证环境仍通过 `PYTHONPATH`、`LD_LIBRARY_PATH` 或系统 site-packages 偶然访问主环境，则不能证明 wheel 自包含。

## 12. 算子路由验证

启用 Torch-FL 的 dispatch 日志，确认代表性算子走到了预期后端：

```bash
FLAGOS_LOG=dispatch python - <<'PY'
import torch_fl
import torch

x = torch.randn(128, 128, device="flagos")
y = torch.relu(x @ x)
print(y.sum().cpu().item())
PY
```

根据当前配置，日志应显示算子路由到 CUDA boxing、FlagGems Python 或其他明确后端。若算子落到 CPU fallback，应记录原因并评估设备与主机之间的数据搬运和性能影响。

可通过以下方式检查实际路由配置：

```bash
python - <<'PY'
import os
import torch_fl
print("FLAGOS_BACKEND_CONFIG:", os.environ.get("FLAGOS_BACKEND_CONFIG"))
PY
```

## 13. 常见问题

### 13.1 导入顺序错误

现象：

```text
Cannot initialize CUDA without ATen_cuda library
undefined symbol
PrivateUse1 backend already registered
```

处理：

```python
import torch_fl
import torch
```

并检查是否有其他厂商插件通过 PyTorch backend autoload 提前占用了 `PrivateUse1`。

### 13.2 `undefined symbol`

常见原因：

- CPU torch 和厂商 torch minor 版本不一致；
- 厂商 `libtorch` 文件集合不完整；
- PPU SDK/Driver 版本不匹配；
- Python ABI 不一致；
- RPATH 指向了错误目录；
- 进程先加载了 CPU torch 的核心 `.so`，之后才尝试替换。

不要通过随意增加全局 `LD_LIBRARY_PATH` 掩盖问题。应使用 `ldd`、`readelf -d` 和精确的库路径确认最早被加载的错误依赖。

### 13.3 构建时误用 CPU torch 的 `torch/lib` 作为厂商来源

症状是 wheel 中虽然存在 `lib_ppu/`，但里面实际是 CPU torch 的库，没有 PPU `libtorch_cuda.so`。

应在进入构建虚拟环境前记录厂商目录，并显式设置：

```bash
export FLAGOS_VENDOR_TORCH_LIB=/absolute/vendor/path/torch/lib
```

### 13.4 同一环境中安装了两套 torch

CPU torch 和厂商 torch 使用相同的包名。不要依靠安装顺序切换二者；使用独立虚拟环境，并把厂商库作为只读构建输入。

### 13.5 wheel 在厂商镜像里可用，换环境失败

这通常说明 wheel 仍然隐式依赖了主环境。重点检查：

- `PYTHONPATH`；
- `LD_LIBRARY_PATH`；
- 是否启用了系统 site-packages；
- RPATH/RUNPATH；
- 厂商库是否位于全局 loader 默认路径；
- wheel 是否遗漏了间接依赖。

必须以干净验证虚拟环境的结果作为自包含结论依据。

## 14. 验收清单

### 构建记录

- [ ] 已记录 Torch-FL 精确 commit。
- [ ] 已记录厂商 torch wheel、PyTorch 版本和 Python ABI。
- [ ] 已记录 PPU SDK 和 Driver 版本。
- [ ] 已确认当前 commit 使用 `FLAGOS_ACCELERATOR=ppu` 还是旧接口。
- [ ] 已记录厂商 `torch/lib` 的绝对来源路径。
- [ ] bundle 过程由项目脚本或经过审查的等价流程完成。
- [ ] wheel 带有明确的 PPU/SDK 版本标识。

### wheel 检查

- [ ] wheel 包含 `torch_fl/lib_ppu/*.so*`。
- [ ] `_build_config.py` 记录了正确的平台和 kernel 集合。
- [ ] RPATH/RUNPATH 已检查。
- [ ] 间接依赖不存在 `not found`。
- [ ] 未意外引入普通 NVIDIA CUDA 12 运行库。

### 部署验证

- [ ] 干净环境只安装官方 CPU torch 和自包含 Torch-FL wheel。
- [ ] 验证环境未通过 `PYTHONPATH` 或系统 site-packages 访问厂商 torch。
- [ ] `import torch_fl` 后设备可见。
- [ ] `flagos` Tensor 能够创建。
- [ ] 代表性算子能在 PPU 上执行。
- [ ] 输出能够正确传回 CPU。
- [ ] Dispatch 日志符合预期，没有未解释的 CPU fallback。
- [ ] `ldd` 显示关键依赖来自 wheel 的 `lib_ppu` 或预期 PPU Runtime。

## 15. 推荐最终产物

完成适配后，至少保留以下可追溯信息：

```text
Torch-FL commit
厂商 torch wheel 文件名及 SHA-256
CPU torch 版本及 wheel 来源
PPU SDK/Driver 版本
构建镜像标识
构建命令
bundle 脚本及参数
生成 wheel 文件名及 SHA-256
干净环境验证命令和结论
已验证的算子、训练/推理能力及未验证范围
```

不要在仓库中提交厂商 wheel、完整 `.so` 集合、驱动包或大体积构建产物；本地文档只记录版本、哈希、来源和验证结论。

## 16. 上游参考

- Torch-FL 仓库：<https://github.com/flagos-ai/Torch-FL>
- PPU 安装说明：<https://github.com/flagos-ai/Torch-FL/blob/main/docs/vendors/ppu/installation.md>
- Torch-FL 构建入口：<https://github.com/flagos-ai/Torch-FL/blob/main/setup.py>
- Torch-FL 兼容性矩阵：<https://github.com/flagos-ai/Torch-FL/blob/main/docs/reference/compatibility.md>

