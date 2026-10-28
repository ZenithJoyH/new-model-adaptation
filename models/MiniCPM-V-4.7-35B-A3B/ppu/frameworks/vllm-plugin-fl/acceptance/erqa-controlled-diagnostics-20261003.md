# ERQA 真实图片与图/eager 诊断（非正式验收）

日期：2026-10-03；目标 Host `PPU-13`，运行容器 `minicpmV4.7-35B`，
Host/容器工作根均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，
设备号:inode 均为 `41:14016406509`。模型容器全程保持运行。
本报告为适配问题 010 的一次性诊断，不替代 FlagEvalMM 原始评测或
profile 的正式精度回执。

## 输入和身份

沿用 MiniMax-M3.1 ERQA 评测留在共享 NFS 上的公开数据集：
`/mnt/nfs/users/jinghao/minimaxM3.1/03-acceptance/erqa-full-temp1-p95-k20-c32-20261002/`。
`manifest.json` SHA-256
`224cfd3a6a0181d4a468a48cdc02b74b3993635ba1034c7f1f278260dc657817`，
标记 FlagEval/ERQA test revision
`6bf393250b0981c3f6dd77eb58b6d6879038633f`。PPU-13 模型容器可直接
读取 `images/` 下 630 张图片；逐一重算 630/630 SHA-256 与清单一致。
原 `cpm35B-erqa_ptg.json` 的 400 题，逐题图片标记数量与清单一致。
请求沿用原结果中的完整 `question`，按 `<image N>` 的出现顺序插入
清单图片 data URL。所选 45 题及完整复测 400 题的
`usage.prompt_tokens` 均与原平头哥文件逐题相同。历史 NV/PPU
结果没有图片字节哈希；token 数一致不能单独证明历史请求图片完全同字节。

权重的 `config.json`、`generation_config.json`、
`tokenizer_config.json`、`model.safetensors.index.json` 在当前
PPU-13 与现存 H100-149 FlagOS 容器上逐文件 SHA-256 一致；
这只核对元数据和索引，未哈希 17 个完整权重 shard。
用户随后明确历史 `cpm35B-erqa_nv.json` 指向 **H100-149 的 8020**；
只读核实当前 8020 实际为原生 vLLM 容器 `MinicpmV4.7-35B-native`，
此前查看的 FlagOS 容器是 8021，并非历史 NV 目标。
原文件仍没有进程实例 ID，无法证明历史与当前 8020 是同一进程。
模型 `generation_config.json` 与 PPU 当前启动日志一致：
`temperature=1.0, top_p=0.95, top_k=20`。原始评测请求
参数、并发、超时、图片哈希和 NV 服务实例仍未附在两份历史 JSON 中。

## 400 题同图复测

一次性客户端
`02-issues/erqa_full_repeat_20261003.py` SHA-256
`b9a632a2b695e2121f6c06b309396e013e48cf5bba57f36be7998f1c703c84bf`，
诊断启动器
`01-environment/start_erqa_full_repeat_20261003.sh` SHA-256
`ff2c2d9fc39ee2609d9b75321c0b55d4fccf49aef0b1f5b88a49428986aded8b`。
预检确认 400 个唯一题号、图片 SHA、模型 ID 和 `/health`；
PPU graph 服务使用相同生效默认采样值，明确上限
`max_tokens=32768`、并发 32、不重试。这个 token 上限高于两份历史
结果的实际最长完成，但因历史请求配置未保存，不能声称请求参数完全复刻。
每题请求参数、题干/图片 SHA、响应正文、`reasoning_content`、
usage、结束原因和错误字段保存在
`04-runs/erqa-full-repeat-defaults-c32-20261003/results.jsonl`；
整合结果 `result.json` SHA-256
`838726f26acda53b20ae06a282a2bbbc0ea9c0575f67f38c8c22b4ceeabdb44b`，
同名 `.log` 为客户端日志。

349.3 秒内完整收到 400/400 个唯一响应，400 个 `finish_reason=stop`，
0 请求错误、0 无效末行答案。依公开标准答案和最后一个独立
`Answer: [A-D]` 行，正确 **200/400（50.00%）**；
原平头哥文件为 198/400（49.50%），NV 文件为 213/400（53.25%）。
新旧平头哥最终字母相同 331/400；原轮独对 23、新轮独对 25，
说明 69 题选项翻转，但总分只变 2 题。NV 与新平头哥
独对分别为 37 和 24，净差 13 题。新轮完成 token 最大 4503，
没有达到本轮上限。

第二轮同一 PPU 图服务、同一脚本和请求设置的完整结果在
`04-runs/erqa-full-repeat2-defaults-c32-20261003/result.json`，SHA-256
`a638403302d0c83c5f5daa8fbf8e06fd7685ebec51b34c760f043a0fc3f88074`。
295.7 秒收齐 400/400，400 个 `stop`，0 请求错误、0 无效答案，
**195/400（48.75%）**。两次 PPU 复测最终字母相同 318/400，
有 82 题翻转，但净分仅差 5 题；与历史 PPU 文件相同 332/400。

## H100-149 8020 同图对照

当前 H100 8020 的原生 vLLM 服务使用另一框架实现。
其评测容器 `flageval-mmeval_v0.3.8` 已有 ERQA test 的 400 题和 630 张 JPEG，
由 Host 通过容器 `/proc` 根只读访问，未移动图片。按题号/图序规范化文件名后，
与 PPU 630 张图片逐一 SHA-256 一致，聚合摘要
`1dd1354be4439731550ec0888e3eb08e7787471ae016abb475e2f6fb0ec204f4`。
400 道题追加评测提示后的文本摘要相同
`4d5ceb985fcb72acc429c257f5c1e696d8680ef72ed9b88665fc12d19c671360`；
本轮 NV/PPU 400 题实际 `usage.prompt_tokens` 聚合摘要也相同
`41a2886e4ead92e9124a5291c948dfa70a13169410fde957434ab405c06b1281`。
H100 Host/容器批准根均为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native`，设备号:inode
`45:242118947849`。
两端 vLLM 4.6 视觉主实现 `minicpmv4_6.py` SHA-256 均为
`fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`，
Idefics2 视觉注意力源码均为
`727706231ab08ae2d3c04fe598273d640cbbfd43742e35e7a2caec712e6c3bbe`；
checkpoint 的 canvas M-RoPE 模块均为
`cf6d70719e9e58bbab40612e56efeb6fb5cb7019b0aa780e1536aedb5023b1c3`。
处理器实现、图像处理器和预处理配置也逐文件 SHA 一致。
权重索引中 459 个视觉/merger 张量落在两个 shard；两端逐文件字节
SHA-256 也相同：`model-00001-of-00018.safetensors` 为
`4db68b027881abfc05c863778842f9695fe1bebe98debde8108dd65de64df277`，
`model-00017-of-00018.safetensors` 为
`8283b85a24a9b9190d819835d3813d2829ca715bf99f71c552b130a3bd61e0f5`。
这核对静态代码、视觉权重字节与请求 token 数，不能替代实际视觉特征张量对照。

NV 一次性客户端、命令与原始结果见
[H100 8020 诊断记录](../../../../nvidia/frameworks/vllm-native/acceptance/erqa-8020-diagnostics-20261003.md)。
它按相同 `temperature=1,top_p=0.95,top_k=20,max_tokens=32768`、
32 并发、不重试完成 400/400，0 请求错误、**195/400** 正确，
但有 19 题 HTTP 200/stop 后 `content` 无最终答案，按零分保留。
当前两端复测均为 195/400；逐题最终字母相同 321/400，
双方各独对 22 题。历史 NV 213/400 与当前 NV 195/400 差 18 题，
其中 77 题最终字母翻转。因此原来的 15 题净差未在同图同参数
复跑中稳定重现；不能凭单轮总分修改 PPU 产品代码。

## 单变量执行模式诊断

使用历史两端一对一有胜负的固定 45 题、相同真实图片与题干，
固定 `temperature=0,max_tokens=4096`，仅作执行模式/批处理对照，
不与上方采样得分混算。一次性客户端
`02-issues/erqa_mode_probe_20261003.py` SHA-256
`f67ed037b6eb67bf705bb33e35eac55d08359fd01f69c49aaa041d593a4583a4`；
可选并发版 `02-issues/erqa_mode_probe_v2_20261003.py` SHA-256
`0ac4d4386ea9a8d61c4e89cbb603c2958b74edf498c1e44dcf75d44f00ced77d`。
完整原始结果均在以下路径的 `result.json`：

| 图服务运行目录（`04-runs/` 下） | 并发 | 正确/45 | 无答案 |
| --- | ---: | ---: | ---: |
| `erqa-graph-45-greedy-20261003` | 8 | 23 | 1 |
| `erqa-graph-45-greedy-repeat-20261003` | 8 | 24 | 1 |
| `erqa-graph-45-greedy-c1-20261003` | 1 | 25 | 0 |
| `erqa-graph-restored-45-greedy-c8-20261003` | 8 | 23 | 0 |
| H100 `erqa-native-8020-45-greedy-c8-20261003` | 8 | 19 | 4 |
| `erqa-sdpa-45-greedy-c8-20261003` | 8 | 25 | 0 |

45/45 题四轮 prompt token 均与历史 PPU 文件相同。四轮之间每对有
7–10 题最终字母不同；13/45 题在四轮内既出现正确也出现错误。
聚焦 `ERQA_165`，20 个完全相同请求的结果如下，prompt token
每次均为 590，均正常结束、无请求错误：

| 模式与运行目录（`04-runs/` 下） | 并发 | 答 A（标准答案） | 答 B |
| --- | ---: | ---: | ---: |
| `erqa-graph-165-greedy-seq20-20261003` | 1 | 0 | 20 |
| `erqa-graph-165-greedy-c20-20261003` | 20 | 4 | 16 |
| `erqa-eager-165-greedy-c20-20261003` | 20 | 0 | 20 |
| `erqa-graph-restored-165-greedy-c20-20261003` | 20 | 1 | 19 |
| H100 `erqa-native-8020-165-greedy-c20-20261003` | 20 | 19 | 1 |
| `erqa-sdpa-165-greedy-c20-20261003` | 20 | 1 | 19 |

两端 `ERQA_165` 的题干 SHA-256
`cc75f32197de7debb0dc0d2e41cb1a20d85cb724615cbf8ed32324e1f661b049`、
图片 SHA-256
`e58b080edb2d7a4f568383113fcf495051124f1a16f051ac6ea67003e23df7ff`、
590 个 prompt token 完全一致。此对照表明当前图服务在同题并发下
可产生不同最终选项；H100 对这道题稳定偏向正确答案 A，PPU
eager/graph 稳定偏向 B。它**没有**定位首个数值分歧算子，
也未证明这道题解释 ERQA 全量净差。
贪心请求与历史文件的采样设置不同，不能把 45 题分数当作历史得分修复。

为隔离 PPU 前段视觉注意力后端，只在同样图服务命令中添加
`--mm-encoder-attn-backend TORCH_SDPA`。诊断启动器
`01-environment/start_erqa_sdpa_20261003.sh` SHA-256
`d1da9cf5b5920215f3a2ad1db0c59ee1f9b675cfa246a67b7fd9aa2b063d4174`，
启动日志 `04-runs/erqa-sdpa-service-20261003.log` 明确选择
`AttentionBackendEnum.TORCH_SDPA`，保留七个图尺寸与前缀缓存，
HTTP `/health` 为 200。`ERQA_165` 仍仅 1/20 正确，结果 SHA-256
`63a5a440062c013d90ece86cfb9e9321e6831f86e33343f1e67b7ed3770bedb0`；
固定 45 题为 25/45，0 错误/无答案，结果 SHA-256
`7dd65889bf64f7225884d011e930c0fba014acbd7c1252c6b7244ae0f2ab45ec`。
后端切换未修复 `ERQA_165`；45 题仅比此前图服务的
23–24 题多 1–2 题，处于已观察到的运行间波动内。

## 服务生命周期与边界

在确认原服务 API PID `1786418`、EngineCore/TP Worker、
原根级 `start-model.sh` SHA-256
`36a661b067a072e8d3f7d0689fc05f8e7b2cf0c156ce15db8d61d376f6621e01`、
端口和空闲状态后，仅对本适配 API 发 TERM；四进程退出且端口空闲。
通过 `01-environment/start_erqa_mode_20261003.sh`
（SHA-256
`b91755f1b146d319b58abd0720854054fa4c2b630107def28ad6a4a1cd469416`）
依次启动 eager 与恢复图模式；此脚本只切换
`--enforce-eager` / 原 `FULL_AND_PIECEWISE` 图配置，保留
设备 0/1、TP2、普通前缀缓存、视觉处理器缓存设置和完整黑名单，
日志写 `04-runs/`。eager API PID `1795736`，完成单题对照后只停止
该服务；恢复后图 API PID `1831055`，有效命令含七个图尺寸，
`/health` 为 HTTP 200，容器保持运行。原根级启动脚本未改。
eager 的 45 题尝试因约 25 token/s 吞吐过慢，在精确核对客户端
PID `1800130` 后终止；该轮没有完整结果，未计分。

只在确认本任务 8010 服务无连接、精确 PID 和四进程组后，先后
停止原图 API `1831055` 和对照 API `1839026`；每次确认四进程均退出、
端口空闲，适配容器保持运行。最终恢复普通图服务 API PID
`1840933`，核对有效参数无 `TORCH_SDPA` 覆盖、保留前缀缓存与七个
指定图尺寸，`/health` HTTP 200；根级启动脚本 SHA-256 仍为
`36a661b067a072e8d3f7d0689fc05f8e7b2cf0c156ce15db8d61d376f6621e01`。
Plugin、vLLM、FlagGems 产品源码及根级启动脚本本轮均未改。
当前没有证据支持将全量净分差归因于某个视觉、GDN、FlagGems 或图捕获
算子；下一步需比较同图同题的视觉特征、位置编码与首个分歧 token，
确认可复现的错误后才修改可编辑 Plugin。
