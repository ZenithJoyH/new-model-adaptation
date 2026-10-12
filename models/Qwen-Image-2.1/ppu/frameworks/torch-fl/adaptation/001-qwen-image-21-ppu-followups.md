# 001：Qwen-Image-2.1 PPU CPU-wheel 推理后续修复

## 元数据

- 状态：`open`
- 首次出现时间：2026-09-17
- 最后验证时间：2026-09-22
- 模型：Qwen-Image-2.1
- 平台与 Host 别名：PPU，`PPU-07`
- 容器名称与镜像：`qwen-image-flagos`，`qwen-image-flagos:from-qwen-image-20260920`
- Torch-FL revision：容器内 `30ff88f431b80fa20fca0476ea7094f0470948af`；PR HEAD `a3e6031e2c29fe1c583921e40360a0e390d9589d`，其父 commit `da75e80519509ad52f05c03c330901badd590912` 与容器 tree 相同；base `7298bfbd14c604f260bd84052dd1d8b2dd7ddc82`
- 执行模式与负载：eager，Qwen-Image-2.1 文生图和 `tests/manual/qwen_image_21/` 手工流程

## 问题现象

- 官方 `torch 2.10.0+cpu` 与 PPU CUDA-enabled libtorch 解耦使用时，实际 CUDA 运行时已可用，但 `torch.version.cuda` 仍为 `None`；`bitsandbytes` 因此误选 `libbitsandbytes_cpu.so` 并报缺失。
- Qwen-Image-2.1 在 PPU 的第 2 步去噪进入 complex64 rotary cache 切片，FlagGems `slice.Tensor` 拒绝 complex dtype；`_unsafe_view` 的 reshape 实现可静默拷贝，不符合 ATen alias/error contract。
- 原手工流程强制使用机器私有 Diffusers 路径，且 benchmark 可只收集一次超长调用，阶段计时在每步同步，运行参数与日志摘要也不易留存。
- 全有效 prompt mask 会使 SDPA 选择器排除 Flash 路径，实测存在明显性能损失。

## 已有经验匹配

| 历史问题 | 相同点 | 差异 | 结论 |
|---|---|---|---|
| upstream #342 | 同一 Qwen-Image-2.1 手工流程 | #342 未覆盖 CPU wheel 元数据、PPU complex slice 和本轮性能参数 | 作为 follow-up，不重复提交已合入代码 |
| upstream #360/#363/#364 | 同一 benchmark 与 GCU mask/内存统计 | 上游在本分支准备期间合入 | 已变基到 `7298bfbd`，保留两侧功能 |

## 根因

- Python wheel 的 `torch/version.py` 是构建时常量，换入 PPU libtorch 不会自动更新它；可靠信息应从已加载的 `torch._C._cuda_getCompiledVersion()` 获取。
- PPU 当前 FlagGems 路由对 complex slice 和 `_unsafe_view` 语义不完整，这是路由能力边界，不应在模型层隐藏。
- Qwen-Image-2.1 编码后仍携带全 1 mask；数学上是 no-op，但会改变 attention kernel 选择。

## 解决方法与设计审查

- 在 PPU 初始化边界增加 `restore_ppu_cuda_version()`，仅当 PPU build、当前元数据为空且 CUDA runtime 真实可用时从 C++ runtime 恢复版本；vendor torch 的已有值保持不变，无 runtime 时显式报错。
- 在可重生的 PPU backend config 生成器中将 `_unsafe_view` 和 `slice.Tensor` 路由到 CUDA boxing，避免模型名或机器特例散落到公共执行代码。
- 手工流程允许已安装的兼容 Diffusers，仍保留显式 source checkout fallback；增加 CLI cache/autoload/run/log 参数、至少两次实测调用和不逐步同步的去噪计时。
- `--omit-all-valid-prompt-mask` 为显式 opt-in；仅当实际 mask 全有效时替换为 `None`，有 padding 时原样传递。它可改变 bf16 舍入，不作为默认部署设置。
- 影响矩阵：PPU runtime 初始化和 PPU 路由会变；手工 Qwen-Image-2.1 工具为跨平台路径，新优化默认关闭。未修改 Diffusers、FlagGems、vendor torch 或权重。
- 原综合分支：`fix/qwen-image-21-ppu-followups`，HEAD `a3e6031e2c29fe1c583921e40360a0e390d9589d`。发布后按维护边界拆为 `fix/ppu-cpu-wheel-cuda-metadata`（当前 HEAD `d00266f4c24b71d4cf5f33a945609386feff7ebd`）和 `perf/qwen-image-21-elide-valid-prompt-mask`（`985959f42fcc1bbced3e06599e40add60695358d`）。

## 验证结果

- `python3 scripts/codegen/gen_vendor_confs.py --check`：通过。
- device-free 聚焦回归：20 passed。
- PPU `synchronizeDevice` 设备回归：2 passed。
- `bash -n tests/manual/qwen_image_21/run.sh`、Python `compileall` 和 `git diff --check origin/main...HEAD`：通过。
- Ruff 未在容器中安装，未为此修改运行环境；交由上游 CI 补充。
- 首轮上游 CI 检出 `sweep.py` 重复 `placement` 键和 4 个 Ruff 格式差异；commit `a3e6031e2c29fe1c583921e40360a0e390d9589d` 修复后，Ruff 0.15.12 的 check/format 均通过，上游 lint job 已成功。
- 历史同环境已完成 Qwen-Image-2.1 eager 和 mask A/B；但本次 rebase 后未重跑完整模型，因此不将新 profile 的 formal `model-eager` 标为已通过。

## 限制与下一步

- 上游 issue：[flagos-ai/Torch-FL#368](https://github.com/flagos-ai/Torch-FL/issues/368)。综合 PR [#369](https://github.com/flagos-ai/Torch-FL/pull/369) 已关闭并由两个独立 PR 替代：[CPU wheel/bitsandbytes #370](https://github.com/flagos-ai/Torch-FL/pull/370) 和 [Qwen prompt-mask #371](https://github.com/flagos-ai/Torch-FL/pull/371)。
- #370 仅含 4 个 runtime/单测/PPU CI 配置文件，11 项聚焦单测通过；#371 仅含 6 个 Qwen 手工流程/单测文件，2 项聚焦单测通过。两者 Ruff 0.15.12 check/format、diff check 均通过；各自上游 lint、platform-agnostic 和平台发现检查已成功。
- #370 首轮 PPU 集成测试仍断言导入 `torch_fl` 后 `torch.version.cuda is None`，与修复后的 `13.0` 行为冲突；commit `d00266f4c24b71d4cf5f33a945609386feff7ebd` 已同步集成预期，新一轮 CI 已启动。
- 原综合 PR 中的 PPU 算子路由、benchmark 计时和其他手工流程改造未夹带进任一拆分 PR。
- formal model-eager 仍需在当前最终 commit 上重跑并绑定原生证据；本 experimental profile 不声称完整 acceptance 或 optimized。
- 知识库处理状态：`local-only`。
