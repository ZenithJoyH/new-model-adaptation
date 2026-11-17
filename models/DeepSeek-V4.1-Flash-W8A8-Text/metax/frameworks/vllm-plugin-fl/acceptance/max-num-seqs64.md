# max_num_seqs=64 有界验证

后续PR整理更新：为真实图测试临时隔离GPU后，已用同一脚本和完全相同生效设置恢复64服务，当前实例为`v41-pr-cleanup-restored-v1-20261105`；恢复后8项文本sanity及独立审阅通过。下文原实例PID/契约保留历史，最新源码和服务身份见[016](../adaptation/016-final-source-review.md)，没有把旧精度转移到新实例。

2026-11-05，用户要求将GPQA阈值设为86%并验证序列上限从16增至64。原GPQA strict-match 171/198＝86.3636%达到用户阈值，原配置/报告保留；该旧服务得分不转移为64序列精度结论。

范围限定：只操作mx-102、mx-103当前任务的推理进程及批准根 `/public-flash/jinghao/deepseekV4.1`，保留推理及评测容器运行。产品源码不改，保留Plugin35(runtime34)/FGV43/FGclone3、TP8/PP2、V2 runner、FULL、async ON、prefix ON、50000上下文、512 MiB/rank KV及1024 batch tokens；启动脚本唯一参数变化为 `--max-num-seqs 16` → `64`。根级与容器内部 `/opt/deepseek-v41-runtime/start-model.sh` 同步字节，继续使用同一最小启动入口。

执行前两机映射、容器ID、实际进程、源码版本与diff哈希均只读核实；服务health200、running/waiting均0，FlagEval容器仅idle进程。102各卡已占65040～65046 MiB/65536 MiB，103约40675～41129 MiB；64可能增加初始化、graph或metadata显存，需实际验证，不预先判定可行。历史MCCL双机容器内通信前置已完成，本轮通信栈/映射不变。

远端控制计划：`03-acceptance/seq64-v1-20261105/<host>/prepare/plan.json`；进程/源码执行前快照、停止结果、原脚本备份同目录。启动控制位于各host的 `launch/`；原始启动日志及请求/metrics证据位于 `04-runs/seq64-v1-20261105/`。旧脚本SHA-256 `58583a1e64346d5e40ebfba0620f78706add35ce22cfc11ad662acc3ccaaee6d`，64候选 `364d18c989f8ce0e5e1406e714eb79cd8586af95487512b6c39aaf9845f9bce9`。

验证计划：先检查FULL初始化和两端实际argv/生效配置；再从小批量到64个在途HTTP请求，核对正确输出、原生engine running峰值、错误/OOM和服务健康；补充流式及thinking请求，观察PP2+async。只有实际engine running=64才声称64序列执行，HTTP在途64本身不足以证明。此为有界功能/容量诊断，不是正式吞吐测试或64序列完整精度验收。若失败保留证据，定位后必要时恢复已验证16服务；不得静默降低graph档位或上下文长度。

结论：**64序列有界验证通过，服务现保持max_num_seqs=64运行**。两机只重启本任务推理进程，适配与CPU工具容器均保持运行；两端实际argv、启动脚本、源码身份与前后进程身份已复核。FULL默认捕获19个尺寸（1、2、4、8及16至128每8递增）完成，未降低图模式或上下文长度。

| 检查 | 结果 |
| --- | --- |
| 原生service-sanity及独立审阅 | 8/8，含中英文算术、排序、JSON、翻译、解释、thinking和上下文理解 |
| 诊断预热 | 4/4，含流式及thinking |
| 持续生成 | 64/64完成，实际client peak=64、engine running peak=64、waiting peak=0 |
| 算术突发 | 64/64正确、正常stop；client peak=64，采样engine peak=63、waiting peak=5 |
| 流式/thinking/中文混合 | 8/8正确并正常结束，流式均收到DONE，thinking有独立reasoning |
| 运行健康 | 共148条请求，0请求错误、0 HTTP超时、0抢占；日志无ERROR/OOM/EngineCore失败，结束health200、running/waiting均0 |

持续生成是预先冻结的容量/输出健康检查，要求重复指定单词并允许长度结束；64条均产生非空内容并达到512 completion tokens，finish_reason=length。不能将这些长度结束当作64次空答案或HTTP超时，也不将该重复任务当成精度得分。该阶段约128.39秒，整个140请求诊断约146.46秒；这些时长是诊断观察，不是正式吞吐测量。

原生metrics共894份，实测引擎峰值64、KV使用峰值34.8214%、抢占0。测试后mx-102每卡64968 MiB，mx-103每卡40531～40985 MiB；这是测试后快照，不冒充峰值显存。现有277438-token逻辑KV容量、50000上下文和512 MiB/rank预算未改变，64为序列上限，不能保证64条50000-token上下文同时驻留。长推理压力和64配置的完整GPQA精度尚未测量；旧16配置86.3636%的GPQA结果只用于用户指定86%门槛的历史判定。

PP2+async ON在本轮实际64序列生成、流式和thinking范围内未复现额外挂起/输出异常；本轮没有重做async OFF对照，不外推未测负载。源码未改，vLLM工作区仍干净。没有执行正式性能、重新推理GPQA或提升整体适配状态。正式验收仍需针对最终配置绑定和重核；`framework.yml`的服务契约已按当前64脚本与参数重冻结，16配置契约作为历史保留在本文件；本轮64诊断使用下述独立冻结契约，不复用旧精度回执。

证据根为mx-102的 `/public-flash/jinghao/deepseekV4.1/04-runs/seq64-v1-20261105/`（两机共享）：

- `final-validation.json`：status=`bounded_max_num_seqs64_passed`，SHA-256 `835c4ecbd09df92a7b5f15801bf8f1e322adbb359a903a2792bdfab66789868a`。
- `service-contract.json`：请求前冻结两端实际argv、允许环境、进程、源码、脚本及生效配置，SHA-256 `b4896818f93390c76b802091249a18c5445474dad99aede6e891ceb6c60c14ba`。
- `runtime/effective-config.json`：SHA-256 `0f6e2ef60dd6c8e1bf2c0ec2754f5caa6e580a3ca9a8dbe885d8e36cfa969317`。
- `native-sanity.json`：原生needs_review原始响应保持不变，SHA-256 `d81597c659649c96b15b998ce3b41305274d01929dcfd2dda83b4befb8712ec1`；`native-sanity-review.json`独立审阅及原生validate_result通过，SHA-256 `3150fa49d2b2c996b6c65433e780704a0190acca141d3bec344c99f0238db006`。
- `probe-v1/result.json`、`probe-v1/responses/`、`probe-v1/metrics.jsonl`及`probe-v1-exit.json`：140条原始响应、并发采样、退出0；文件哈希清单保留在报告内。
- `final-mx-102.log`、`final-mx-103.log`：最终不可变日志快照；两机测试后状态快照位于 `03-acceptance/seq64-v1-20261105/mx-102/final-inspection/<host>.json`。

本轮原生accuracy Skill选择 `service-sanity`，bundle SHA-256 `a1c3dce2e0dde6304b95d5a7ee0d54bf436dd4fab94ed4719c377737122fe6a2`，仅8条文本小批量及独立审阅通过，不冒充完整框架验收。控制计划SHA-256 `9a405e9851154251529c1d2b9a932d6314788e4d288e153c75c36de290422c0c`；其中GPQA阈值独立冻结为0.86。两机根级和容器内部启动脚本均为64候选SHA `364d18c989f8ce0e5e1406e714eb79cd8586af95487512b6c39aaf9845f9bce9`，bash语法检查及实际启动通过；未打包或发布镜像。
