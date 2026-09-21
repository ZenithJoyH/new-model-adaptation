# 评测 Skills 项目适配入口

本目录保留两个同名调用入口，具体公共方法由 skills-hub 维护；本地 SKILL.md 只负责加载
公共能力和 [唯一项目契约](../docs/skills-project-contract.md)，不维护另一套测试方法。

调用时明确模型、平台、framework profile、Host 和操作：

- 精度：`service-sanity`、`hard-case`、`formal-full`、`gate-check`。
- 性能：`single-scenario` 或 `full-suite`，说明是诊断比较还是正式验收。

旧调用名的映射见项目契约。按实际安装位置读取 skills-hub；没有公共能力或原生结果不兼容
时返回 incomplete，不复制一套实现。Torch-FL 实验验证走自己的 profile，不自动调用
vLLM 的精度/性能服务测试。
