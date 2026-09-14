# TP worker `sample_tokens` 超时、通信序号分叉与 EngineCore RPC 退出

- 状态：`hypothesis`
- 可信度：`medium`
- 平台：需要按当前目标平台复验
- 模型范围：使用 tensor parallel、由 EngineCore 调度多个 worker 的推理服务
- 软件及 revision：每次使用前必须记录并确认当前 vLLM/Plugin/runtime revision
- 首次记录日期：2026-09-06
- 最近复验日期：尚无仓库内复验证据

## 症状与识别条件

该经验只适用于以下连续症状，不能仅凭单条 RPC timeout 套用：

1. 某个 TP worker 在 300 秒内没有响应 `sample_tokens`。
2. 随后各 rank 报告的通信 work 序号出现分叉或不再一致。
3. EngineCore 最终因 RPC timeout 退出。

应先确认最早异常发生在哪个 rank、哪个调用和哪个时间点。EngineCore 的 RPC timeout
可能只是下游结果，而不是最初根因。

## 可能原因

- 首次编译、长 kernel 或资源压力导致 worker 很慢，但进程仍在持续取得进展。
- 某个 rank 已异常、OOM 或进入不一致的数据依赖分支。
- 各 rank 的 collective 调用顺序或次数不同。
- 通信库、Plugin dispatch 或 graph replay 出现死锁或状态分叉。

在获得各 rank 证据前，以上均为假设。

## 受控诊断或缓解尝试

- 类型：`diagnostic` / `mitigation`
- 候选变量：`VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS`

执行要求：

1. 保存各 rank 的关键日志时间线、最早异常、进程状态、设备利用率和显存，以及当时的
   模型、并行拓扑、请求和执行模式。
2. 确认当前安装的运行时确实读取 `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS`，并记录验证方式。
3. 记录变量原值和试验值；每轮只调整这一项，不同时更改 batch、并发、graph 配置或
   通信参数。
4. 如果变量只在服务启动时读取，仅停止并重启当前适配的推理服务或相关进程；不得停止、
   重启或删除适配容器。
5. 使用原始最小 workload 复验，比较所有 rank 的 work 序号、完成时间、错误和资源状态。

不在此条目中规定通用目标秒数。试验值应依据已观测的有效进展时间和当前服务 SLO 制定，
避免无限延长故障发现时间。

## 停止条件

出现以下任一情况时，不得继续通过增大 timeout 掩盖问题：

- worker 没有日志或计算进展。
- 通信 work 序号仍然分叉。
- 已发现 rank 异常、OOM、非法内存访问或明确算子错误。
- collective 调用顺序或次数不一致。
- graph capture/replay 状态不一致或服务进入死锁。

此时应回到最早异常 rank，检查其算子、Plugin dispatch、数据依赖控制流和 collective
顺序。若定位为 FlagGems 算子报错或精度问题，按规则在工作根 `07-bugs/` 中整理最小复现，
并通过已核实的容器对应路径原地执行；已有用例不再复制到 `/bug`。

## 通过标准

- 同一最小 workload 多次完成，所有 rank 的 work 序号保持一致。
- `sample_tokens` 和 EngineCore RPC 均在试验 timeout 内完成，没有 rank 异常或死锁。
- 分别记录受影响模式；如涉及 graph，必须验证 capture/replay，不能只验证 eager。
- 记录延长 timeout 对失败发现时间、请求延迟和吞吐的影响。
- 进入验收后按 10 并发进行小批量预检，并以至少 32 并发进行正式全量精度评测。

即使通过，上述结果默认只能证明 timeout 调整是有效缓解；只有因果证据充分时，才能标记
为根因修复。

## 复验与反例

| 日期 | 模型/平台 | revision | 原值/试验值 | eager/graph | 结果 | 来源记录 |
|---|---|---|---|---|---|---|

## 来源

- 2026-09-06 操作者提供的故障模式与候选处理经验；尚待具体模型适配记录复验。
