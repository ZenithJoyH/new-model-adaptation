# MiniMax-M3 / PPU 适配问题索引

本目录只保存 Markdown 问题台账。Plugin 必要产品实现与可维护回归测试保留在容器内 `/workspace/vllm-plugin-FL`；一次性诊断代码和原始输出分别保留在批准工作根的 `02-issues/`、`05-tmp/` 与 `04-runs/`，不复制到本目录。

## 问题列表

| ID | 问题 | 状态 | 首次出现 | 根因 | 解决方法 | 验证结果 | 记录 |
|---|---|---|---|---|---|---|---|
| 001 | MiniMax-M3 fused QK-norm/RoPE/cache-insert op 缺失 | resolved | 2026-09-15 | PPU 原生扩展缺少该 symbol；FlagGems 无兼容实现 | 缺失时 patch vLLM Python 包装函数，经 Plugin FlagOS dispatch 调用通用 Triton fallback | focused、dense 重复、整模 eager/graph 通过 | [001-missing-fused-minimax-m3-preprocess.md](001-missing-fused-minimax-m3-preprocess.md) |
| 002 | prefill index top-k 在 PPU Triton 编译失败 | resolved | 2026-09-15 | FlagTree 默认自动 block-size 调整使真实 bitonic kernel 触发错误 constexpr 断言 | 删除 Plugin monkey patch；模型进程设置 `FLAGTREE_AABS=0`，使用 vLLM 原生 kernel | 最小复现、focused 4/4、65K graph 6/6、真实 sparse-prefill HTTP 200；请求后服务存活；上游 [FlagTree#1181](https://github.com/flagos-ai/FlagTree/issues/1181) | [002-prefill-index-topk-compile-assert.md](002-prefill-index-topk-compile-assert.md) |
| 003 | T-Head FA3 backend 导入引用不存在的符号 | resolved | 2026-09-15 | Plugin 导入了当前 vLLM 已移除且从未使用的 `flash_attn_supports_fp8` | 删除单个未使用导入 | backend class import 通过 | [003-thead-fa3-unused-import.md](003-thead-fa3-unused-import.md) |
| 004 | 多模态部分 RoPE 在 OOT fallback 中广播失败 | resolved | 2026-09-15 | OOT native 假定旋转维度等于完整 head width，无法处理视觉塔 78/80 partial RoPE | Plugin 注册 partial-aware `ApplyRotaryEmbFL` | partial/full/graph 3/3、整模 eager/graph warmup 通过 | [004-partial-vision-rope-oot.md](004-partial-vision-rope-oot.md) |
| 005 | MiniMax-M3 MoE 路由缺少 `_moe_C.topk_sigmoid` | resolved | 2026-09-15 | Plugin bias router 仍直达当前 PPU 环境不存在的 native op | T-Head-only 单 group `grouped_topk` 等价映射 | 聚焦/联合/整模 eager/graph 通过 | [005-missing-topk-sigmoid.md](005-missing-topk-sigmoid.md) |
| 006 | Plugin modular MoE 不支持 `SWIGLUOAI_UNINTERLEAVE` | resolved | 2026-09-15 | Plugin activation helper 落后于当前 vLLM enum，且调用处丢弃 clamp/alpha/beta | packed-layout Triton 激活与参数透传 | focused 3/3、联合 13/13、整模 eager/graph 通过 | [006-swigluoai-uninterleave.md](006-swigluoai-uninterleave.md) |
| 007 | 可选 MiniMax 工具解析配置依赖未构建的 Rust 扩展 | resolved | 2026-09-15 | graph 启动中开启 auto tool parser，当前镜像无 `vllm._rust_tool_parser` | 移除三个非基础适配必需的可选参数 | run1 HTTP 500 负对照；run2 graph 6/6 与 changed-input 2/2 通过 | [007-optional-tool-parser-extension.md](007-optional-tool-parser-extension.md) |
| 008 | MiniMax 缺失算子实现归属/dispatch kind 不一致 | resolved | 2026-09-15 | 初次 bring-up 将可移植 kernel/ABI bridge 放在错误层级，且未复用最新 FlagGems-vllm 能力 | 缺失 kernel 迁入 `default.flagos`；vLLM 专属包装函数由 `patches` 条件接管 | focused 15/15；其余 dispatch 277/277；`native_schema=False`、`python_patch=True` | [008-flaggems-dispatch-reclassification.md](008-flaggems-dispatch-reclassification.md) |

状态使用：`open`、`investigating`、`mitigated`、`resolved` 或 `blocked`。

## 适配阶段结论

- TP16 eager run5 已完成 59/59 权重加载、dummy profile、KV cache/warmup、health/model identity 与固定问答；证据在 `/mnt/nfs/users/jinghao/minimaxM3/04-runs/eager-service-run5/`。
- TP16 graph run2 已完成 `FULL_DECODE_ONLY` capture sizes `1,2,4,8,16,32`，6/6 捕获与北京/巴黎 changed-input 2/2 通过；证据在 `/mnt/nfs/users/jinghao/minimaxM3/04-runs/graph-service-run2/`。
- Plugin 基线为 `29712e42dba86680577aef9f2f6b5b7f04050a89`。2026-09-16 经用户授权，`support-minimax-m3` 最终压缩为单一提交 `7e412e6f8b6d8a5e4350e0237e1a8548dfaf7b94`（tree `6c8696f227fd049aaa3686aef0d73143514851e1`），父提交直接为该基线。该提交精确包含最终 19 个文件、1430 行新增/13 行删除，`git diff HEAD^ HEAD --check` 通过；四个 `.orig` 备份未纳入提交。
- FlagGems/FlagGems-vllm 已分别同步至 `3c6f7537`/`bfe7ac06`：MiniMax fused preprocess 与 packed SwiGLUOAI kernel 位于 `flaggems/impl`，partial ApplyRotaryEmb 复用 FlagGems-vllm/FlagGems rotary，sigmoid router 复用 grouped-topk；vLLM 缺失 fused-op 时由 `patches/minimax_m3.py` 条件替换 Python 包装函数，不合成 `_C` ABI。原 PPU 专属 index-topk monkey patch 已从 editable source 删除，改由启动环境 `FLAGTREE_AABS=0` 使原生 vLLM kernel 正常编译；删除后的聚焦测试为 4/4。
- 用户要求把原 `aee54f3` 与 `4e67e87` 两笔提交合并；已使用远端旧 tip `4e67e87` 的精确 `force-with-lease` 更新为 `7e412e6`。新提交的 tree 与合并前最终 tree 完全一致，容器、本机临时仓库和 GitHub ref 均已一致核验，因此仅 Git 历史变化，产品代码字节不变。
- index-topk 无 patch 且使用默认 AABS 的负对照在首个真实 sparse-prefill 请求精确复现上游 `tl.static_assert` 编译失败并导致服务退出。2026-09-16 单变量验证确认 `FLAGTREE_AABS=0` 可使同一原生 kernel 通过；当前 PID `2153450` 使用 TP16 graph、`max_model_len=65536`、prefix caching enabled，完成 59/59 加载、6/6 capture、health 200 和真实 sparse-prefill HTTP 200，请求后 API/EngineCore 存活。证据位于 `04-runs/index-topk-aabs0-no-patch-graph-65k-20260916-01/`。
- 根目录最终启动脚本为 host/container `/mnt/nfs/users/jinghao/minimaxM3/start-model.sh`，32 行，SHA-256 `e65ba3a1b01d2d8196d9a754e8c3b4c82cbfa35c6d1dba683e05fa4ff63c7326`。它只保留已有 API/8013 占用保护、批准目录下的日志/缓存路径、`FLAGTREE_AABS=0`，以及 TP16、BF16、`max_model_len=65536`、prefix caching enabled 的 graph 启动命令；2026-09-16 已通过容器映射、语法、拒绝重复服务和 health 验证。

## 尚存范围与风险

- 基础功能适配已完成，但 formal sanity/accuracy/performance 必须按验收门禁独立完成，不能由两个 smoke 请求代替。
- 实际图像 API、MTP/speculative、1M context、FP8 KV cache 与 auto tool choice 不在本轮基础自回归完成声明。
- Plugin 容器工作树仍含本轮 patch 工具生成的四个未跟踪 `.orig` 备份；它们不进入 import、测试或 commit，在用户明确授权删除前保留。远端分支已创建并完成 SHA 校验。
- 服务实例 `ppu13-minimaxM3-7ffdd70d-boot-e0f88877-pid1551482-start219575444-cmd4735fa06` 曾完成 TP16 eager/graph、固定前十题 10/10 与全量 GPQA c64 177/198；该实例使用 index-topk patch，结果作为历史证据保留。当前 no-patch + AABS0 服务已通过功能请求，但 sanity/全量 GPQA 尚未重跑，不能把旧精度 receipt 绑定到新实例。
