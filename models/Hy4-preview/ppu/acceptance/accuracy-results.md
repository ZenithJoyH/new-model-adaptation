# Hy4-preview / PPU 精度验收汇总

## 验收范围

- Host：`PPU-07`
- 模型：`/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`
- 服务：`hy4`，TP16，graph `FULL_DECODE_ONLY`
- 评测：GPQA Diamond，全量 198 题
- Runner：`test/Accuracy_test/llmrun.py`
- 评测镜像：`harbor.baai.ac.cn/flageval/flageval-llmeval:v1`
- 正式并发：32；64 并发轮次作为失败诊断保留

本文件只保存验收结论。配置、包装、缓存、完整 result/sample 和日志保存在下表列出的
远端目录，不复制到本仓库。

## 评测轮次

| 日期与配置 | 结果 | 判定 | 远端证据 |
|---|---|---|---|
| 2026-08-29，32 并发，no-think，1,024 token | 198/198，0 timeout；strict 64.1414%，flexible 39.3939% | 早期基线；未预设准确率阈值，不作为当前正式通过结论 | `/mnt/nfs/users/jinghao/hy_v4/test/Accuracy_test/outputs/hy4-latest-ppu07-gpqa-full-c32-nothink-20260829/20260829-043440/` |
| 2026-08-29，32 并发，thinking/high，40K | 198 个唯一题；strict 90.9091%，flexible 44.4444%；4 个无效项 | 失败；4 题达到 40K 后仍无最终答案 | `/mnt/nfs/users/jinghao/hy_v4/test/Accuracy_test/outputs/hy4-latest-ppu07-gpqa-full-c32-thinking40k-20260829/20260829-050554/` 及独立失败项重跑目录 |
| 2026-09-04，修复版，64 并发，thinking/high，40K | 仅产生 16 个 SQLite `None`，其余 182 题为 `<TIMEOUT>` | 失败且分数无效；FlagGems 共享调优 SQLite `database is locked` 导致服务退出 | `/mnt/nfs/users/jinghao/hy4-preview/acceptance/gpqa-fixed-c64-20260904/` |
| 2026-09-06，修复版，32 并发，thinking/high，40K | 最终 198 个唯一题；strict 178/198（89.8990%），flexible 97/198（48.9899%）；6 个无效项 | 正式精度失败；`allow_timeouts=false` 校验返回 1 | `/mnt/nfs/users/jinghao/hy4-preview/acceptance/gpqa-fixed-c32-20260906/` |
| 2026-09-08，当前修复分支，32 并发，thinking/high，80K | 仅 3 条真实返回且 strict 3/3 正确；其余 195 条因服务退出无效；receipt `failed` | 正式精度失败；`sample_tokens` 1800 秒超时，部分百分比不是可信模型精度 | `/mnt/nfs/users/jinghao/hy4-preview/05-runs/gpqa-full-graph-c32-high80k-t09-20260908-1710/` |
| 2026-09-10--11，Plugin `2fa5f18` + `index` blacklist，64 并发，thinking/high，80K | 198 个唯一题；strict 180/198（90.9091%），flexible 96/198（48.4848%）；1 个唯一 `<TIMEOUT>` | 用户以 87% 为业务阈值并明确接受本轮，accuracy passed；保留 `allow_timeouts=false` 校验失败、runner exit 1、无 passing receipt 的限制 | `/mnt/nfs/users/jinghao/hy4-preview/04-runs/gpqa-full-graph-c64-high80k-plugin2fa5f18-indexoff-20260910/` |

## 最新正式轮次

2026-09-06 轮次使用独立输出和响应缓存，不复用 64 并发失败轮次。preflight 核实数据集
198 条、服务 HTTP 200 和模型名 `hy4`。小批量 graph sanity 为 8/8 严格正确，512 个输出
token 用时 39.77 秒，平均 ITL 0.2590 秒，0 抢占。

正式评测首轮及 12 题定向重试均已结束。重试恢复 6 题；`doc_id` 15、71、81、88、145、
147 再次达到 40,000-token 上限且没有最终答案，被 runner 标为 `<TIMEOUT>`/refusal。
实际 HTTP timeout 为 0，服务 error/abort 为 0，因此本轮失败不是客户端超时或服务崩溃。

最终文件位于：

- result：`/mnt/nfs/users/jinghao/hy4-preview/acceptance/gpqa-fixed-c32-20260906/outputs/hy4-w8a8-fg842b19d-graph-c32-thinking40k-20260906/<run-id>/.../results_2026-09-06T15-51-06.411193.json`
- samples：同一 run 目录下 `samples_gpqa_diamond_generative_cot_2026-09-06T15-51-06.411193.jsonl`
- 响应缓存：评测容器 `/tmp/lm_eval_cache/hy4-w8a8-fg842b19d-graph-c32-thinking40k-20260906/`

## 关键诊断结论

- 40K 无效项均为模型生成达到长度上限后未给出最终答案；继续增加客户端 timeout 无法解决。
- 64 并发轮次的 `database is locked` 属于 FlagGems 调优缓存并发问题，该轮指标不得使用。
- 阶段计分曾因 `top_k=-1` 与 `-1.0` 的缓存键归一化差异显示 `matched=0`；这只影响旁路
  进度统计，不影响正式 runner 的最终计分。
- 用户未指定业务准确率阈值，因此这里只报告原始分数；但 6 个无效响应已明确违反
  `allow_timeouts=false` 和零无效响应要求。

## 当前结论

最新 Plugin `2fa5f18` + `index` blacklist 的 graph 服务完成了 c64/80K 全量 198 题并保持健康，
未再复现 EngineCore 卡死。strict 90.9091% 已超过用户指定的 87% 业务基线；2026-09-11 用户明确
接受该结果并要求进入下一步，因此 accuracy 状态记为 passed。doc_id 81 的一个唯一 `<TIMEOUT>`、
`allow_timeouts=false` 校验失败、runner exit 1 和没有 passing `acceptance-result.json` 仍是显式限制，
不会被隐藏或改写。适配阶段按用户纠正保持 `in_progress`；项目性能门禁要求 adaptation complete，
因此正式性能尚未启动。
