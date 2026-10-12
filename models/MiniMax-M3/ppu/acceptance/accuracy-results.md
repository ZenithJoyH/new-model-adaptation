# MiniMax-M3 / PPU GPQA Diamond 全量精度结果

> 当前状态：`passed`。当前 redesign 的固定前十题 greedy sanity 已于 2026-09-16 以 10/10 通过；随后 GPQA Diamond 198 题 c64 在同一 65K graph 服务上得到 177/198（89.39%），高于冻结门限 80%。

## 当前运行

- run id：`minimax-m3-gpqa-diamond-full-c64-20260916-01`。
- run root：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/minimax-m3-gpqa-diamond-full-c64-20260916-01/`。
- 运行日志：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/minimax-m3-gpqa-diamond-full-c64-20260916-01/runner.log`，SHA-256 `65e4992123f2a0166968f6d3edd63d122df7fcf86c5f50ac4129222292572537`。
- 配置：全量 198 题、客户端并发 64、graph、`max_model_len=65536`、`temperature=1,top_p=0.95,top_k=20,max_gen_toks=30000`；门禁指标 `exact_match,strict-match`，minimum `0.80`，timeout 保留为错误样本。
- 原生终态收据状态为 `passed`：`exact_match,strict-match = 0.8939393939393939`，`n-samples original/effective = 198/198`，0 timeout、0 refusal，`failed_tasks=[]`、`errors=[]`，attempt 1 返回码 0。
- 原生 receipt：`outputs/minimax-m3-gpqa-diamond-full-graph-c64-current-redesign/minimax-m3-gpqa-diamond-full-c64-20260916-01/acceptance-result.json`，SHA-256 `ef05d52b19020624b4ff9a8bb52fb84ece4240143950db0e3826b2aab37d1d28`。
- results / samples SHA-256：`cea291ffa40ffaea36cd2647b4c56e04b4bbf797a79fc15cc2500f7bf5cfb4e0` / `c5f3b69e558b0ce0f56791933c7c72c26df6324b274e0056e856840e4d60ded6`；source / effective config SHA-256：`823b2160f6d6bc67b96077068deb3acef4f69a367cd2c7d0febb3c05f4d96847` / `a6e01c9275e0c1eda8b9b8d1560d24ff44e485505300929a01eb7ada979142cb`。
- 服务身份：`ppu13-minimaxM3-7ffdd70d-boot-e0f88877-pid1551482-start219575444-cmd4735fa06`；评测前身份 SHA-256 `bd8ee8232f855ff7cb5cb751ab6dd41cb8843aa0e851ebf20f763f25b5b40fa5`，提交后 health 仍为 200。

> 2026-09-16 Git 历史固定：评测时服务加载的是完整 redesign 工作树；随后在不改变工作树字节或运行实例的前提下，将 Plugin 本地分支固定为 `support-minimax-m3@aee54f38580e0b8b3db5ed433663ed5359ca308b`（tree `6fac31e4cdf13f6d31cf4e37b23e1f88ef38d2c0`）。

## 当前结论与指标

`passed`。冻结门禁指标为 `177/198 = 0.8939393939393939`，高于 minimum `0.80` 约 9.39 个百分点；198 个样本全部进入分母，没有 timeout、refusal、runner/request error 或被丢弃样本。非门禁 `flexible-extract` 为 `0.5909090909090909`。

## 历史基线结论

`passed`。在 `PPU-13` 的同一 graph 服务实例上，使用 FlagEval/lm-eval 对 GPQA Diamond 198 题进行 c64 全量评测；冻结门禁指标 `exact_match,strict-match = 178/198 = 0.898989898989899`，高于 minimum `0.80`。198 个唯一题号完整覆盖，0 timeout、0 refusal、0 runner/request error，没有丢弃样本或从分母中排除失败项。

## 历史基线指标与覆盖

| 项目 | 结果 |
|---|---:|
| GPQA Diamond 唯一题目 | 198/198，doc_id `0..197` |
| strict-match | 178/198 = 89.90% |
| strict-match 标准误 | 0.02146973557605533 |
| 冻结门限 | 80.00% |
| 高于门限 | 9.90 个百分点 |
| flexible-extract（非门禁） | 112/198 = 56.57% |
| timeout / refusal | 0 / 0 |
| 原生样本行 | 396：两个 filter 各 198 行 |

## 历史基线身份、配置与并发

- Host / 容器：`PPU-13` / `minimaxM3`；评测容器 `flageval_llmeval-jinghao`，镜像 `harbor.baai.ac.cn/flageval/flageval-llmeval@sha256:ae679b186f9ff5efa092969051285f8d97200fd4dac54fe4e7c23732d1cde615`。
- 服务：`MiniMax-M3`，`http://127.0.0.1:8013/v1/chat/completions`，graph `FULL_DECODE_ONLY`，TP16，prefix caching 开启，`--max-model-len 50000`，`--max-num-seqs 32`。
- 服务实例 ID：`ppu13-minimaxM3-7ffdd70d-boot-e0f88877-pid374998-start216316862-cmd575f2e9b`；运行前后 PID、boot ID、start ticks 与 cmdline SHA-256 均一致。
- 客户端配置并发为 `64`；现场 vLLM telemetry 峰值观察到 `32 running + 32 waiting(capacity)`，与服务端 `--max-num-seqs 32` 一致。原生 receipt 的 `observed_concurrency` 字段为 `null`，实际并发证据按其说明由服务 telemetry 单独记录。
- 生成参数：`temperature=1,top_p=0.95,top_k=20,max_gen_toks=30000`；API timeout `7200s`，最大重试 `3`，任务 attempt `1` 返回码 `0`。
- 数据 Arrow SHA-256：`501f307f9e8bc34041af4120c8eb5a735f0ea29cd83c90167b913651071bb4c4`；任务模板、配置和 `process_docs` SHA-256 分别为 `8b94339a9f47545f44edcbb509ce277e0809057294e162638ed1caccb7be4a9e`、`ce56205939ed9a24bb5dd062e4c68f3936b8f9c8990c63f11fa5e6225f2a554a`、`a43f7a6d142ac7bc6fa1a29418076737903e3dbd0031b58acefcc4100256d8ac`。

## 历史基线远程证据

- run root：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/minimax-m3-gpqa-diamond-full-c64-20260915-01`。
- 原生 receipt：`outputs/minimax-m3-gpqa-diamond-full-graph-c64/minimax-m3-gpqa-diamond-full-c64-20260915-01/acceptance-result.json`，SHA-256 `86a8f7b6f0a971c09e5ffe16a09a7e18dcca31eeb2d7dbda4db2301831f344aa`。
- 原生 results SHA-256：`30650da956480c24f57f796062d743a0dad0896b02e948e686b9b87637fbf2ff`。
- 原生 samples SHA-256：`47aec3ca7549960264f6203186cf88592bf35e198c3892e70dd818dc8b5240e0`。
- source / effective config SHA-256：`37ad03dec5e8856cae7370d22f3dcc4569dd913f076d98db144f0c65bd2ac01e` / `875ccc4a391c2f6f69f21045518e299cc8a9ed26aed053e12db6b022fc5d10ff`。
- service identity before / after SHA-256：均为 `034911dfa7cfffa80d2c6820859ccb20309a1855aa53b11c614fc02314136b26`。
- metrics before / after SHA-256：`342028398fa9bd1aa9929ab6357374704edc0d1ce54eeee099587924730e3312` / `1a4ed4c7817bd609b13ea91a97e559b992192af994c3f6b8c88cab4acb4fc9e9`。

## 结论边界

当前 redesign 的正式 `accuracy` 子步骤已通过。未执行本次未选择的 `performance`、`evidence` 和 `summary`；平台整体保持 `functional` / acceptance `in_progress`，不得据此标记为 `optimized` 或生成最终验收总结。
