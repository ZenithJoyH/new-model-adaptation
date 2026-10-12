# PPU-07 T-Head 原生 sparse MLA backend 重构

日期：2026-09-03  
目标主机：`PPU-07`  
容器：`hy4`  
插件工作树：`/workspace/vllm-plugin-FL-hy4-preview`  
插件分支/基线：`support-hy4-preview` / `11848598449f6d650df64170db4187c387361ce5`

## 结论

已将 T-Head sparse MLA backend 从“继承 FlagGems backend，并对 H=4 调用插件自有 Triton”重构为“直接继承 vLLM sparse MLA 控制流，仅用平头哥 `flash_mla` 原生扩展执行 sparse attention”。旧的 `vendor/thead/impl/sparse_mla_h4.py` 已从插件工作树移除。

这次修改尚未启动完整模型服务，因此结论限于静态边界、dispatch、数值、eager 和 graph 聚焦测试；端到端 graph capture、生成正确性及性能仍待后续服务验收。

## 修改边界

- `vendor/thead/impl/mla.py`
  - 直接继承 vLLM `FlashMLASparseBackend` / `FlashMLASparseImpl`，不再继承 `MLASparseFLBackend` / `MLASparseFLImpl`。
  - `_bf16_flash_mla_kernel` 直接调用平头哥 wheel 的 `flash_mla.flash_mla_sparse_fwd`。
  - 删除 4→64 head padding；原生 H=4 已实测支持。
  - vendor 文件不再 import FlagGems，也不包含插件自有 Triton 实现。
- 删除 `vendor/thead/impl/sparse_mla_h4.py`。删除前内容已备份到容器内 `/tmp/codex-hy4-native-sparse-mla-backup-20260903/sparse_mla_h4.py.removed`。
- 将 `concat_mla_q` 和 `mla_kv_cache_update` 建模为独立 dispatch op：
  - `default.flagos` 分别调用 `flag_gems.cat_out` 和 `flag_gems.concat_and_cache_mla`；
  - `reference.torch` 提供 PyTorch fallback；
  - T-Head vendor attention 类只调用通用 dispatch，不直接依赖 FlagGems。
- `thead.yaml` 固定 `attention_backend: vendor → flagos → reference`，两个辅助 op 使用 `flagos → reference`。

## 为什么 cache write 不能直接继承 vLLM

容器中的 vLLM `_C_cache_ops.concat_and_cache_mla` 未注册，独立调用报错：

```text
AttributeError: '_OpNamespace' '_C_cache_ops' object has no attribute 'concat_and_cache_mla'
```

进一步检查 `flash_mla==2.0.0+v0.1.0.ppu2.1.0`：公开接口只有 `flash_mla_sparse_fwd`、`flash_mla_with_kvcache` 和 `get_mla_metadata`；原生扩展公开 `sparse_prefill_fwd`、`fwd_kvcache_mla` 和 `get_mla_metadata`，没有主 MLA KV-cache 写入 API。因此 cache write 作为与 attention 解耦的 FlagOS dispatch op 保留，而不是伪装成 T-Head 原生实现。

## 验证结果

执行：

```bash
.venv/bin/ansible-playbook .local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/run-ppu07-thead-native-sparse-mla-integration-test.yml
.venv/bin/ansible-playbook .local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/verify-ppu07-thead-native-sparse-mla.yml
```

结果：

- `STRUCTURE_OK`：vendor 文件不存在 `flag_gems`、`MLASparseFL` 或 `sparse_mla_h4` 依赖，旧 Triton 文件已移出工作树。
- dispatch：`attention_backend=vendor.thead`，`concat_mla_q=default.flagos`，`mla_kv_cache_update=default.flagos`。
- 两个辅助 op：eager 和 graph capture/replay 均通过。
- 原生 sparse MLA：BF16、H=4、D=576、V=512、top-k=2048、带 sink 和 `topk_length`，数值参考对齐通过；eager 和 graph replay 均通过。
- Python AST/import 和 `git diff --check` 通过；容器没有安装 `ruff`，因此未执行 ruff。
- `/workspace/vllm` 保持 clean，revision 为 `ee0da84ab9e04ac7610e28580af62c365e898389`。
- `/workspace/FlagGems` 保持 clean，revision 为 `60d043094d0217cad75528cb0e47a606c87ab1e4`。
- 模型服务保持停止，`SERVICE_MATCHES []`；容器没有停止或重启。

## 风险与下一步

- 插件基线原本就是 dirty worktree，且本地分支比 `origin/support-hy4-preview` 落后 1 个提交；本轮只覆盖已锁定校验和的 6 个文件并移除 1 个自有 Triton 文件，未拉取、提交或丢弃其他修改。
- 尚未验证完整模型初始化、全量 decode graph capture、单请求生成、8 并发 sanity 或性能收益。
- 后续启动前应先重新核对实际启动脚本指向本工作树，然后按“导入 → 最小服务 → graph capture → 正确性 → 8 并发性能”顺序验收。
