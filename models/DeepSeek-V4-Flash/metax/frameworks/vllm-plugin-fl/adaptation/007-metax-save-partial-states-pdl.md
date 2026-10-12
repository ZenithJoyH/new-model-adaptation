# 007：MetaX partial-state Triton launch_pdl 兼容

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-21
- 最后验证时间：2026-09-22
- 模型：DeepSeek-V4-Flash INT8
- 平台与 Host 别名：MetaX C550 x8，`mx-59`
- 容器名称与镜像：`deepseek`，见 `framework.yml`
- Plugin / FlagGems-vllm / vLLM revision：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `c0ffa628e945dc6b51af466d4f1a9b81df9ac4b8` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：eager，TP8+EP，KV cache profile dummy run

## 问题现象

- 错误签名：`KeyError: 'Keyword argument launch_pdl was specified but unrecognised'`。
- 发生顺序：109/109 权重加载成功后，KV cache profile 进入 Plugin INT8 indexer 压缩；Plugin 调用只读 vLLM `save_partial_states` 并为 MetaX 传入 `launch_pdl=False`，MetaX Triton 拒绝未知 launch keyword；其后的 `ncclCommAbort` 缺失仅是失败清理噪声。
- 影响范围：Plugin 的 DeepSeek-V4 INT8 indexer partial-state 写入；尚未到 sparse MLA decode。
- 原始证据：`/public-flash/jinghao/deepseekV4/04-runs/pr427-eager-tp8-20260921-21-decode-mla-fix/service.log`；停止记录同目录 `shutdown.txt`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| Plugin 已有 Hopper FP8 `launch_pdl` 兼容处理 | 都是 launch keyword 的平台能力差异 | 本次调用来自 vLLM partial-state kernel，且当前代码只排除 ROCm/XPU | 中 | 复用“仅能力支持平台传参”的原则，不复用具体算子补丁 |

## 诊断与假设

- 已验证：当前 Plugin 逻辑对非 ROCm/XPU 一律传 `launch_pdl=False`；MetaX 的 Triton JIT 不识别该关键字。
- 假设：该提示仅是 NVIDIA PDL launch 控制，Plugin 应仅在 `vendor_name == "nvidia"` 时传入，其他厂商传空字典。
- 已排除：权重映射、分布式初始化和模型加载失败；它们已在本轮先后完成。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 21 | decode bridge 与 MODEL1 修复 | run20 外部资源阻塞 | 完整 eager 启动 | `04-runs/pr427-eager-tp8-20260921-21-decode-mla-fix/` | 权重加载完成，profile 在 launch_pdl 失败 | 形成当前独立问题 |
| 22—24 | PDL vendor 能力守卫 | 非 NVIDIA 仍传 `launch_pdl` | 仅 NVIDIA 传参 | Plugin INT8 indexer 及聚焦测试 | 原错误消失，整模继续进入后续 compressor / GEMM 路径 | 根因和修复层级得到验证 |

## 根因

- 已验证根因：Plugin 用设备类别排除法选择 PDL 参数，误把 CUDA-like 的 MetaX 当作支持 NVIDIA PDL launch keyword 的平台。
- 完整 profile 已越过该调用点；后续失败签名与 PDL 无关。

## 解决方法或 Workaround

- 修改思路：在 Plugin INT8 indexer 模块集中封装 PDL launch kwargs，仅 NVIDIA 返回 `{"launch_pdl": False}`，MetaX/ROCm/XPU/其他 vendor 返回空字典。
- 层级依据：平台参数选择属于 Plugin vendor compatibility；vLLM 与 Triton runtime 保持只读。
- 影响：仅 DeepSeek-V4 INT8 indexer partial-state 调用；NVIDIA 保持旧参数，其他平台不再接收不支持的关键字；不增加计算 fallback。
- 计划源码/测试：`vllm_fl/ops/deepseek_v4_int8_indexer.py`、`tests/unit_tests/ops/test_deepseek_v4_int8_indexer.py`。
- vLLM 未修改证明：验证后记录 `/workspace/vllm` clean 状态。

## FlagGems 证据

- 此错误在调用 FlagGems sparse MLA 前发生，不是 FlagGems 算子缺陷；本轮不扩大 FlagGems 修改范围。

## 验证结果

- 最小回归：相关 Plugin 单测最终汇总 `72 passed, 3 skipped`，证据为 `04-runs/pr427-related-unit-after-graph-correctness-20260922/pytest-output.txt`。
- `eager`：run26 完成真实 OpenAI 请求并精确返回 `OK`，证明完整 profile 已越过 PDL 路径。
- `graph`：PDL 错误未复现；图模式的独立问题和最终配置见 009。

## 限制与下一步

- 下一步：上游评审时保留 vendor 能力守卫及聚焦回归，避免以 CUDA-like 平台类别代替 NVIDIA 能力判断。
- 设计审查：若守卫未命中，保留 Triton 默认 launch 行为；不改 kernel 数学、dtype、shape 或 layout。

## 经验沉淀

- 是否可跨模型或平台复用：可复用“CUDA-like 不等于 NVIDIA launch capability”的诊断原则。
- 知识库处理状态：`local-only`
- 候选知识库条目：out-of-tree CUDA-like 平台的 Triton launch keyword 能力守卫。
