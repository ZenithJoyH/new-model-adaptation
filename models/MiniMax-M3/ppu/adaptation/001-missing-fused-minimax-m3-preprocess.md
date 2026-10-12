# 001：MiniMax-M3 fused QK-norm/RoPE/cache-insert op 缺失

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-15
- 最后验证时间：2026-09-15
- 模型：`MiniMaxAI/MiniMax-M3`，本地权重 `/mnt/cpfs/models/MiniMax-M3`
- 平台与 Host 别名：T-Head PPU-ZW810E，`PPU-13`
- 容器名称与镜像：`minimaxM3`；`harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`
- Plugin / FlagGems / vLLM revision：Plugin `29712e42dba86680577aef9f2f6b5b7f04050a89`；FlagGems 同步后 `be05ef1db6758adca7a18de3bf529c18a6ac9a87`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：算子导入/注册探测；尚未启动模型服务

## 问题现象

- 错误签名或症状：加载 PPU PlatformFL 后，`torch.ops._C` 中不存在 `fused_minimax_m3_qknorm_rope_kv_insert`。
- 发生顺序：模型 registry/config 可识别 → PPU Plugin fallback schema 注册 → MiniMax-M3 专用 `_C` symbol 缺失。
- 影响范围：vLLM MiniMax-M3 dense 与 sparse attention 的共同预处理路径；整模型 forward 会在首个调用处失败。
- 精简证据及原始证据位置：环境分析第 4 节；后续回归原始输出固定写入 `/mnt/nfs/users/jinghao/minimaxM3/04-runs/001-fused-preprocess/`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| Plugin `patches/moe_sum.py` | vLLM 原生调用桥接 Plugin dispatch | MiniMax op 是有 alias/mutation schema 的多输出原地算子 | 中 | 复用 `CachedOp` 与 vendor registration，不复用函数签名 |
| FlagGems DeepSeek-V4 fused qnorm/RoPE/cache op | 都组合 norm、RoPE、cache 写入 | 头宽、张量打包、RoPE/KV 语义与缓存布局不同 | 高 | 判定不兼容，不作适配层强行复用 |

## 诊断与假设

已验证事实：容器内 `vllm_fl._C` 不存在；fallback `_C` schema 列表没有该算子的 PPU kernel；vLLM NVIDIA 分支直接调用该 symbol；同步后的 FlagGems 没有契约兼容实现。当前假设是：在 Plugin 的 T-Head vendor backend 实现等价 Triton kernel，并以精确 `_C` schema 桥接既有 vLLM 调用点，可同时覆盖 eager 与 CUDA-compatible graph capture。

已排除方向：修改只读 vLLM；把 DeepSeek-V4 fused op 当作同义算子；在模型名判断中散布 PPU 特例；用纯 Python token/head 循环作为正式实现。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | FlagGems revision | `4d9c3477548...` | `git pull --ff-only origin master` → `be05ef1db675...` | `/workspace/FlagGems` | clean fast-forward；仍无兼容 op | 缺口应由 Plugin 承担 |
| 2 | Plugin PPU op | symbol 缺失 | Plugin-owned Triton + vendor dispatch + `_C` bridge | Plugin actual diff；原始结果 `04-runs/001-fused-preprocess/` | dense/sparse/graph focused 通过 | ABI 与主要语义已覆盖 |
| 3 | norm/RoPE kernel 内部组织 | 单 kernel 偶发少量大偏差 | norm 与 64-dim RoPE 拆为同流两阶段 kernel | `04-runs/minimax-fused-dense-repeat*.log` | 原实现第 3 次复现失败；两阶段固定种子 20/20 | 判定 in-place peer-load/store 在 PPU 上不稳定，保留确定性两阶段实现 |

## 根因

- 已验证根因：当前 PPU 镜像的 Python-only Plugin 没有提供 vLLM MiniMax-M3 新增 custom-op ABI，FlagGems 也没有满足该模型 main/index paged-cache contract 的等价实现。
- 若未完全证实，当前假设与缺失证据：根因定位已完成；修复是否覆盖 PPU Triton 编译、数值和 graph alias 仍需测试。

## 解决方法或 Workaround

- 修改思路：保持 vLLM 原调用不变，在 Plugin 内注册精确 `_C` schema/PPU implementation；实现经 `CachedOp` 进入 `vendor.thead`，Triton 分别完成 Gemma per-head RMSNorm + partial NeoX RoPE、主 KV cache 写入和 index-K cache 写入。
- 选定层级/扩展点、职责依据和替代方案：模型语义仍归 vLLM；硬件能力归 Plugin T-Head backend。FlagGems 无兼容 op，直接改 vLLM 或使用不兼容算子均被排除。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：只在 `PPU_SDK` 环境注册且 dispatch 仅允许 `vendor:thead`；非 PPU 与有原生 `_C` 的环境保持旧行为。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：是；这是整模型共有硬阻塞并对应稳定 vLLM ABI，不是一次性诊断。
- Plugin 内必要实现或回归测试路径：`vllm_fl/dispatch/backends/vendor/thead/minimax_m3.py`、`vllm_fl/ops/minimax_m3.py`、T-Head registration/config 与 `tests/unit_tests/dispatch/test_thead_minimax_m3.py`。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：补丁暂存于 `05-tmp/minimax-m3-ppu-plugin.patch`，完成后可清理；不创建源码镜像。
- 分支与 revision/commit：`main`，基线 `29712e42dba86680577aef9f2f6b5b7f04050a89`；未 commit。
- 正式回归测试路径：同上；`04-runs/minimax-plugin-focused-final.log` 为 4/4 PASS，`04-runs/minimax-fused-dense-repeat-two-pass.log` 为 20/20 PASS。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：重复注册、dense/sparse、eager/graph、upstream prefill/decode index、sparse-attention prefill/decode、Thead FA3 import 与模型类解析均已通过；整模证据待补。
- workaround 的适用条件、默认策略/性能影响和退出条件：首轮只支持 FP16/BF16 与 `kv_cache_dtype=auto`；未验证 FP8 显式报错。FlagGems 或 Plugin 原生扩展提供完全兼容且更优实现后退出。
- 服务停启操作及核对结果：无服务停启。
- vLLM 未修改证明：应用前后 `/workspace/vllm` 均为 `ee0da84ab9e04ac7610e28580af62c365e898389` detached clean。

## FlagGems 证据

- 同步后的 revision 与检索证据：`be05ef1db6758adca7a18de3bf529c18a6ac9a87`，`master...origin/master`、clean。
- 已有算子及接入方式，或缺失结论：没有 MiniMax-M3 同名 op；DeepSeek-V4 fused op 与 generic sparse attention 均不满足精确契约。
- 如为 FlagGems 缺陷，工作根 `07-bugs/<issue>/`、容器对应路径与复现命令：不判为 FlagGems 缺陷；本问题是 Plugin/vLLM ABI 覆盖缺口。
- 如确因工具要求使用 `/bug`，记录指向同一目录的已批准映射或明确例外（不得复制已有用例）：不需要 `/bug`。

## 验证结果

- 最小回归：Plugin focused 4/4 通过。
- `eager`：dense/sparse BF16 对齐 FP32 reference；V 未改；main/index cache 与实际 kernel 输出 bit-exact；TP16 run5 整模初始化和最小推理通过。
- `graph` capture/replay：dense 预处理 changed-input replay 通过；TP16 graph run2 6/6 捕获及两个 changed-input API 通过。
- 数值、dtype、shape、layout、边界条件：已覆盖 dense/sparse、BF16、padding slot、独立 main/index mapping、外部 Q/index-Q buffer、主/索引缓存；FP8 未覆盖并显式拒绝。
- 最终结论与通过标准：算子级和整模 eager/graph 均通过，状态转 `resolved`。

## 限制与下一步

- 尚存限制：FP8 KV/index cache 不在本轮已验证 PPU 能力；MTP/speculative 和 1M context 未覆盖。
- 后续动作：在共享模型/其他平台合入前扩展回归；本轮基础路径不再保留 workaround 退出条件。
- 设计审查结论及 PR 范围的影响：初始设计符合 Plugin vendor ownership；最终审查需基于实际 diff 与回归结果刷新。

## 经验沉淀

- 是否可跨模型或平台复用：ABI bridge/dispatch 模式可复用；算子语义只适用于 MiniMax-M3 contract。
- 知识库处理状态：`local-only`
- 候选知识库条目：验证完成前不提升。

## 2026-09-15 FlagGems dispatch 重分类

issue 008 的二次职责审查取代了本记录中的 T-Head ownership 结论。同步到 FlagGems
`3c6f7537` 和 FlagGems-vllm `bfe7ac06` 后仍不存在满足 MiniMax-M3 精确 packed/cache
contract 的现成算子，因此 Triton kernel 仍必须由 Plugin 提供；但它不包含 PPU 专属语义，
已迁入 `vllm_fl/dispatch/backends/flaggems/impl/minimax_m3.py` 并注册为
`default.flagos`。最终设计不再合成 `_C` schema：
`vllm_fl/patches/minimax_m3.py` 仅在原生 symbol 缺失时替换
`vllm._custom_ops` 中的 MiniMax 专属包装函数，并通过 `CachedOp` 进入 dispatch；原生
symbol 存在的平台完全保留 vLLM 原路径。PPU 观测为 `native_schema=False`、
`python_patch=True`，focused/graph 与共享 dispatch 回归通过；其他平台仅证明 dispatch
设计可达，尚无实机验证。详见 [008](008-flaggems-dispatch-reclassification.md)。
