# Hy4-preview 重启服务 sanity 与 GPQA 80K 启动记录

## 范围与身份

- 日期与 Host：2026-09-08，`PPU-07`。
- 模型容器：`hy4`，container ID `550e93f0ba4c3109f05002d3a39c55d10c42eee13d661f3062757d9505535ca2`，
  image ID `sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f`。
- 评测容器：`flageval_llmeval-jinghao`，container ID
  `b0147718f168aa81f9181b2e7854126b2cfc9f3bf22411396bfbb8e7906c5b30`，image ID
  `sha256:bcefa10b9be062ed449ac1e7b7925fa4f9a46e1361fbb25cc6e99616bc59a4f5`。
- 主机与两个容器中的批准根均解析为 `/mnt/nfs/users/jinghao/hy4-preview`，三处 `stat`
  device/inode 均为 `41:21477849219`。
- 当前服务实例：`PPU-07:550e93f0ba4c:2724059:155832651`；served model `hy4`，TP16，
  最大上下文 100,000，端口 8010，`FULL_DECODE_ONLY` graph。
- FlagGems / Plugin / vLLM revision：
  `bca444b8569294e7d4e4deff7ddfec7f05682033` /
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`。FlagGems 与 vLLM clean；Plugin 保留既有
  `PROVENANCE.md` 删除和 `thead.yaml` 修改，本轮未覆盖。

## 重启后阶梯 sanity

保持服务 revision 与 graph 配置不变，依次增加短请求并发；每级均要求所有算术响应严格正确、
`finish_reason=stop`、服务健康且新增日志中没有 EngineCore fatal、RPC timeout、SQLite 锁、
bool slice、OOM 或非法内存错误。

| 并发 | 结果 | 耗时 | 抢占 | 远端证据与 SHA-256 |
|---|---:|---:|---:|---|
| 8 | 8/8 | 25.6828 秒 | 0 | `/mnt/nfs/users/jinghao/hy4-preview/05-runs/graph-sanity-hy4-restarted-20260908-1655/graph-sanity-result.json`，`16701af185b5b5e6eef88eb8152a89232676d509f2cf1401c3d08233c973330d` |
| 16 | 16/16 | 28.2953 秒 | 未触发错误 | `/mnt/nfs/users/jinghao/hy4-preview/05-runs/stability-c16-hy4-restarted-20260908-1700/probe-result.json`，`ba8c89ab1f5199c1930b5d5f312f343a6d6e1d6699835aed5e991a4a86f44eba` |
| 32 | 32/32 | 69.7900 秒 | 0 | `/mnt/nfs/users/jinghao/hy4-preview/05-runs/stability-c32-hy4-restarted-20260908-1700/probe-result.json`，`149f6ebc9ecb532a637e674e2a4e0bd443da36fbb6b342c965bff995a2c10af3` |

c8 是本轮正式 accuracy 的前置 sanity；c16/c32 是问题 018 的阶梯诊断。短请求通过不能单独
排除长输出、近满 KV 与 preemption/recompute 组合触发的 1800 秒超时。

## 全量 GPQA 80K

- 状态：`running`；本记录不把启动成功当作精度通过。
- 数据集：离线缓存 `Idavidrein/gpqa` / `gpqa_diamond` / `train`，preflight 验证 198 条。
- Runner：规定的 `test/Accuracy_test/llmrun.py`，远端 SHA-256
  `05ba9891380952bb0e49b0d2963c5ca01dea70f0370c9ad1da5a55205a52ea1f`，与本地公共 runner 一致。
- 参数：graph、全量、并发 32、`reasoning_effort=high`、`temperature=0.9`、`top_p=1`、
  `top_k=-1`、`max_gen_toks=80000`、每请求 timeout 43,200 秒、0 个历史响应缓存命中。
- 配置：`/mnt/nfs/users/jinghao/hy4-preview/04-acceptance/gpqa-full-graph-c32-high80k-t09-20260908-1710/llm_config.json`，
  SHA-256 `baf49806696d357f3ea191c6bd1a7b0584fe15d6b2c3615d4ab16ac2e77ff549`。
- preflight：
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/gpqa-full-graph-c32-high80k-t09-20260908-1710/preflight.log`，
  SHA-256 `18a4639a3db74c8e4655a143516983563927897212f8fa8307adfef9e7f0fcc9`。
- 运行目录：
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/gpqa-full-graph-c32-high80k-t09-20260908-1710/`。
- 响应缓存：
  `/mnt/nfs/users/jinghao/hy4-preview/07-cache/lm_eval/gpqa-full-graph-c32-high80k-t09-20260908-1710/`。
- 评测容器 runner PID：`16077`；其子进程已进入 `lm_eval` 的 198 请求阶段。
- 启动后快照：27 running、5 waiting、KV usage 2.6320%、0 preemption、2476 prompt tokens、
  3348 generation tokens；模型 health 200，新增服务日志无上述致命错误。

验收契约要求 198 个样本完整结束、`allow_timeouts=false`，并记录 strict 指标。用户尚未提供业务
精度阈值，因此配置中的 minimum 为 0，仅用于约束指标存在和范围；即使运行完整，也只能报告实际
分数和零无效响应结果，不能据此宣称达到未定义的业务阈值。正式性能测试保持 `not_started`。

## 生命周期与限制

- 服务由用户在本轮前重启；本轮没有停止或重启模型服务，也没有停止、重启或删除任何容器。
- 本轮只新增批准根下的 `03-issues/` 诊断工具、`04-acceptance/` 配置、`05-runs/` 证据和
  `07-cache/` 独立缓存；没有修改 Plugin、FlagGems 或 vLLM。
- 最终结果需等待远端 `acceptance-result.json`、result/sample 文件、198 唯一样本数、timeout、
  服务健康和分数全部核验后再更新；当前不得标记 accuracy passed 或启动 performance。
