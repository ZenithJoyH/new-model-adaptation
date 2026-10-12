# 014：BF16 Indexer top-k 调度归属收敛

## 元数据

- 状态：`verified_focused`
- 首次出现时间：2026-09-07
- 最后验证时间：2026-09-07
- 模型：Hy4-preview W8A8
- 平台与 Host 别名：T-Head PPU / `PPU-07`
- 容器：`hy4`
- 执行模式：eager 与 graph

## 问题现象

`bf16_indexer_topk` 当前作为独立公共 dispatch 点，但语义上属于 BF16 Indexer
生成 Sparse MLA 候选 indices 的内部阶段。它不是 `mla_prefill` 或 attention backend
执行的注意力计算；后两者只消费已经生成的 indices。过细的公共 dispatch 会扩大注册、
配置和跨平台维护面。

## 已有经验匹配

与 [007](007-mla-helper-ownership-ppu07-20260904.md) 相同之处是需要按唯一调用者收敛
helper 所有权；差异是 top-k 属于 Indexer，而 concat/cache helper 属于 attention backend。
在确认实际调用者前结论保持为假设。

## 诊断与假设

- 假设：若唯一产品调用者为 BF16 Indexer backend，应删除独立注册/YAML/public proxy，
  由 FlagGems 与 T-Head BF16 Indexer backend 各自在内部调用对应实现。
- 排除方向：不把 decode Indexer top-k 放入 `mla_prefill`；不让 attention backend
  反向拥有候选生成逻辑。
- 需验证：FlagGems/reference/T-Head 的实际调用图、graph custom-op 边界、共享模型调用者
  和显式 vendor fallback 行为。

## 选定方案

- 将 decode Indexer 收敛为单一公共契约 `bf16_indexer_decode`：后端负责
  paged logits、按有效序列长度 top-k，以及恢复按 logit 降序的最终 indices。
- `bf16_indexer_cache_write` 仍保持独立；它是 KV/indexer cache 的写入副作用阶段，
  不属于 decode 候选生成。
- FlagGems backend 实现完整 graph-safe 契约，内部调用
  `bf16_paged_mqa_logits` 和 `top_k_per_row_decode`。reference backend 只提供 eager
  正确性回退。
- T-Head 不注册缺少 paged-logits 原生实现的“半个 Indexer backend”；同时将
  原来共享的 core capability guard 改为校验
  `_C::dynamic_scaled_int8_quant`，避免删除 top-k 后动态量化被错误判定。
- 模型层只组装 Indexer 输入、管理 padding/unpadding 和共享输出 buffer；
  不再理解 backend 内部的候选重排。

## 现场诊断结果

- 唯一产品调用点是 `vllm_fl/models/hy_v4.py` 的
  `_indexer_topk = CachedOp("bf16_indexer_topk")`。
- FlagGems 和 T-Head 的 backend facade、注册项及 `thead.yaml` 配置只是该公共 op 的
  两套实现/选择层；未发现其他模型、`mla_prefill` 或 attention backend 调用者。
- FlagGems 实现最终调用 `flag_gems.fused.top_k_per_row_decode`；T-Head 实现最终调用
  `torch.ops._C.top_k_per_row_decode`。两者的接口契约可由各自 BF16 Indexer backend
  内部保持，不需要继续暴露独立公共 dispatch。
- 当前 FlagGems 是用户修改后的 clean
  `sparse-mla-opt@717a9ef60d38b559d8b4424488ca5cad2fe61a59`；Plugin dirty 基线与
  vLLM clean 基线均已保存，设备空闲且无服务进程。

## 实施结果

- `vllm_fl/models/hy_v4.py` 仅保留 `CachedOp("bf16_indexer_decode")`；
  padding/unpadding 和最终共享 buffer copy 仍属于模型适配器。
- FlagGems facade/register 只对外提供 `bf16_indexer_decode`，实现内部依次
  调用 `bf16_paged_mqa_logits`、`top_k_per_row_decode` 和候选降序重排。
  原来两个 public op 仅剩 backend-private helper，不再进入 dispatch 名单。
- reference backend 实现完整 eager 契约，并修正 `next_n > 1` 且只给最终
  request length 时的逐 token 有效长度展开。
- T-Head 删除独立 Indexer top-k facade/register/native wrapper；原生 SO 中的 schema
  仍可供其他内部用途，但不伪装成完整 BF16 Indexer backend。动态 INT8 量化
  capability guard 现在校验它真正调用的 `_C::dynamic_scaled_int8_quant`。
- `thead.yaml` 现为 `bf16_indexer_decode: [flagos, reference]`，与“先用
  FlagGems 跑通，再引入完整厂商高性能实现”的阶段目标一致。

## 验证证据

- 源码 AST、旧 public op 清理、`git diff --check`、FlagGems/vLLM 版本与
  clean 状态：通过。
- 真实注册表：`bf16_indexer_decode` 仅有 `default.flagos` 和
  `reference.torch`；`bf16_indexer_topk`/`bf16_paged_mqa_logits` 注册为空。
- Hy4 模型 fresh-process 导入：通过。
- Plugin 契约测试：`3 passed`，覆盖 FlagGems 候选排序、reference 变长
  `next_n=2`、FlagGems top-k changed-input graph replay。
- 真实算子组合：`FULL_INDEXER_DECODE_EAGER_OK` 和
  `FULL_INDEXER_DECODE_GRAPH_CHANGED_INPUT_OK`；输入实际经过 paged logits、
  FlagGems top-k 与最终有序重排。
- 一条非失败 warning：当前 Triton backend 无 replay benchmarker，FlagGems
  退回 event timing；不影响本轮数值/graph 结论。
- Plugin 目标文件的修改前备份在
  `/mnt/nfs/users/jinghao/hy4-preview/tmp/bf16-indexer-ownership-20260907/before`；
  一次性复现脚本在同根的 `issues/bf16-indexer-ownership-20260907/`。
- 部署 playbook 再次执行为 `changed=0`，输出
  `unchanged: BF16 Indexer ownership patch already applied`，哈希门控和幂等性通过。
- 本轮 5 个新/更新 playbook 的定向 Ansible syntax-check 全部通过；
  `platform.yml` YAML 解析和 adaptation `--check-only` 通过。仓库级
  `scripts/syntax-check` 另因工作树中已缺失的
  `test/nccl_test/mthreads/mccl_test.sh` 产生 13 项无关失败；
  `audit-workspace` 还报告无关失效链接和历史身份告警，本轮未越界修复。
- 正式 adaptation verification 绑定未伪造：当前
  `environment/deployment-identity.yml` 仍缺 model revision、镜像 digest 和三个仓库的
  tracked/untracked 指纹，因此 `workflow.adaptation` 保持 `in_progress`，并显式记录该门禁。

## 受控命令

```bash
./scripts/playbook models/Hy4-preview/ppu/environment/inspect-ppu07-indexer-topk-ownership.yml --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/inspect-ppu07-indexer-topk-focused.yml --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/inspect-ppu07-indexer-topk-write-set.yml --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/deploy-ppu07-indexer-backend-ownership.yml --limit PPU-07 --check --diff
./scripts/playbook models/Hy4-preview/ppu/environment/deploy-ppu07-indexer-backend-ownership.yml --limit PPU-07 --diff
./scripts/playbook models/Hy4-preview/ppu/environment/verify-ppu07-indexer-backend-ownership.yml --limit PPU-07
```

后续部署和验证命令在执行前追加到本记录。vLLM 必须保持只读，容器不得停启。

## 限制与下一步

聚焦实现与组件回归已通过，但本轮未启动整模型服务，也未做 GPQA 或正式
性能 A/B；因此不将 Plugin 整体适配或平台状态升级为 `optimized`。完整 PR
base 与 inherited dirty/untracked 来源仍需在提交前独立审计。
