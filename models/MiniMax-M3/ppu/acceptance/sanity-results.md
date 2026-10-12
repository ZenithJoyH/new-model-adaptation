# MiniMax-M3 / PPU GPQA sanity 结果

## 结论

`passed`。2026-09-16 经用户确认后，仅将生成策略从随机采样改为确定性 greedy，固定题集仍为 GPQA Diamond 数据顺序前 10 题（`doc_id 0..9`），并以 c10 在同一已验收 graph 服务实例上重跑。固定 manifest verifier 确认 `exact_match,strict-match = 10/10 = 1.0`，样本覆盖 10/10、0 timeout、0 request error，满足 sanity 逐题全正确门禁，可以进入全量 accuracy。

## 受控变更与结果

- 本轮配置：`temperature=0,top_p=1,top_k=-1,max_gen_toks=30000`，并发 10，limit 10，API timeout 7200s，API max retries 3，评测重试 0。
- 固定题目、提示模板、runner、模型服务和 30k 输出上限均未改变；唯一有意变更是确定性 greedy 生成策略。
- 原生 lm-eval 终态：strict-match 1.0、flexible-extract 0.6；固定 manifest verifier 返回 `passed`。
- 阶段 scorer 在 SQLite 最终提交时曾报告一次 schema unavailable；该信息明确不是分数，最终结论只绑定原生 results/samples 与固定 manifest verifier。

## 身份与配置

- Host / 容器：`PPU-13` / `minimaxM3`；评测容器 `flageval_llmeval-jinghao`，host network，`/mnt` 1:1 挂载。
- 服务：graph `FULL_DECODE_ONLY`，TP16，prefix caching 开启，`max_model_len=65536`。
- 服务实例：`ppu13-minimaxM3-7ffdd70d-boot-e0f88877-pid1551482-start219575444-cmd4735fa06`；评测前后身份文件 SHA-256 均为 `bd8ee8232f855ff7cb5cb751ab6dd41cb8843aa0e851ebf20f763f25b5b40fa5`。
- 固定 manifest：`doc_id 0..9`，SHA-256 `ca36a36fe88ca81556dd8823494095bb5d6d115bf8dfb76287f7f03c0b4ca4c7`；Arrow SHA-256 `501f307f9e8bc34041af4120c8eb5a735f0ea29cd83c90167b913651071bb4c4`。

## 远端证据

- run root：`/mnt/nfs/users/jinghao/minimaxM3/04-runs/minimax-m3-gpqa-sanity-first10-greedy-c10-20260916-01/`。
- sanity receipt SHA-256：`ad18eec6ac44bc25f8feb576ebb1483f387f0d7233ed10f3a9a1ee61b2e78881`。
- verifier log SHA-256：`84973bb1895a397a4d02df1cbb02a7b6a73fa5757b3306bc08baf441e4b0a2c7`。
- 原生 results SHA-256：`7647845bbb609a67b071b20f1d17a38673adb43130e6252640899cc826fb84f8`。
- 原生 samples SHA-256：`3adc16b44f8139a50d75690457562e7edfd9498b03b93e049064a47153e41a53`。
- versioned runner/config/manifest bundle hash 清单 SHA-256：`8a5fc98fc27e3e6b43ca9fd2ef633ce278e8d7c787708f40f474cc9d2f9b6f91`。

## 历史失败边界

同一服务此前以 `temperature=1,top_p=0.95,top_k=20` 运行固定十题时为 9/10，`doc_id=8` 生成满 30,000 token 后答错。该失败证据继续保留在 `/mnt/nfs/users/jinghao/minimaxM3/04-runs/minimax-m3-gpqa-sanity-first10-c10-20260915-02/`，不被本轮覆盖；本轮是经用户授权、重新冻结生成策略后的独立受控运行。
