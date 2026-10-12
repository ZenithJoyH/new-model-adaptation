# Hy4-preview / PPU 问题索引

本目录仅保存编号 Markdown 问题记录。沿用历史编号、试验日期和结论，不因整理重新编号或
声明通过。执行前核对[环境分析](../environment/environment-analysis.md)、平台状态及阶段门禁。

## 数值、注册与运行故障

- [001：FlagGems-first 切换与 reference 注册边界](001-flaggems-first-20260904.md)。
- [002：SQLite 并发锁的独立因果复现（含 2026-09-07 当前 revision 复现）](002-flaggems-sqlite-lock-reproducer.md)。
- [003：W8A8 根因修复与移除插件分块保护](003-flaggems-w8a8-fix-installed-20260904.md)。
- [004：W8A8 大 M 错误复现与消融](004-flaggems-w8a8-large-m-reproducer.md)。
- [005：GPQA 乱码的诊断、失败尝试与修复过程](005-gpqa-corruption-triage-20260904.md)。
- [012：W8A8 CPU/PPU 舍入边界对照](012-w8a8-rounding-issue-readme.md)。
- [015：PPU-07 hy4 启动脚本报错](015-start-script-failure-ppu07-20260907.md)。
- [016：FlagGems bool slice 导致 GPQA 首批请求击穿服务](016-flaggems-bool-slice-service-failure.md)。
- [017：GPQA c32/c8 差异、W8A8 large-M 根因与修复分支交付](017-gpqa-temp0-length-preemption.md)。
- [018：2026-09-08 精度评测新故障](018-latest-accuracy-eval-failure-20260908.md)。

003 是修复记录，004/012 保留对应诊断；不能把所有量化差异归为同一原因。002 的数据库
等待是独立 mitigation，不证明 W8A8 数值正确或正式精度完成。

## 插件职责与兼容性问题

- [013：FlagGems Sparse MLA 小 head 原生支持](013-flaggems-sparse-mla-small-head.md)。
- [014：BF16 Indexer top-k 调度归属收敛](014-bf16-indexer-topk-ownership.md)。
- [007：MLA helper 的通用与厂商职责](007-mla-helper-ownership-ppu07-20260904.md)。
- [008：T-Head sparse MLA backend 分层](008-native-sparse-mla-refactor-ppu07-20260903.md)。
- [011：T-Head 初始化下沉的历次尝试](011-vendor-bootstrap-refactor-ppu07-20260904.md)。

011 保留多次已撤回的中间方案；不按旧段落重建已移除的转发层。

## 归位与追溯

006、009、010 是已经结束的历史编号，不再占据问题目录，也不复用。
正式轮次与配置见[验收索引](../acceptance/README.md)；过程脚本按
环境与验收记录中的准确路径取证，不作为当前执行入口。
