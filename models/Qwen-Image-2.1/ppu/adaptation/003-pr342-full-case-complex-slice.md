# 003：PR #342 完整 40 步在 PPU complex slice 路由失败

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-18
- 最后验证时间：2026-09-18
- 模型：Qwen-Image-2.1，权重 `/mnt/cpfs/models/Qwen-Image-2.1`
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器名称与镜像：`qwen-image`；镜像身份见环境分析
- Plugin / FlagGems / vLLM revision：Torch-FL PR #342 head `229386dcb4734334bd695c6aabe24a35b8b491d2`，本地分支 `codex/pr-342-ppu-fixes` 含未提交修复；FlagGems 与 vLLM 未修改
- 执行模式与负载：Diffusers eager，1024x1024，40 步，seed 42，单 PPU `flagos:0`

## 问题现象

- 错误签名：完整推理在第二个去噪 step 访问 `rotary_emb[prefix_len:]` 时，FlagGems `slice.py` 报 `AssertionError: slice: unsupported dtype torch.complex64`。
- 发生顺序：`text-encoder`、`transformer-step`、`vae` 隔离阶段均通过；只有开启 KV cache 的完整第二步触发。
- 影响范围：PPU 默认将 `slice.Tensor` 路由到 FlagGems 的 complex64/complex128 切片；不是 Qwen-Image-2.1 数值逻辑本身。
- 原始证据：`/mnt/nfs/users/jinghao/qwen-image/04-runs/pr342-declared-cases-20260918-01/infer-full-40.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 002 PPU `_unsafe_view` 路由 | FlagGems 默认路由不满足 ATen 契约 | 本次为 complex dtype 支持，非别名契约 | 高 | 沿用 vendor-conf 生成器的最小 boxing gap 扩展点，重新实测 |

## 诊断与假设

- 已验证：失败 tensor 是 rotary cache 的 `torch.complex64`；FlagGems 在进入 `as_strided` 实现前即拒绝 complex dtype。
- 已验证：同一 `complex64` 切片切到 PPU CUDA boxing 路径后，dtype、shape、device 和数值均正确。
- 已排除：不需要修改 Diffusers KV cache 或禁用 KV cache；这会改变模型路径和输出，只是规避而非根因修复。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 0 | 模型阶段 | 隔离 transformer step | 完整 40 步 + KV cache | `infer-full-40.log` | 第 2 step 报 complex slice assertion | 隔离阶段没有覆盖 cache 增量路径 |
| 1 | `slice.Tensor` 路由 | `flaggems` | PPU `cuda` boxing | `backends_ppu.conf` | 最小 complex slice 通过 | 确认路由是唯一实质变量 |
| 2 | 完整模型复验 | 修复前失败 | 修复后 40 步 | `infer-full-40-rerun.log` | 完成出图，0 CPU fallback | 根因修复有效 |

## 根因

- PPU `backends_ppu.conf` 将 `slice.Tensor` 默认路由到 FlagGems，而当前 FlagGems slice wrapper 显式不支持 complex dtype。Qwen-Image-2.1 的 rotary KV cache 从第二个去噪 step 开始切片 complex64 tensor，因此稳定触发。

## 解决方法或 Workaround

- 修改思路：将 PPU `slice.Tensor` 加入 `BOXING_TRITON_GAPS`，默认走 CUDA/PPU vendor boxing，保留 FlagGems kernel 以便显式 A/B 诊断。
- 选定层级：限制是 PPU + FlagGems 能力组合，因此修复放在 vendor-conf 生成器，不在模型脚本散布设备特例。
- 影响调用方：PPU 上所有 `slice.Tensor` 默认改走 boxing；其他 vendor 与显式 override 不变。
- Plugin 路径：`scripts/codegen/gen_vendor_confs.py`、`torch_fl/configs/backends_ppu.conf`、`tests/unit/test_ppu_unsafe_view_route.py`。
- 过程补丁：`/mnt/nfs/users/jinghao/qwen-image/05-tmp/pr342-ppu-complex-slice.patch`。
- 分支：`codex/pr-342-ppu-fixes@229386dcb4734334bd695c6aabe24a35b8b491d2`，修复未 commit、未 push。
- 服务停启：未停止、重启或删除容器及服务。
- vLLM 未修改证明：本轮未进入 vLLM 源码或安装路径。

## FlagGems 证据

- FlagGems 源码与安装未修改。
- 实测失败点：`/workspace/FlagGems/src/flag_gems/ops/slice.py:199`。
- 安全默认策略：PPU boxing；退出条件是 FlagGems slice 在 PPU 支持 complex64/complex128 并通过 dtype、view/stride 和完整 KV-cache 回归。

## 验证结果

- 最小回归：共 `6 passed`；实时 complex64 slice 返回 `(6,) torch.complex64 flagos:0` 且数值正确。
- eager 完整流程：1024x1024、40 步成功；text encoder 1.438 s，去噪 40.241 s，VAE 1.301 s；图像 mean 0.3732、std 0.3775。
- 算子 census：141100 次 dispatch，64 种 ATen op；40 种走 `flagos_python`，24 种走 boxing；CPU fallback 0，libentry failure 0。
- 确定性：两次同 seed PNG 字节完全一致，SHA-256 均为 `e3a115f296f280c1efbc529643839abf2e90c1d34f843ae40dca347b9a9b3ff2`。
- 配对精度：共享初始 latent 时，flagos 相对 CUDA/PPU vendor 为 PSNR 37.88 dB、MAE 1.2481；与 PR A100 参考 37.82 dB / 1.194 同一量级。
- 逐算子：36/36 运行，7/7 view aliasing 一致；35 个在容差内，仅 `cumsum` 因 FlagGems fp32 累加与 vendor bf16 累加不同，符合 PR 已声明预期。
- prompt 01 sweep：CUDA 和 flagos 均生成 1024x1024 图像及 manifest；side-by-side 视觉检查均语义清晰、无黑图/花屏/结构崩坏。
- 主证据根：`/mnt/nfs/users/jinghao/qwen-image/04-runs/pr342-declared-cases-20260918-01`。
- 关键哈希：`infer-full-40-rerun.log` `92431e6f49c878936ec58e937d79c1dfe883be3a58109a12008e9d0f688e0d52`；`compare-paired.log` `a54eff1c837095e7316910dca5e015c6b62b9f11d7d011420d94595152bff5a6`；`numerics-compare.log` `d5f0131acd43126bc5aca60d437b21fe05e0afc78449dad5c12c40024c1973ff`。
- `graph` capture/replay：未选择、未验证。

## 限制与下一步

- 用户已确认 `--no-enable-prefix-caching` 是 vLLM 服务性能前置；当前为 Diffusers 本地 pipeline，该要求不适用。PR 正式 bench 已执行。
- batch-1：CUDA 36.24 s/image，flagos 37.42 s/image（`1.03x`）；两者均 2 个正式调用、36.80 GiB 峰值分配显存、确定性通过。
- batch-4 flagos：36.41 s/image，0.0275 images/s，56.52 GiB，2 个正式调用、确定性通过；该过程新发现的 receipt 样本数问题见 004。
- 设计审查：本次修复位于现有 PPU vendor 路由扩展点，对其他平台无行为变化；代价是 PPU 上所有 slice 默认使用 boxing，后续可在 FlagGems 具备 dtype-aware 路由后缩小范围。

## 经验沉淀

- 可跨模型复用：隔离的 single-step transformer 不会覆盖增量 KV cache 的后续 step；complex rotary cache 需要单独验证 dtype-aware slice 路由。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：PPU/FlagGems complex view/slice 路由诊断与 KV-cache 完整步验证。
