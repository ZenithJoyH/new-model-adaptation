# GPQA 19 个截断样本 40K 定向重跑

状态：`running`。本轮于 `2026-09-07 10:28:26 +0800` 启动；只重跑 2026-09-06 正式全量 GPQA 中达到 30000 completion
tokens 的 19 个样本，用于验证提高生成上限能否恢复自然停止和最终答案；不得把本轮结果
拼接进正式 198 题验收成绩。

- 服务实例：`PPU-13:bf3487115c28:1339072:146131942`；graph，TP16，
  `max_model_len=65536`。
- 源样本 SHA256：
  `7477fd810474f782c6a82517402ae4eb91d76eb1725b3efa9bb94b9f205dec46`。
- doc_id：`8,15,32,47,48,64,71,76,81,88,94,127,130,145,147,162,170,185,194`。
- 并发：19（全部目标同时提交）；`max_tokens=40000`；单请求客户端上限 14400 秒。
- 输出目录：
  `/mnt/nfs/users/jinghao/glm5.3-flash/runs/graph-65k-40k-20260907-v2/targeted`。
- 成功条件：19 个请求均 HTTP 200，结束后服务 health 200。`natural_stop`、仍被 40K
  截断数、答案匹配数和重复度是诊断结果，不通过包装器退出码伪装。

只有同一实例的新 65K sanity 已通过，且目标目录/控制文件从未使用时，才运行以下命令：

```bash
./scripts/syntax-check models/GLM-5.3-Flash-BF16/ppu/acceptance/trigger-ppu13-gpqa-truncated19-40k.yml
ansible-playbook -i inventory/hosts.yml models/GLM-5.3-Flash-BF16/ppu/acceptance/trigger-ppu13-gpqa-truncated19-40k.yml --check --diff
ansible-playbook -i inventory/hosts.yml models/GLM-5.3-Flash-BF16/ppu/acceptance/trigger-ppu13-gpqa-truncated19-40k.yml
```

运行期只读状态命令；`progress.json` 是阶段进度，不作为正式全量成绩：

```bash
ssh PPU-13 'run=/mnt/nfs/users/jinghao/glm5.3-flash/runs/graph-65k-40k-20260907-v2; cd "$run" && test "$(pwd -P)" = "$run"; date "+%F %T %z"; test -f targeted.done && echo EXIT=$(cat targeted.done) || echo RUNNING; test -f targeted/progress.json && python3 -c '\''import json; d=json.load(open("targeted/progress.json")); print({k:d.get(k) for k in ("elapsed_seconds","completed","http_success","natural_stop","length_capped")})'\''; curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null && echo HEALTHY'
```

完成后仅输出结构化汇总和哈希，不打印模型回答或 reasoning 正文：

```bash
ssh PPU-13 'run=/mnt/nfs/users/jinghao/glm5.3-flash/runs/graph-65k-40k-20260907-v2; cd "$run" && test "$(pwd -P)" = "$run"; test "$(cat targeted.done)" = 0; sha256sum targeted/result.json targeted/exit.json; python3 -c '\''import json; d=json.load(open("targeted/result.json")); print({k:d.get(k) for k in ("status","elapsed_seconds","request_count","http_success","natural_stop","length_capped","failed","label_matches_target","health_after")})'\'''
```

启动后首个检查点为 `RUNNING`、服务 health 200；尚无已完成响应。Codex heartbeat
`glm5-3-40k` 每 15 分钟只读检查本轮，在有意义进展、完成或故障时通知。
