# 001：容器 Diffusers 缺少 Qwen-Image-2.1 专用类

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-17
- 最后验证时间：2026-09-20
- 模型：Qwen-Image-2.1，权重 `/mnt/cpfs/models/Qwen-Image-2.1`
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器名称与镜像：原适配容器 `qwen-image`；2026-09-20 用户要求的 CPU-wheel-plus-PPU-runtime 实验环境为 `qwen-image-flagos`，镜像 `qwen-image-flagos:from-qwen-image-20260920`
- Plugin / FlagGems / vLLM revision：Torch-FL `codex/pr-342-ppu-fixes@229386dcb4734334bd695c6aabe24a35b8b491d2` 含未提交审查修复；FlagGems `454f68853424970deb800290b7d7538a09a0b4bb` 未修改；vLLM `0.23.0+v0.2.0.ppu2.1.0` site-packages only
- 执行模式与负载：Diffusers eager；失败发生于模型加载前，未分配 PPU

## 问题现象

- 错误签名：`AttributeError: module diffusers has no attribute QwenImage21Pipeline`。
- 发生顺序：运行 `inference_with_gems.py` → `DiffusionPipeline.from_pretrained` 读取 `model_index.json` → 查找 Pipeline 类立即失败。
- 影响范围：Qwen-Image-2.1 无法加载；Qwen-Image-2512 使用旧 `QwenImagePipeline`，不直接受首个错误影响。
- 原始证据：`/mnt/nfs/users/jinghao/qwen-image/04-runs/qwen-image-21-error-repro-20260917-01/inference.log`，SHA-256 `42acb95ca2be379a33c62f01413944c31d210358d0a4fd3bf5191d5279776726`。

## 已有经验匹配

仓库知识库没有匹配“Diffusers 缺模型专用类”的已验证条目。既有 Qwen-Image complex64 slice 问题发生在模型已加载后的 RoPE 阶段，与本问题的加载期签名不同，仅作为后续风险，不用于解释当前根因。

## 诊断与假设

- 已验证：当前 Diffusers 0.40.0 仅有 `QwenImagePipeline`、`QwenImageTransformer2DModel`、`AutoencoderKLQwenImage`。
- 已验证：权重要求 `QwenImage21Pipeline`、`QwenImage21Transformer2DModel`、`AutoencoderKLQwenImage21`，模型目录不附带 remote-code Python 文件。
- 已验证：用户参考 ZIP 是 Diffusers 0.41.0.dev0 完整源码，固定提交 `9511e982...`，包含上述类和测试。
- 已验证：容器 `torchao 0.11.0` 不提供 `FqnToConfig`；引用者是 `transformers 5.8.1` 的 TorchAO 量化集成。模型四份配置均未声明 `quantization_config`，普通 BF16 推理不进入该可选路径。2026-09-20 在不升级 TorchAO 的前提下，参考开发版的类导入、完整权重加载和 40 步推理均已通过。
- 已验证：`peft 0.20.0` 已安装在 `qwen-image` 容器中，满足本轮要求，不重复升级依赖集合。
- 已排除：设置 `trust_remote_code=True`；模型目录没有可加载的自定义代码。
- 已排除：修改 `model_index.json` 使用旧类；架构、text encoder、DiT、VAE 均不兼容。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 结果 | 结论 |
|---|---|---|---|---|---|
| 0 | 模型路径 | Qwen-Image-2512 | Qwen-Image-2.1 | 加载期缺类 | 已保留负对照 |
| 1 | Diffusers 来源 | 0.40.0 | pinned 0.41.0.dev0 reference，`--no-deps` | 新旧类与配置解析通过；随后撤销 | 开发版可导入，但用户确认该基线与 `torchao 0.11.0` 存在潜在 API 代差，不作为最终方案 |
| 2 | 移植范围 | 整套 0.41.0.dev0 | 官方 0.40.0 wheel + 4 个 Qwen-Image-2.1 实现文件和必要 lazy-import 注册 | 导入、配置解析、无大权重 pipeline 装配通过 | 保留 stable 行为，只增加模型所需实现 |
| 3 | 推理脚本默认值 | Qwen-Image-2512、50 步、CFG 4.0 | Qwen-Image-2.1、40 步、CFG 1.0 | 语法与参数审查通过 | 与参考文档默认“40 steps and no guidance”一致；设备执行待资源释放 |
| 4 | 完整开发版 | 0.40.0 最小回移 | 固定 ZIP `9511e982...`构建 0.41.0.dev0 wheel，`--no-deps --force-reinstall` | fresh import、PPU autoload、bitsandbytes 均通过；TorchAO 仍为 0.11.0 | 开发版可在当前非量化环境使用，不需升级 TorchAO |
| 5 | 开发版整模回归 | 0.40.0 backport 成功图片 | 0.41.0.dev0，相同 prompt/seed/1024×1024/40 步 | 成功出图，SHA-256 与基线相同，0 fallback | 整套开发版未引入可见数值差异 |

## 根因

当前容器的公开 Diffusers 0.40.0 早于 Qwen-Image-2.1 专用实现；模型权重与参考 fork 配套，但运行环境未安装该 fork。此问题不属于 Torch-FL 或 FlagGems dispatch。

## 解决方法或 Workaround

- 修改思路：初始为控制兼容面，以 stable `diffusers 0.40.0` wheel 为基线做最小移植。2026-09-20 用户明确要求在实验容器改用完整参考开发版；因此先备份当前包，由固定 ZIP 构建 wheel，再以 `--no-deps --force-reinstall` 仅替换 Diffusers。
- 选定层级：Diffusers 模型框架依赖；不复制模型实现到 Torch-FL，不修改权重索引。
- 共享影响：验证新旧 QwenImage Pipeline 均能导入；任何旧类回归立即回滚。
- Plugin 必要实现：否；预期 Torch-FL、FlagGems、vLLM 均无源码 diff。
- 参考 ZIP：`/mnt/nfs/users/jinghao/qwen-image/Qwen-Image-2.1-ref-qwen-image-2.1.zip`，SHA-256 `0f788ee6b453d223903d1bd88bac0a7108d71bf627f2453b44c0409c75ad62f3`。
- 原始 stable 回滚包：`/mnt/nfs/users/jinghao/qwen-image/05-tmp/qwen-image-21-diffusers/diffusers-0.40.0-installed-backup.tar.gz`，SHA-256 `1a5fd329d8e63953db23fc911925dc5acb59c38a6c19a7b939a31c50eccb8797`。
- 最终兼容 wheel：`/mnt/nfs/users/jinghao/qwen-image/05-tmp/qwen-image-21-diffusers/wheels/diffusers-0.40.0-1qwen21-py3-none-any.whl`，SHA-256 `62dbd1fc1a1c1e361ef6f19b5a24ec801bc2701b2a37bbedd99f159c0d1aaf8e`。
- 开发版 wheel：`/mnt/nfs/users/jinghao/qwen-image/05-tmp/qwen-image-21-diffusers-dev-9511e98-20260920/wheels/diffusers-0.41.0.dev0-py3-none-any.whl`，SHA-256 `daa2b1f4c910bd55ff4748dd2af5ef4d1cdefece2b20595a62ce1de52c2aa603`。
- 开发版安装前回滚包：`/mnt/nfs/users/jinghao/qwen-image/05-tmp/qwen-image-21-diffusers-dev-9511e98-20260920/diffusers-0.40.0-qwen21-installed-backup.tar.gz`，SHA-256 `c9e4a4265333d8f072b11195f1c4b380f6403938e1b1aee5a9520e9f55b2fa8d`。
- 安装证据：`/mnt/nfs/users/jinghao/qwen-image/04-runs/qwen-image-21-diffusers-adaptation-20260917-01/install-stable-qwenimage21-compat.txt`；安装前后 `pip check` 均为既有 `rc=1`，文本完全一致，没有新增依赖冲突。
- 脚本：`/mnt/nfs/users/jinghao/qwen-image/inference_with_gems.py`，SHA-256 `7c4a29de74e8115cb23be0ba0e71df82113a7866f96586dcf83984f293e3235d`；原文件备份位于 `05-tmp/qwen-image-21-script-backups/`。
- workaround：若后续仅复现既有 complex64 slice 缺口，允许进程级 `FLAGOS_OP_slice__Tensor=cuda`；它不是本问题根因修复，退出条件是 dtype-aware dispatch 或 FlagGems complex slice 支持可用并回归通过。
- 服务停启：不停止任何服务，不重启/删除容器；PPU 当前被无关 vLLM 进程占用。
- vLLM 未修改证明：适配结束后重新记录包身份；当前无源码 checkout。
- 适配后复核：2026-09-20 `qwen-image-flagos` 中 Diffusers 为 `0.41.0.dev0`；Torch `2.10.0+cpu`、TorchAO `0.11.0`、Transformers `5.8.1`、PEFT `0.20.0` 和 bitsandbytes `0.48.1` 均未变。安装前后 `pip check` 文本完全一致，无新增依赖冲突。原 `qwen-image` 容器未修改。

## FlagGems 证据

- 当前 revision `454f68853424970deb800290b7d7538a09a0b4bb`、clean。
- 本问题在 ATen/FlagGems dispatch 前发生，不需要 FlagGems 算子集成，因而本轮不修改也不虚构同步结果。
- FlagGems 缺陷复现：本问题不适用；若后续 complex slice 复现，则按 `07-bugs/` 规则另建问题。

## 验证结果

- 最小回归：通过。fresh process 中 `diffusers=0.41.0.dev0`、`peft=0.20.0`；`QwenImage21Pipeline`、DiT 和 VAE 可导入。PPU autoload 后 `torch.version.cuda=13.0`，bitsandbytes 选择 `CudaBNBNativeLibrary`。
- 无大权重装配：通过。保留本地 `Qwen3VLProcessor` 与 scheduler、将 text encoder/transformer/VAE 显式置空后，`DiffusionPipeline.from_pretrained(..., local_files_only=True)` 得到 `QwenImage21Pipeline`，且三个大组件均未加载。
- `eager`：通过。0.41.0.dev0 下 1024×1024、seed 42、40 步完整推理成功；text encoder 1.472 s、denoise 38.948 s、VAE 0.849 s，reserved 37.62 GiB。
- `graph`：未选择、未验证。
- 数值/shape：40 步输出 SHA-256 `e3a115f296f280c1efbc529643839abf2e90c1d34f843ae40dca347b9a9b3ff2`，与 0.40.0 backport 及 vendor Torch 成功基线逐字节一致；141100 次 dispatch、64 个 distinct ATen op、0 CPU fallback、0 libentry failure。
- 当前通过标准：安装不改变既有依赖冲突集合，fresh import、最终权重加载、PPU 设备推理和配对图片对照均通过，问题关闭。证据位于 `/mnt/nfs/users/jinghao/qwen-image/04-runs/qwen-image-21-diffusers-dev-install-20260920-01/`。

## 限制与下一步

- 尚存限制：当前结论只覆盖非量化 eager BF16 路径；TorchAO 量化、graph、训练和分布式未验证。
- 下一步：若要使用 TorchAO 量化，需单独验证 Torch/TorchAO/PPU runtime 组合；不应为普通 Qwen-Image-2.1 推理升级 TorchAO。
- 设计审查结论：当前为“无 Plugin 变更”；若实际产生 Plugin diff，必须重新审查。

## 经验沉淀

- 可复用结论：本地权重的 `_diffusers_version` 数字不能替代类存在性检查；必须同时核对 Pipeline、模型组件和固定源码来源。
- 知识库处理状态：`needs-validation`
- 候选条目：本地 Diffusers 模型包声明了未发布/定制类时的安全依赖替换与回滚流程。
