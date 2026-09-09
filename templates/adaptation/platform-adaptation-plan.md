# 平台适配计划与差距清单

## 输入材料

- 模型结构与推理链路分析：
- 平台环境分析：
- 用户提供的参考文件及其原始位置：
- Plugin、FlagGems、vLLM baseline：
- 已阅读的目标插件设计/dispatch/贡献规范和现有测试入口（路径与 revision）：
- 设计与 PR 标准：仓库 `docs/plugin-contribution-policy.md`

## 修改边界

- 只允许修改适配容器中已核实的 editable-install Plugin 源码；不得在远端工作根目录
  创建第二份 checkout。
- vLLM 源码必须保持不变并保留前后状态证据。
- 适配容器不得停止、重启或删除。
- 服务和当前适配相关进程可以按需停止或重启，但必须记录并核对目标。
- 使用用户指定并已核实的远端工作目录；逐 Host 的 `host_root/container_root` 记录在
  `runtime-config.yml.workspace.roots`。除上述 Plugin 源码和已授权同步的现有 FlagGems
  checkout 外，目录外默认只读；必要写入须精确记录并单独取得授权。
- Plugin 仓库只接收必要的产品实现和可长期维护的回归测试。
- 一次性诊断、部署、日志分析、探针、试验脚本和代码放在已指定容器工作根目录内、
  各源码仓库之外的 `05-tmp/<issue-or-run-id>/`，不得提交，也不得复制到 `adaptation/`。

## 差距清单

| ID | 模型组件/阶段 | Plugin 当前路径 | 平台能力 | 算子来源 | eager 影响 | graph 影响 | 修改计划 | 最小验证 | 状态 |
|---|---|---|---|---|---|---|---|---|---|

算子来源必须明确为：Plugin 已支持、FlagGems 兼容实现、Plugin 内新增 Triton 实现，
或尚未确认。不能使用临时直接调用绕过 Plugin dispatch。

## 设计选择与共享影响

| 变更 ID | 所属层级与职责依据 | 复用的接口/扩展点 | 替代方案及未选原因 | 公共契约/默认值影响 | 受影响模型/平台/调用方 | 守卫与未命中行为 |
|---|---|---|---|---|---|---|

- 可选 vendor 依赖、lazy import、spawn/重复注册与缓存失效影响：
- workaround 的最小作用域、性能代价、上游关联和移除条件：
- 代表性回归矩阵：目标路径、已有相关调用方、不应受影响路径及选择依据：
- 无可用硬件的检查替代、未验证范围和风险：
- 最终设计自检与 PR 材料：`plugin-change-review.md`（审查必须对应实际 HEAD 和 dirty diff）。

## FlagGems 同步与检索证据

- 同步前 remote/branch/upstream/revision/status：
- fast-forward-only 同步命令：
- 同步后 revision/status：
- 算子检索范围和结果：

## 运行配置

- 结构化配置：`runtime-config.yml`
- 服务状态：`service-state.yml`
- 容器内 Plugin 必要实现与正式回归测试位置：
- 各 Host 的宿主工作根目录、容器内对应目录及映射证据：
- 容器内工作根目录下、仓库外的临时工作子目录：
- 每个 worker 的 cwd、TMPDIR、框架缓存和输出参数（核实版本支持后逐项配置）：
- 目录外写入的必要性、精确范围及用户授权（没有则保持禁止）：

## 验证顺序

依次验证导入与注册、单算子、组件组合、最小模型执行、完整服务，并为适用项覆盖
`eager` 与 `graph` capture/replay。
