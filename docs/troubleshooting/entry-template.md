# 故障标题

- 状态：`verified` / `hypothesis` / `deprecated`
- 可信度：`low` / `medium` / `high`
- 平台：
- 模型范围：
- 软件及 revision：
- 首次验证日期：
- 最近复验日期：

## 症状与识别条件

- 错误关键行或数值异常摘要：
- dtype、shape、layout、设备和执行模式：

## 最小复现与证据

- 复现脚本的工作根 `08-bugs/` 路径与容器对应路径：
- 实际使用的 `/bug` 兼容映射或明确例外（如有）：
- 执行命令：
- 期望结果：
- 实际结果：

## 根因

明确区分已验证事实与假设。

## 诊断尝试、缓解措施或根因修复

- 类型：`diagnostic` / `workaround` / `mitigation` / `root-cause-fix`
- 修改变量及原值/试验值：
- 为什么该动作适用于当前故障特征：
- 停止条件和回退方式：

## 修复与 Plugin 接入方式

- 修改位置：
- FlagGems revision 和检索证据：
- Plugin dispatch/backend/注册方式：
- vLLM 未修改证据：

## 验证结果

- 单算子数值测试：
- `eager`：
- `graph` capture/replay：
- 模型或服务回归：

## 适用限制与回退

-

## 复验与反例

| 日期 | 模型/平台 | revision | 结果 | 新增约束或反例 |
|---|---|---|---|---|

## 来源记录

- `models/<model>/<platform>/adaptation/...`
