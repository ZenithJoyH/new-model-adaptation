# 003：Plugin worker 未接收异步池化输出

2026-10-23，范围：PPU-01 的 `minicpm-jev-vllm`。状态：接口修复通过，整模型数值继续定位。

FlagGems clone 修复后，完整视觉及文本权重成功加载，eager 分类服务在 8330 就绪。首个真实样例在前向和池化后返回 HTTP 500，EngineCore 在 Plugin `worker.py:1016` 的 `IntermediateTensors` 断言失败。证据为工作根 `04-runs/eager-clone-fix-20261023/server.log` 和 `04-runs/eager-first-request-20261023/http-error.json`。此请求未产生有效数值结果，不能记为通过。

Plugin `ModelRunnerFL._pool()` 返回 `AsyncGPUPoolingModelRunnerOutput`，继承 vLLM `AsyncModelRunnerOutput`；Plugin worker 只接受同步 `ModelRunnerOutput`/None，将异步输出误判为流水线中间张量。当前只读安装的 vLLM worker 已接受该异步基类。

修复实际安装的 `/workspace/vllm-plugin-FL/vllm_fl/worker/worker.py`：返回注解和输出类型守卫加入 `AsyncModelRunnerOutput`。沿用既有异步复制/同步协议，不强制同步，不添加模型名特例，不修改 vLLM 或数值路径。

新增维护测试 `tests/unit_tests/worker/test_pooling_output.py`，覆盖真实异步池化输出类型、普通输出、None 和流水线中间张量。修复前 1 failed / 3 passed，唯一失败与线上断言一致；修复后 4 passed。JUnit XML 和日志在 `04-runs/eager-first-request-20261023/worker-before.*` 和 `worker-after.*`。

整模型以相同参数运行 12 个样例两轮，24 次 HTTP 200，token 数全部对齐、阈值侧全部一致、重复概率一致，异步返回值不再崩溃。证据为 `04-runs/eager-worker-fixed-samples-20261023/`。末例概率最大误差 0.008402884，超过预设 0.005；此结果只证明接口修复有效，未证明数值验收通过。Ansible 会话传输中断，已通过独立只读连接核验完整落盘的 24 行结果及 summary，而非凭断连会话退出状态推断通过。

设计审查：变更属于 worker 既有返回值协议，与只读 vLLM 当前接口一致；正常结果、None 及 PP 中间张量保持行为。真实模型覆盖单卡多模态 pooling，单测覆盖 PP 发送选择；多卡设备通信和其他实际平台未执行，不宣称通过。无模型名特例、强制同步、异常重试或数值容差修改。

知识库状态：local-only。上游 worker 接口对齐且同一测试通过后可移除此补丁。无提交、推送或 PR；保留继承自 OCR 容器的其他源码改动。
