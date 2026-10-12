# Xing4.0-29B-A4B PPU 适配问题索引

本目录只保存精简 Markdown 问题记录。源码和可维护测试位于容器的 verified Plugin checkout；
原始输出与临时诊断位于批准远端工作根的编号目录。

## 问题列表

| ID | 问题 | 状态 | 首次出现 | 根因 | 解决方法 | 验证结果 | 记录 |
|---|---|---|---|---|---|---|---|
| 001 | 新 Xing4_0 身份未注册且需严格新权重协议 | resolved | 2026-09-16 | Plugin 缺少新 identity；graph 启动还缺 `trust_remote_code` 和 FlagGems MLA 开关 | 新增严格 Plugin model/config/parser 注册并复用既有 dispatch | TP4 graph 权重加载、两类 graph capture、最小生成和 7 个 focused tests 通过 | [001-xing4-registration-and-loader.md](001-xing4-registration-and-loader.md) |

## 尚未解决的风险

- PR #57135 仍为 draft；本轮以 checkpoint 远程实现、权重字段和现有 clamp/Sinkhorn focused
  tests 为语义基准，不把 draft 的全部平台结论外推到 PPU。
- 未选择正式 acceptance；accuracy/performance、eager、MTP/DSA/量化和 tool-call API 端到端
  尚未验证，也未创建最终 `start-model.sh`。
- Plugin 起始 dirty tree 的 5 个 mode-only 文件及 `thead.yaml` 修改仍为 inherited changes，
  没有纳入本任务改动。
