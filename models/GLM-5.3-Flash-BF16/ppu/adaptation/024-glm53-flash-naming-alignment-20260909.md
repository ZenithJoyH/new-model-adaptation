# 024：GLM-5.3-Flash 命名与 vLLM 主线对齐

## 元数据

- 状态：`verified naming refactor`（新 served name 待下次服务启动生效）
- 首次出现时间：2026-09-09
- 最后验证时间：2026-09-09
- 模型：`GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / 当前运行镜像（本轮不重启容器）
- Plugin / FlagGems / vLLM revision：Plugin `support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8`；FlagGems `bca444b8569294e7d4e4deff7ddfec7f05682033`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：命名整理与 CPU/import 回归；不改变当前服务执行模式或负载

## 问题现象

- 错误签名或症状：插件自有模型、processor、patch、dispatch 和 kernel 模块使用 `glm5_next` 路径，但 vLLM 主线的模型实现模块使用 `glm5next`；启动入口仍暴露权重目录名 `GLM-5.3-Flash-BF16`。
- 发生顺序：功能适配完成后进行代码归属审查时发现命名不一致。
- 影响范围：代码可读性、与上游 diff 的可比性及 API 服务模型名；当前没有证据表明它造成数值错误。
- 精简证据及原始证据位置：vLLM PR `vllm-project/vllm#53906`；远端插件 `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 020 Hy4 最新基线最小适配 | 要求模型代码沿用上游结构 | 本次只处理命名，不重做功能适配 | 高 | 复用最小变更原则 |

## 诊断与假设

- 已验证事实：vLLM 主线将产品称为 `GLM-5.3-Flash`，模型包和 processor 模块命名为 `glm5next`。
- 已验证事实：权重 `config.json` 的 `architectures` 为 `Glm5NextForConditionalGeneration`，`model_type` 为 `glm5_next`。
- 待验证假设：仅重命名插件自有 Python 模块并同步导入，不改变 class/config identity，可保持现有加载行为。
- 已排除方向：把 class 改成 `Glm53Flash*` 或把 `model_type` 改成 `glm53_flash`；这会破坏权重与 Transformers/vLLM 注册契约。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 模块与对外名称 | 插件模块 `glm5_next`，服务名为权重目录名 | 插件模块 `glm5next`，服务名 `glm5.3-flash` | 远端 editable Plugin 与根级 `start-model.sh` | 12 个模型专属文件/目录完成重命名，导入与 launcher 同步 | 与主线模块命名一致，checkpoint identity 未改 |

## 根因

- 已验证根因：早期适配直接把 Hugging Face `model_type` 的蛇形命名扩散为插件模块名，没有区分产品名、上游模块名和 checkpoint 兼容键。
- 若未完全证实，当前假设与缺失证据：重命名后的完整模型服务重启尚未执行；本轮先做静态、import 和单元回归。

## 解决方法或 Workaround

- 修改思路：对外使用 `GLM-5.3-Flash`/`glm5.3-flash`，插件自有模块跟随主线使用 `glm5next`；保留 checkpoint identity。同步把 docstring、错误信息和日志中的旧产品名收口，并删除两组在 `ModelRegistry` 构造后才修改原始 registry 字典、不会影响实际注册的冗余 `setdefault`。
- 选定层级/扩展点、职责依据和替代方案：只改模型专属模块路径、导入、测试和 launcher 的 served name；不修改共享 dispatch 语义。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：只影响 GLM-5.3-Flash 注册入口；其他模型的注册与 backend 选择不变。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：命名属于可维护性整理；现有 GLM 专项测试同步改名并继续覆盖注册/导入。
- Plugin 内必要实现或回归测试路径：远端 `vllm_fl/**/glm5next*`、`tests/unit_tests/test_glm5next_support.py`。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：无；使用控制端临时 Ansible playbook，完成后不进入 Plugin。
- 分支与 revision/commit：`support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8`，dirty 工作树，未提交。
- 正式回归测试路径：远端 `tests/unit_tests/test_glm5next_support.py` 与 `tests/unit_tests/dispatch/test_input_support.py`。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：最终轮上述两文件合计 `36 passed, 1 warning in 11.20s`；注册进程成功导入 causal、conditional 和 processor 三个入口。
- workaround 的适用条件、默认策略/性能影响和退出条件：不是 workaround；预期无性能影响。
- 服务停启操作及核对结果：本轮不停止或重启当前服务。
- vLLM 未修改证明：容器内 `/workspace/vllm` 的 `git status --porcelain` 为空；FlagGems 工作树同样为空。

## FlagGems 证据

- 同步后的 revision 与检索证据：本轮不修改 FlagGems。
- 已有算子及接入方式，或缺失结论：不涉及算子接入变化。
- 如为 FlagGems 缺陷，工作根 `07-bugs/<issue>/`、容器对应路径与复现命令：不适用。
- 如确因工具要求使用 `/bug`，记录指向同一目录的已批准映射或明确例外（不得复制已有用例）：不适用。

## 验证结果

- 最小回归：281 个 Plugin/单测 Python 文件全部通过 `compile()`；重命名后的三个入口完成 import/注册；36 项专项单测通过；`git diff --check` 通过。
- `eager`：不改变；整模未重启验证。
- `graph` capture/replay：不改变；整模未重启验证。
- 数值、dtype、shape、layout、边界条件：没有数学或 tensor 契约变更。
- 最终结论与通过标准：已通过。旧模块导入和旧斜杠路径扫描为空；`configs/glm5_next.py`、三个 `model_type` 以及 registry 的 `glm5_next` key 按 checkpoint 契约保留；专项测试通过。

## 限制与下一步

- 尚存限制：当前服务进程在修改前已加载旧模块，`/v1/models` 仍返回 `GLM-5.3-Flash-BF16`；它只证明变更没有打断既有服务，不等价于新 launcher 的整模冷启动验证。
- 后续动作：在用户允许的服务窗口执行新 launcher 启动与最小推理；再决定是否重跑正式验收。当前 launcher SHA-256 为 `1217bc7c6673eba57ea6b7233084b2c56f1273d2ee73b8b6d83c8b5d0c6f5533`。
- 设计审查结论及 PR 范围的影响：纯命名整理可与 GLM 模型适配同一 PR，需保留重命名历史并避免兼容键误改。

## 经验沉淀

- 是否可跨模型或平台复用：可复用“产品名、上游模块名、checkpoint identity 分层”原则。
- 知识库处理状态：`local-only`
- 候选知识库条目：无。
