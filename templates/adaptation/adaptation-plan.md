# Plugin 适配计划与差距清单

## 输入材料

- 模型结构与推理链路分析：
- 平台环境分析：
- 用户提供的参考文件：
- Plugin、FlagGems、vLLM baseline：

## 修改边界

- 只允许修改适配容器中的 Plugin 代码。
- vLLM 源码必须保持不变并保留前后状态证据。
- 适配容器不得停止、重启或删除。
- 服务和当前适配相关进程可以按需停止或重启，但必须记录并核对目标。

## 差距清单

| ID | 模型组件/阶段 | Plugin 当前路径 | 平台能力 | 算子来源 | eager 影响 | graph 影响 | 修改计划 | 最小验证 | 状态 |
|---|---|---|---|---|---|---|---|---|---|

算子来源必须明确为：Plugin 已支持、FlagGems 兼容实现、Plugin 内新增 Triton 实现，
或尚未确认。不能使用临时直接调用绕过 Plugin dispatch。

## FlagGems 同步与检索证据

- 同步前 remote/branch/upstream/revision/status：
- fast-forward-only 同步命令：
- 同步后 revision/status：
- 算子检索范围和结果：

## 验证顺序

依次验证导入与注册、单算子、组件组合、最小模型执行、完整服务，并为适用项覆盖
`eager` 与 `graph` capture/replay。
