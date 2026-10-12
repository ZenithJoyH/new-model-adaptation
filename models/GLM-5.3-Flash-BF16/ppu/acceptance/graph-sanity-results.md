# Graph 并发 8 sanity 结果

## 2026-09-07 65K 新实例执行模式与待执行 sanity

- 主机/容器：`PPU-13` / `glm5.3-flash`；服务实例
  `PPU-13:bf3487115c28:1339072:146131942`，PID `1339072`。
- deployment fingerprint：
  `9531e3e7fd695d477a12f3e02f8363856d02096f09740501154c4d82d61af94b`。
- 已于 `2026-09-07T09:55:35+08:00` 验证 `/health` 返回 200，16/16 worker
  存活；命令行为 TP16、PIECEWISE graph、`--max-model-len 65536`、
  `--max-num-seqs 32`。本节先绑定 execution-mode，不预判 sanity 结果。
- 服务和后续验收由共享锁 worker PID `1089029` 持有；run id
  `glm53-graph65k-targeted40k-v2-20260907`，资源包括 tcp/8010、16 个物理
  PPU 以及 vLLM/plugin/FlagGems 三个 checkout。

本轮 sanity 的可重复控制与核验命令如下；控制文件只能在精确实例、健康状态、锁 worker
以及未使用结果目录均满足时创建：

```bash
./scripts/syntax-check models/GLM-5.3-Flash-BF16/ppu/acceptance/trigger-ppu13-graph65k-sanity.yml
ansible-playbook -i inventory/hosts.yml models/GLM-5.3-Flash-BF16/ppu/acceptance/trigger-ppu13-graph65k-sanity.yml --check --diff
ansible-playbook -i inventory/hosts.yml models/GLM-5.3-Flash-BF16/ppu/acceptance/trigger-ppu13-graph65k-sanity.yml
ssh PPU-13 'run=/mnt/nfs/users/jinghao/glm5.3-flash/runs/graph-65k-40k-20260907-v2; test -f "$run/sanity.done" && cat "$run/sanity.done"; test -f "$run/sanity/result.json" && sha256sum "$run/sanity/result.json"; tail -n 40 "$run/sanity.log" 2>/dev/null || true; curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null && echo HEALTHY'
ssh PPU-13 'result=/mnt/nfs/users/jinghao/glm5.3-flash/runs/graph-65k-40k-20260907-v2/sanity/result.json; python3 -c '\''import json,sys; d=json.load(open(sys.argv[1])); print({"run_id":d["run_id"],"service_max_model_len":d["service_max_model_len"],"concurrency":d["concurrency"],"elapsed_seconds":d["elapsed_seconds"],"health_after":d["health_after"],"passed":d["passed"],"http_success":sum(x["http_status"]==200 for x in d["results"]),"nonempty":sum(x["content_chars"]>0 for x in d["results"]),"max_latency":max(x["elapsed_seconds"] for x in d["results"])})'\'' "$result"'
```

10:25（UTC+8）控制轮退出码为 `0`，服务仍 health 200；结果文件 SHA256 为
`7a247fa8e180c6a292096ab7ed11722b1577d348cb4e13982c90c9c4b628c729`。结构化结果确认
8/8 HTTP 200、8/8 content 非空，`passed=true`；总耗时 569.272 秒，最大单请求延迟
569.263 秒。长延迟对应新 shape 首次 FlagGems/Triton 调优与编译，期间请求持续为 8
running，未见 rank 异常、OOM 或 EngineCore fault；该结果只作正确性 sanity，不作性能结论。


## 2026-09-06 FlagGems SQLite bounded-wait 服务轮

- 服务 PID `951344`；启动脚本、TP16/50K/seq32/PIECEWISE 参数均不变，仅在 `docker exec`
  边界注入
  `FLAGGEMS_DB_URL=sqlite:////root/.flaggems/config_cache/TunedConfig_thead_triton_3_6.db?timeout=1800`。
- 首轮即 8/8 正确、零错误，418 completion tokens，20.34921 秒、20.54134 tokens/s，
  最大延迟 20.34580 秒；19 次 16 卡采样无错误，固定 sanity 判据全部通过。
- 结果：远端
  `/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-flaggems-db-timeout-20260906/result.json`，
  SHA256 `2d6b5b8772f80bbbdf1d78a404d7fab31f719e510066a936bd2d20f33047afcb`。
- 请求后 health 正常、16/16 worker；日志无 `database is locked`、illegal memory access、
  worker exception 或 EngineCore fault。后续两级 spawn 进程内探针确认 EngineCore 与 worker
  的 Python `os.environ` 均继承完整 DB URL；`/proc/<pid>/environ` 在设置进程标题后丢失该项，
  不能作为反证。该结果只验证 c8 已调优 shape，不替代正式 GPQA 的新 shape/c64 验证或
  性能验收。

## 2026-09-06 padded physical slot 根因修复

- 服务：PPU-13 / `glm5.3-flash`，PID `921199`，TP16、50K、seq32，PIECEWISE graph；
  无 probe、无 `PYTHONPATH`、无 `VLLM_FL_CONFIG`，执行超时 1800 秒。
- 首轮冷态：8/8 正确、零错误，418 completion tokens，23.58446 秒，
  17.72354 tokens/s，最大延迟 23.57895 秒；22 次 PPU 采样无错误。由于低于固定
  20 tokens/s 门槛，严格判为失败，不改阈值。
- 同配置热态复测：8/8 正确、零错误，416 completion tokens，8.64940 秒，
  48.09580 tokens/s，平均/最大延迟 8.20296/8.64467 秒；8 次 16 卡采样无错误，
  固定 sanity 判据全部通过。
- 热态结果：远端
  `/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906-hot/result.json`，
  SHA256 `1149e4e711e55fad712728e19c05d3272e36a4cb342fd9034dc2e652c4adef55`。
- 复测后 health 正常；请求窗口内无 illegal memory access、Traceback 或 worker exception。
  本结果验证最小整模 graph correctness，不替代 198 题 GPQA，也不作为正式性能结论。

## 2026-09-06 正确 BF16 快照最终精简配置

- 服务 PID `770859`；TP16、50K、seq32，`PIECEWISE`，使用默认 11 个捕获规模；
  `VLLM_USE_BREAKABLE_CUDAGRAPH=1`，执行超时 1800 秒。
- 插件为有状态 `sparse_attn_indexer_kpool` 增加 eager capture break；主模型仍为
  PIECEWISE graph。精确捕获 1–32 的实验已证伪并删除。
- 最小请求 job `j91320499128.2955450`：答案 `2`、`finish_reason=stop`，通过。
- 首轮 job `j598595833062.2977549`：8/8、零错误/超时，419 completion tokens，
  15.0523 秒，27.8362 tokens/s；平均/最大延迟 14.5827/15.0435 秒。
- 热态 job `j549289690117.2995006`：8/8、零错误/超时，419 completion tokens，
  8.7806 秒，47.7186 tokens/s；平均/最大延迟 8.3563/8.7719 秒。
- 两轮 `9-9` 均输出 `0`。16 卡显存约 88.9 GiB；采样无监控错误。
- 这是正式 accuracy 前的 sanity，不替代 GPQA 或最终性能验收。

日期：2026-09-04；PPU-13，容器 `glm5.3-flash`，16×PPU-ZW810E。
服务 PID 123167；TP16/50K/seq32，breakable FULL_AND_PIECEWISE。
镜像、版本、四文件插件变更见 `../environment/runtime-config.yml` 和 `progress.md`。
这不是正式性能基准，也不是正式准确率验收。

## 自动 PPU 默认配置回归（10:00:50–10:00:54）

服务 PID 158392，默认 `vllm_fl/dispatch/config/thead.yaml` 与原 profile 完全相同，
不再设置 VLLM_FL_CONFIG。主脚本仅启动推理，宿主机入口管理 PID/日志。

- job `j409560991110.2779258`，rc=0，8/8 正确，0 错误/超时。
- 422 输出 tokens，4.0104 秒，105.2267 tokens/s，1.9948 requests/s。
- 平均延迟 3.8383 秒，最大 4.0004 秒；16 卡显存 88720–88760 MiB。
- 4 次采样无错误，各卡平均利用率 48.5%–64.5%，峰值 100%。
- 同一 sanity 判据全部通过；不是正式性能结果，不据此宣称性能优化。
- 先行最小推理 job `j649399829307.2755644`：最终答案 `2`，2.2982 秒，通过。

## 直接安装与脚本精简后的回归（09:41:59–09:42:08）

服务 PID 145798，资源/graph 参数与原基线一致，直接安装插件，不再使用
PYTHONPATH/VLLM_PLUGINS、trust_remote_code 或显式 mp 启动选项。

- job `j790165970920.2393416`，rc=0，8/8 正确，0 错误/超时。
- 420 输出 tokens，8.8149 秒，47.6464 tokens/s，0.9076 requests/s。
- 平均延迟 8.6378 秒，最大 8.8049 秒；16 卡显存 88712–88744 MiB。
- 8 次资源采样、无采样错误；每卡平均利用率 36.5%–50%，峰值 100%。
- 原 sanity 判据全部通过。重启后首轮结果，不与旧热运行轮做严格 A/B 性能结论。
- 先行最小推理 job `j675261207890.2371796`：最终答案 `2`，2.3109 秒，通过。

## 首轮（07:57:47–07:57:59）

- job `j327973832578.320192`，返回 0；脚本 `graph_sanity.py`。
- 8/8 正确，0 错误，0 超时，全部 finish_reason stop。
- 总耗时 12.5023 秒，419 输出 tokens（包含 reasoning tokens），
  33.5137 tokens/s，0.6399 requests/s。
- 请求平均 12.3278 秒，最大 12.4925 秒。
- 12 次采样、16 卡全部有效，无 telemetry 错误。
- 每卡显存 88720–88768 MiB；每卡平均利用率 24.33%–30.33%，峰值 100%。
- 已达到预设 sanity 条件：全部正确、无错误、最大延迟 <60 秒、输出 >=20 tokens/s。

| 输入 | 期望/实际 | 输出 tokens | 延迟秒 |
|---|---|---:|---:|
| 1+1 | 2 / 2 | 51 | 12.2651 |
| 2+4 | 6 / 6 | 55 | 12.4081 |
| 3*7 | 21 / 21 | 59 | 12.4925 |
| 20/5 | 4 / 4 | 46 | 12.1816 |
| 12-3 | 9 / 9 | 47 | 12.2092 |
| 5+5 | 10 / 10 | 55 | 12.3841 |
| 9-9 | 0 / 0 | 47 | 12.2088 |
| 8+3 | 11 / 11 | 59 | 12.4728 |

## 同配置重复轮

- 07:59:01–07:59:07，job `j672166716028.351477` 返回 0。
- 8/8 正确，无错误/超时；420 输出 tokens，5.8443 秒，71.8644 tokens/s，
  1.3688 requests/s。平均延迟 5.6731 秒、最大 5.8340 秒。
- 6 次资源采样，每卡 88792–88808 MiB；平均利用率 46.67%–62.33%，峰值 100%。
- 没有修改配置或源码；复测速度提升与首轮额外执行开销一致，但未做正式 profiling
  归因。两轮均通过既定 sanity 条件，没有发现阻止全量精度测试的明显性能异常。
- 个别请求思考 token 数有小幅变化，最终答案均严格正确；不宣称逐 token 确定性。
# 2026-09-04 12:18 超时1800秒配置回归

PPU-13 / glm5.3-flash / graph PID314202，TP16/50K/seq32保持不变。
job `j675029313951.1522012`，rc0：8/8正确，零错误/超时，420输出tokens，
总3.8363秒、109.4805 tokens/s，平均延迟3.6637秒、最大3.8255秒。
16卡89630–89662MiB，平均利用率45.5–73%，峰值100%，4次采样、无监控错误。
先前已通过2937-token长prefill两次；见 `../adaptation/015-timeout1800-validation-20260904.md`。
以下保留历史证据。
