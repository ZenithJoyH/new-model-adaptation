# 当前提交全量 GPQA（2026-09-10）

## 状态

已完成，accuracy 未通过。本轮用于验证已经发布的 Plugin 与 FlagGems 提交；在 2026-09-11
迁移到 compact 记录并完成 adaptation 绑定后，当前 execution-mode 与 sanity 证据可重新绑定，
但失败的 accuracy 不能生成通过凭据。

## 绑定现场

- 主机：`PPU-13`（`bm-aliyun-wlcb-zonea3-c-810e-96g-10-13`）。
- 容器：`glm5.3-flash`，ID
  `bf3487115c28f4ac45b34667ce7f3853a3eaa9879b54715a6cde5e2bc81ca6b1`，运行中，
  restart count 为 0。
- Plugin：`ZenithJoyH/vllm-plugin-FL` 的 `support-glm5.3-flash`，revision
  `db09b64afdc222d1c32e4e80f30820a243358e34`；容器 editable import 指向
  `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`，工作树 clean。
- FlagGems：`ZenithJoyH/FlagGems` 的 `support-glm5.3-flash`，revision
  `4a3cba029d87ec06b5222ed94542f1f1d2e267a0`；容器 editable import 指向
  `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems`，工作树 clean。
- 服务：`FULL_DECODE_ONLY` graph、TP16、`max_model_len=65536`、
  `max_num_seqs=32`、端口 8010；health 200，16/16 worker。进程环境中不存在旧的
  FlagGems ATen blacklist。
- 最终 launcher：host/container 均为
  `/mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh`，SHA-256
  `5d54dacc5f5af26bd3e4847aad85ae4575b98d7072093aa21ad2ed550b4534ba`。

## 前置验证

- FlagGems 数值回归：11 passed；Plugin 聚焦回归：9 passed；六个新增 capability 均实际
  dispatch 到 `default.flagos`。原始证据见
  `/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/flaggems-gap-20260910/`。
- 冷态 c8：8/8 正确、零错误，但新 shape 编译/调优使 415 tokens 用时 55.30 秒，
  7.50 tokens/s，按固定性能门槛保留为失败证据。结果 SHA-256
  `f3511dcd7114e1e6b3413a940bd0aae8111bcc983c066dcb45fbb0ccfe08673e`。
- 相同请求热态复测：8/8 正确、零错误，419 tokens 用时 2.73 秒，153.28 tokens/s，
  通过固定 c8 判据。结果位于
  `/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/glm53-current-commits-preflight-hot-20260910/graph-sanity.json`，
  SHA-256 `065cc5b7fcf7205cf74f21b2beacae6317354f50429e987d3d68c70abe49e4bf`。

## 全量配置与运行

- 数据集/任务：GPQA Diamond `gpqa_diamond_generative_cot`，全量 198 题。
- 并发：32；生成配置：`temperature=1,top_p=0.95,max_gen_toks=60000`；客户端单请求
  timeout 14400 秒，API retries 3，eval retries 0。
- 准确率口径：`exact_match,strict-match`，目标 0.88；同时要求 198 个唯一题目且没有
  timeout/无效响应。
- 配置：
  `/mnt/nfs/users/jinghao/glm5.3-flash/03-acceptance/glm53-current-commits-20260910/llm_config_c32_60k.json`，
  SHA-256 `58a61a6c69fabe2eab9f783f7b22db196faeb019b72fac98158c2e8c603ad4fb`。
- 运行目录：
  `/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/glm53-gpqa-full-current-c32-60k-20260910-2125/`。
- cache：
  `/mnt/nfs/users/jinghao/glm5.3-flash/06-cache/glm53-gpqa-full-current-c32-60k-20260910-2125/`。
- runner：host PID `3368412`，于 2026-09-10 21:23:15 +08:00 启动。
- 启动预检：数据集 198 条、模型 ID `glm5.3-flash`、服务 HTTP 200；日志 SHA-256
  `7698cca72cf56d5e96e84c37ee806de3be0d6aabbe3e558f4945e0eb6ae1576d`。

## 最终结果

- 运行结束时间：2026-09-11 05:17:07 +08:00；runner 已正常退出，lm-eval 本身返回 0，
  runner 因不允许无效响应而将任务判定为 failed。
- `exact_match,strict-match=0.8686868686868687`，即 172/198（86.87%）；88% 门槛需要
  至少 175/198，当前少 3 题。
- 样本文件共 396 行（strict/flexible 各一行），对应 198 个唯一 `doc_id`，全量覆盖完整。
- 10 个唯一无效样本为 doc_id `8,15,32,71,88,94,102,130,145,147`；它们的
  `completion_tokens` 全部精确为 60000，API 返回 `finish_reason=length`、reasoning 非空而
  content 为空，随后被 runner 转成 `<TIMEOUT>`。这不是 14400 秒客户端 timeout，也不是
  1800 秒 vLLM RPC timeout。
- 非截断的 188 题中 strict 正确 172 题（91.49%）；该条件分数不能替代全量 198 题的
  正式分数。
- 评测结束后模型服务仍为 health 200、16/16 worker，容器 running/restart 0；本轮未出现
  EngineCore、worker、非法访存或数据库锁致命错误。

原始产物：

- result JSON：SHA-256
  `bd08bf514a1df57922d3eba84da84cbe4a461e333ffccc7e08db7ad28dc3ae24`。
- samples JSONL：SHA-256
  `5950c67b7221e6eabccc1ee134d02b35889bda2dc153b027b756ecb8fb37a19e`。
- runner log：SHA-256
  `050c0ef37fc06e06bb80958683d376fcc159b6c3577feb5d398ad909e024b5a1`。

结论：本轮证明当前提交能够稳定完成全量 GPQA 负载，但 accuracy/零无效响应门槛未通过；
适配阶段可按 `functional` 完成，不能标为 `optimized`，acceptance accuracy 继续为 failed。
