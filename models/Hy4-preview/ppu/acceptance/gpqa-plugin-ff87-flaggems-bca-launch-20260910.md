# Hy4-preview Plugin/FlagGems 同步版 GPQA 全量启动记录

## 身份与服务

- Host：`PPU-07`；服务容器：`hy4`；评测容器：`flageval_llmeval-jinghao`。
- host root 与两个容器中的对应路径均为
  `/mnt/nfs/users/jinghao/hy4-preview`，已用设备号/inode 核对为同一 RW 映射。
- Plugin：`ff87b683ec9c6c1925dbedf12261914e45569b52`，工作树 clean。
- FlagGems：`bca444b8569294e7d4e4deff7ddfec7f05682033`，工作树 clean；这是包含当前
  W8A8 MoE 分类修复的跟踪分支最新提交。官方 master 的更新不含该修复，未用它覆盖功能分支。
- vLLM：`ee0da84ab9e04ac7610e28580af62c365e898389`，工作树 clean。
- 服务为 TP16、100K context、`FULL_DECODE_ONLY` graph、
  `--max-num-batched-tokens 2048`；launcher SHA-256
  `0184b7cd0a768a9d2b173d26dca3636ddf3389e0ba7ff8f2f5aedcdfdca2a4f1`。
- 新服务完成 131/131 权重加载和 51/51 graph capture，API PID 2254555、EngineCore PID
  2255041，启动后 `/health=200`。只终止了此前已核实空闲的 Hy4 API；没有停止或重启容器。

## 前置验证

Plugin、FlagGems 与 vLLM 的聚焦测试合计 31 passed。固定 8 条 GPQA 高风险输入、c8、
thinking/high、temperature 0.9、max tokens 2,048 的 graph sanity 在 643.318 秒完成：8/8
HTTP 200、失败 0、runner exit 0；终态 0 running、0 waiting、health 200，无 EngineCore fatal、
worker died 或 RPC timeout。证据目录：
`/mnt/nfs/users/jinghao/hy4-preview/04-runs/gpqa-sanity-c8-pluginff87-fgbca-20260910/`。

## 全量评测

- 数据集：离线 `Idavidrein/gpqa` / `gpqa_diamond` / `train`；preflight 严格为 198 条，
  服务模型列表包含 `hy4`。
- 参数：全量 198 题、并发 64、thinking/high、temperature 0.9、top-p 1、top-k -1、
  `max_gen_toks=80000`、单请求 timeout 43,200 秒、API retry 3、评测 retry 0、
  `allow_timeouts=false`。
- 配置：
  `/mnt/nfs/users/jinghao/hy4-preview/03-acceptance/gpqa-full-graph-c64-high80k-pluginff87-fgbca-20260910/llm_config.json`。
- 运行与结果根目录：
  `/mnt/nfs/users/jinghao/hy4-preview/04-runs/gpqa-full-graph-c64-high80k-pluginff87-fgbca-20260910/`。
- 缓存：
  `/mnt/nfs/users/jinghao/hy4-preview/06-cache/lm_eval/gpqa-full-graph-c64-high80k-pluginff87-fgbca-20260910/`。
- 2026-09-10 13:37 +08:00 启动，评测容器 runner PID 21634。首批观测为 11 running、
  53 waiting、KV 约 0.9%、preemption 0、health 200，无 fatal。

用户未指定业务准确率阈值，因此配置中 `minimum=0` 只验证指标存在、取值合法和 receipt 生成，
不能据此声明模型精度达到业务要求。最终结论必须等待 runner exit、198 个唯一样本、零 timeout/
无效项、实际 strict-match 分数与服务终态全部核验后更新。
