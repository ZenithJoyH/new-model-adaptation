# GLM-5.3-Flash-BF16 / PPU 适配阶段总结（未完成全部验收）

> 2026-09-10 源码终审补充：GLM 与 HY4 的 row-wise prefill/decode top-k 已归并为通用
> dispatch capability；HY4 保留完整 `bf16_indexer_decode` composite model 边界，backend
> 内复用共享 helper，HY4 prefill 也已从本地 `torch.topk` 收敛到该 capability，并修复二维
> 显式 `seq_lens` 被收窄为最后一列的问题。共享修复提交已进入
> `support-hy4-preview@4f9630ca0701d5a569d8c8ee7cff6e039f15a9c9`；GLM
> 唯一子提交为 `d07e87035b253ba407772a168d266ab22c23d845`。FlagGems 为
> `8fef991a6b97d85310f1a3cd9c6425e84d395e5d`。22 项聚焦测试、真实 PPU prefill 集合对照和 decode graph replay、
> TP16 7/7 decode FULL capture、health 与请求 `2`/`5` 均通过；容器 running/restart 0。
> 当前容器没有 HY4 权重，未做 HY4 整模验收；GLM GPQA/性能也未重跑，故本总结仍不是
> 全部验收完成结论。见 [030](../adaptation/030-shared-rowwise-topk-20260910.md)。

> 2026-09-08 启动入口更新：最终 host/container 启动脚本均为
> `/mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh`，SHA-256
> `031923efe0f33a5ce4052f69cc076b48eaad9e8559b4b7e28ba37f759320740f`。脚本由 105 行
> 精简为 26 行，只在现有容器内运行；进入容器后直接执行 `cd
> /mnt/nfs/users/jinghao/glm5.3-flash && ./start-model.sh`。它使用
> TP16、65,536 context、32 sequences、0.90 显存比例、`glm45` parser 和
> `FULL_DECODE_ONLY`；prefill eager，decode FULL graph，不设置
> `VLLM_USE_BREAKABLE_CUDAGRAPH`。
> 日志位于 `05-runs/service/service.log`，cache 位于 `07-cache/service/`，
> tmp 位于 `06-tmp/service/`。2026-09-08 在 PPU-13 完成真实启动：120/120 shard、7/7
> decode FULL capture、16/16 worker、health 200；最终两轮各并发 8，共 16/16 正确且自然
> 停止。Plugin、
> FlagGems、vLLM revision 分别为 `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`、
> `bca444b8569294e7d4e4deff7ddfec7f05682033`、
> `ee0da84ab9e04ac7610e28580af62c365e898389`；容器始终 running、restart 0。
> 入口在 8010 已占用时统一拒绝覆盖；没有 `runtime_dir`、`VLLM_FL_CONFIG`、
> `PYTHONPATH` 或诊断参数。完整参数理由及生命周期见
> [022](../adaptation/022-remote-workspace-numbered-layout-20260908.md)，RLock 与 graph 根因见
> [023](../adaptation/023-full-decode-graph-without-breakable-20260908.md)。本次不是新的正式
> accuracy/performance 轮，以下历史验收状态及 GPQA 失败结论不因此刷新。

> 2026-09-06 当前权威状态：正确 BF16 快照已完成服务适配，eager/graph 最小推理及
> graph 并发 8 sanity 已通过；全量 GPQA 正在运行，故本总结尚非最终验收结论。
> 以下 2026-09-04 内容均为历史记录。

当前代码基于 ZenithJoyH `support-hy4-preview@5329cb1`，editable 安装路径为
`/workspace/vllm-plugin-FL-glm53-hy4-adaptation`。最终 graph 配置为 TP16、50K、seq32、
PIECEWISE 默认捕获规模、`VLLM_USE_BREAKABLE_CUDAGRAPH=1` 和
`VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=1800`。主启动脚本不包含 `runtime_dir`、
`VLLM_FL_CONFIG` 或实验性的捕获尺寸列表，插件自动读取 bundled `thead.yaml`。

本轮关键修复是在插件有状态 `sparse_attn_indexer_kpool` 上增加
`@eager_break_during_capture`。这消除了 graph 下重复 `!` 以及 `9-9 -> 3/6` 的静默
错误，同时保留其余模型 PIECEWISE graph。最终服务 PID `770859`，健康检查 200；
固定并发 8 两轮均 8/8、零错误/超时，27.84/47.72 tokens/s。完整诊断、证伪实验、
补丁与生命周期证据见 `../adaptation/008-graph-correctness-fix-20260906.md`。

GPQA 正式轮使用 FlagEval v1、原样 `test/Accuracy_test/llmrun.py`、198 题、并发 64、
独立缓存，strict-match 门槛 88 分；2026-09-06 11:11（UTC+8）preflight 后启动。
在唯一题数、零超时、结果文件和最终分数全部核验前不标记完成，也不启动正式性能评测。

2026-09-04 用户确认权重选错，要求撤销全部当前 GLM 适配并重新开始。
正确目录 `/mnt/cpfs/models/GLM-5.3-Flash-BF16` 尚在下载；当前无可验收服务。
以下内容全部为历史记录，不可沿用为新快照的通过证据。见 [撤销记录](../adaptation/016-withdrawal-20260904.md)。

2026-09-04 21:26补充：FP8排除名单前缀已通过插件mapper修复，34个b_proj BF16分配、
排除名单/权重映射专项与313项回归通过。实际启动越过原错误后，因use_mla=False导致
已有CUSTOM prefill未启用，在MLA构建阶段失败。API已退出，平台仍blocked，未运行新精度测试。
详见 [前缀修复及剩余MLA配置问题](../adaptation/005-fp8-prefix-fix-20260904.md)。

2026-09-04 最新适配增量：FlagGems-vllm KDA prefill 已通过插件 DEFAULT dispatch 接入，
8组eager/graph、28项组件、313项插件回归通过。原库 auto 路径不支持PPU的TLE，以及变长
graph缓存旧metadata导致17%输出误差，均已打包在容器 `/bug/flaggems-vllm-kda-ppu-5865ed5`；
命令为 `CUDA_VISIBLE_DEVICES=0 python3 repro.py` 和
`CUDA_VISIBLE_DEVICES=0 FLAGGEMS_CHUNK_KDA_BACKEND=triton python3 repro.py --graph --varlen`。
接入复用新库计算内核，仅插件补齐GPU动态metadata和beta/backend契约。
当前模型已更新为 `/mnt/cpfs/models/GLM-5.3-Flash` FP8；BF16 b_proj因前缀匹配错误被量化导致
启动失败仍未修复，平台blocked。本轮不是正式验收，未启动服务/GPQA/性能；以下为历史状态。
完整证据见 [KDA接入记录](../adaptation/012-kda-integration-20260904.md)。

最新：用户已明确要求安装新版；HY4基线5329cb1适配插件已editable安装并通过
独立导入、GLM注册和默认配置验证。旧三个插件树移至可恢复归档
`/workspace/.plugin-archive/glm53-20260904/`，未丢弃未提交修改。
原模型目录config.json当前缺失，整模未启动；1项原有回归失败尚未解决。
以下“未安装”是此前阶段状态，当前不能宣称整模或精度验收完成。

当前变更：用户要求后续基于support-hy4-preview@5329cb1，GLM代码已迁入独立新树，
317/318测试通过，1项mock兼容问题因拟修改被安全审查拒绝而待批准；尚未切换安装。
服务保持停止，以下eager/graph和GPQA结果均为旧基线历史，不能用于新基线验收。
详见 `../adaptation/009-hy4-base-migration-20260904.md`。

诊断补充：21个TIMEOUT标记实际为30000-token长推理截断，content为空，经评测
None→TIMEOUT分支生成；不是计时超时。部分明确重复，未见明显编码乱码，更深层
模型/采样/数值原因未定。参见 `../adaptation/007-gpqa-timeout-marker-diagnosis-20260904.md`。
此次只读排查，未改服务、生成参数或评分；下文“原因待查”指此前状态。

最新结果（13:31）：c64-t1800轮13:25:12以exit.code=1结束，无活动评测进程。
198唯一题目中21个TIMEOUT标记、177有效，完整结果文件存在但有效性校验失败，
acceptance-result.json未生成。文件原始strict-match=82.323232%、flexible-extract=
31.313131%，不是有效全量精度，88分验收未通过。服务PID314202仍在且health成功，
不能把本轮失败归因于已发生1800秒RPC超时；标记来源待排查。accuracy/acceptance
blocked，正式性能未启动，非全部验收完成；监控结束，日志与数据保留。
耗时64分14秒、实际客户端并发64、曾观测服务32 running+32 waiting；详见
`gpqa-full-20260904.md`。以下为启动历史。

用户授权将RPC超时改为1800秒并验证后重跑。新graph PID314202已通过
2937-token prefill两次（112.0945/23.3454秒，均正确）及并发8 sanity（8/8、零错误，
109.4805 tokens/s）。c64-t1800全量新轮12:20:30预检通过，12:20:58启动，runner12171，
12:21:46确认64并发运行中，accuracy为in_progress。旧故障未被宣称根治，
最终准确率仍待新轮完整结果；以下保留历史过程。

最后核实：2026-09-04。状态：functional（历史最小推理已通过）；正式精度验收因服务运行故障阻塞，不是 optimized/任务完成，当前服务健康状态不能沿用此前结论。

## 范围与可复现环境

- 主机 `PPU-13`，16×PPU-ZW810E 96 GiB；容器 `glm5.3-flash`。
- 模型 `/mnt/cpfs/models/GLM-5.3-Flash-BF16`，BF16 120 个分片。
  config SHA256 `33e63ec7fe607658be712bd6dd3c16c6549960d8e7f0483d34b939881b55f943`。
  本地 checkpoint 未提供可独立确认的上游 revision，不能用插件提交替代权重 revision。
- 镜像 `hy4-ppu07-snapshot:20260903`，ID
  `sha256:29a6712e24ca8e758ac8b33d3412892f0541bff108e2c057445fa671578237f6`。
- Python 3.12.3、Torch 2.10.0、vLLM 0.24.0、Transformers 5.8.1、FlagGems 5.3.5。
- vLLM `/workspace/vllm` 固定 `ee0da84ab9e04ac7610e28580af62c365e898389`，持续 clean。
- FlagGems `/workspace/FlagGems` ff-only 同步到
  `db33988eca77bcc45bb70719ca6b1db94229b4c6`，保持 clean。
- 专用插件 `/workspace/vllm-plugin-FL-glm53-adaptation`，基线
  `265824413097126166b1072e1f564d00661a347a`（support-glm-5.3-flash）。
- 参考：模型配置/实现、架构分析、环境分析、插件专用分支与其中 provenance；
  初期审计的官方 vLLM GLM 模型参考提交 `4500c80c080328dfe62435d083f4063e00d987df`。

## 实现与启动

采用插件专用分支的 GLM5 Next/KDA/mHC/KPool/PPU BF16 cache 及 dispatch 路径，
保留 ConditionalGeneration 视觉塔，没有改为纯文本架构。
本轮最终专用插件新增四文件改动：有效 profile 黑名单传播、slice 排除、
worker MLA backend/压缩缓存 adapter 安装、BF16 sparse MLA topk_length 参数转发。
重放补丁为 `../adaptation/patches/glm53-2658244-current.patch` 和
`../adaptation/patches/glm53-mla-topk-length.patch`；经验证的部署 playbook 同目录可查。
远端完整 diff SHA256：`c058a681a4814d9a78e3038739d694922ce704ba619e632489974a5f453cd55a`。

当前 graph 服务 PID 123167；启动脚本 `../adaptation/service/start_glm53_graph.sh`，
容器路径 `/workspace/glm53-adaptation-runtime/graph/start.sh`。
配置 TP16、max_model_len=50000、max_num_seqs=32、显存比例 0.90、port8010、
reasoning-parser glm45、FULL_AND_PIECEWISE，capture sizes 1/2/4/8/16/32。
设置 `VLLM_USE_BREAKABLE_CUDAGRAPH=1`：保留分段 graph 和必要 eager 区段，
禁用 torch.compile。不能表述为整个模型一张无中断图。
模型配置实际最大上下文 1048576，按规则初始使用 50000，没有缩短以掩盖问题。

容器始终 running、RestartCount=0。只管理本任务 inference API/worker，
服务切换过程与五次 eager 尝试见 `../environment/service-state.yml`。
原 Hy4 插件目录没有被替换或丢弃其既有修改；初期尝试的回移代码保留，
当前服务不使用该目录。没有修改 vLLM 源文件，没有提交或推送。

## 已验证结果

- 专项模型测试 27/27、dispatch 275/275、PPU eager/graph 组件 28/28。
- slice 配置回归、worker MLA 注册测试通过。
- 四种压缩页布局的 eager/graph reshape、存储共享、replay 通过。
- BF16 sparse MLA topk_length 数值与动态长度 graph replay 通过，
  FP32 reference，atol/rtol=0.02，包括有效长度为零的边界。
- eager 与 graph 实际请求均返回严格正确的 `2`；相同 23 输入/51 输出 tokens，
  分别 9.3908 秒与 2.3154 秒。这是最小请求对照，不是正式性能基准。
- 后续 sanity 均使用 graph：两轮并发 8 均 8/8 正确、零错误/超时。
  首轮 33.51 tokens/s；复测 71.86 tokens/s、平均延迟 5.67 秒、最大 5.83 秒。
  复测每卡显存 88792–88808 MiB，平均利用率 46.67%–62.33%，峰值 100%。
  详见 `graph-sanity-results.md`，吞吐包含 reasoning tokens。

## 遇到的问题、原因与处理

1. 原镜像没有 GLM5 Next 模型支持。初期独立回移暴露 vLLM 版本/cache-manager
   兼容差距，随后选用固定提交的专用插件分支；保留失败探索记录。
2. FlagGems FP8 indexer 在 PPU 编译为不支持的 fp8e4b8。改变 Torch FP8 dtype
   仍失败；当前采用专用插件 PPU BF16 cache 路径，不声称修复了 FlagGems 本体。
3. worker 黑名单读取忽略 VLLM_FL_CONFIG，加之 FlagGems slice 缺少 step 默认值，
   首次启动报 TypeError。修复有效 profile 读取并排除 slice，原生操作恢复正确。
4. MLA prefill backend 只在配置进程注册，worker 构造失败。插件模型构造入口补齐幂等注册。
5. GLM compressed-cache adapter 同样只在配置进程安装，worker 通用 reshape
   将缓存尺寸扩大 6 倍。补齐 worker 安装入口，小缓存回归及整模启动通过。
6. vLLM 0.24 BF16 sparse MLA 调用新增 topk_length，插件旧签名不兼容，首次请求 500。
   将有效长度完整传给同步版 FlagGems，不忽略 mask 语义。
7. 测试传入 enable_thinking=false，但本 checkpoint 固定 `<think>` 开始，导致
   parser 与模板开关不一致。移除不支持的测试参数，未修改原模板/parser，最终答案正确分离。
8. 首轮权重加载预取较慢，I/O 增量证明仍推进；未误判为死锁或重启容器。
   冷加载 482.36 秒，热缓存加载约 28–32 秒。

## FlagGems 复现包

均位于适配容器根目录 `/bug`，非模型/插件/vLLM 源码树，已执行并验证错误：

- `/bug/flaggems-indexer-k-quant-ppu-e4b15`：`CUDA_VISIBLE_DEVICES=0 python3 repro.py`，
  PPU FP8 编译错误。当前 BF16 路径规避。
- `/bug/flaggems-slice-default-step`：`CUDA_VISIBLE_DEVICES=0 python3 repro.py`，
  缺省 step TypeError。当前 profile 黑名单规避。

进入相应目录执行；包内包含镜像、revision、输入、seed 与预期/实际行为。
当前选用专用分支已有插件 Triton 实现，没有在本轮新增独立算子实现。

## 未完成项与下一步

最新配置交付：已将原 PPU profile 放入插件自动加载目录
`vllm_fl/dispatch/config/thead.yaml`，不改加载器；删除主脚本的 VLLM_FL_CONFIG、
runtime_dir、PID 写入和日志重定向，日志/PID 由宿主机入口管理。
后台 stdin 传脚本曾导致空日志退出，已改为复制文件后执行并验证。
当前 PID 158392：最小推理 2.2982 秒，固定并发 8 全部正确、零错误/超时，
105.2267 tokens/s（仅 sanity，不宣称优化或正式验收完成）。vLLM 未变，容器未重启。

后续按用户要求直接安装专用插件并精简启动脚本：删除 PYTHONPATH/VLLM_PLUGINS、
trust_remote_code、显式 mp 和多余变量，保留必要 PPU profile 与 graph/资源设置。
新 PID 145798 已通过 graph 最小推理（2.3109 秒）与并发 8 回归（8/8、零错误，
47.6464 tokens/s，重启后首轮 sanity，非正式性能基准）。容器未重启，vLLM 未修改。
安装命令、边界与证据见 `../adaptation/013-plugin-installation.md`；此前历史结果仍保留。

- 用户已确认 GPQA Diamond 198 题通过阈值 88 分；以原始 strict-match >=0.88
  判定，完整唯一样本数及零超时同时满足。不以简单题 100% 代替正式精度。
- 后续严格使用目标机 FlagEval v1 容器内 `test/Accuracy_test/llmrun.py`，先 preflight
  再全量；首轮8并发因用户要求提升并发已主动停止并保留证据。64请求并发新轮
  11:19:12 preflight通过，11:19:16后台启动，runner PID11453；11:50:32失败退出，
  11:55:27确认exit.code=1、进程退出。EngineCore返回500后连接失败，102个TIMEOUT
  导致结果校验失败，没有有效全量strict/flexible成绩。根因待诊断，未自动修复或重跑。
  模型seq32未变，超额客户端请求排队；证据见 `gpqa-full-20260904.md`。
- 正式准确率通过后才运行 `test/perf_test/` 和适用通信验证；均使用当前已通过的 graph 配置。
- 正式验收、最终 summary 收敛及 retrospective 未完成，整体工作流未关闭。
- 多模态实际请求、MTP/speculative、完整 1048576 上下文均未验收；不能声称支持已验证。
