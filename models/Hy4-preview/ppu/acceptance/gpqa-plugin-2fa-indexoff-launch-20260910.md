# Hy4-preview Plugin 2fa / index 黑名单版 GPQA 全量启动记录

## 身份与服务

- Host：`PPU-07`；服务容器：`hy4`；评测容器：`flageval_llmeval-jinghao`。
- host root 与两个容器的对应路径均为 `/mnt/nfs/users/jinghao/hy4-preview`，已核对为同一
  RW 映射。
- Plugin：`2fa5f1816fe0e9a08fd66f515c5de28e9c8199e2`；该提交是原部署版本
  `497cd7cc7a36b67ffd200e0ee4e4003d2f95706c` 的单提交 fast-forward。工作树仅保留经授权的
  `vllm_fl/dispatch/config/thead.yaml` 修改，用于将通用 FlagGems `index` 留在 T-Head
  blacklist；配置 SHA-256 为
  `85e0dbe54884c77bc6109b4b54dee643bd273f02377e9055d9dd892089d37ff7`。
- FlagGems：`bca444b8569294e7d4e4deff7ddfec7f05682033`；vLLM：
  `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 服务为 TP16、100K context、`FULL_DECODE_ONLY` graph、
  `--max-num-batched-tokens 2048`。launcher SHA-256 为
  `6bf2e151423f65f860d6f7e45e164e29ee99ca0de656cdd32150cf6bffd02748`；API PID
  467407、EngineCore PID 467899。服务完成 51/51 graph capture 后 `/health=200`；只终止了
  已核实的旧 Hy4 服务进程，没有停止或重启容器。

## 前置验证

Plugin 聚焦 UT 共 19 passed，覆盖 BF16 indexer 后端职责、top-k-per-row、T-Head native
extension 和 Hy4 模型回归。日志：
`/mnt/nfs/users/jinghao/hy4-preview/04-runs/plugin-2fa5f18-focused-tests-20260910/focused-tests.log`。

同一服务上的固定 8 条 GPQA graph sanity 使用 c8、thinking/high、temperature 0.9、
max tokens 2,048，在 430.375 秒完成：8/8 HTTP 200、失败 0、runner exit 0；共生成 11,819
tokens，终态 health 200、0 running、0 waiting、0 abort/error，未发现 EngineCore fatal。
证据目录：
`/mnt/nfs/users/jinghao/hy4-preview/04-runs/gpqa-sanity-c8-plugin2fa5f18-indexoff-20260910/`。

## 全量评测

- 数据集：离线 `Idavidrein/gpqa` / `gpqa_diamond` / `train`；preflight 为 198 条，服务模型
  列表包含 `hy4`。
- 参数：198 题、并发 64、thinking/high、temperature 0.9、top-p 1、top-k -1、
  `max_gen_toks=80000`、单请求 timeout 43,200 秒、API retry 3、评测 retry 0、
  `allow_timeouts=false`。
- 配置：
  `/mnt/nfs/users/jinghao/hy4-preview/03-acceptance/gpqa-full-graph-c64-high80k-plugin2fa5f18-indexoff-20260910/llm_config.json`。
- 运行目录：
  `/mnt/nfs/users/jinghao/hy4-preview/04-runs/gpqa-full-graph-c64-high80k-plugin2fa5f18-indexoff-20260910/`。
- 缓存目录：
  `/mnt/nfs/users/jinghao/hy4-preview/06-cache/lm_eval/gpqa-full-graph-c64-high80k-plugin2fa5f18-indexoff-20260910/`。
- 2026-09-10 20:48 +08:00 启动，runner PID 22842。初始观察中 64 个客户端并发全部被
  服务接收为 running 或 capacity waiting；服务 health 200、preemption 0、fatal 0，生成 token
  持续增加。

配置中的 `minimum=0` 只用于校验指标存在和 receipt 结构，不代表业务精度阈值。必须等待 runner
正常退出、198 个唯一样本、零 timeout/无效项、实际 strict-match 分数和服务终态全部核验后，才能
更新正式 accuracy 结论。

## 终态结果

评测于 2026-09-11 19:16:27 +08:00 结束，覆盖 198 个唯一 doc_id；样本文件因 strict 与 flexible
两个过滤器包含 396 行。正式结果的 strict-match 为 0.9090909091（90.91%，超过用户指定的 87%
业务基线），flexible-extract 为 0.4848484848。服务在最后一条请求返回后保持运行，正确端口
`8010` 的 `/health` 于 20:31 +08:00 复核为 HTTP 200；日志末尾为 0 running、0 waiting，未见
EngineCore fatal。

但 doc_id 81 最终被记录为一个唯一 `<TIMEOUT>`（两个过滤器各一行）。由于本轮明确设置
`allow_timeouts=false`，wrapper 判定 result validation failed，runner exit 为 1，且没有生成通过的
`acceptance-result.json`。2026-09-11 用户明确以 strict 90.91% 超过 87% 业务基线为精度通过条件，
并接受该单条 timeout 风险，因此项目状态将本轮记为“用户接受的 accuracy passed”；这不改写
runner 原始失败事实，也不等同于零无效项的原生 receipt 通过。

- result SHA-256：`6c1e8f3ed858fd073133fba33969806410c6ff862d0a8e5d002d4caa82194b64`
- samples SHA-256：`ab06b18f7bc39df507f9ca816cceb51dd9b3daf690725144ae2b4e0cafa76388`
- runner log SHA-256：`a0d57a9a40d8850784207d0be49e3075021a8a7c063bea0a754ff8d489998295`
- exit.code SHA-256：`4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`

本轮与此前服务卡死不同：Plugin `2fa5f18` 加通用 `index` blacklist 的服务完成了全部请求，未发生
RPC/EngineCore 退出。精度子步骤按用户业务判定完成；doc_id 81 和缺失的原生 passing receipt 作为
已接受限制继续保留，后续不得表述为“198/198 零 timeout”。性能是业务顺序中的下一步，但项目
门禁要求 adaptation 先为 complete；用户已纠正要求其保持 `in_progress`，因此本轮不启动正式性能。
