# Qwen3.8-Flash-Next / PPU：Plugin 设计审查

> 复核日期：2026-09-07。结论：**当前集成修改合理，已推送为可复核候选；正式精度和性能验收仍待完成。**
> 审查遵循[Plugin 贡献规范](../../../../docs/plugin-contribution-policy.md)，设计结论与验收状态分开记录。

## 最终身份与范围

- 目标仓库：`ZenithJoyH/vllm-plugin-FL`，分支 `support-qwen3.8-flash`。
- 远端最终 revision：`a5c6f0ca373afa606b68d2daa4bb4a9dcc1833c5`，已从 GitHub 回读确认。
- 集成工作树：PPU-01 容器内
  `/mnt/nfs/users/jinghao/qwen38-adaptation-20260904/01-repos/vllm-plugin-FL-qwen38-integration`，
  提交后 clean。该历史在远端原分支 `489d22d52d5d1f9a8c3071c7955d0d655a55e334` 上依次包含
  HY4 整理、T-Head native bundle 缺失 fallback、Qwen 模型适配和本轮收口提交。
- vLLM 保持 `ee0da84ab9e04ac7610e28580af62c365e898389`；FlagGems `/workspace/FlagGems`
  已 fast-forward 到 clean `master@dcd0cfeae8187dee691656c0616c1ed95899c2ae`。

## 本轮设计修正

1. Qwen 专用 n-gram runner 路径改由显式 `supports_qwen38_ngram_context` capability 与
   `ple_layer_ids` 共同触发，并增加“有同名字段但未声明 capability”的守卫测试，避免影响其他模型。
2. config 和模型注册改为保留已有注册：配置表使用 `setdefault`，注册架构前检查
   `ModelRegistry.get_supported_archs()`，为未来 vLLM 原生实现保留所有权。
3. T-Head 默认 blacklist 保持 tracked 平台策略；Qwen 现场的 `slice`、`conv1d`、
   `_conv_depthwise2d`、`index` 通过 `VLLM_FL_FLAGOS_BLACKLIST_APPEND` 追加，避免用模型配置覆盖
   HY4 已验证的平台默认项。
4. PLE graph padding 的状态索引按 block-table 契约使用 `NULL_BLOCK_ID=0`；文档明确它与 flattened
   slot mapping 使用的 `PAD_SLOT_ID=-1` 属于不同索引空间，并移除未决 TODO。
5. 原来的三项一次性 runtime 脚本和配置已复制到批准工作根的 `04-acceptance/` 与
   `02-environment/`；产品分支只保留可维护 pytest。旧工作树中的四个 untracked 文件因自动审批
   拒绝删除而继续保留，不参与最终提交或运行时导入。

## 验证证据

| 层次 | 结果 | 证据 |
|---|---|---|
| 静态 | `compileall`、`git diff --check` 通过；容器未安装 Ruff | 集成工作树与提交 `a5c6f0c` |
| 聚焦回归 | 34 passed | Qwen runner capability、dispatch、blacklist append、T-Head bootstrap |
| Plugin 回归 | 410 passed，12 warnings，24.95 s | `05-runs/plugin-regression-dcd0cfe-20260907-1714/pytest.log` |
| PPU 算子 | slice、index、depthwise conv 的 eager/graph/变输入探针全部通过；最大卷积额外峰值约 497 MiB | `05-runs/workaround-probes-dcd0cfe-20260907-1721/` |
| 全模型 | TP8、FULL_DECODE_ONLY、`max-model-len=65536`、`max-num-seqs=32`、`max-num-batched-tokens=4096`；请求 `1+1` 返回 `2`，HTTP 200，服务随后健康 | `05-runs/full-model-smoke-dcd0cfe-20260907-1740/` |

首次用非连续空闲卡 `0,5,6,7,12,13,14,15` 的启动曾在健康后随宿主机其他 TP4 工作负载同时消失；
容器未 OOM、未重启。只改变拓扑为连续且此前验证过的 8–15 卡后完整冒烟通过，因此该次记录为
宿主机加速器状态变化，不归因于 Plugin 修复。

## 影响面与剩余限制

Qwen 模型语义仍位于模型 adapter，算子通过既有 dispatch/registration 路径接入，硬件限制留在
T-Head capability/config 边界。本轮覆盖了缺失 native bundle、未来上游注册所有权、普通非 capability
config 的 miss path，以及 eager/graph PPU 运行。视觉、MTP、量化、EP、PP 和其他硬件没有验收，
不能据此声明支持。正式 GPQA 与性能验收尚未在最终 `a5c6f0c` + FlagGems `dcd0cfe` 组合上重跑，
所以平台状态保持 `functional`，不标记 `optimized` 或 complete。

## 2026-09-10：算子所有权复审

本轮以当日最新 `support-hy4-preview@ff87b683ec9c6c1925dbedf12261914e45569b52`
重新承载 Qwen 适配，并将此前 Plugin-local 的 10 个 Triton 算子迁至
`ZenithJoyH/FlagGems:flaggems-for-day0`。最终远端 head 已从 GitHub 回读确认：

- FlagGems `37716d41b0d6da34b9a9672b637d52f028d1a4e1`，基线 `187fc1f7`；
- Plugin `939600b323c02c21916f1f76bfb4cd8c2b02578d`，该 head 是唯一的 Qwen3.8 适配提交；
- vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`，detached clean。

职责划分调整为：FlagGems 持有纯 tensor/scalar ABI、Triton 实现和独立 reference 测试；Plugin
通过现有 `FlagGemsBackend` 注册 `default.flagos`，只保留 common-slot cache-group 对象拆包。
Plugin 的独立 Triton backend 已完整删除。10 个 dispatch 名称使用算子语义，FlagGems 按 QSA、
PLE、GDN 和 slot mapping 顶层模块组织；每个符号独立检测 capability，不完整安装不会连带禁用
仍存在的算子，已有 vendor policy miss path 保持可选。Qwen 模型专用实现合并为单个
`vllm_fl/models/qwen3_8_flash_next.py`，删除 package 子模块和只做转发的 wrapper。

实际 diff 复核未发现模型名或机器特例进入共享执行代码。FlagGems 新增或修改 10 个文件。
Plugin 历史从最新 upstream/main `e2c6e2c` 开始，依次重放 HY4 PR 的五笔提交，最后一笔
`939600b` 集中包含 21 个文件的 Qwen3.8 适配。六笔重建提交的 author 和 committer 均为
`ZenithJoyH <1355922182@qq.com>`。服务器测试树和本机推送树的 tree 哈希分别为
`8cb8cf98de8760cfbec0ec4f2c5f20af45c9fd4c` 与
`aeada664f13f0bb04efd8e5b54410c56cca149cb`，均完全一致。

无 PPU 验证结果为 FlagGems 80 passed、Plugin 390 passed、目标模块编译与两个工作树
`git diff --check` 通过。PPU-01 的 16 张卡均被四组无关 TP4 服务占用，本轮没有运行迁移后的
eager/graph 或整模测试，也没有停止这些进程。设计结论为通过，适配完成门禁仍被设备级证据阻塞；
详细影响矩阵、命令位置和后续验证顺序见
`../adaptation/006-flaggems-qwen38-operator-ownership.md`。

## 2026-09-11：FlagGems 通用模块归属复审

FlagGems 当前候选已改为 `support-qwen3.8-flash@4bce4f20fbd589299dc4ebf966b2748d2dff9144`，
父提交是复核时官方最新 `upstream/master@851ba60493692f5c84c5636f9117c53ab1f156ae`。适配仍为
唯一一笔提交，author 和 committer 均为 `ZenithJoyH <1355922182@qq.com>`；GitHub、容器 HEAD 与
跟踪分支已回读一致。

实际产品 diff 不再包含 `src/flag_gems/fused/qwen3_8_flash_next/`。四类 tensor/scalar 实现按算子
语义位于 `qsa.py`、`ple_state.py`、`gdn_packed_decode.py` 和 `common_slot_mapping.py`，并从
`flag_gems.fused` 直接导出；这四个模块中没有 Qwen 或 day-0 文本。Qwen 名称仅保留在 reference
和测试文件，表示已验证的模型输入几何，不参与运行时 dispatch 或模块解析。

整理后的 FlagGems 精确 CPU/reference/validation 用例为 80 passed；Plugin Qwen 与共享 dispatch
回归为 405 passed，Plugin 工作树保持 clean。未运行 PPU eager/graph 与整模，设计审查结论仍为
可作为 PR 候选，设备级验收门禁继续保持 open。证据为远端
`04-runs/flaggems-ownership-organized-20260911.txt`，SHA-256
`ae28fca9410ccae05cfb3fc3d4224ad3ac245c1f457b22e7714ac9094b9d5cf1`。
