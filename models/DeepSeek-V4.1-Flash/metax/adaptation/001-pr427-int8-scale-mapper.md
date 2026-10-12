# 001：PR 427 的 DeepSeek-V4 INT8 scale mapper 不匹配

## 元数据

- 状态：`resolved`（仅权重加载问题；整模推理未通过）
- 首次出现时间：2026-09-21 11:34:12 +0800
- 最后验证时间：2026-09-21
- 模型：`/public-flash/models/DeepSeek-V4-Flash-Quant-W-INT8-PerChannel-A-INT8-PerToken`
- 平台与 Host 别名：MetaX C550 x8，`mx-59`
- 容器名称与镜像：`deepseek`，`harbor.baai.ac.cn/flagrelease-public/metax-vllm-0.24.0-pluginfl-tree3.6:xingchen4-0907`
- Plugin / FlagGems / vLLM revision：Plugin `main@fd5c727f` 加未提交 PR 427 `da62cdde`；FlagGems `711cf839`；FlagGems-vLLM `c0ffa628`；vLLM `ee0da84a`
- 执行模式与负载：eager，TP8/EP8，`max_model_len=50000`，FP8 KV，启动加载

## 问题现象

- 错误签名或症状：所有 TP rank 在首个 checkpoint 分片加载时抛出 `KeyError: 'layers.0.attn.fused_wqa_wkv.weight_scale_inv'`，EngineCore 初始化失败。
- 发生顺序：模型与 MetaX dispatch 初始化成功 → 选择 `FLW8A8DynamicLinearKernel` → 109 个分片开始加载 → 第一个 attention scale 映射失败。
- 影响范围：当前 W8A8 per-channel weight / dynamic per-token activation checkpoint 无法完成加载；尚未进入 dummy forward、eager 请求或 graph。
- 精简证据及原始证据位置：`mx-59:/public-flash/jinghao/deepseekV4/04-runs/pr427-eager-tp8-20260921-01/termination-record.txt`；原始日志同目录 `service.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 既有 TP timeout 条目 | 都会导致 EngineCore 退出 | 本次在权重加载阶段同步抛出确定的 `KeyError`，不是 worker 无响应 | 高 | 排除 timeout 方向，不放大超时 |

## 诊断与假设

已验证事实：checkpoint 的 `expert_dtype` 为 `int8`，量化为 compressed-tensors `int-quantized`；其 scale 键使用 `.scale`。vLLM 0.24 NVIDIA DeepSeek-V4 mapper 对所有非 `fp4` expert dtype 都把 `.scale` 改为 `.weight_scale_inv`，这是 FP8 参数契约；当前 compressed-tensors W8A8 linear 与 MoE 注册的参数后缀均为 `.weight_scale`。PR 427 的 Plugin 子类继承了 upstream mapper，未为 INT8 checkpoint 覆盖该规则。

待验证假设：在 Plugin 的 DeepSeek-V4 模型适配层中，仅对 `expert_dtype=int8` 且格式为 `int-quantized` 的模型使用 `.scale -> .weight_scale` mapper，可以越过本错误且不改变 FP4/FP8 调用方。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 合入 PR 427 | 最新 Plugin main | PR 427 squash，保留主线冲突修复 | Plugin 分支 `pr-427-metax-validation` | 25 项相关单测通过；整模在 scale mapper 失败 | PR 可导入且设备算子可执行，但 mapper 未覆盖此 INT8 权重格式 |

## 根因

- 已验证根因：尚待 mapper 单测与整模对照完成后确认。
- 若未完全证实，当前假设与缺失证据：缺少 `.weight_scale` mapper 后的完整 109/109 加载及推理结果。

## 解决方法或 Workaround

- 修改思路：为 PR 新增的 Plugin DeepSeek-V4 registry 子类增加严格受守卫的 INT8 compressed-tensors mapper。
- 选定层级/扩展点、职责依据和替代方案：权重命名兼容属于 Plugin 模型适配层；不修改只读 vLLM，也不改 checkpoint。替代方案是改 vLLM 通用 mapper或权重文件，影响更广且越过所有权边界，因此不采用。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：仅 DeepSeek-V4 Plugin registry 条目；守卫未命中继续使用 upstream FP4/FP8 mapper。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：PR 427 明确支持 W8A8，且当前失败发生于该模型适配的权重契约，需加入 mapper 单测。
- Plugin 内必要实现或回归测试路径：待实现于 `/workspace/vllm-plugin-FL/vllm_fl/models/deepseek_v4.py` 及对应 `tests/unit_tests/models/`。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：`/public-flash/jinghao/deepseekV4/05-tmp/resolve-pr427.py` 仅用于 PR 冲突解析，保留为过程证据。
- 分支与 revision/commit：`pr-427-metax-validation`，基线 `fd5c727f`，未提交。
- 正式回归测试路径：待补充。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：待补充。
- workaround 的适用条件、默认策略/性能影响和退出条件：仅 INT8 compressed-tensors；无预期性能影响；上游 mapper 原生支持时删除。
- 服务停启操作及核对结果：本任务启动 API PID 41965，失败后自行退出；无残留 EngineCore/worker，容器未停止或重启。
- vLLM 未修改证明：`/workspace/vllm@ee0da84a` 保持只读、clean，待最终复核。

## FlagGems 证据

- 同步后的 revision 与检索证据：`/workspace/FlagGems@711cf839`，可编辑安装成功。
- 已有算子及接入方式，或缺失结论：PR 的 INT8 indexer 设备单测在 MetaX 上 2/2 通过；本问题发生于权重名字映射，未进入 FlagGems kernel。
- 如为 FlagGems 缺陷，工作根 `07-bugs/<issue>/`、容器对应路径与复现命令：不归类为 FlagGems 缺陷。
- 如确因工具要求使用 `/bug`，记录指向同一目录的已批准映射或明确例外（不得复制已有用例）：不适用。

## 验证结果

- 最小回归：PR 相关 25 项单测通过；mapper 修复测试待执行。
- `eager`：失败于权重加载，尚未通过。
- `graph` capture/replay：未执行，因 eager 前置未通过。
- 数值、dtype、shape、layout、边界条件：INT8 checkpoint scale 是 per-output-channel FP32；映射后的加载形状仍待整模验证。
- 最终结论与通过标准：修复需至少完成 109/109 加载、健康检查与最小真实请求；随后才进入 graph。

## 限制与下一步

- 尚存限制：PR 原说明与验证范围偏 NVIDIA；MetaX 整模尚未完成。
- 后续动作：实现受守卫 mapper、补单测、复跑 eager；eager 通过后再验证 graph。
- 设计审查结论及 PR 范围的影响：修复应收敛在 Plugin DeepSeek-V4 模型适配文件，不改变 dispatch 通用策略或 vLLM。

## 经验沉淀

- 是否可跨模型或平台复用：可能适用于相同 DeepSeek-V4 W8A8 checkpoint，但需更多平台验证。
- 知识库处理状态：`local-only`
- 候选知识库条目：暂无，先完成整模验证。

## 2026-09-21 后续验证

上述初始调查记录保留原样；mapper 已实现于 Plugin 模型适配层，单测为
`tests/unit_tests/models/test_deepseek_v4_weights_mapper.py`。后续多次 TP8 运行均完成
109/109 分片加载并进入 forward，确认原 `.weight_scale_inv` 加载错误消失。
例如 `mx-59:/public-flash/jinghao/deepseekV4/04-runs/pr427-eager-tp8-20260921-18-hash-topk-fix-blacklist-mm/service.log`。
相关测试最新为 50 passed、3 skipped，证据在工作根
`04-runs/pr427-related-unit-after-qnorm-abi-20260921/{pytest-output.txt,junit.xml}`。
这只证明 mapper 修复有效，不能代表真实请求或 graph 已通过；后续问题见 002—004。
