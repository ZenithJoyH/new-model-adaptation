# 005：CPU Torch 与 PPU Torch-FL 的完整 runtime 和兼容元数据

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-20
- 最后验证时间：2026-09-20
- 模型：Qwen-Image-2.1，权重 `/mnt/cpfs/models/Qwen-Image-2.1`
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器名称与镜像：实验容器 `qwen-image-flagos`，由原 `qwen-image` 容器快照 `qwen-image-flagos:from-qwen-image-20260920` 创建；原容器保持运行且未修改
- Plugin / FlagGems / vLLM revision：Torch-FL `229386dcb4734334bd695c6aabe24a35b8b491d2`，editable `/workspace/PyTorch-Plugin-FL`，含既有未提交修复；FlagGems 与 vLLM 未修改
- 执行模式与负载：Diffusers eager，`torch 2.10.0+cpu` Python wheel + 完整 PPU libtorch runtime；单卡 `flagos:0`，1024×1024，seed 42，40 步

## 问题现象

- 错误签名或症状：只把 vendor Torch 三件套替换成官方 CPU wheel 后，首先在 PyTorch 后端自动加载 `torch_fl._C` 时失败：`ImportError: libtorch_cuda.so: cannot open shared object file`。完整 bundle 修复 native runtime 后，bitsandbytes 仍打印 `libbitsandbytes_cpu.so: cannot open shared object file`。
- 发生顺序：官方 CPU Torch 安装成功 → `TORCH_DEVICE_BACKEND_AUTOLOAD=0` 时 CPU 运算正常 → 默认 `import torch` 自动加载已保留的 `torch_fl` → `_C` 动态依赖缺失；完整 relink 后实际 PPU/CUDA dispatch 已可用，但 CPU wheel 生成的 `torch.version.cuda` 仍为 `None`，bitsandbytes 因此错选 CPU native library。
- 影响范围：当前 PPU 编译的 Torch-FL；并非纯 CPU Torch 自身安装错误。
- 精简证据及原始证据位置：`/mnt/nfs/users/jinghao/qwen-image/01-environment/qwen-image-flagos-after-cpu-torch-20260920.txt`；最终证据位于 `/mnt/nfs/users/jinghao/qwen-image/04-runs/cpu-torch-ppu-bundle-20260920-01/`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| Torch-FL `scripts/vendor/bundle_ppu_libtorch.sh` 与 `_ppu_libtorch_link.py` | 明确定义官方 CPU wheel + PPU vendor C++ runtime 的组合方式 | 当前 editable 安装此前没有 `torch_fl/lib_ppu/` | 高 | 直接使用维护者提供的 bundle/relink 扩展点，不手工补单个 SO |
| 002 的构建期自动加载问题 | 都涉及旧/不匹配 native extension 的自动加载 | 本次是运行期 libtorch ABI/runtime 缺失 | 中 | 构建或纯 CPU 诊断仍可禁用 autoload；最终运行通过完整 PPU bundle 恢复默认导入 |

## 诊断与假设

- 已验证 `_C` 直接加载 `libtorch_bindings.so`，后者依赖 `libtorch_cuda.so`；`libtorch_fl.so` 还直接依赖 `libc10_cuda.so`、PPU `libtorch_cpu.so` 等同一 ABI 集合。
- Torch-FL 源码记录的符号归因显示，插件约 2092 个未定义符号由 PPU `libtorch_cpu.so` 提供，`libtorch_cuda.so` 提供 0 个、`libc10_cuda.so` 提供 10 个。因此单独复制 `libtorch_cuda.so` 不是可用修复。
- 原 `qwen-image` 容器的 vendor Torch 为 `2.10.0`、CUDA ABI `13.0`、Git `e42faac0fd33a8652c8325146b75675454b3daa3`；目标官方 CPU wheel 为 `2.10.0+cpu`。完整来源库集和三个 MKL 依赖均已实读存在。
- 已排除只靠 `LD_LIBRARY_PATH`/ctypes 混载官方 core 与 vendor 单库；Torch-FL 的 vendor relink 设计说明这会形成双份 libc10 或未定义符号风险。
- bitsandbytes 0.48.1 的后端判断同时依赖 `torch.cuda.is_available()` 和 `torch.version.cuda`。在目标容器中前者为 `True`、后者为 `None`，因此 `get_cuda_specs()` 返回空并回退到不存在的 CPU SO。只设 `BNB_CUDA_VERSION=130` 不会越过这个前置判断。
- 运行时 C++ 侧 `torch._C._cuda_getCompiledVersion()` 已实读返回 `13000`；这是 relink 后真正加载的 PPU libtorch 的 ABI 事实，可用于恢复 Python wheel 中过时的 `torch.version.cuda`。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 0 | PyTorch wheel | PPU vendor Torch | 官方 `torch/vision/audio` CPU wheel，保留 `torch_fl` | 环境记录与 CPU matmul | CPU matmul 通过；默认导入缺 `libtorch_cuda.so` | Python wheel 可用，但 PPU 插件需要完整 vendor C++ runtime |
| 1 | runtime 完整性 | 无 `lib_ppu` | 只读检查 `_C`/`libtorch_fl.so` DT_NEEDED 和构建源码 | 容器内 `readelf`/`ldd` | 需要 core、CUDA side 和 MKL 自洽集合 | 拒绝单 SO 复制 |
| 2 | PPU bundle | 无 | 仓库 `bundle_ppu_libtorch.sh`，完整 9 个 libtorch SO + 3 个 MKL SO | `04-runs/cpu-torch-ppu-bundle-20260920-01/bundle-ppu-libtorch.log` | bundle、RPATH、bootstrap 成功 | 官方支持路径可用 |
| 3 | 最小整模链路 | 未运行 | 512×512、1 步 full | `model-smoke-1step/infer-full-1step.log` | 全阶段完成、0 fallback；1 步图为常量黑图 | 只证明链路，不作图像正确性结论 |
| 4 | 完整推理 | vendor Torch 旧基线 | CPU wheel + PPU runtime，1024×1024、40 步 | `model-full-40/infer-full-40.log` | 成功出图，0 fallback | 功能通过 |
| 5 | 数值对照 | 2026-09-18 vendor Torch 图片 | 相同 seed/prompt/尺寸/步数 | `model-full-40/compare-with-vendor-torch.log` | MAE 0、max 0、PSNR inf | 与旧基线逐像素一致 |
| 6 | CUDA 兼容元数据 | `torch.version.cuda is None` | 由已加载 C++ runtime 的 `_cuda_getCompiledVersion()` 恢复 | `ppu-cuda-version-fix/` | 显式/自动加载均得到 `13.0`，bitsandbytes 选择 `CudaBNBNativeLibrary` | 修复属于 PPU runtime 适配，不需 bitsandbytes 特例 |
| 7 | 修复后整模回归 | 修复前成功图片 | 相同 seed/prompt/1024×1024/40 步 | `model-full-40-after-ppu-cuda-metadata/` | 无 bitsandbytes CPU SO 报错，图片 SHA-256 相同 | 元数据修复未改变模型数值输出 |

## 根因

- 已验证根因分为两层：PPU 版 `torch_fl` 是针对 vendor CUDA-ABI libtorch 编译的 native extension。官方 CPU wheel 不包含 `libtorch_cuda.so/libc10_cuda.so`，且其 core libtorch 也不是插件所需的 PPU fork，因而保留插件却只替换 Python wheel 会在动态加载阶段失败。完整 relink 解决了 C++ runtime，但不会重写 CPU wheel 构建时生成的 `torch/version.py`，造成 Python 元数据与实际已加载 runtime 不一致，这正是 bitsandbytes 错选 CPU SO 的直接原因。
- 若未完全证实，当前假设与缺失证据：eager 单卡整模已证实；graph、训练、分布式和其他 PPU SDK/Torch revision 未验证。

## 解决方法或 Workaround

- 修改思路：保留官方 `torch 2.10.0+cpu` Python wheel和 `torch_fl 0.1.0+ppu` editable 安装，从匹配的原容器只读提取自洽 vendor runtime，使用 Torch-FL 自带 PPU bundle/relink 机制；在 PPU 初始化中再从已加载 C++ runtime 动态恢复 `torch.version.cuda`。
- 选定层级/扩展点、职责依据和替代方案：使用 `scripts/vendor/bundle_ppu_libtorch.sh`、`torch_fl/accelerator/ppu/_ppu_libtorch_link.py` 和通用 `_vendor_libtorch.py`；在 `torch_fl/__init__.py` 完成 relink 并 import torch 之后、可选依赖检测之前执行 PPU-only 恢复。不在模型脚本或 bitsandbytes 中散布机器/版本特例，也不拷贝 vendor `version.py`。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：仅 `ACCELERATOR=ppu` 且存在 `lib_ppu`/显式 vendor lib 路径时 relink；其他平台沿用各自逻辑。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：是。元数据不一致由 Torch-FL 支持的 CPU-wheel-plus-vendor-runtime relink 形态造成，且会影响所有依赖 PyTorch CUDA ABI 元数据的可选包，不是 Qwen 或 bitsandbytes 专属语义。
- Plugin 内必要实现或回归测试路径：`torch_fl/__init__.py`、`torch_fl/accelerator/ppu/_ppu_libtorch_link.py`、`tests/unit/test_ppu_cuda_version.py`。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：无一次性源码；来源库中转与 SHA-256 位于 `/mnt/nfs/users/jinghao/qwen-image/05-tmp/ppu-libtorch-2.10.0-e42faac/` 和 `04-runs/cpu-torch-ppu-bundle-20260920-01/source-library-sha256.txt`，为回溯保留。
- 分支与 revision/commit：`229386dcb4734334bd695c6aabe24a35b8b491d2`，既有工作树改动未提交，本轮未 commit/push。
- 正式回归测试路径：`/mnt/nfs/users/jinghao/qwen-image/04-runs/cpu-torch-ppu-bundle-20260920-01/model-full-40/`。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：PPU 元数据和已有 DCU decoupling 共 43 个单测通过；fresh-process 显式导入、PyTorch 自动 backend 加载、bitsandbytes CUDA native 库选择、FlagOS matmul 和完整模型均通过；原 `qwen-image` 仍为 Torch `2.10.0`/CUDA `13.0`/Git `e42faac...`。
- workaround 的适用条件、默认策略/性能影响和退出条件：仅适用于与 bundle 完全匹配的 PPU Torch/SDK；运行保留 `FLAGOS_DISABLE_CUDA_ASSETS=1`，避免 NVIDIA CUDA asset preload。pip 元数据显示 `+cpu`，但实际 C++ runtime 和计算均为 PPU，不应表述为纯 CPU 推理。
- 服务停启操作及核对结果：未停止、重启或删除两个容器；测试后 16 张 PPU 均 1 MiB、0%、无进程。
- vLLM 未修改证明：本轮为 Diffusers 本地 pipeline，未进入或修改 vLLM。

回滚点位于官方 CPU wheel 的 `/usr/local/lib/python3.12/site-packages/torch/lib/_orig_backup/`；应调用 Torch-FL 的 `restore_original_libtorch()` 机制，不手工删除链接。`patchelf 0.17.2.4` 已安装用于受支持的 RPATH 处理。

## FlagGems 证据

- 同步后的 revision 与检索证据：FlagGems 未同步或修改；沿用容器现有版本。
- 已有算子及接入方式，或缺失结论：40 步日志记录 141100 次 dispatch；107371 次 `cuda` boxing、33729 次 `flagos_python`，64 个 distinct ATen op，`cpu_fallback=0`，`libentry failures=0`。
- 如为 FlagGems 缺陷，工作根 `07-bugs/<issue>/`、容器对应路径与复现命令：本问题不是 FlagGems 缺陷，不新建复现目录。
- 如确因工具要求使用 `/bug`，记录指向同一目录的已批准映射或明确例外：不适用。

## 验证结果

- 最小回归：43 个单测通过；fresh explicit import 中 `torch.version.cuda` 在 `import torch_fl` 前为 `None`、之后为 `13.0`；自动 backend 加载路径同样为 `13.0`。`torch.__version__ == 2.10.0+cpu`、`torch.cuda.is_available() is True`，bitsandbytes 0.48.1 的 native 类型为 `CudaBNBNativeLibrary`；`flagos:0` 矩阵乘法结果正确。证据在 `ppu-cuda-version-fix/`。
- `eager`：1024×1024、40 步完整 Pipeline 成功；text encoder 1.499 s、denoise 41.336 s、VAE 5.036 s；reserved 37.62 GiB、allocated 30.22 GiB。
- `graph` capture/replay：未选择、未验证。
- 数值、dtype、shape、layout、边界条件：修复后 1024×1024、40 步输出 SHA-256 仍为 `e3a115f296f280c1efbc529643839abf2e90c1d34f843ae40dca347b9a9b3ff2`，与修复前成功图片逐字节相同；141100 次 dispatch、64 个 distinct ATen op、`cpu_fallback=0`、`libentry failures=0`。
- 最终结论与通过标准：CPU Python wheel + 完整 PPU vendor libtorch + PPU Torch-FL 的 eager 模型链路通过，且未产生相对既有 vendor Torch 基线的数值差异。

## 限制与下一步

- 尚存限制：这不是纯 CPU 执行；底层仍使用 PPU runtime。元数据恢复目前只在当前 PPU runtime/CUDA ABI 13.0 组合实测，graph、正式 accuracy/performance、训练和分布式未验证。
- 后续动作：若要制作可分发环境，应按仓库 wheel 流程把 `lib_ppu` 打入 wheel，并在匹配 SDK 的干净容器复验，不应依赖当前 editable 源码树的手工状态。
- 设计审查结论及 PR 范围的影响：修复复用 PPU bundle/relink 的平台所有权，仅在 `_is_ppu_build()` 命中时生效；vendor Torch 已有非空 `torch.version.cuda` 时 no-op；版本来自 C++ runtime 而非硬编码；失配时明确报错，不作广泛 fallback。当前实现为未提交工作树改动，本轮未 commit/push/PR。

## 经验沉淀

- 是否可跨模型或平台复用：可复用于同一 PPU Torch/SDK ABI 的模型，但不可把当前库集推广到其他 Torch commit、Python ABI 或 PPU SDK。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：vendor-native Torch extension 与官方 CPU wheel 组合时必须 bundle/relink 自洽 core runtime，不能只补 vendor-side SO。
