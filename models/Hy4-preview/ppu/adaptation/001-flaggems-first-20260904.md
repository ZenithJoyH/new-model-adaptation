# FlagGems 优先策略切换

日期：2026-09-04。目标：PPU-07 / `hy4`，插件 `/workspace/vllm-plugin-FL-hy4-preview`，分支 `support-hy4-preview`，HEAD `11848598449f6d650df64170db4187c387361ce5`，保留原有 dirty 工作树。

## 范围及原因

用户要求先基于 FlagGems 建立正确性基线，再逐项尝试厂商高性能实现。原配置虽为 `prefer: flagos`，但 8 项独立顺序覆盖使 attention、Indexer cache/top-k、动态 INT8、MoE align/sum/topk/grouped_topk 优先 vendor。

仅修改插件 `vllm_fl/dispatch/config/thead.yaml`：把上述顺序调整为 FlagGems 首位，其他候选顺序保留；保留黑名单、`strict: false`、厂商注册及原生实现。没有新增/选择新的 FlagGems 算子实现，仅切换已经集成的实现优先级；未更新 FlagGems 依赖。此策略不是“只允许 FlagGems”，运行失败仍可能走已有 fallback，整模型验证必须检查实际调用与回退日志。

## 环境及边界

- vLLM 0.24.0+empty，源码 `/workspace/vllm`，HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`，前后 clean。
- FlagGems `/workspace/FlagGems`，master，HEAD `60d043094d0217cad75528cb0e47a606c87ab1e4`，前后 clean。
- 精确镜像身份及已核实环境见[环境分析](../environment/environment-analysis.md)。本轮未替换容器镜像。
- 当前服务模型 `/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`（本轮未变更权重，未新核实权重 revision）。API PID `2084145`，进程 starttime 前后不变。
- 命令：`vllm serve /mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/ --served-model-name hy4 --host 0.0.0.0 --port 8010 --trust-remote-code --reasoning-parser hy_v4 --load-format safetensors --tensor-parallel-size 16 --max-model-len 50000 --max-num-batched-tokens 1024 --gpu-memory-utilization 0.85 --compilation-config '{"cudagraph_mode":"FULL_DECODE_ONLY"}'`。
- 未发现服务有覆盖分发顺序的 `VLLM_FL_CONFIG` / `VLLM_FL_PER_OP` / `VLLM_FL_PREFER` 环境设置；只发现已有无效的 SAFE_DETOKENIZER 设置，未改启动脚本。
- 插件全部已有 Python 源文件哈希前后不变。服务与容器未停止或重启；运行服务尚未重载配置。未提交或推送。

## 复现与验证

命令（管理仓库根目录）：

```bash
./scripts/connectivity-check --limit PPU-07
./scripts/playbook .local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-flaggems-first.yml
./scripts/playbook .local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-flaggems-first.yml
```

部署先核实 YAML 哈希、依赖状态及进程身份，再备份并替换唯一文件，测试失败自动恢复原配置。容器内修改使用 command，不能用 Ansible check 模式验证实际执行，采用哈希门禁和部署后断言。原文件备份：`/tmp/hy4-flaggems-first-NOKtPanv/thead.before.yaml`。

最终 YAML SHA256：`47168bb5e82bd32fcbe5a3e5adc2eeecc0e5957a0d2f6aa6dfb5ea0c1b743c8e`。

- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_flaggems_first_policy.py`：13 个 per-op 配置全部解析为 `default.flagos`；sparse MLA backend 为 `vllm_fl.dispatch.backends.flaggems.impl.mla_sparse.MLASparseFLBackend`，模块导入成功；显式 `vendor:thead` 选择仍有效，退出 override 后恢复 FlagGems。
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_w8a8_boundary_necessity.py`：固定 seed=20260904，BF16 输入 `[8,128]`，INT8 权重 `[128,64]`，FP32 scale `[64]`；现有 W8A8 wrapper fullgraph（backend=eager）及变更输入的 CUDA graph replay 与 eager 精确一致。
- unwrapped 对照仍无法 fullgraph；本轮首先遇到插件 policy `ContextVar.get` 的 Dynamo 限制，并非新 FlagGems 算子错误。保留现有 wrapper，不改实现。
- `./scripts/syntax-check`、专用 playbook syntax-check、`git diff --check` 通过。PPU-07 changed，failed=0，unreachable=0。

## 尚未验证

本轮仅配置切换及聚焦回归，不等同于所有算子 eager/graph 数值验收或整模型重新跑通。尚需用新配置重启当前适配服务后做增量验证，检查 sparse MLA、Indexer、MoE 实际执行及 fallback，再建立端到端基线。性能没有重新测量，不宣称比 vendor 更快；已有黑名单和原生 SO 预加载依赖仍保留。
