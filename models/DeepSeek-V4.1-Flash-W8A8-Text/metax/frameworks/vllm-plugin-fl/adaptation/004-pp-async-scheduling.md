# 004：PP与异步调度专项回归

状态（2026-11-05）：已完成目标整模15组async ON/OFF对照，均正常完成且最终答案正确；本次已测范围未复现PP与异步调度叠加的挂起或输出异常。当前FULL、TP8/PP2、V2 runner、async ON的完整1319题第二轮仍在运行，尚无完整精度或性能结论。2026-11-03，用户补充曾在沐曦遇到PP同时开启异步调度异常，要求本次核验是否仍存在。
范围严格为本任务两机、0.28指定镜像和DeepSeek-V4.1-Flash-W8A8-Text，不沿用其他模型/平台结论。

## 前置与单变量对照

- 验证嵌入正常适配流程：先观察目标模型在TP8×PP2、异步调度实际开启时的启动及请求表现。
  未发现异常就继续整体适配和验收，不以额外历史问题排查阻断进度。
- 若出现异常，再固定相同源码、权重、并行拓扑、graph档位、上下文、请求集、采样和前缀缓存设置，
  仅切换原生异步调度开关做单变量对照。
- 分别核实框架默认值、最终有效值、两端worker和通信路径；不能用启动参数出现或HTTP就绪代替运行验证。
- 对照覆盖单请求、并发请求和长短prefill/decode混合，含流式与非流式；固定请求和随机种子，
  重复多轮，记录完成数、超时、token序列/输出健康、TTFT和停滞位置。
- 保留两端日志、进程身份、异常首发点和必要线程栈；失败样本不得删除或以重试结果覆盖。
  只停止本任务服务及其精确后代，保持适配容器运行。

尚未修改异步调度相关产品源码或固定关闭该开关。若复现，先定位stream/event、PP发送接收、
异步输出对象和调度批次交互；按真实根因限定Plugin修复，vLLM保持只读。
诊断A/B不替代正式精度、性能或最终graph档位验收，最终配置及启动脚本需绑定实测结论。

## 最初源码核对

当前只读vLLM HEAD `2cf0a691...` 的 `config/vllm.py` 在无不兼容项时默认启用async；
`max_concurrent_batches` 对V2 runner采用PP-size+1，对V1保留PP-size，并注明V1尚未完整支持PP异步。
这是一项源码限制信号，不能直接证明本次请求会失败。
当前 `GPUModelRunner.sample_tokens` 包含最后PP阶段广播采样token、非最后阶段接收token路径；
后续还需核对Plugin实际override是否保留这些调用及对应stream等待。
没有据此更改只读框架或声称问题已修复。

实际 `WorkerFL` 在 `use_v2_model_runner` 开启时构造上游 `GPUModelRunnerV2`，
否则构造 `ModelRunnerFL`。安装树中 `gpu/model_states` 是包，其 `init_model_state`
支持模型公开 `get_model_state_cls` 扩展点；不能因同名.py文件不存在就判断V2模型状态能力缺失。
V4.1后续将结合该实际入口接入模型状态，最终结论须明确实际采用的runner，不混用V1/V2证据。

已进一步逐函数核对实际Plugin：`sample_tokens` 保留PP广播/接收调用；
`_pp_broadcast_prev_sampled_token_ids`、`_pp_receive_prev_sampled_token_ids_to_input_batch`
与当前只读上游逻辑一致，`_prepare_input_ids` 也等待并清空 `_pp_recv_work`。
因此当前不能把问题归因于Plugin漏接这些上游hook，仍需目标模型A/B实测。

## 独立通信证据及限制

已补官方未修改的sendrecv_perf：16rank、host交错映射、每rank一卡、BF16、8B–256MiB、factor4、
检查开启、warmup5/20次；返回0、Out of bounds0，16/16 rank归属与实际加载库观察齐全。
原生测试为环形send-next/recv-previous；实际全局rank为102:2i、103:2i+1、各自local_rank=i，
覆盖8条102 GPU i→103 GPU i前向PP边，反向环边为103 GPU i→102 GPU(i+1)。
该结果不证明vLLM PP调度、异步输出或graph行为。

结果 `04-runs/mccl-cross-pp-two-stage-tp8-pp2-node-interleaved-20261103/result.json`，
SHA-256 `65ed138f74fd4f021c087588535f386ad8ac0e028bc7b1940fc4ffbe2461d7a6`；
日志SHA-256 `ef5a96b01df7c00d8d1ecbb58d0c245e242725742beb1ac16ea9bbd41308aea6`。
全尺寸平均busbw为2.38865GB/s，保留为该测试指标，不作为端到端速度或PP性能结论。

## 目标整模运行结论

最终运行时代码的v19（async ON）与v20（async OFF）保持FULL、TP8/PP2和相同请求字节。15组对照覆盖短请求并发、流式DONE、中英文、thinking及69-token/1694-token输入，均完成且最终答案正确；reasoning文本不保证逐字相同。证据为 `04-runs/mx-102/pp-async-comparison-v2-20261105.json`，SHA-256 `780a181ea37d635c2a6ac4e6d1bb55e13c57574c64e3a8be1a8a2d2de01857ef`，详细运行绑定见[015](015-output-health-and-pp-async.md)。没有修改只读vLLM，未将该结果外推到V1 runner、其他模型、拓扑或未测压力场景。

v22共享最小启动脚本保持async ON及正常prefix ON，原生八项C8文本sanity均经独立审阅。完整GSM8K首轮出现的14条空最终答案已定位为原任务停止词`Q:`截断thinking，同题只移除该停止词即可恢复最终答案；该证据不支持将其归因于PP异步故障，见[017](017-reasoning-stop-condition.md)。完整第二轮采用独立run/cache身份，保留原1319题、prompt、目标、评分器和0.95门槛，仍需等待终态并校验完整性。

最新结果：用户已要求将唯一未完成题计错，v2的1318份缓存经原生请求键核对并保留，独立汇总1171/1319=88.78%，未达原95%门槛。原生评测客户端已结束，保留退出143及原始证据；模型服务与容器继续运行。先前“仍在运行/无最终分数”描述为历史阶段，当前结论见[末题计错汇总](../acceptance/accuracy-cutoff-summary.md)。该自定义截止汇总不提升正式验收或证明PP覆盖之外的正确性。
