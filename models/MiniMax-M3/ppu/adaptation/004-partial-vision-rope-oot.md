# 004：多模态部分 RoPE 在 OOT fallback 中广播失败

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-15
- 最后验证时间：2026-09-15
- 模型：`MiniMaxAI/MiniMax-M3`，本地权重 `/mnt/cpfs/models/MiniMax-M3`
- 平台与 Host 别名：T-Head PPU-ZW810E，`PPU-13`
- 容器名称与镜像：`minimaxM3`；`harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`
- Plugin / FlagGems / vLLM revision：Plugin 基线 `29712e42dba86680577aef9f2f6b5b7f04050a89`；FlagGems `be05ef1db6758adca7a18de3bf529c18a6ac9a87`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：TP16 eager 服务启动期间的多模态 dummy profile，视频 token 数 `199680`

## 问题现象

- 错误签名或症状：权重 59/59 加载完成后，worker 在 `ApplyRotaryEmb.forward_native` 的乘法处广播失败；输入半头宽为 40，cos/sin 最后一维为 39。
- 发生顺序：权重加载完成 → device-side postprocessing → multimodal dummy video profile → vision tower partial RoPE → FlagGems `mul` 广播报错 → engine workers 自然退出。
- 影响范围：MiniMax-M3 视觉塔的图像/视频 token profile 和实际多模态推理；文本模型虽已加载，但服务无法完成内存探测并 ready。
- 精简证据及原始证据位置：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/eager-service-run2/server.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| vLLM `ApplyRotaryEmb.forward_cuda` | 明确支持 `rotary_dim < head_dim`，只旋转前缀并保留尾部 | PPU 走 OOT fallback，未复用 CUDA 实现 | 高 | 以其接口语义作为 Plugin OOT 修复依据 |
| Plugin `RotaryEmbeddingFL` | 已处理 partial RoPE 的 query/key 尾部保留 | 接口是 position/cache 驱动，不是直接 cos/sin 的 vision op | 高 | 复用职责层级，不强行复用不同签名 |

## 诊断与假设

已验证模型视觉头宽为 80，而三轴 RoPE 合并后只覆盖 78 维（cos/sin 各 39 维）。上游 CUDA 路径按 `rotary_dim` 切分输入；当前 OOT native 路径却把完整 80 维等分为 40+40 后与 39 维 cos/sin 相乘。FlagGems 只是在执行该不兼容广播，不是根因。

已排除：增补一维伪造 cos/sin、修改只读 vLLM、在 MiniMax 模型名处特判、禁用多模态 profile。这些做法会改变旋转语义、越过源码边界或隐藏实际功能缺口。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 整模路径 | 原生 OOT `forward_native` | TP16 eager run2 | `04-runs/eager-service-run2/server.log` | 80/78 广播失败 | 复现并锁定 vision partial-RoPE contract gap |
| 2 | Plugin `ApplyRotaryEmb` OOT | 完整 head 等分 | 只旋转 `2 * cos.shape[-1]` 前缀，尾部原样保留 | `04-runs/partial-vision-rope-focused.log` | partial/full/graph 3/3 通过 | 修复满足数值与 capture/replay 契约 |
| 3 | 组合回归 | 独立测试 | fused preprocess、index top-k、partial RoPE 同跑 | `04-runs/minimax-plugin-focused-final-v2.log` | 7/7 通过 | 未破坏已有 MiniMax-M3 Plugin 路径 |

## 根因

- 已验证根因：当前 vLLM revision 的 `ApplyRotaryEmb` CUDA 实现支持 partial RoPE，但通用 OOT fallback 假定旋转维度等于完整 head width；MiniMax-M3 视觉塔的 78/80 contract 首次触发该缺口。
- 若未完全证实，当前假设与缺失证据：算子根因已证实；整模 eager/graph 仍需证明修复已覆盖真实 dummy profile 和服务路径。

## 解决方法或 Workaround

- 修改思路：新增 `ApplyRotaryEmbFL`，由 cos/sin 宽度计算旋转前缀，在 FP32 中完成 NeoX/GPT-J 两种布局运算，并原样拼回未旋转尾部。
- 选定层级/扩展点、职责依据和替代方案：通过 Plugin 既有 `CustomOp.register_oot` 注册通用 `ApplyRotaryEmb` OOT 实现；硬件 fallback 能力属于 Plugin，而模型结构继续由 vLLM 定义。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：只替换启用 Plugin OOT 的调用；full-RoPE 作为回归用例，其他平台或未启用 OOT 时维持上游路径。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：是；它补齐上游已定义的 partial-RoPE 公共语义并修复整模硬阻塞。
- Plugin 内必要实现或回归测试路径：`vllm_fl/ops/rotary_embedding.py`、`vllm_fl/ops/custom_ops.py`、`tests/unit_tests/ops/test_apply_rotary_emb_thead.py`。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：补丁位于 `05-tmp/004-partial-vision-rope*.patch`；最终收尾时清理或登记保留。
- 分支与 revision/commit：`main`，基线 `29712e42dba86680577aef9f2f6b5b7f04050a89`；未 commit。
- 正式回归测试路径：`04-runs/partial-vision-rope-focused.log` 与 `04-runs/minimax-plugin-focused-final-v2.log`。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：78/80 partial、128/128 full、graph replay 通过；与 fused preprocess/index top-k 组合回归 7/7。
- workaround 的适用条件、默认策略/性能影响和退出条件：当前实现为 correctness fallback；上游 OOT 原生提供同等 partial 语义或 vendor 提供更优实现时退出。性能影响待整模性能验收量化。
- 服务停启操作及核对结果：run2 进程因异常自然退出；未停止或重启容器。
- vLLM 未修改证明：回归后仍为 `ee0da84ab9e04ac7610e28580af62c365e898389`，工作树 clean。

## FlagGems 证据

- 同步后的 revision 与检索证据：`be05ef1db6758adca7a18de3bf529c18a6ac9a87`。
- 已有算子及接入方式，或缺失结论：广播由 FlagGems `mul` 执行，但输入 shape 已由错误的 OOT 切分产生；不判定为 FlagGems 缺陷。
- 如为 FlagGems 缺陷，工作根 `07-bugs/<issue>/`、容器对应路径与复现命令：不适用。
- 如确因工具要求使用 `/bug`，记录指向同一目录的已批准映射或明确例外（不得复制已有用例）：不需要 `/bug`。

## 验证结果

- 最小回归：部分旋转、全量旋转、图回放 3/3 通过。
- `eager`：算子级通过；run5 整模 multimodal dummy warmup 及文本 API 通过。
- `graph` capture/replay：算子级 changed-input replay 通过；run2 整模 6/6 graph 捕获、multimodal warmup 和两个 changed-input API 通过。
- 数值、dtype、shape、layout、边界条件：BF16 输入、FP32 cos/sin；78/80 partial 和 128/128 full；NeoX layout；未旋转尾部 bit-exact。
- 最终结论与通过标准：整模 eager 与 graph 真实 profile/warmup 均通过，转 `resolved`。

## 限制与下一步

- 尚存限制：GPT-J layout 由实现支持但本轮未做 PPU 专项测试；实际图像请求尚未进入验收。
- 后续动作：若需声称完整视觉能力，须另行冻结图像输入和期望结果。
- 设计审查结论及 PR 范围的影响：新增一个公共 OOT op 与一个 focused test；最终审查必须检查共享模型调用方与默认注册边界。

## 经验沉淀

- 是否可跨模型或平台复用：可复用于所有 head width 大于 rotary width 的 OOT `ApplyRotaryEmb` 调用，但当前只在 PPU/MiniMax-M3 环境验证。
- 知识库处理状态：`local-only`
- 候选知识库条目：完整整模 eager/graph 与至少一个额外 partial-RoPE 模型验证前不提升。

## 2026-09-15 FlagGems 链路复核

`ApplyRotaryEmbFL` 本身仍必须保留：PPU 使用 OOT，而当前 vLLM native 实现对
80 维 head/78 维 rotary 仍会把完整 head 等分为 40+40，与 cos/sin 的 39 维广播失败。
本轮不再在该 OOT 类中维护一套 PyTorch 旋转计算；它只通过
`CachedOp("apply_rotary_emb")` 适配 standalone/partial contract，实际计算优先复用
FlagGems-vllm `apply_rotary_pos_emb`，缺少该包时复用 FlagGems 的同接口实现。PPU 的
partial/full/changed-input graph 3/3 通过。详见 [008](008-flaggems-dispatch-reclassification.md)。
