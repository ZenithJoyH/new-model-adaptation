# Qwen-Image-2.1 PPU 适配问题索引

| 编号 | 问题 | 状态 | 首次发现 | 根因/当前结论 | 记录 |
|---|---|---|---|---|---|
| 001 | 容器 Diffusers 缺少 Qwen-Image-2.1 专用类 | resolved | 2026-09-17 | 原 0.40.0 最小移植和后续固定 0.41.0.dev0 开发版均已验证；开发版 40 步图片与旧基线逐字节一致，无需升级 TorchAO | [001-missing-qwenimage21-diffusers.md](001-missing-qwenimage21-diffusers.md) |
| 002 | Torch-FL PR #342 集成与审查问题修复 | verified | 2026-09-18 | PR 已构建安装；放置、计时、receipt、数值契约、stable Diffusers 与 PPU `_unsafe_view` 路由修复通过，完整用例见 003 | [002-pr342-integration-and-review-fixes.md](002-pr342-integration-and-review-fixes.md) |
| 003 | PR #342 完整 40 步在 PPU complex slice 路由失败 | resolved | 2026-09-18 | `slice.Tensor` 的 FlagGems 路由不支持 complex64；改用 PPU boxing 后完整 40 步、确定性、配对精度、逐算子与 prompt 01 sweep 通过 | [003-pr342-full-case-complex-slice.md](003-pr342-full-case-complex-slice.md) |
| 004 | PR #342 慢负载 benchmark 未保证两个正式样本 | resolved | 2026-09-18 | autorange 单调用超过最短时间时只记 1 个 sample；已补足第二个 timed call，batch-4 receipt 实测通过 | [004-pr342-benchmark-minimum-samples.md](004-pr342-benchmark-minimum-samples.md) |
| 005 | CPU Torch 保留 PPU Torch-FL 时 runtime 与 CUDA 元数据不完整 | resolved | 2026-09-20 | 完整 PPU libtorch/MKL bundle + 由 C++ runtime 恢复 CUDA ABI 元数据；bitsandbytes 原生库选择正常，40 步图片与旧基线逐字节一致 | [005-cpu-torch-ppu-libtorch-bundle.md](005-cpu-torch-ppu-libtorch-bundle.md) |
| 006 | FlagOS 高频路由与 Qwen SwiGLU 融合性能优化 | verified-candidate | 2026-09-20 | 精选 8 个热点改走 PPU boxing、SwiGLU 使用 FlagGems 融合后，当前 `-0920` 负载由 37.4423 降至 36.9812 s/图；正式集成前仍需同步 FlagGems 并补 graph/精度验收 | [006-qwen21-flagos-hotop-performance.md](006-qwen21-flagos-hotop-performance.md) |
| 007 | 全有效 prompt mask 阻断去噪 Flash SDPA | verified-candidate | 2026-09-20 | 只省略数学上无效的全有效 mask，3 步中 96 次 SDPA 由 Efficient 转 Flash；1024²/40 步配对 A/B 延迟降低 31.35%，仍需正式精度与 graph 验收 | [007-qwen21-all-valid-mask-flash-sdpa.md](007-qwen21-all-valid-mask-flash-sdpa.md) |

当前已有 eager 完整功能与 PR 手工精度用例证据；不代表 graph 或项目正式精度/性能验收完成。
