# 评测 Skills 项目入口

本目录的两个入口由项目维护，以 [项目契约](../docs/skills-project-contract.md) 和既有
原生 runner 执行。保留旧目录名，能力身份分别为 `adaptation/accuracy`、
`adaptation/performance`；不等同于 Hub 的同名公共包，也不运行时读取旁边的 Hub 工作区。

调用方明确模型、平台、framework profile、Host 和一个操作：

- 精度：`service-sanity`、`hard-case`、`formal-full`、`gate-check`。
- 性能：`single-scenario` 或 `full-suite`，明确已冻结场景和结论范围。

`interface.json` 供机器校验操作、身份、接口版本与结果契约，`scripts/skill_bundle.py`
对完整包建立指纹。项目入口仅接受其明确声明支持的版本和契约，不因名称相同自动兼容。
缺少参数或原生证据不兼容返回 `incomplete`。旧操作名须在调用前明确映射，不能猜测模式。
Torch-FL 实验验证走自己的 profile，不自动调用 vLLM 的服务验收。

长任务的可恢复记录及当前已接入的原生完成 gate 见 [执行记录](../docs/agent-execution.md)。
公共 Hub 更新只作为显式比较/迁移输入，不自动改变本项目方法。
