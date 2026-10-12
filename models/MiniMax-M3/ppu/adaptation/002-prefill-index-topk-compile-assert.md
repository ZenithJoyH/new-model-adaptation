# 002：prefill index top-k 在 PPU Triton 编译失败

## 元数据

- 状态：`resolved`
- 首次/最后验证时间：2026-09-15 / 2026-09-16
- 模型/平台：MiniMax-M3，T-Head PPU-ZW810E，Host `PPU-13`
- revisions：Plugin `7e412e6f8b6d8a5e4350e0237e1a8548dfaf7b94`（tree `6c8696f227fd049aaa3686aef0d73143514851e1`）；FlagGems `be05ef1db6758adca7a18de3bf529c18a6ac9a87`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`

## 问题现象与根因

上游 `test_prefill_index_topk_correctness` 的 score 阶段可运行，top-k 阶段在 PPU Triton 编译期于 `tl.static_assert(BLOCK_SIZE_K > BLOCK_SIZE_T)` 失败。模型配置 `topk=16`，合法候选 `BLOCK_SIZE_K` 最小为 64，逻辑不变量成立；decode 的另一套 top-k kernel 原样通过。原始失败为 `/mnt/nfs/users/jinghao/minimaxM3/04-runs/minimax-index-prefill-direct.log`。

已验证触发条件位于 PPU Triton 3.6 的自动 block-size 调整链路：默认 `FLAGTREE_AABS=1` 时，真实 bitonic top-k kernel 在 autotune/heuristic constexpr 组合中触发错误断言；同一原生 vLLM kernel 在 `FLAGTREE_AABS=0` 时编译并执行成功。它不是输入 top-k 超界或 score 错误。

## 解决方法与边界

- 当前采用运行时 workaround：模型进程启动前显式 `export FLAGTREE_AABS=0`，保留 vLLM 原生 `minimax_m3_index_topk`，不再安装 Plugin monkey patch；vLLM checkout 不修改。
- Plugin 已从 `vllm_fl/__init__.py` 删除自动安装调用，删除 `vllm_fl/patches/minimax_m3_thead.py` 及其 patch 专用测试；最终内容包含在单一适配提交 `7e412e6`，并已推送到 `ZenithJoyH/vllm-plugin-FL: support-minimax-m3`。
- `FLAGTREE_AABS=0` 会关闭本进程中 PPU Triton 的自动 block-size 调整，属于平台运行时 workaround，不是 FlagTree frontend 的根因修复；退出条件是上游 issue #1181 修复并在同一整模 graph 路径复验通过。
- prefill wrapper 之外的 score、decode、sparse attention 均保持 vLLM 原实现；FlagGems 未找到满足 MiniMax per-token block score/top-k contract 的等价算子。

## 验证

- 原始失败 reproducer 在默认环境下稳定失败；在 `FLAGTREE_AABS=0` 下输出 `PASS: shape=(2, 7, 6)`，日志 `/mnt/nfs/users/jinghao/minimaxM3/04-runs/index-topk-aabs0-repro-20260916-01/repro.log`，SHA-256 `5d4bdfce60519f113703d52ab41b755bd17d72b1f8a8e4a51551678ec3e2da96`。
- 删除 patch 后，标准插件加载确认原生函数无 `_vllm_fl_thead_patch` 标记；相同 reproducer 通过，聚焦 dispatch 测试 `4 passed`。证据 `/mnt/nfs/users/jinghao/minimaxM3/04-runs/index-topk-aabs0-no-patch-validation-20260916-01/validation.txt`，SHA-256 `01d7d6aa5957b9d872fb16b1c558e5966f7bb5954c7252733c04033817960a01`。
- decode 原路径：`04-runs/minimax-index-decode-direct.log`，PASS。
- sparse attention NHD prefill/decode：`04-runs/minimax-sparse-prefill.log` 与 `minimax-sparse-decode.log`，PASS。
- 整模 graph：TP16、BF16、`max_model_len=65536`、prefix caching enabled、6/6 graph capture；真实 sparse-prefill 请求 HTTP 200，回答“北京”，请求后 API/EngineCore 存活且日志无原静态断言。运行目录 `/mnt/nfs/users/jinghao/minimaxM3/04-runs/index-topk-aabs0-no-patch-graph-65k-20260916-01/`。
- 限制：本轮未在 no-patch + AABS0 配置上重跑全量 GPQA；FP8 indexer 非本轮默认 BF16 路径。

## 经验沉淀

- 知识库处理状态：`local-only`；仅一个模型/PPU Triton revision 验证，不提升为通用结论。

## 上游 issue 与最小复现

- 上游 issue：[flagos-ai/FlagTree#1181](https://github.com/flagos-ai/FlagTree/issues/1181)，参考同类 vendor-backend 有效 Triton 编译失败问题 #1179 的结构提交。
- 去重：提交前以 `index_topk/static_assert/BLOCK_SIZE_K/BLOCK_SIZE_T`、`CompileTimeAssertionFailure ppu` 和 `MiniMax-M3` 检索 FlagTree open/closed issues，未发现重复项。
- 无模型权重 reproducer：`/mnt/nfs/users/jinghao/minimaxM3/07-bugs/index-topk-static-assert/repro.py`，SHA-256 `feb248ff36f6137f4980ee1490beafd2879911495eac9194740abcd05f1ebfc0`。
- reproducer 日志：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/index-topk-static-assert-repro-20260916/repro.log`，SHA-256 `46b9e9d1a65b9b840cfd23773c08c33c5309444ff49487e5ecb51de378978922`；返回码 1，并精确命中 `CompileTimeAssertionFailure` 与断言行。
- 收敛结果：只含同一 `autotune + heuristics + static_assert` 的标量 kernel 能通过；调用真实 vLLM bitonic top-k kernel 的小张量脚本稳定失败，因此 issue 将范围限定为该 kernel 结构下的 PPU Triton frontend constexpr/static-assert 处理，而未泛化为所有比较断言均失败。
- issue 由 `ZenithJoyH` 创建；当前账号无上游仓库 `AddLabelsToLabelable` 权限，`bug/ppu/triton_v3.6.x/P1/flagos2.2-rc2` 标签留待维护者 triage。

## 2026-09-15 无 patch 负对照

- 唯一变量：从 `register_model()` 移除 `patch_minimax_m3_index_topk()` 安装调用；其他 MiniMax-M3、FlagGems dispatch、TP16 graph 参数不变，补丁实现文件暂时保留但不会自动加载。
- 安装核对：标准 vLLM general-plugin loader 后观测 `index_topk_thead_patch=False`。
- 启动参数：TP16、BF16、block size 128、`max_model_len=50000`、prefix caching enabled、`FULL_DECODE_ONLY` graph capture sizes `1,2,4,8,16,32`。
- 服务操作：精确停止本任务旧服务 PID `374998`；容器未停止或重启；新诊断服务 PID `915542`。
- 日志：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/graph-no-thead-index-topk-patch-20260915/server.log`；启动配置同目录 `launch-command.txt`。
- 负对照结果：服务完成启动和 warmup 后，首个真实 sparse-prefill 请求在 TP3 精确复现 `triton.compiler.errors.CompileTimeAssertionFailure`，失败点为上游 `tl.static_assert(BLOCK_SIZE_K > BLOCK_SIZE_T)`；API 服务随后退出。原始日志保留于上述 `server.log`。
- 恢复结果：重新启用 `patch_minimax_m3_index_topk()` 自动安装，标准加载观测 `index_topk_thead_patch=True`；`test_prefill_index_topk_matches_reference` 1/1 通过。新 TP16 graph 服务 PID `1129978` 使用 `max_model_len=65536`，完成 6/6 graph capture、warmup 和 health 200；日志为 `/mnt/nfs/users/jinghao/minimaxM3/04-runs/graph-restored-index-topk-patch-65k-20260915/server.log`。
- 当时结论：默认环境下，无 patch 的真实请求失败与恢复后的 focused/service 对照确认补丁可以规避问题。该结论已被下面的 AABS 单变量实验收窄：补丁并非唯一解。

## 2026-09-16 AABS 单变量对照与当前结论

- FlagTree 代码核对：`/usr/local/lib/python3.12/site-packages/triton/knobs.py` 将 `adjust_block_size` 绑定到 `FLAGTREE_AABS`，默认值为 true；autotuner 在编译前据此调用 `auto_adjust_block_sizes`。
- 最小对照：完全相同的原生 vLLM reproducer，默认环境命中 `CompileTimeAssertionFailure`；仅增加 `FLAGTREE_AABS=0` 后通过。随后删除 Plugin index-topk patch，加载检查、相同 reproducer 与 4 项聚焦测试全部通过。
- 服务切换：精确停止旧 API PID `1551482`，未停止或重启容器；新 API PID `2153450`、EngineCore PID `2154046`。启动脚本为 `/mnt/nfs/users/jinghao/minimaxM3/02-issues/index-topk-aabs0-no-patch/start.sh`，显式导出 `FLAGTREE_AABS=0`。
- 服务参数：TP16、BF16、block size 128、`max_model_len=65536`、prefix caching enabled、`FULL_DECODE_ONLY` graph capture sizes `1,2,4,8,16,32`。
- 整模结果：59/59 权重加载、6/6 graph capture、health 200；复用 SHA-256 `e2ab3f9004ff5aa2d14aff305790b61715a66d960da6b89cee2ddca94b5a8f2d` 的真实请求，HTTP 200，回答“北京”。响应 SHA-256 `83ea7b971f15e5074b05b3d27c96027a320f47503cee65eb69e207d526d3cd4b`；请求后 health 200，API/EngineCore 均存活，日志无 `CompileTimeAssertionFailure` 或 `BLOCK_SIZE_K > BLOCK_SIZE_T`。
- 当前判定：对本容器、当前 revisions 与 BF16 graph 配置，`FLAGTREE_AABS=0` 足以取代 Plugin index-topk patch。问题在适配层标记为 `resolved`，但上游 #1181 仍需 FlagTree 根因修复；AABS0 的全局性能影响和 no-patch 配置的全量 GPQA 尚未重新评估。
- 最终启动脚本：host/container `/mnt/nfs/users/jinghao/minimaxM3/start-model.sh`，32 行，SHA-256 `e65ba3a1b01d2d8196d9a754e8c3b4c82cbfa35c6d1dba683e05fa4ff63c7326`。脚本只保留重复服务/端口保护、批准目录下的日志与缓存、`FLAGTREE_AABS=0` 和已验证的模型启动命令；2026-09-16 验证通过。
