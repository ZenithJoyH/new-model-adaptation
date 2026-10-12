# 002：Torch-FL PR #342 集成与审查问题修复

## 元数据

- 状态：`verified`
- 首次出现时间：2026-09-18
- 最后验证时间：2026-09-18
- 模型：Qwen-Image-2.1，权重 `/mnt/cpfs/models/Qwen-Image-2.1`
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器名称与镜像：`qwen-image`；完整镜像身份见环境分析
- Plugin / FlagGems / vLLM revision：Torch-FL PR #342 head `229386dcb4734334bd695c6aabe24a35b8b491d2`，本地分支 `codex/pr-342-ppu-fixes` 含未提交修复；FlagGems 与 vLLM 未修改
- 执行模式与负载：Diffusers eager；最小回归与真实权重 1024x1024、40 步用例已验证，完整用例新问题和结果见 003

## 问题现象

- PR 默认多卡参数把 text encoder/transformer/VAE 分散到不同卡，与“默认单卡”说明和 Pipeline 的执行设备假设冲突。
- 去噪阶段计时在异步回调中直接读时间，遗漏第一个 step，且未用设备同步界定阶段边界。
- `sweep.py`/`bench.py` 忽略显式 `--vae-device`，清单可能记录未实际使用的放置。
- 数值比较把 candidate view 异常当作可跳过项，且布尔 mask 的构造几乎全为真，覆盖不到假分支；`_unsafe_view` 的别名和异常契约没有被验证。
- PR 强制使用作者机器上的 Diffusers 源码默认路径，不能直接复用当前容器已安装的 stable 0.40.0 Qwen-Image-2.1 backport。
- PPU 默认把 `_unsafe_view` 路由到 FlagGems；非连续输入上 FlagGems 以 `reshape` 返回副本，而 CUDA boxing 按 ATen 契约抛出异常。
- 原始构建第一次失败于旧 `_C.so` 被 build backend 自动加载，报缺少 `_set_backend_config_path`。

## 已有经验匹配

001 已确认当前容器采用 Diffusers 0.40.0 最小 backport，且不能直接安装依赖 `torchao.FqnToConfig` 的开发版。此次复用这一环境结论，但 Torch-FL manual flow 与 PPU 路由问题均为新的 Plugin 变更。

## 诊断与假设

- 已验证 PR #342 head 为 `229386d...`，基线为 `main@a3b46f8...`。
- 已验证当前 editable package 解析到 `/workspace/PyTorch-Plugin-FL`。
- 已验证 `TORCH_DEVICE_BACKEND_AUTOLOAD=0` 可阻止构建进程载入旧二进制扩展；同一源码随后构建安装成功。
- 已验证 PPU FlagGems `_unsafe_view` 对不兼容 stride 静默产生不别名副本；改走 `cuda` boxing 后恢复 RuntimeError 契约。
- 已排除把整份 PR #340 合入本分支：其 head 基于更新的主线并包含大量无关改动；只移植 PPU 所需、可再生的最小路由例外。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 0 | Torch-FL revision | `a3b46f8...` | PR #342 `229386d...` | `/workspace/PyTorch-Plugin-FL` | PR 分支创建成功 | 可在原 editable tree 内集成，无需复制仓库 |
| 1 | build autoload | 默认 | `TORCH_DEVICE_BACKEND_AUTOLOAD=0` | `04-runs/pr342-fixes-20260918-01/build-install*.log` | 默认失败、禁用后成功 | 旧扩展自动加载是构建期故障原因 |
| 2 | Diffusers 来源 | 强制源码 checkout | 优先已安装兼容包，缺类时才要求显式源码 | `tests/manual/qwen_image_21/common.py` | 0.40.0 backport 导入成功 | 保留 stable 环境且去除作者路径 |
| 3 | `_unsafe_view` 路由 | `flaggems` | PPU `cuda` boxing | `backends_ppu.conf` | 别名成立；不兼容 stride 抛 RuntimeError | 恢复 ATen 契约 |

## 根因

- manual flow 的放置、计时、receipt 和数值比较各自缺少跨脚本共享约束或负向测试。
- 源码 checkout 被误写为唯一可接受依赖形式，并带有机器私有默认路径。
- `_unsafe_view` 是带别名/错误语义的元数据算子，不能只做数值比较；FlagGems 的 `reshape` 实现与 ATen 契约不同。
- 构建失败不是源码不兼容，而是 pip build backend 自动加载了与新 Python 源码不匹配的旧 `_C.so`。

## 解决方法或 Workaround

- 修改思路：在 PR 分支上修正共享放置与阶段计时，保证 sweep/bench 使用真实 VAE 设备；强化数值、错误与别名比较；增加设备同步、manual flow 和 PPU 路由单测；兼容已安装 backport；将 PPU `_unsafe_view` 纳入生成器例外并同步生成配置。
- bench 可用性：增加 `--disable-backend-autoload`、`--cache-dir`、wrapper `--run-dir` 和 `--log`，使模型、运行根、cache、receipt 和 backend autoload 策略均可通过单次命令显式传入，无需预先 export。
- 选定层级：模型流程语义留在 `tests/manual/qwen_image_21/`；设备同步实现使用 PR 的 `DeviceGuardImplInterface` 扩展点；硬件路由限制留在 PPU vendor-conf 生成路径，不散布模型名判断。
- 受影响调用方：Qwen-Image-2.1 manual tools 和 PPU `_unsafe_view` 默认路由；显式强制 FlagGems 仍可用于 A/B 诊断。
- Plugin 必要实现：`csrc/runtime/guard.h` 的同步修复来自 PR；PPU 路由与回归测试属于必要维护项。
- 源码路径：`/workspace/PyTorch-Plugin-FL`。
- 过程补丁：`/mnt/nfs/users/jinghao/qwen-image/05-tmp/pr342-*.patch`；仅用于可追溯应用，不提交。
- 旧构建备份：`/mnt/nfs/users/jinghao/qwen-image/05-tmp/build.before-pr342-a3b46f8`；当前新 build 保留在源码树的标准 `build/`。
- 分支与 revision：`codex/pr-342-ppu-fixes@229386dcb4734334bd695c6aabe24a35b8b491d2`，工作树有未提交修复；未 commit、未 push。
- 构建证据：`/mnt/nfs/users/jinghao/qwen-image/04-runs/pr342-fixes-20260918-01/build-install.log` 和 `build-install-retry.log`。
- 最终验证证据：同目录 `unit-tests.log`（SHA-256 `44e74b4f62911246dd2e74301356c75b06465ad6bb49510270badfcbe9b80c10`）、`diffusers-import.log`（`5d4e51b16f3a4f291c9b0e896962b97a551a5328393318815cbb1fcae59cf3a6`）和 `ppu-unsafe-view-live.log`（`76653d76a6d5197a44b2bb7bd04496ab52d1d2cc3dc57d930e0630a0349f12d3`）。
- 服务停启：没有停止、重启或删除容器及服务。
- vLLM 未修改证明：本轮未进入 vLLM 源码或安装路径。

## FlagGems 证据

- FlagGems 源码与安装未修改。
- PPU live 对照：FlagGems `_unsafe_view` 在非连续输入上返回 `ALIASES False`；切换默认路由到 CUDA boxing 后，可视图输入 `ALIASES True`，非兼容 stride 得到预期 RuntimeError。
- 该缺陷以 Torch-FL vendor route 规避；退出条件是 FlagGems `_unsafe_view` 实现恢复 ATen 别名/异常契约并在 PPU 回归通过。

## 验证结果

- 最新最小回归：`8 passed`，覆盖 manual flow、benchmark 最少样本、无环境变量 CLI、`synchronizeDevice` 和 PPU 路由可再生性；仅有 pytest/Python 3.12 既有 deprecation warnings。
- 构建与导入：editable install 成功；`torch_fl 0.1.0+ppu`、build accelerator `ppu`、16 个设备可见。
- Diffusers：未设置 `QWEN_IMAGE_21_DIFFUSERS` 时，从 site-packages 导入 `0.40.0` 且存在 `QwenImage21Pipeline`。
- 设备同步：当前设备同步成功；指定另一设备同步后原 current device 恢复。
- `eager`：最小 PPU `_unsafe_view` 契约通过；完整 Qwen-Image-2.1 40 步推理已通过，过程中新发现并修复 complex `slice.Tensor` 路由，证据见 003。
- `graph` capture/replay：未选择、未验证。
- 数值、dtype、shape、layout、边界条件：布尔真假 mask、candidate 缺失、异常类型和 `_unsafe_view` alias/error 已覆盖；PR 手工配对精度为 37.88 dB / MAE 1.2481，正式项目 accuracy 验收未选择。
- `git diff --check`：通过。

## 限制与下一步

- 已有完整模型加载、40 步去噪、VAE 解码和 PR 手工图片比较证据，因此 functional 成立；不等同于 graph、正式 accuracy 或 performance 验收完成。
- 容器中没有 `ruff` 命令，本轮未临时安装新 lint 依赖。
- 当前工作树有意保持未提交，便于用户审查；如需回推 PR，应先复跑完整推理并审查最终 diff，再 commit/push。
- PR #340 的 CUDA `_unsafe_view` 修复没有覆盖 PPU 配置；本分支的 PPU 例外应作为独立补充反馈上游。

## 经验沉淀

- 可跨模型复用：view 类算子必须比较 storage alias 与错误契约，单纯 `allclose` 不足；异步设备阶段计时必须在阶段边界同步。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：PrivateUse1/FlagGems view 算子契约测试与设备阶段计时方法。
