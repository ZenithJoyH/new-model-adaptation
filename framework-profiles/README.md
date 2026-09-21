# 推理框架适配 Profile

本目录保存可复用的推理框架适配约束，不保存任何具体模型、Host、容器实例或运行结果。
一个 profile 描述一套完整适配栈，而不只是单个 Python 包。例如 `vllm-plugin-fl` 同时约束
vLLM、vllm-plugin-FL、FlagGems、执行模式、代码修改边界和验收方式。

模型适配的完整身份为：

```text
模型 × 硬件平台 × framework profile
```

新增框架时，从 `_template/` 复制并完善以下内容：

- `profile.yml`：组件角色、修改策略、执行模式、服务协议和验收能力。
- `workflow.md`：该框架在通用五阶段中的具体操作流程。
- `acceptance.md`：该框架的执行模式、精度、性能和启动脚本验收要求。

Profile 只能收紧仓库通用安全边界，不能授权停止适配容器、修改未声明可写的源码或绕过
证据要求。draft 仅支持分析和只读调查；experimental 允许已声明的适配和验证能力，
但不能通过完整正式验收；active 才具备完整验收契约。

现有直接位于 `models/<model>/<platform>/` 的历史记录按隐式 `vllm-plugin-fl` profile 解释；
不应为了目录一致性批量搬迁。新工作区使用：

```bash
./scripts/new-framework <model> <platform> <framework-id>
```

当前 profile：

| ID | 状态 | 适用范围 |
| --- | --- | --- |
| `vllm-plugin-fl` | `active` | vLLM 服务、vllm-plugin-FL 与 FlagGems 模型适配 |
| `torch-fl` | `experimental` | PPU 直接集成、算子路由、eager 模型验证，以及可选自包含 wheel |

`new-framework` 接受 active 和 experimental，按 profile 生成各自验收步骤；Torch-FL 不生成
vLLM 的 sanity/accuracy/performance 状态。可选 wheel 需在运行前按顺序加入 substeps。
证据与命令见 [框架证据契约](../docs/framework-evidence.md)。
