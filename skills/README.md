# 评测 Skills

本目录提供与“端到端推理优化”项目一致的精度、性能评测调用接口。两个项目统一：

- Skill 名称和调用方式；
- 分层评测模式及触发条件；
- `passed`、`failed`、`incomplete` 三态结论；
- 服务身份、工作负载、证据、结论边界和下一触发点等报告字段；
- 正式性能前必须重新核验正式精度门禁。

各项目保留自己的测试实现和证据格式。Skill 只负责编排，不复制 runner：本项目通过每个
Skill 的 `references/project-contract.md` 将统一逻辑映射到 `test/`、五阶段适配流程、远端
工作目录和本地 Markdown 记录。另一个项目可使用同名 Skill 和相同模式，并由它自己的项目
适配说明映射到对应工具。

可直接在 Codex 中调用：

```text
使用 $inference-accuracy-evaluation，以 formal-gate 模式对 Hy4-preview 的 PPU graph 服务进行正式精度验收。
```

```text
使用 $inference-performance-evaluation，以 targeted 模式验证本次 MoE dispatch 修改的性能影响。
```

未明确模式时，Skill 根据触发场景选择最小充分模式。项目规则、用户指定的执行边界和当前
现场证据始终优先于 Skill 中的通用建议。
