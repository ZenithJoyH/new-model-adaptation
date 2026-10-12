# Xing4.0-29B-A4B / ppu

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)


旧平台阶段记录按原位置保留（不作为新增执行入口）：
- [环境与设计](environment)。
- [问题台账](adaptation/README.md)。

## 整理前平台说明（历史原文）

- Host / 容器：`PPU-13` / `xing4_0`
- Plugin：容器内 editable `/workspace/vllm-plugin-FL` 仍以 `0ef3d87a...` 为工作树基线；远端
  Xing4-only 分支直接基于 `origin/main@d2d7234a...`，单一提交为
  `origin/support-Xing4.0@f888ec82...`
- vLLM：`0.24.0`，HEAD `ee0da84a...`，未修改
- 模型：`/mnt/cpfs/models/Xing4.0-29B-A4B`（只读）
- 工作根：Host/容器均为 `/mnt/nfs/users/jinghao/xingchen4`

2026-09-16 已按 vLLM PR #57135 在 Plugin 扩展点新增严格 `xing4_0` config/model、reasoning
和 tool parser，不兼容旧 config/权重字段。TP4 BF16 graph smoke 已完成 41/41 权重加载、
mixed PIECEWISE 51/51、FULL decode 51/51，并成功生成 16 个 token。当前启动还必须包含
`--trust-remote-code` 和 `VLLM_FL_USE_FLAGGEMS_ATTN=1`。

2026-09-17 已进一步删除 XingChen4 config/model/reasoning 文件及注册，将 Xing4.0 config、
model 和 reasoning parser 改为独立实现。13/13 focused tests、fresh-process Xing4-only 注册断言
和真实 checkpoint config/module 验证通过。该重构后的 graph 尚未重跑：原 8040 服务已退出，
PPU 0–15 当前由后来启动的四个非本轮 TP4 服务占用，本轮未停止或干扰这些服务。

主要记录：

- 架构：[architecture-and-inference.md](../architecture-and-inference.md)
- 环境：[environment-analysis.md](environment/environment-analysis.md)
- 实现审查：[plugin-change-review.md](environment/plugin-change-review.md)
- 问题与验证：[001-xing4-registration-and-loader.md](adaptation/001-xing4-registration-and-loader.md)

本轮未选择 acceptance，未运行正式 accuracy/performance，也未创建最终 `start-model.sh`；因此
不宣称 optimized 或正式交付完成。旧 graph 原始日志位于远端
`04-runs/graph-smoke-20260916-03/`；最新 focused 收据位于
`04-runs/xing4-only-20260917-01/`。容器本身未停止或重启，无关服务未触碰。
