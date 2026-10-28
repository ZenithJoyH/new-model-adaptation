# 扩展算子黑名单后的 GPQA 32/64 并发全量诊断

日期：2026-10-03。唯一目标 Host `PPU-13`；模型容器
`minicpmV4.7-35B`、评测容器 `flageval_llmeval-jinghao` 均保持运行。
Host 和两个容器的批准工作根均为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，已核对同一设备号:inode
`41:14016406509`。以下路径均以该根为前缀；权重保持只读。

## 服务与冻结输入

用户在根级 `start-model.sh` 加入 `copy_`、`_index_put_impl_` 后重启模型服务；
脚本 SHA-256 为
`36a661b067a072e8d3f7d0689fc05f8e7b2cf0c156ce15db8d61d376f6621e01`。
实际 API 进程环境包含完整的
`VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy,index_put,nonzero,copy,index_put_,index,copy_,_index_put_impl_`
和 `CUDA_VISIBLE_DEVICES=0,1`。服务 TP2，前缀缓存开启，
`FULL_AND_PIECEWISE` 对 `[1,2,4,8,16,32,64]` 完成 PIECEWISE 7/7
和 decode FULL 7/7 捕获。API、EngineCore、TP0、TP1 的 Host PID
分别为 `3065077`、`3073243`、`3076461`、`3076466`，两轮结束后仍是
09:10–09:11 启动的相同进程。没有修改服务脚本、源码或容器。
补充核对：宿主机 `/proc` 中 EngineCore 和两个 Worker 的**初始环境**
未显示该黑名单或 `CUDA_VISIBLE_DEVICES`，而 API 初始环境均有；
启动日志还出现 vLLM 对 `VLLM_FL_FLAGOS_BLACKLIST` 的“unknown environment
variable”告警。
容器 `/tmp/flaggems_enable_oplist.txt` 的运行期快照未列出
`GEMS COPY_` 和 `GEMS _INDEX_PUT_IMPL_`。该共享快照及 `/proc`
初始环境不能直接证明每个 Worker 的运行时环境、注册表或每次算子分派；
因此本报告只确认当前服务脚本/API 设置和实际 GPQA 行为，
不把算子退回原生实现当成已验证事实。

评测使用远端原生 `03-acceptance/gpqa-temp0-diagnostic-20261002/llmrun.py`
（SHA-256
`4f9076aaae6e3efb32246a66053f971d1d70b04d99f196599daf5e57ca2eb2cc`）。
两份冻结配置为
`03-acceptance/gpqa-blacklist-expanded-20261003/32c/config.json`
（SHA-256 `0c9526904804d0738463278626bcba3bbe605e7f4a7623168bbea5e17ea31995`）
和 `03-acceptance/gpqa-blacklist-expanded-20261003/64c/config.json`
（SHA-256 `18aaadf9a7c9b1265a1a78205b5c8160d11c6e4e8d5b02de65aac1039a7b59a3`）。
两者只在并发数、隔离的缓存目录和运行 ID 上不同；32 并发配置与
前次原生 32 并发配置相比也只改变缓存目录和运行 ID。
GPQA Diamond 全量 198 题，`temperature=1.0,do_sample=false,max_gen_toks=18000,top_p=0.95,top_k=20`，
请求超时 600 秒，重试 0，`formal_acceptance=false`。两份配置的原生
preflight 均确认 198 题、服务 HTTP 200；实际运行缓存命中均为 0。
临时文件放在 `05-tmp/gpqa-blacklist-expanded-{32c,64c}-20261003/`，
运行缓存放在 `06-cache/gpqa-blacklist-expanded-{32c,64c}-20261003/`。
配置经 Ansible 语法和 `--check --diff` 核对后写入；两轮依次运行。

## 全量结果与复现判定

| 运行 | 原生 strict-match | 原生 flexible-extract | 历史提取式重算 | strict 无效题 | 缺 `</think>` | 后 101 题无效 | timeout / 请求错误 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 32 并发 | 142/198（71.72%） | 127/198（64.14%） | 149/198 | 11 | 2 | 8 | 0 / 0 |
| 64 并发 | 136/198（68.69%） | 124/198（62.63%） | 143/198 | 12 | 1 | 5 | 0 / 0 |
| 用户先前异常文件 | 88/198（44.44%） | 79/198（39.90%） | 88/198 | 85 | 85 | 85 | 0 / 未知 |

每轮原生进程退出码均为 0，严格和宽松各 198 行、共 396 行，
198 个唯一题号全部齐全。两轮的 `doc_hash`、`prompt_hash`、
`target_hash` 与用户异常文件逐题 198/198 一致。32 并发第 0–96 题
严格正确 72/97、后 101 题 70/101；64 并发分别为 67/97 和
69/101。异常轮分别为 76/97、12/101，并从第 97 题起集中出现
85 个无效回答。本次两轮均未出现同样的后半段连续乱码：缺少
`</think>` 的 32 并发 2 题和 64 并发 1 题均是长输出，分别有
2 题达到 18,000 token 上限；这些题保留在分母中。历史提取式
仅是与旧参考同口径的诊断重算，原生分数以前两列为准。

服务日志在两轮对应窗口实际记录的 `Running` 峰值分别为 32 和 64，
没有评测期 `ERROR`、`Traceback` 或 `Exception`。内核日志从
09:35 到两轮结束后 09:58 没有新增记录，因此没有新的 Xid；
评测容器对同一服务的最终 `/health` 检查为 HTTP 200。
这两轮**未复现**先前的 85 题失效或双卡 `Xid 1155`。
32 与 64 并发原生分数相差 6 题，但单轮波动不能判定并发导致
精度下降；此前旧黑名单服务的单轮 32 并发严格分数为 146/198。
在增加两个条目以前，同一旧服务的 32 并发重放也曾未复现乱码，
因此本次结果不能证明这两个条目是根因修复。

## 原生证据路径

两轮结果根分别为
`04-runs/MiniCPM-V-4.7-35B-A3B/gpqa-blacklist-expanded-32c-20261003/`
和 `04-runs/MiniCPM-V-4.7-35B-A3B/gpqa-blacklist-expanded-64c-20261003/`。
各自下的
`gpqa_diamond_generative_cot/attempt-1/MiniCPM-V-4.7-35B-A3B/`
包含原生结果及逐题样本：

| 并发 | `results_*.json` SHA-256 | `samples_*.jsonl` SHA-256 | 控制日志 SHA-256 | `effective_config.json` SHA-256 |
|---|---|---|---|---|
| 32 | `f99b2ec787abb0da2565de62ff68a148ef7136a7b4216eaec98b281ee8fe4780` | `2524b2c82ea1873c06d294e70577323e55b8d001ab3e3ac662d800ed07819f9d` | `4ae4f304d41160e7c832c5967bcf41df63efad5a38b6f2c605579f583674858d` | `32492297fc7c3ada0ff9923fe51057d91bf183ee0e5c54e60aa1e8929d57ea6e` |
| 64 | `5270d301dcd37b9c5e4ed2c46c302e603c950b99b1732406b4b3e2946755f188` | `014babd26d5e7e6bfe8100c539eb9921c08a1a6b62b1568891b654279196f564` | `980d80b121e9805be7d19270b577f93b700d9f0b2eb00ced743ee43d05cc0ceb` | `a21acda37487ad339dc8b9d116eac132a1f629ca3c56bfb8696df7ce6b9658b5` |

原生结果文件名分别为 `results_2026-10-03T01-46-08.002487.json`、
`results_2026-10-03T01-56-44.032836.json`；样本文件使用对应时间戳。
控制日志和 `exit-code` 分别在
`04-runs/gpqa-blacklist-expanded-32c-20261003-controller/`、
`04-runs/gpqa-blacklist-expanded-64c-20261003-controller/`。
这些是故障复现诊断，执行模式正式回执、sanity 和冻结阈值精度验收
仍未完成，故不改变 `framework.yml` 状态。
