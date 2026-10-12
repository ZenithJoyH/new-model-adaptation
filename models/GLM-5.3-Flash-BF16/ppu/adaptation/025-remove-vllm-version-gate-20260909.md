# 025：移除 GLM-5.3-Flash 的 vLLM 版本判断

## 元数据

- 状态：`verified cleanup`（整模冷启动未在本轮执行）
- 首次出现时间：2026-09-09
- 最后验证时间：2026-09-09
- 模型：`GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / 当前适配容器
- Plugin / FlagGems / vLLM revision：Plugin `support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8`；FlagGems `bca444b8569294e7d4e4deff7ddfec7f05682033`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：源码注册与 CPU/import 回归；不改变当前服务进程

## 问题现象

- 错误签名或症状：GLM 注册入口通过 `patches/_version.py` 判断 vLLM 0.24，并把版本号扩散到三个 patch 模块名和两个函数名。
- 发生顺序：命名整理后，用户确认目标环境固定，不需要运行时版本判断。
- 影响范围：GLM-5.3-Flash 注册入口和 patch 命名；不涉及模型数学、权重或 tensor 契约。
- 精简证据及原始证据位置：远端 Plugin `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 024 命名与主线对齐 | 同为 GLM 专属模块整理 | 本次移除版本 gate，不改变 checkpoint identity | 高 | 延续最小命名边界 |

## 诊断与假设

- 已验证事实：`register_model()` 仅在 `is_vllm_024()` 为真时导入 GLM patch；三个 patch 文件带 `_v024` 后缀。
- 已验证事实：当前环境固定使用 vLLM 0.24 API，GLM 实现本身直接依赖这些 API。
- 待验证假设：删除 gate 并直接注册、同步去掉版本后缀，不影响幂等注册和专项测试。
- 已排除方向：删除包级 `vllm_fl/_version.py`；该文件属于插件自身版本元数据，与 GLM 的 vLLM gate 无关。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | GLM vLLM gate | `is_vllm_024()` 条件注册 | 无条件直接安装 GLM patch | editable Plugin | gate 文件/导入/分支删除，三个模块及函数去版本后缀 | 注册和专项回归通过 |

## 根因

- 已验证根因：早期适配为多版本兼容预留了运行时 gate，但当前插件部署目标固定，该抽象没有实际需要。
- 若未完全证实，当前假设与缺失证据：新进程 import/注册与专项回归待执行。

## 解决方法或 Workaround

- 修改思路：删除 `vllm_fl/patches/_version.py`，去掉 `is_vllm_024()` 条件；三个 GLM patch 模块及函数去掉 `_v024` 后缀。
- 选定层级/扩展点、职责依据和替代方案：只改 GLM 注册/patch 层，不修改共享版本元数据或其他模型的版本说明。
- 受影响的公共调用方、已有模型/平台，以及守卫未命中时的行为：GLM patch 改为每次插件注册时幂等安装；其他模型路径不变。
- 是否确属 Plugin 必要实现或可维护回归测试，判断依据：用户明确要求固定目标版本，不保留运行时判断；现有专项测试同步覆盖。
- Plugin 内必要实现或回归测试路径：远端 `vllm_fl/patches/glm5next*.py`、`vllm_fl/__init__.py`、`tests/unit_tests/test_glm5next_support.py`。
- 容器内仓库外临时过程脚本/代码路径、用途和清理状态：无。
- 分支与 revision/commit：上述 Plugin base，dirty 工作树，未提交。
- 正式回归测试路径：GLM 命名/注册与 dispatch input-support 专项测试。
- 针对旧行为、可选依赖隔离和相关共享路径的回归证据：最终轮 `36 passed, 1 warning in 10.97s`；causal、conditional 和 processor 三个入口在新进程完成注册/import。
- workaround 的适用条件、默认策略/性能影响和退出条件：不是 workaround；预期无性能影响。
- 服务停启操作及核对结果：本轮不停止或重启当前服务。
- vLLM 未修改证明：容器内 `/workspace/vllm` 与 FlagGems 的 `git status --porcelain` 均为空。

## FlagGems 证据

- 同步后的 revision 与检索证据：本轮不修改 FlagGems。
- 已有算子及接入方式，或缺失结论：不涉及。
- 如为 FlagGems 缺陷，工作根 `07-bugs/<issue>/`、容器对应路径与复现命令：不适用。
- 如确因工具要求使用 `/bug`，记录指向同一目录的已批准映射或明确例外（不得复制已有用例）：不适用。

## 验证结果

- 最小回归：删除一个 Python 文件后，余下 280 个 Plugin/单测 Python 文件全部通过 `compile()`；新进程注册/import 通过；36 项专项单测通过；`git diff --check` 通过。
- `eager`：不改变；整模未重启验证。
- `graph` capture/replay：不改变；整模未重启验证。
- 数值、dtype、shape、layout、边界条件：无变更。
- 最终结论与通过标准：已通过。GLM 路径不存在 `patches._version`、`is_vllm_024`、`*_v024`、旧 installer 名或旧测试名；注册/import 和专项测试通过。

## 限制与下一步

- 尚存限制：不再对非目标 vLLM API 提供静默跳过；依赖不匹配时将直接暴露导入或接口错误。
- 后续动作：服务冷启动留到用户安排的窗口。当前 PID `2893015` 在源码整理后仍健康，但它是修改前启动的进程，不能替代新代码的整模冷启动证据。
- 设计审查结论及 PR 范围的影响：减少一个模块和条件分支，固定插件支持的运行时契约。

## 经验沉淀

- 是否可跨模型或平台复用：仅适用于明确固定运行时 API 的部署。
- 知识库处理状态：`local-only`
- 候选知识库条目：无。
