# 013：FlagGems Sparse MLA 小 head 原生支持

## 元数据

- 状态：`resolved_source_and_focused_tests_passed`
- 首次出现时间：2026-09-02
- 最后验证时间：2026-09-07
- 模型：Hy4-preview W8A8
- 平台与 Host 别名：T-Head PPU / `PPU-07`
- 容器：`hy4`
- 执行模式：eager 与 graph

## 问题现象

TP16 下 Hy4 每 rank 只有 4 个 query heads。FlagGems
`flash_mla_sparse_fwd` 当前只允许 `HQ in {64, 128}`，Plugin FlagGems backend
因此将 Q 从 4 heads 补到 64 heads，完成计算后再切回 4 heads。这会产生
多余张量操作、显存和算力开销。

## 诊断与方案

小 head 约束属于 FlagGems 算子契约，不应由 Plugin 持续暴露 padding workaround。
本轮选择在 FlagGems 普通 Triton Sparse MLA kernel 中支持小 HQ：对 head 轴
使用合适的 block size 与边界 mask；TLE 路径仍保持其 64-head 对齐契约。
随后移除 Plugin FlagGems backend 的 4→64 padding，不改 vLLM。

## 实施结果

- FlagGems 普通 Triton 路径新增 `BH=16` 调优候选，并对 Q、sink、output、max
  logits、LSE 的 head 维访问增加边界 mask；H=4 不再要求构造 64-head 输入。
- 64/128-head 对齐且满足既有条件的 TLE 路径未修改；本次只扩展普通路径的
  小 head 能力。
- Plugin `MLASparseFLImpl._bf16_flash_mla_kernel()` 删除 `needs_padding`、
  `q_padded`、64-head sink 扩展和输出切片，直接把真实 H=4 Q 交给
  `flag_gems.flash_mla_sparse_fwd`。FP8 路径未修改。
- FlagGems 与 Plugin 各增加一个归属清晰的聚焦回归文件；过程 patcher 和生产形状
  探针只保存在批准工作根的 `issues/flaggems-small-head-20260907/`，没有放入插件仓库。
- 修改前快照保存在
  `/mnt/nfs/users/jinghao/hy4-preview/tmp/flaggems-small-head-20260907/before/`。

## 受控命令

```bash
./scripts/playbook models/Hy4-preview/ppu/environment/inspect-ppu07-flaggems-small-head-baseline.yml --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/inspect-ppu07-flaggems-small-head-code.yml --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/sync-ppu07-flaggems-small-head.yml --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/deploy-ppu07-flaggems-small-head.yml --limit PPU-07 --check --diff
./scripts/playbook models/Hy4-preview/ppu/environment/deploy-ppu07-flaggems-small-head.yml --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/test-ppu07-flaggems-small-head.yml --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/inspect-ppu07-flaggems-small-head-test-state.yml --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/review-ppu07-flaggems-small-head.yml --limit PPU-07
```

执行变更与测试前核实 `PPU-07` 的实际设备状态、相关服务以及 FlagGems/Plugin
checkout 身份；不停止或重启 `hy4` 容器。

## 验证结果

- FlagGems 新增用例：`3 passed`，覆盖 H=4/H=64、sink、`topk_length`，以及
  H=4 graph replay 变输入；output、max logits 和 LSE 均与 PyTorch reference 对齐。
- Plugin 新增用例：`1 passed`，通过 mock 精确断言传给 FlagGems 的对象仍为
  `(2, 4, 576)`，不存在 4→64 padding。
- 生产形状探针：BF16、H=4、D=576、V=512、top-k=2048，eager 与 graph
  changed-input replay 均通过，输出标识分别为
  `FLAGGEMS_H4_TOPK2048_EAGER_OK` 和
  `FLAGGEMS_H4_TOPK2048_GRAPH_CHANGED_INPUT_OK`。
- FlagGems 与 Plugin `git diff --check` 均通过；vLLM 仍为
  `ee0da84ab9e04ac7610e28580af62c365e898389` 且工作树 clean。
- 远端源文件 SHA-256：FlagGems 实现
  `9dfd6ec17fc58a0f9069b255d3fdcbce113a3b754dbfb873b788709d225a2225`；
  Plugin 实现
  `3bbfb3458fb5d42f12282917faef0aff915b53982b85c4c4ef76305c9dfe2b69`。
- 本地统一检查通过：298 项主测试（1 skipped）、6 项附加测试、50 个
  playbook 与 19 个 shell 入口均通过；审计仍提示既有 deployment identity/
  历史 verification 等待复核，不把警告隐藏为成功。

## GitHub 分支交付

- 目标仓库：`https://github.com/ZenithJoyH/FlagGems.git`。
- 基线：`master@34bd6d68928c8b0039c42987840929da52aa6a62`；该基线目标实现文件
  SHA-256 与 PPU-07 修改前版本一致。
- 新分支：`sparse-mla-opt`。
- 提交：`717a9ef60d38b559d8b4424488ca5cad2fe61a59`
  (`feat: support small-head sparse MLA prefill`)。
- 提交只包含 FlagGems 实现和维护性测试两个文件；没有带入 Plugin、W8A8 分支或
  已重命名的 `dense-mla-opt@dbd96aa`。推送后 `ls-remote` 已核实两个分支 HEAD 独立。
- 未创建 PR；是否发起 PR 仍由用户决定。

## 限制与下一步

本次 H=4 输入不再膨胀到 H=64，但普通 Triton kernel 的最小内部 block 为
`BH=16`，因此仍有被 mask 的 lane；这不是“完全按 4 lane 计算”的最终性能上限。
H=128 的既有 TLE/普通路径未在本轮新测试中重新覆盖，其他平台也未实测。
服务没有启动或重载，尚未完成整模型 graph、精度和正式性能 A/B；不得由单算子通过
推断吞吐提升。Plugin 工作树在本轮前已有大量 inherited dirty/untracked 文件，当前变更
只对上面两个 focused 文件负责，提交前仍须在确认 PR base 后做完整来源审计。
