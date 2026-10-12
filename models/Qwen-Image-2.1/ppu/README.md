# Qwen-Image-2.1 / ppu

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)

当前 framework 记录：
- [torch-fl](frameworks/torch-fl/README.md)（v2；历史结论不自动成为新门禁通过）。

旧平台阶段记录按原位置保留（不作为新增执行入口）：
- [环境与设计](environment)。
- [问题台账](adaptation/README.md)。

## 整理前平台说明（历史原文）

- Inventory group: `ppu`
- Hardware query: `ppu-smi`

平台根目录只保留本索引与 `platform.yml`。运行 `scripts/adapt-model` 后，环境材料、
适配过程和验收证据分别放入 `environment/`、`adaptation/` 和 `acceptance/`。
容器没有暴露 `ppu-smi` 时必须记录为环境阻塞，不得回退到其他平台命令。

当前实验容器的 editable Torch-FL 源码位于 `codex/qwen21-ppu-latest`分支，
已合入并更新 PR #342 相关能力。PR 已完成 PPU 构建安装；
放置、计时、receipt、数值/别名契约、Diffusers 导入和
PPU `_unsafe_view`/complex `slice.Tensor` 路由修复已验证。真实权重的 eager 1024x1024、40 步完整出图、
同 seed 确定性、CUDA/flagos 配对精度、逐算子和 prompt 01 sweep 均已通过，可标记为 functional。
本次还完成了 PR 的 batch-1 CUDA/flagos 正式 bench 与 flagos batch-4 throughput；当前为 Diffusers 本地
pipeline，vLLM 的 `--no-enable-prefix-caching` 前置不适用。graph 仍未验证；详见
`adaptation/003-pr342-full-case-complex-slice.md` 和 `adaptation/004-pr342-benchmark-minimum-samples.md`。

2026-09-20 用户要求的实验容器 `qwen-image-flagos` 已在 `torch 2.10.0+cpu` Python wheel +
PPU vendor runtime 组合上，以 `--no-deps` 安装固定参考提交的完整 Diffusers
`0.41.0.dev0`。TorchAO 保持 `0.11.0`；fresh import、PPU autoload、bitsandbytes native 库选择和
1024×1024/40 步完整推理通过，输出与旧基线逐字节一致。该实验容器不取代
`platform.yml` 记录的原适配容器；详见 `adaptation/001-missing-qwenimage21-diffusers.md` 和
`adaptation/005-cpu-torch-ppu-libtorch-bundle.md`。

同日完成 `Qwen-Image-2.1-0920` 的 eager 性能热点 A/B：不把 CUDA 当作上限，保留混合
FlagGems/vendor 路由，仅将 8 个实测负收益热点切到 PPU boxing，并用 FlagGems 融合
SwiGLU。候选从 37.4423 降至 36.9812 s/图（延迟降低 1.23%），图片 sanity 为
PSNR 42.89 dB；它仍是显式实验 profile，尚未完成 FlagGems 同步、正式产品接入、graph 与
正式精度/性能验收，详见 `adaptation/006-qwen21-flagos-hotop-performance.md`。

进一步的 SDPA 分阶段计数确认，当前 pipeline 将已去掉 padding 后的全有效
prompt mask 继续传入去噪 Transformer，使数学上的空操作阻断 Flash SDPA。在显式
`--omit-all-valid-prompt-mask` 守卫下，3 步中 96 次 SDPA 从 Efficient 转为 Flash，
1024²/40 步配对 A/B 从 37.3766 降至 25.6606 s/图（降低 31.35%，1.4566×）。
优化后图像与基线的 PSNR 为 44.95 dB，由于 Flash/Efficient bf16 归约顺序不同并非逐像素一致；
当前保持 opt-in，含 padding 的 mask 不会被省略。正式精度、真实 padded batch 和 graph 尚未验收，
详见 `adaptation/007-qwen21-all-valid-mask-flash-sdpa.md`。
