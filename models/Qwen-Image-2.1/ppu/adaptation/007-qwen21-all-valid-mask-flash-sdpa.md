# 007：Qwen-Image-2.1 全有效 Prompt Mask 阻断 Flash SDPA

## 元数据

- 状态：`verified-candidate`
- 首次出现时间：2026-09-20
- 最后验证时间：2026-09-20
- 模型：Qwen-Image-2.1，权重 `/mnt/cpfs/models/Qwen-Image-2.1-0920`
- 平台与 Host 别名：T-Head PPU，`PPU-07`
- 容器名称与镜像：`qwen-image-flagos`，`qwen-image-flagos:from-qwen-image-20260920`
- Plugin / FlagGems / vLLM revision：Torch-FL `codex/qwen21-ppu-latest@706b26af9ab32a2a210d41caded14c399e7e3f02`，工作树包含已有未提交适配改动；FlagGems `master@454f68853424970deb800290b7d7538a09a0b4bb`；本链路不使用 vLLM
- 执行模式与负载：Diffusers eager，bf16，batch 1，1024×1024，40 步，seed 42，KV cache 开启，共享固定 latent，2 次预热，至少 60 s 正式测量

## 问题现象

- 症状：推理已调用 Flash SDPA，但 1024²/40 步仍为约 37.4 s/图，去噪阶段占绝大部分。
- 发生顺序：3 步 profiler 中共 165 次 SDPA，仅 36 次走 Flash，129 次走 Efficient；全程 0 次 math SDPA。
- 影响范围：当 Qwen-Image-2.1 编码后的 prompt mask 全为有效位，但仍以显式 `attn_mask` 传入去噪 Transformer 时，该 PPU/PyTorch SDPA 选路不能使用 Flash。
- 原始证据：路由基线 `/mnt/nfs/users/jinghao/qwen-image/02-issues/sdpa-route-qwen-image-21-20260920.json`；本轮 A/B `/mnt/nfs/users/jinghao/qwen-image/04-runs/qwen21-mask-sdpa-opt-20260920/`；集成烟测 `/mnt/nfs/users/jinghao/qwen-image/04-runs/qwen21-mask-elision-integrated-20260920/`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 006 FlagOS 高频路由与 SwiGLU 优化 | 同一模型、设备、eager 去噪热点 | 006 处理算子路由/融合；本问题是 SDPA mask 语义造成的 kernel 选路 | 高 | 单独做 mask-only A/B，不叠加 006 候选 |
| 003 complex slice 路由 | 同一 Torch-FL/FlagGems 混合链路 | 003 是 correctness 失败；本问题是语义等价的性能选路 | 中 | 保持 003 修复不变，只改 prompt mask |

## 诊断与假设

已验证事实：

- 当前 canonical prompt 产生 `prompt_mask.shape == (1, 26)`，26/26 个元素均有效。
- 仅在 prompt 编码后将该全有效 mask 置为 `None`，3 步 profiler 的总 SDPA 调用仍为 165，Flash 由 36 增至 132，Efficient 由 129 降至 33；正好有 96 次从 Efficient 转为 Flash。
- 剩余 33 次 Efficient 没有被强制改路，表明优化没有全局禁用 mask 或强制 Flash。
- 耗时收益几乎全部来自去噪，文本编码与 VAE 时间基本不变。

已排除：不是 CPU fallback、libentry 编译失败、显存不足、vLLM prefix cache 或 Flash SDPA 完全未启用。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 省略全有效 prompt mask | 3 步中 Flash 36 / Efficient 129 | mask 全为 True 时返回 `None` | `02-issues/qwen21-mask-sdpa-opt-20260920/sdpa_profile.py` | Flash 132 / Efficient 33 | 根因假设成立 |
| 2 | 同一 mask-only 优化 | 37.376551 s/图 | 显式开启 mask elision | `04-runs/qwen21-mask-sdpa-opt-20260920/` | 25.660589 s/图 | 延迟降低 31.35%，1.4566× speedup |
| 3 | 正式 case 集成开关 | 一次性 monkeypatch | `--omit-all-valid-prompt-mask` | `04-runs/qwen21-mask-elision-integrated-20260920/` | 512²/3 步退出 0，2 次测量确定性一致 | 正式 `run.sh bench` 入口可用 |

首次 profiler 文件命名为 `profile.py` 时意外遮蔽 Python 标准库 `profile`，导致 `cProfile` 循环导入；已改名为 `sdpa_profile.py`，这是诊断脚本命名问题，不是模型或 Torch-FL 故障。

## 根因

- 已验证根因：Diffusers Qwen-Image-2.1 pipeline 已移除 prompt padding，却仍传递全为有效位的显式 key mask。该 mask 在数学上不改变 attention，但使当前 SDPA selector 将去噪 attention 选到 Efficient 而非 Flash kernel。
- 证据边界：只验证了当前 PPU 软件栈、bf16、batch 1 与当前 sequence shape；不外推到其他后端或 graph。

## 解决方法或 Workaround

- 修改思路：在 Qwen-Image-2.1 manual case 的 prompt 编码边界增加显式开关；将 mask 搬到 CPU 检查，仅当每个 batch row 的每个元素均有效时返回 `None`，含 padding 时保持原 mask。
- 选定层级：当前放在模型手工 case 的 `common.py`，由 `bench.py`/`infer.py`/`sweep.py` 显式启用。不修改只读的 Diffusers site-packages，不在 Torch-FL 通用 SDPA 里每次做数据相关同步，也不强制其他模型走 Flash。
- 守卫未命中行为：未传开关时完全保持原行为；mask 为 `None` 时保持；任一位为无效时保持完整 mask。
- Plugin 路径：`tests/manual/qwen_image_21/common.py`、`bench.py`、`infer.py`、`sweep.py`、`README.md`；回归测试 `tests/unit/test_qwen_image_21_manual_flow.py`。
- 一次性过程代码：`/mnt/nfs/users/jinghao/qwen-image/02-issues/qwen21-mask-sdpa-opt-20260920/mask_opt.py` 和 `sdpa_profile.py`；用于受控 A/B 与选路计数，不是产品入口。
- 多进程数据集入口：已将同一 opt-in 守卫接入 `/mnt/nfs/users/jinghao/qwen-image/generate_qwen21_dataset.py`；每个 worker 在自己的 pipeline 上安装，manifest 记录 `omit_all_valid_prompt_mask`。修改后 SHA-256 为 `4f05fca62c0fd9612ef0a656ec9b98dc14e9886b90fc3594bd664c14d2dbf651`；`infer_acc.sh` 已传入该开关，内容未改。
- 分支与 revision：`codex/qwen21-ppu-latest@706b26af9ab32a2a210d41caded14c399e7e3f02`；改动未提交、未推送。
- 服务停启：无；容器未停止、重启或删除；验证后 PPU 0% util、1 MiB/卡。
- vLLM 未修改：本地 Diffusers pipeline 不使用 vLLM，未检出 vLLM checkout，不涉及 `--no-enable-prefix-caching`。

## FlagGems 证据

- FlagGems revision 保持 `454f68853424970deb800290b7d7538a09a0b4bb`，本轮未同步、未修改。
- 本问题不是 FlagGems 算子缺失或错误；它发生在进入 SDPA kernel 前的模型 mask 语义层，不创建 `07-bugs/` 算子复现器。

## 验证结果

- 最小回归：修改文件 `py_compile`、`tests/unit/test_qwen_image_21_manual_flow.py` 全文件和 `git diff --check` 通过；单测覆盖全有效 mask 被省略、含 padding mask 保留及重复安装无重复包装。
- 路由：3 步中 96/165 次 SDPA 从 Efficient 转为 Flash；Flash 36→132，Efficient 129→33，math 保持 0。
- 1024²/40 步配对 A/B：37.376551→25.660589 s/图，节省 11.715962 s，延迟降低 31.35%，加速 1.4566×；去噪 36.790282→25.075630 s，每步 919.757→626.891 ms，降低 31.84%；峰值显存均为约 36.800 GiB。
- 数值：基线与优化图像均为 1024² RGB；MAE 0.6824/255，RMSE 1.4418，PSNR 44.95 dB，max abs 77。这证明图像接近，但不是逐像素一致或正式精度回执。
- 集成烟测：正式 `run.sh bench --omit-all-valid-prompt-mask` 在 512²/3 步退出 0，JSON 记录开关为 `true`，2 次测量均为 0.701895 s/图、确定性一致，0 CPU fallback、0 libentry failure、0 traceback。
- 数据集入口烟测：`/mnt/nfs/users/jinghao/qwen-image/04-runs/qwen21-dataset-mask-opt-smoke-20260920/` 以单 worker、batch 1、512²/3 步生成 `case_001.png`，退出 0；日志确认全有效 mask 已省略，manifest 记录开关为 `true`，worker 退出码 0，0 CPU fallback、0 libentry failure、0 traceback。首次 37.14 s 包含新 cache 的 Triton 编译，不作为稳态性能数据。
- `graph` capture/replay、正式 accuracy 和项目正式 performance acceptance：未执行，不更新 `platform.yml` 状态。

## 限制与下一步

- 尚存限制：真实 padded multi-prompt batch、true CFG、其他分辨率/序列长度、graph 与其他后端尚未进行完整回归。
- 数据集脚本默认跳过输出目录中已存在的非空 PNG；若 `qwen21-dataset-100` 里已有旧图，再次执行 `infer_acc.sh` 不会将其自动替换为优化路径的新图。重生时应明确选择新输出目录或 `--overwrite`，不应默认覆盖旧数据。
- 后续动作：在决定默认开启前，用固定 latent 运行 prompt cohort/正式图像精度验收，补真实 padding batch 和 graph 证据；长期应评估向 Diffusers 上游提交模型语义修复，而不是将数据相关判断下沉到通用 SDPA dispatch。
- 设计审查：当前显式 opt-in 开关、模型边界守卫和 receipt 自描述足以作为可维护的现场性能 profile；在完成精度与 graph 验收前不宜改为默认行为。

## 经验沉淀

- 可跨模型或平台复用：诊断“Flash 已有调用但仍慢”时，应按阶段和 mask 类型统计 SDPA 实际 kernel；全有效 mask 可能仅因 API 形态阻断 Flash。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：显式全有效 attention mask 造成 SDPA kernel 降级的诊断与安全省略条件。
