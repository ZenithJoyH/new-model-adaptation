# GLM-5.3-Flash-BF16 / PPU 问题索引

本目录只保留编号 Markdown 问题记录；编号沿用历史，排序不表示发生时间或验证完成顺序。
当前操作先核对[运行配置](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/runtime-config.yml)和阶段门禁；状态以问题正文和
[验收轮次](../acceptance/README.md)为准。

## 当前 BF16 路径

- [001：GPQA c64 EngineCore 故障与 padded physical slot 根因](001-graph-c64-enginecore-crash.md)。
- [008：stateful sparse indexer 的 graph 正确性问题](008-graph-correctness-fix-20260906.md)。
- [018：FlagGems autotune SQLite 锁与有界等待缓解](018-flaggems-sqlite-autotune-lock-20260906.md)。
- [019：GPQA 长推理耗尽 30000-token 上限](019-gpqa-generation-length-exhaustion-20260907.md)。
- [020：基于最新 Hy4 基线重整 GLM-5.3-Flash 最小适配](020-hy4-latest-minimal-rebase-20260907.md)。
- [021：FlagGems small-head sparse MLA 原生无 padding 接入](021-flaggems-sparse-small-head-no-padding-20260908.md)。
- [022：远端工作根收敛到 01-repos～08-bugs](022-remote-workspace-numbered-layout-20260908.md)。
- [023：去除 breakable workaround 并启用 FULL decode graph](023-full-decode-graph-without-breakable-20260908.md)。
- [024：GLM-5.3-Flash 命名与 vLLM 主线对齐](024-glm53-flash-naming-alignment-20260909.md)。
- [025：移除 GLM-5.3-Flash 的 vLLM 版本判断](025-remove-vllm-version-gate-20260909.md)。
- [026：收敛 GLM-5.3-Flash kernel 与 dispatch 边界](026-kernel-dispatch-boundary-20260909.md)。
- [027：全量禁用 FlagGems ATen 后的 full-graph 惰性导入与 GPQA c32 诊断](027-all-flaggems-aten-blacklist-gpqa-c32-20260909.md)。
- [028：将 GLM-5.3-Flash Triton 算子归入 FlagGems](028-flaggems-kernel-ownership-20260910.md)。
- [029：迁移算子从 Thead 候选重分类为 FlagGems dispatch](029-flaggems-dispatch-reclassification-20260910.md)。
- [030：GLM 与混元复用通用 row-wise top-k dispatch](030-shared-rowwise-topk-20260910.md)。
- [031：FlagGems day0 分支分叉阻塞剩余算子补齐](031-flaggems-day0-diverged-sync-blocker-20260910.md)。

001、018 与 019 是不同失败签名；不能把 SQLite mitigation、slot 根因修复和生成长度耗尽
互相替代。

## 历史诊断、失败与撤销

- [002：早期 FP8 启动修复](002-bringup-20260904.md)。
- [003：插件精简及错误 FP8 权重验证](003-cleanup-final-20260904.md)。
- [005：FP8 未量化层前缀](005-fp8-prefix-fix-20260904.md)。
- [006：旧 c64 服务崩溃诊断](006-gpqa-crash-diagnosis-20260904.md)。
- [007：旧轮 TIMEOUT 标记与生成截断](007-gpqa-timeout-marker-diagnosis-20260904.md)。
- [009：HY4 基线迁移及兼容缺口](009-hy4-base-migration-20260904.md)。
- [011：KDA TLE 选择与变长 graph metadata 复现](011-kda-bug-README.md)。
- [012：KDA 接入、尝试及限制](012-kda-integration-20260904.md)。
- [013：editable 安装入口与宿主启动问题](013-plugin-installation.md)。
- [014：共享 prefill 和 YAML 差异收敛](014-shared-prefill-refactor-20260904.md)。
- [015：旧轮 1800 秒 RPC 验证与重跑](015-timeout1800-validation-20260904.md)。
- [016：错误权重适配的撤销与恢复边界](016-withdrawal-20260904.md)。

旧 FP8/错误快照结果不继承为正确 BF16 通过；历史“当前”只代表该记录的时间点。

## 非问题材料已归位

004 库安装、010 范围审查、017 BF16 计划已移到 `environment/`，旧→新映射见
[环境索引](../environment/README.md)。编号不复用，新问题继续从现有最高编号向后分配。
设计选择统一导航到[Plugin 审查](../environment/plugin-change-review.md)，不在本目录放源码或补丁。

2026-09-08 以前记录中的远端 `accuracy/`、`runs/`、`runtime/` 等路径是当时的准确位置；
整理后的逐项映射和当前启动入口见 [022](022-remote-workspace-numbered-layout-20260908.md)，
不要改写历史命令或原始日志来伪装新路径。

原始过程脚本的本地归档不提交 Git，也不直接执行；只按记录的准确路径取证。
