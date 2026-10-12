# 007：可选 MiniMax 工具解析配置依赖未构建的 Rust 扩展

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-15
- 最后验证时间：2026-09-15
- 模型：`MiniMaxAI/MiniMax-M3`，权重 `/mnt/cpfs/models/MiniMax-M3`
- 平台与 Host 别名：T-Head PPU-ZW810E，`PPU-13`
- 容器：`minimaxM3`
- 执行模式与负载：TP16 graph run1，`FULL_DECODE_ONLY`，prefix caching 开启

## 问题现象

- 错误签名：`Rust tool parsing requires the vllm._rust_tool_parser PyO3 extension`。
- 发生顺序：6/6 graph 捕获成功 → API 健康检查成功 → 无 tools 的普通 chat 请求在入队 EngineCore 前返回 HTTP 500。
- 影响范围：当启动参数包含 `--reasoning-parser minimax_m3 --tool-call-parser minimax_m3 --enable-auto-tool-choice` 时的 OpenAI chat 入口；已通过的 eager 基础配置没有这三项。
- 原始证据：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/graph-service-run1/server.log` 和 Ansible HTTP 500 收据。

## 诊断、假设与受控尝试

启动成功与 graph 捕获已排除模型加载、Plugin 算子和 graph 初始化。HTTP 500 明确指向当前镜像中不存在的 Rust 工具解析扩展。工具解析不是基础文本/多模态推理正确性前提，也不应留在最小最终启动脚本。

| 轮次 | 唯一变量 | 结果 | 结论 |
|---|---|---|---|
| 1 | graph run1 含三个可选工具解析参数 | 6/6 graph 捕获通过，chat HTTP 500 | API 配置与镜像构建不匹配 |
| 2 | 仅移除三个可选参数 | graph run2 再次完成 6/6 捕获，北京/巴黎 changed-input chat 均为 HTTP 200 且正确 | 受控对照成立；这是不可用的可选特性，不引入 Rust 构建改造 |

## 解决方法、验证与限制

- 已验证解决：从本次基础适配启动配置移除三个可选工具解析参数。
- 不采用：不在适配期间重建 vLLM 或改动容器镜像，不用与用户基础推理目标无关的工作扩大 Plugin 范围。
- 验证：`04-runs/graph-service-run2/server.log`、`smoke-responses.json`、`smoke-receipt.txt`；6/6 graph 捕获与两个 changed-input chat 均通过。
- 限制：最终基础服务不承诺 auto tool choice；若未来确需该特性，应在单独镜像构建/功能范围内补齐 Rust 扩展后再验证。

## 经验沉淀

- 知识库处理状态：`local-only`
- 暂不提升：属于当前镜像构建选项与可选 API 特性的组合；未验证其他镜像。
