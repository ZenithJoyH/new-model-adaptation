# MiniCPM-V 4.7 35B-A3B / PPU-13 / vllm-plugin-fl

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

2026-09-29 诊断进展：唯一目标 Host 为 `PPU-13`，容器
`minicpmV4.7-35B` 保持运行。批准工作根的宿主机与容器路径均为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`；权重只读路径为
`/mnt/cpfs/models/MiniCPM-V-4.7/weights/35b-a3b`。环境和部署指纹见
[环境分析](environment/README.md)，具体问题与改动见[适配问题](adaptation/README.md)。

Plugin 原 HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`；仅当前未提交
工作树增加 4.7 模型注册、MoE/canvas adapter、视觉 data 模式加载 workaround，
以及只在平头哥 4.7 视觉窗口合并后启用的 FP32 注意力 helper。vLLM、FlagGems
源码树保持干净，FlagGems 未同步。聚焦 CPU 数值对照 4/4 通过。

已有 eager TP2 文本、红/蓝单图最小诊断请求。请求 prefill 与 decode 全量图时，
两个 rank 的 GDN backend 均报告只支持 `UNIFORM_BATCH`，自动降至
`FULL_DECODE_ONLY`；decode 图 4/4 捕获，graph 服务健康检查 200，文本、
红/蓝单图、红蓝双图和红蓝两帧视频请求均 HTTP 200、正常停止、答案符合预期。
graph 固定启动日志证据为
`04-runs/graph-tp2-full-v1/startup-capture.log`，SHA-256
`eb5ca836c6e3b3024375818c67b1b2760f084311923d3fc0fa72f4ca64cebdd6`。
该轮实际图级别为 `decode-full`，不能记为 prefill full graph。

随后核查发现上述 eager/graph EngineCore 生效配置均为
`enable_prefix_caching=False`，违反 profile 的非性能前置条件。上述请求和原
环境/适配回执均降为历史诊断；旧部署指纹失效。独立新实例显式
`--enable-prefix-caching`，两种模式的生效配置均为 `True`。eager 文本、
红/蓝单图，以及 graph 文本、红/蓝单图、双图、两帧视频均重新通过。
graph 两个 rank 再次确认 GDN 限制，实际最高已核图级别为 `decode-full`。
新 graph 固定日志为
`04-runs/graph-tp2-full-v2-cache-on/startup-capture.log`，SHA-256
`7b8839ee460c18dbdf0d0a90c63fe8e84f1ad545d2908d1c336291bcd80a2f27`。
新部署指纹 `e66b5c293bb60296c932b1e3291282867a6d66c70d7be42e37411f7e31f09a37`；
环境与适配回执均已重建，并在 `PPU-13` 上通过读取原生产物的仓库门禁，
见[005](adaptation/005-prefix-cache-effective-default.md)。
原生状态门禁要求执行模式正式回执完成后才能标记顶层 `functional`，因此
适配阶段即使已完成最小推理，顶层状态仍保持 `environment_ready`。

2026-09-30 按用户要求提前创建了首版根级
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh`（Host 与容器路径相同，
SHA-256 `75f3d9ba4dc78416fdd8a40ad13c9a8563e7c3e78e92fe73a3b6e3c4add3a973`，
0755，容器内 `bash -n` 通过）。在准确识别旧任务服务并确认四进程退出后，
经此脚本启动新服务，没有重启容器。生效配置是 `FULL_AND_PIECEWISE`、
`VLLM_COMPILE` mode 3、前缀缓存开启；混合 prefill/decode PIECEWISE 图捕获 5/5，
decode FULL 图捕获 4/4，服务 `/health` 为 HTTP 200。文本、红蓝单图、双图和
两帧视频基本请求均正常返回预期答案。启动与冒烟日志快照 SHA-256
`f1837e46e3eac8a06330163f4d9f1c31c1422fd161659fc374a8a45b85f85b98`；
路径、五项结果哈希及每个启动参数的理由见[启动脚本记录](acceptance/launcher-20260930.md)。
用户随后要求删除非必要设置：当时根级脚本删去冗余的 `HF_HOME` 和无人消费的
日志路径打印，经单 Host 审核、安装及重启复验，SHA-256 为
`e486d32980a24d7cb3607abd7015783cf7dd9f0bd0f4005c6ba7a314250c1a04`。
当前服务仍保持 `FULL_AND_PIECEWISE` 与前缀缓存开启，PIECEWISE 5/5、
FULL decode 4/4，健康检查 HTTP 200，文本与红色单图基本请求正确。
首版脚本已保存为历史快照；精简范围、命令、进程及新结果哈希见
[精简版记录](acceptance/launcher-minimal-20260930.md)。
用户再次编辑根级脚本后的版本（SHA-256
`0a9af9c6844ae85ce8dc908588f186acd404187d070a6b0963f9371fa410e599`）
在 PIECEWISE 图 47/51 时因 TP1 显存耗尽而未就绪；当时清理了核实的本任务
进程，并从已验证脚本副本恢复服务。随后按用户指定，仅为根级脚本增加
`cudagraph_capture_sizes=[1,2,4,8,16,32,64]`，当时 Host 与容器中的
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh` SHA-256 为
`4051002a7e813e81efc71123a5adf5db7c4ba62c44bb9844824d69ae0a258750`。
容器内 `bash -n` 通过；重新启动本任务服务后，实际 EngineCore 配置确认
`FULL_AND_PIECEWISE`、七个指定尺寸、前缀缓存开启，PIECEWISE 7/7、
decode FULL 7/7，`/health` HTTP 200，文本 `42` 与红色单图 `红色` 正常。
日志快照为 `04-runs/start-model-seven-graphs-20260930/startup-and-smoke.log`，
SHA-256 `5804fa268d7709fe4e4f480d451186f7cd215d58a5365c73bc10790c37dbfffb`。
这次启动从批准的 `04-runs/` 工作目录执行，缓存及临时目录由外部环境提供；
脚本仍使用相对日志路径，独立运行边界尚未完成。比较和证据见
[006](adaptation/006-user-launcher-graph-oom.md)。
2026-10-01 按单变量顺序分别删除视觉 `data` 模式和显式 `TORCH_SDPA`，
两轮均完成两类图各 7/7、健康检查 HTTP 200、文本及重复红图/蓝图共 5/5
正确。默认视觉后端实际选择 `FLASH_ATTN`。根级脚本仅删除这两行后重新
实际启动并再次通过相同 5/5 请求；该轮 Host/容器根级脚本 SHA-256 为
`1aac69a02c3fed37be7ce6fff446e5e22bd3edf9fae628e847d8f4abcbb4731a`，
权限 0755，服务保持运行。新脚本仍保留视觉处理器缓存禁用以维护 canvas
尺寸元数据；受控比较、日志及结果哈希见
[参数删减记录](acceptance/launcher-mm-flags-20261001.md)。
这只是用户指定配置的启动验证；正式精度评测按用户要求暂缓。该配置的 prefill
是 piecewise，未达到 profile 的正式 full-graph 验收要求，因此正式执行模式、
精度、性能和总结均未标记通过，`framework.yml` 状态保持 `environment_ready`。

2026-10-01 用户又从根级脚本删除 `--max-model-len 50000`，这是与上一轮脚本
相比唯一的文本变化。新脚本 Host/容器 SHA-256 为
`4819df586f8cb17286951fbe764615afa717ca9acd24543f9e3fef07f8f6f17c`，
0755，容器内 `bash -n` 通过。由该根级脚本重新启动后，生效上下文长度为
262,144，PIECEWISE 与 decode FULL 各捕获 7/7，`/health` 为 200，五次短
图文请求全部通过，服务保持运行。启动和请求证据见
[无 max-model-len 验证](acceptance/launcher-no-max-len-20261001.md)。本轮未验证
接近 262,144 token 的负载；正式验收状态不变。

2026-10-02 对用户提供的 GPQA Diamond NV/PPU 结果做同题对照：
NV 152/198，初始 PPU 143/198。两端题目、prompt、target 哈希逐题一致；
NV 服务使用 `qwen3` reasoning parser，PPU 未使用，解释了响应中思考文本
显示差异，但不改变参考样本严格答案提取。保持原评测参数在 PPU 复跑
198 题，无超时或 API 错误；按参考文件可重建的同一答案提取式为
151/198，与 NV 仅差 1 题。当前评测容器的更严格正则将 11 个裸字母
结尾答案记为无效，原生分数为 147/198；正式跨平台比较需要固定相同
task 版本和提取式。原 PPU 的重复符号与乱码未复现，服务仍健康。
本轮没有足以支持产品代码修复的稳定低精度证据，也没有改评测参数、
生产脚本或模型源码。原因分析、运行哈希和边界见
[007](adaptation/007-gpqa-decoding-mismatch.md) 与
[GPQA 诊断报告](acceptance/gpqa-diagnostic-20261002.md)；先前设备非法页
单列于 [008](adaptation/008-gdn-index-invalid-page.md)。正式验收状态不变。

2026-10-02 用户在根级脚本中增加
`VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy,index_put,nonzero,copy,index_put_,index`
并重启模型服务。该变量已在服务 PID `1709269` 环境中核实；在同一服务上
按原参数跑完 GPQA Diamond 32 并发 198 题，0 timeout、0 API 错误。
原生严格分数 146/198；按参考文件可重建的同口径提取式重计
153/198，NV 参考为 152/198。当前 task 正则与参考结果不一致，
两个分数用途不同。服务日志无新非法页或崩溃，单轮成功不等于
黑名单根因修复；完整配置、样本和哈希见
[重启后 GPQA 报告](acceptance/gpqa-32c-after-restart-20261002.md)。
正式验收状态仍不变。

2026-10-02 用户另提供 `gpqa_cpm35B_ptg.jsonl`（SHA-256
`136303924883ae3e3be7db6bfa84fe9773b785b698be262dfeb33d3c0096db3b`）。
198 题完整，但严格匹配仅 88/198，85 题无效；前 97 题正常，第 97 题起
多数原始输出从开头乱码。按历史答案提取式重算仍为 88/198，说明本次主要是
生成异常而非提取式差异。同轮宿主机内核在 21:33:10 对本服务 TP0/TP1
分别记录 `Xid 1155 / L1 Invalid page`，尽管服务继续返回 200。
保持原服务和生成参数的单题、异常区间 32 并发及 198 题全量诊断都未复现
乱码或新 Xid。对服务日志逐行计数显示，Xid 前已完成本轮至少 160 次响应；
85 个无效答案中至少 47 个必须在 Xid 前返回，故 Xid 不是首次乱码的
起点。全部 85 个无效请求的 prompt 少于 544-token 缓存块，不能由它们
直接恢复坏前缀块解释。在空闲 PPU3 上对 FlagGems `copy_` 与
`_index_put_impl_` 做真实索引/状态形状的 eager 与图重放对照，结果均与
原生算子一致；仍未定位首次污染的 kernel 或调度状态。
详见[009](adaptation/009-gpqa-late-run-garbled-output.md)。
正式验收状态不变。

2026-10-03 用户在根级脚本黑名单增加 `copy_`、`_index_put_impl_` 并重启服务，
当前脚本 SHA-256 为
`36a661b067a072e8d3f7d0689fc05f8e7b2cf0c156ce15db8d61d376f6621e01`。
确认新进程环境及七种指定图尺寸后，依次用原生 FlagEval 跑完 GPQA
Diamond 32、64 并发各 198 题。两轮均 0 timeout、0 请求错误，严格分数
分别为 142/198、136/198；后 101 题的无效答案分别为 8、5 题，
未复现用户异常文件的 85 题集中失效。服务实际 `Running` 峰值
分别达到 32、64，评测期无新 Xid，终态健康检查 200，服务 PID 不变。
该对比不能证明新增黑名单是根因修复，因为旧服务此前全量重放也未稳定复现。
冻结配置、样本、结果和哈希见
[32/64 并发复测报告](acceptance/gpqa-blacklist-expanded-32-64-20261003.md)
及[009](adaptation/009-gpqa-late-run-garbled-output.md)。正式验收状态不变。

2026-10-03 对用户提供的 ERQA NV/PPU 各 400 题结果做只读同题比较，
按公开 FlagEval/ERQA 标准答案诊断重算，NV 213/400、PPU 198/400；
两端最终答案一致 330 题，NV 独对 30、PPU 独对 15。
NV 有 5 个 `RetryError ... TypeError` 无答案，PPU 400 题均有
可提取的行尾答案；两端正常返回的 395 题上 NV 213、PPU 195。
PPU 没有本模型 GPQA 异常轮或另一模型 ERQA 异常轮的大面积乱码。
文件未附图片字节、请求参数和部署指纹，故当前不能定位 15 题
分差的服务或算子根因。证据与边界见
[ERQA 对照报告](acceptance/erqa-nv-ptg-comparison-20261003.md) 和
[010](adaptation/010-erqa-nv-ptg-accuracy-gap.md)；正式验收状态不变。

随后从 PPU-07 的 MiniMax-M3.1 ERQA 数据清单找到 630 张公开真图，
在 PPU-13 容器逐张校验 SHA；同题复测的 400/400 prompt token
与原 PPU 文件相同。当前图服务按模型生效默认采样参数、32 并发
两次完成 400/400，分别 200/400、195/400 正确，均无请求错误和
无效答案；原 PPU 为 198/400。用户确认历史 NV 指向 H100-149
的原生 vLLM 8020 服务；用逐图 SHA 一致的 630 张图片和相同文本、
采样参数复测当前 8020，得 195/400，与第二次 PPU 同分；
逐题 prompt token 摘要相同。历史 NV 213/400 与当前 NV
195/400 相差 18 题，历史 15 题净分差未稳定复现。
固定贪心单题 `ERQA_165` 的 H100 8020 为 19/20 答标准 A，
PPU 图服务两轮分别 4/20、1/20，eager 0/20；切换 PPU
视觉前段后端至 `TORCH_SDPA` 仍为 1/20，45 题得 25/45，
处于此前 23–25/45 波动范围。首个分歧算子仍未定位。
诊断后已恢复原七尺寸 `FULL_AND_PIECEWISE` 服务，API PID
`1840933`，`/health` 200，容器始终运行。没有改产品源码或
根级启动脚本。
完整路径、哈希、参数边界和后续证据需求见
[ERQA 受控诊断](acceptance/erqa-controlled-diagnostics-20261003.md)。
这不是正式精度回执；`framework.yml` 状态不变。

2026-10-08 按用户要求应用 [FlagGems PR #6873](https://github.com/flagos-ai/FlagGems/pull/6873)
的公共 split-KV 输出寻址修复到实际安装包，并撤除 T-Head 专用
`vision_attention.py`、其测试及 adapter 中的 FP32 绑定。修复前公共入口
81.1% 元素不匹配，修复后 34 项算子回归通过；完整 BF16/TP1 eager
9/9 正确、189 次实际 attention 全有限，真实命中原 252-token 两路 split。
TP2 图服务两类图各 7/7，文本/单图/双图及两轮 10 并发共 25/25 HTTP
回归正确。最终 API PID `1944850`，8010 `/health=200`，容器保持运行。
按非性能规则将根级脚本的一个缓存参数改为 `--enable-prefix-caching`；
首次仅移除禁用参数仍得到 False，守卫拦截后已显式修正并重启验证。
其余启动参数不变，仍为七尺寸 `FULL_AND_PIECEWISE` 和默认 262144 上下文。
根级脚本 Host/容器 SHA-256
`4c48934d95b428f4952ba4550657e33ce1e39afcbca9b5dfb87aa63ba33f41ba`，
0755，语法与启动验证通过。当前视觉 encoder 本身未编译或捕图。
原生证据在远端 `04-runs/pr6873-20261008/`，完整版本、哈希、回退备份与
限制见 [011](adaptation/011-flaggems-splitkv-vision-fix.md)。本轮未复跑 ERQA/GPQA
正式精度、性能或镜像验证，不据此声明历史 ERQA 分差已解决，也不更新历史
`framework.yml` 绑定。

2026-10-08 按用户要求，将实际安装的 `/workspace/vllm-plugin-FL` 切换至
用户 `support-minicpmV4.7` 分支的固定提交
`aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68`，工作树干净；原模型注册与 adapter
已备份并保留 stash。FlagGems PR #6873 修复、根级启动脚本及启动参数未改变。
分支自带单测 14/14、完整 BF16/TP1 eager 9/9、TP2 图服务 33/33 HTTP 定向回归
通过，包括大图分片、左右分色图、双图顺序和两轮 10 并发。PIECEWISE 与 FULL decode
各捕获 7/7；当前 API PID `1955096`，8010 健康检查 200，前缀缓存开启，容器未重启。
首轮新增大图请求等待 134–153 秒，第二轮相同输入约 0.42–0.43 秒，未将缓存复用
视作独立视觉性能结论。原生证据在远端 `04-runs/plugin-support-minicpmv47-20261008/`；
源码身份、回退备份、实际测试条件和限制见 [012](adaptation/012-user-plugin-branch-validation.md)。
该结论适用于当前默认视觉 weights 模式；分支未包含 data 模式加载 workaround。
本轮未重跑正式 ERQA/GPQA、性能或镜像验证，历史验收状态不变。

2026-10-09 按用户要求，将完整 MoE 和 decoder full-attention 切换至容器已安装的
FlagGems-vllm。MoE 实际使用库的平头哥实现；attention 使用库自身通用 BF16 内核，
当前 head_dim 256 不满足平头哥 INT8 attention 的 64/128 维限制。改动经现有 dispatch
接入，仅在当前服务对三个符号选择 `vendor:thead`；vLLM 与 FlagGems-vllm 源文件未变。
18 项直接算子检查、26 项 Plugin 测试、隔离和主服务各 35/35 HTTP 请求通过，包含三类
输入各 10 并发。主服务由根级脚本启动，GPU0/1、8010、API PID `2195726`，两类图各
7/7，前缀缓存实际新增命中 4,896 tokens；2026-10-09 22:28:34 +08:00 健康检查 200。
根级 Host/容器脚本路径仍为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh`，
SHA-256 `03c096bdd0c7b191544e9a7b733059826d732082d8c03f1589c8650faea23298`，0755；
容器内部交付副本为 `/workspace/model-launchers/MiniCPM-V-4.7-35B-A3B-ppu-flagos/start-model.sh`。
脚本按交付规范显式开启前缀缓存，日志在 `04-runs/service.log`、缓存在 `06-cache/`。
隔离实例已停止、GPU6/7 已释放；容器未重启。原生证据在
`04-runs/flaggems-vllm-switch-20261009/`，版本、设计审查、失败记录与限制见
[013](adaptation/013-flaggems-vllm-moe-attention.md)。未跑正式精度/性能或镜像验证，历史状态不变。

2026-10-10 按用户纠正撤回上述 vendor provider 方案，恢复原 factory、注册、policy、
registry 与 PPU staged MoE，仅在三处 Plugin 计算接口直接替换 FlagGems-vllm 调用。
根级脚本移除 `VLLM_FL_PER_OP`，使用现成的 `VLLM_FL_USE_FLAGGEMS_ATTN=1`；
没有新增调度分支。MoE 使用库的 THead public invoke；库内 BF16 paged Flash 接口
复用该库自己的 GQA 在线 softmax 内核，修复长上下文配置回退及 mixed 批次共享KV重复计算。
66项回归通过。同 GPU0/1，c64/n128、输出1024、三轮去首轮，4K/16K/32K输出吞吐
1532.71/594.22/269.62 tok/s，1152/1152请求成功，性能实例实际关闭前缀缓存。
相对历史 nomm CSV 分别+13.14%/+22.66%/+37.01%；16K相对退化结果98.73 tok/s约6.02倍。
历史 CSV 缺少完整源码/部署绑定，该比较属于历史参照，不是重建原源码的受控A/B。
根级与容器内部启动脚本SHA-256均为
`74a4e9e5da5c9b2ec341a02d7015cd790e14648a08074a635158560cb00c0d42`，0755；
内部交付路径仍为`/workspace/model-launchers/MiniCPM-V-4.7-35B-A3B-ppu-flagos/start-model.sh`。
实际通过根级脚本恢复正常服务，API PID `2537572`、tick `432857640`，8010健康检查200，
前缀缓存开启、默认上下文262144，PIECEWISE与FULL decode各7/7。
文本/图片/视频及缓存复用35/35定向请求通过，前缀新增命中4896 tokens；
2026-10-10 14:23:34 +08:00核验运行源码与冻结版本一致，vLLM及普通FlagGems未变。
性能实例已停止，容器未重启；完整证据位于
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/04-runs/direct-flaggems-vllm-20261010-1223/`，
详见[015修复与诊断结果](adaptation/015-direct-flaggems-vllm-long-context.md)。
本轮没有重跑GPQA/ERQA、实际262144-token负载或新镜像验证；`framework.yml`状态不变。

限制：历史 graph 红图冷请求单次耗时 219.513 秒；该样本不足以建立性能分布。
更长上下文、正式十并发固定 sanity 回执、正式 FlagEval 精度和
禁用前缀缓存的正式性能尚未完成。当前脚本已实际启动验证，但它不是最终正式
验收脚本；最终正式配置确定后须重新核验。当前服务前缀缓存已开启。

待用户恢复正式验收后，按 profile 顺序完成执行模式回执、十并发 sanity、
冻结阈值的全量精度、性能、证据汇总与最终启动脚本验证；复盘时评估
本次 FlagGems 修复的验证范围和 GDN full graph 限制的退出条件。`framework.yml`
只在对应远端原生证据核验后更新状态，不以这些 Markdown 结论代替验收。
