# 008：与 1B 共用 dense/MoE Plugin

2026-10-08，按用户要求在 `H100-149` 新建
`MinicpmV4.7-unified-20261008`，整合两个 MiniCPM-V 4.7 的适配器。
当前状态 `functional-passed`；完整设计、组件身份、继承差异、源码哈希、失败尝试及回归范围见
[共同整合记录](../../../../../MiniCPM-V-4.7-1B/nvidia/frameworks/vllm-plugin-fl/adaptation/006-unified-dense-moe-adapter.md)。

共同实现安装在新容器 `/vllm-workspace/vllm-plugin-FL`，无 `PYTHONPATH`；
按实际 `text_config.model_type` 选择 dense/MoE，共用视觉组件与严格 canvas geometry 桥接。
35B 使用原权重 `/data/models/MiniCPM-V-4.7/weights/35b-a3b` 的只读挂载，TP2，
新容器 CUDA 0/1 对应物理 GPU6/7。继承 1B 环境的 FlagGems 广播 mask 修复，
本轮新服务不设置旧 attention 黑名单。

原 `MinicpmV4.7-35B` 容器、原安装、工作根 `start-model.sh` 与 8021 服务未改动。
过程代码在同路径 Host/容器工作根
`/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/02-issues/unified-adapter-20261008/`；
输出在该工作根 `04-runs/unified-adapter-20261008/`。
14 项契约测试及双模型 8 项真实 canvas 对照已通过；两模型各 eager 6/6、
FULL_AND_PIECEWISE 19/19，服务矩阵共 50/50 通过。两模型均捕获 mixed PIECEWISE 7/7、
decode FULL 5/5，大图输入 489 token 的红→蓝→红重放正确。详见
[共同功能验证](../acceptance/unified-code-validation-2026-10-08.md)。
本轮不宣称正式精度、性能或发布镜像通过，不修改 `framework.yml` 流程状态。

后续用户授权的代码提交已完成：
[support-minicpmV4.7](https://github.com/flagos-day0/vllm-plugin-FL/tree/support-minicpmV4.7)，
提交 [aa4228e](https://github.com/flagos-day0/vllm-plugin-FL/commit/aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68)。
新分支基于已验证的 `3a27a6f`，本次提交四文件；相对目标仓库旧 main 另保留 26 个
既有上游提交。详见上述共同整合记录的提交章节。
