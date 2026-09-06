# 平台适配计划与差距清单

## 输入材料

- 模型结构与推理链路分析：
- 平台环境分析：
- 用户提供的参考文件及其原始位置：
- Plugin、FlagGems、vLLM baseline：

## 修改边界

- 只允许修改适配容器中的 Plugin 代码。
- vLLM 源码必须保持不变并保留前后状态证据。
- 适配容器不得停止、重启或删除。
- 服务和当前适配相关进程可以按需停止或重启，但必须记录并核对目标。
- Plugin 仓库只接收必要的产品实现和可长期维护的回归测试。
- 一次性诊断、部署、日志分析、探针、试验脚本和代码放在容器内各源码仓库之外的独立
  临时工作目录，不得提交，也不得复制到 `adaptation/`。

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

## 运行配置

- 结构化配置：`runtime-config.yml`
- 服务状态：`service-state.yml`
- 容器内 Plugin 必要实现与正式回归测试位置：
- 容器内仓库外临时工作目录：

## 验证顺序

依次验证导入与注册、单算子、组件组合、最小模型执行、完整服务，并为适用项覆盖
`eager` 与 `graph` capture/replay。
