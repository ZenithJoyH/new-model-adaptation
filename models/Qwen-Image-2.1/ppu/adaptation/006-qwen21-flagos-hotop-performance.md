# 006：Qwen-Image-2.1 FlagOS 高频算子路由与 SwiGLU 融合优化

## 元数据

- 状态：`verified-candidate`
- 首次出现时间：2026-09-20
- 最后验证时间：2026-09-20
- 模型：Qwen-Image-2.1，当前包装脚本使用 `/mnt/cpfs/models/Qwen-Image-2.1-0920`
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器名称与镜像：`qwen-image-flagos`，`qwen-image-flagos:from-qwen-image-20260920`，image id `sha256:f6456946e47200146d498ff19e884f55cee2c07c4c58eb4480063ed80769f907`
- Plugin / FlagGems / vLLM revision：Torch-FL `codex/pr-342-ppu-fixes@229386dcb4734334bd695c6aabe24a35b8b491d2`，已有未提交适配改动；FlagGems `master@454f68853424970deb800290b7d7538a09a0b4bb`、clean；本次 Diffusers pipeline 不使用 vLLM
- 执行模式与负载：Diffusers eager，bf16，batch 1，1024×1024，40 步，seed 42，KV cache 开启，2 次预热、2 次正式测量

## 问题现象

- 症状：当前同栈基准中，`flagos:0` 为 37.442254 s/图，`cuda:0` 为 36.242277 s/图；CUDA 只作为对照，不定义 FlagOS 的性能上限。
- 发生顺序：dispatch census 显示 141100 次调用、64 个 ATen 算子、0 CPU fallback；33729 次走 `flagos_python`，107371 次走 PPU CUDA boxing。去噪占 FlagOS 总耗时 36.859986 s，是首要优化阶段。
- 影响范围：Qwen-Image-2.1 当前单卡 Diffusers eager 推理；未外推到其他模型、graph、训练或其他 PPU 软件栈。
- 原始证据：基线 `/mnt/nfs/users/jinghao/qwen-image/qwen21-bench/flagos.json`；census `/mnt/nfs/users/jinghao/qwen-image/qwen21-census/infer-flagos.log`；本轮全部 A/B `/mnt/nfs/users/jinghao/qwen-image/04-runs/qwen21-perf-opt-20260920-01/`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 002/003 PPU 算子路由修复 | 同一 Torch-FL dispatch 和 PPU boxing/FlagGems 混合链路 | 本次是性能，不是 `_unsafe_view` 或 complex slice 正确性缺陷 | 高 | 沿用逐算子环境覆盖做可回滚 A/B，不扩大已知 correctness gap |
| 004 benchmark 最小样本修复 | 相同 bench runner、预热和至少两次正式测量 | 本次比较多个优化候选 | 高 | 每轮保留 JSON、阶段统计、spread 和确定性 |

## 诊断与假设

已验证事实：

- 高频 `flagos_python` 中，`add/where/native_layer_norm/mean/pow/rsqrt/tanh/silu` 合计覆盖大部分调用；整体改走 PPU vendor boxing 后，非 `-0920` 定位负载从 37.452895 s 降至 37.017032 s。
- 归一化组单独为 37.16 s，残差/激活组单独为 37.27 s，说明两组均有收益而非单一偶然点。
- 直接把所有可用算子强制到 vendor 加 fused SwiGLU 为 37.33 s，慢于精选路由 36.95 s；因此部分 FlagGems kernel 有正收益，不能把 CUDA/vendor 当作性能上限或全局默认。
- ZeroCenterRMSNorm 保持原 fp32 语义的 FlagGems fused 实验为 37.51 s，是负优化；fused SwiGLU 单独为 37.29 s，有正收益。

当前假设：精选的逐算子 boxing 消除了若干高频 Python/Triton kernel 的负收益，SwiGLU 融合减少一次大张量中间结果和一次 dispatch；剩余差距包含 FlagOS PrivateUse1 调度成本和未逐项 profile 的 kernel 差异。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 显式 cache 复测 | 37.4423 s | 仅把 cache 放入 `06-cache` | `baseline/flagos/bench.json` | 37.4529 s | 与用户基线一致，无目录偏差 |
| 2 | 8 个热点整体路由 | 37.4529 s | 8 op → `cuda` boxing | `group-all-boxing/flagos/bench.json` | 37.0170 s | 路由选择有 1.16% 收益 |
| 3 | 归一化组 | 37.4529 s | norm/mean/pow/rsqrt → boxing | `group-norm-boxing/flagos/bench.json` | 约 37.16 s | 主要贡献组 |
| 4 | 残差/激活组 | 37.4529 s | add/where/tanh/silu → boxing | `group-residual-activation-boxing/flagos/bench.json` | 约 37.27 s | 也有正收益 |
| 5 | fused RMSNorm + SwiGLU | 37.4529 s | 两个 FlagGems fused kernel | `fused-rms-swiglu/flagos/bench.json` | 37.2713 s | 需要拆分 |
| 6 | fused RMSNorm | 37.4529 s | 仅 fp32 ZeroCenterRMSNorm | `fused-rms-only/flagos/bench.json` | 约 37.51 s | 淘汰 |
| 7 | fused SwiGLU | 37.4529 s | 仅 `silu_and_mul` | `fused-swiglu-only/flagos/bench.json` | 约 37.29 s | 保留候选 |
| 8 | 全 vendor 上界诊断 | 37.4529 s | `FLAGOS_FORCE_BACKEND=vendor` + fused SwiGLU | `diagnostic-vendor-swiglu/flagos/bench.json` | 约 37.33 s | 全 vendor 慢于混合路由，淘汰 |
| 9 | 当前 `-0920` 最终候选 | 37.442254 s | 精选 8 op boxing + fused SwiGLU | `candidate-0920-swiglu-boxing/flagos/bench.json` | 36.981160 s | 延迟降低 1.23%，吞吐等价提升 1.25% |

上述相对路径均位于 `/mnt/nfs/users/jinghao/qwen-image/04-runs/qwen21-perf-opt-20260920-01/`。

## 根因

- 已验证根因：当前 PPU 混合 dispatch 下，所列 8 个高频 FlagGems Python 路由在该模型/shape 上合计慢于已有 vendor boxing；Qwen SwiGLU 的独立 `silu` 与 `mul` 还会生成大中间张量和两次 dispatch。
- 未完全证实部分：尚无设备 profiler 的逐 kernel 时间，不能把 1.23% 拆成每个算子的独立贡献，也不能断言同一配置对其他模型或 shape 有益。

## 解决方法或 Workaround

- 当前候选：仅对本模型实验入口启用 8 个逐算子覆盖，并把 Qwen-Image-2.1 SwiGLU 临时替换为 FlagGems `silu_and_mul`。
- 一次性代码：`/mnt/nfs/users/jinghao/qwen-image/02-issues/qwen21-fused-hotops-bench/bench_fused.py`；显式入口 `run_optimized.sh`。SHA-256 分别为 `3b39ed1d0e137099e6244f829ac495d24a1d78ca3742f972022fbb8a0e4fc5a4` 和 `acc0472095c13ad70e393c8d0e38424d3cbe488049ec81e038fee4af1d5f30e2`。
- 入口支持 `infer` 与 `bench`，默认不修改现有 `infer_flagos.sh`、`bench_flagos.sh` 或 Torch-FL 默认配置。
- 本轮未停止、重启或删除容器；完成后 16 卡均 1 MiB、0% util，无残留进程。
- vLLM 未参与、未修改；`--no-enable-prefix-caching` 不适用于此 Diffusers 本地 pipeline。

## FlagGems 证据

- 当前 revision：`454f68853424970deb800290b7d7538a09a0b4bb`，worktree clean；本轮没有同步或修改 FlagGems。
- 已有算子：`flag_gems.fused.silu_and_mul`、`flag_gems.rms_norm`。前者在本模型实测有收益，后者保持 ZeroCenter fp32 语义时无收益。
- 当前仅为仓库外一次性 A/B。按项目规则，正式集成前须取得 FlagGems 同步授权、fast-forward 到明确 upstream 后重新验证，并通过 Torch-FL/模型适配正式扩展点接入；不能把 monkeypatch 作为默认产品实现。
- 本轮没有 FlagGems 错误或数值崩溃，不创建 `07-bugs/` reproducer。

## 验证结果

- 最小回归：优化入口 `bash -n`、Python `py_compile` 和 `bench --help` 通过。
- `eager`：当前 `-0920` 模型 1024×1024、40 步、2 warmup + 2 measured 全部通过；0 CPU fallback，候选两次输出确定性一致。
- 性能：37.442254 → 36.981160 s/图，节省 0.461095 s；去噪 36.859986 → 36.467737 s，每步 921.500 → 911.693 ms；文本编码 115.848 → 46.141 ms；VAE 基本不变；峰值显存 36.800 → 36.816 GiB。
- 候选 JSON SHA-256：`0b98809cba39d4dc0869c25512c86bdd99eb42dc22b42637736490fe903c9996`；候选 PNG SHA-256：`f195fda6822712235e9f0e1feec36ba99b6aee820bd944f4577c706eddde9130`。
- 图片 sanity：候选与当前 `qwen21-census/flagos/full.png` 为 MAE 0.7612、PSNR 42.89 dB、max 112；这不是配对 latent 的正式精度回执。
- `graph`、正式 accuracy、正式 performance acceptance：均未执行；本结果是 eager 优化候选，不更新 `platform.yml` 的正式状态。

## 限制与下一步

- 候选依赖当前 Qwen-Image-2.1 类结构、bf16、PPU 2.1.0 runtime、Torch 2.10.0+cpu relink、Diffusers 0.41.0.dev0 和当前 FlagGems revision。
- 下一步需要用户明确授权同步 FlagGems；随后重新冻结 revision，把 fused SwiGLU 接入可维护的模型适配/dispatch 扩展点，增加守卫未命中、dtype/shape、eager/graph 和完整图片精度回归，再决定是否将逐算子路由缩小到 PPU 默认配置或保留为模型 profile。
- 设计审查结论：一次性入口适合作为性能候选和现场验证工具，不是 PR 候选；直接修改 Diffusers site-packages、全局 `FLAGOS_FORCE_BACKEND=vendor` 和 fused RMSNorm 均已排除。

## 经验沉淀

- 可复用结论：不要把 vendor/CUDA 当作性能上限；先用 census 选高频算子，分组路由 A/B，再验证模型级融合，且保留混合路由。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：PrivateUse1 混合路由的高频算子分组 A/B 与模型级 fused op 筛选方法。
