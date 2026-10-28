# 004：graph能力与最终服务

2026-10-20，H100-149。eager-v5完成15项独立HF参考验证后，仅停止本任务已核实的服务进程树，原生OCR服务和容器均持续运行。

按profile先实测FULL，`04-runs/graph-full-v1-20261020/service.log`记录编译成功后GDNAttentionBackend仅声明UNIFORM_BATCH，vLLM自动选择FULL_AND_PIECEWISE。复查实际GDN metadata builder、CompilationConfig与Triton/FlashInfer prefill选项，后两者共用同一metadata契约，替换prefill算子不能提供ALWAYS支持；未伪造后端能力、未改vLLM。更高模式诊断、源码哈希及退出条件保存在`02-issues/full-graph-limitation.json`。未来需真正支持混合/prefill捕获的后端并重新验证，方可改选FULL。

随后明确启动FULL_AND_PIECEWISE；`04-runs/graph-fap-v1-20261020/service.log`记录19批piecewise捕获及11个full-decode捕获，运行时统计存在FULL和PIECEWISE复用；统计窗口分开，未把启动捕获次数当成运行复用。较大prefill可能以NONE执行，不声称所有请求全图覆盖。该配置下15/15文本、prompt token、completion数及生成token序列匹配冻结HF参考，含4路混合4x/16x；视频另与冻结原生vLLM参考匹配HELLO OCR/TEST 149、prompt534/completion10，不将视频声称为独立HF对照。

最终脚本去掉cudagraph-metrics诊断参数，保留同一模型、源码、权重、BF16/TP1、后端和图级别。实际启动后原生sanity runner重新验证16项文本/图像/视频，4路并发，所有参考文本一致；其中15项再次核对生成token和prompt数。最终服务PID9352及端口归属由挑战nonce、启动时间、命令哈希、boot/container ID绑定，不按健康检查代替参考验证。原始结果在`04-runs/final-sanity-20261020/`。

graph预热功能观察约0.18–0.95秒/请求，视频约1.57秒；eager冷形状编译曾达几十至196.82秒，12秒诊断超时保留。功能观察不构成正式性能、吞吐或加速比结论。未冻结正式性能目标，不能标记optimized。

最终启动器为工作根start-model.sh，容器内部同副本；只含必要环境和vLLM启动命令，前缀缓存开启，正常缓存路径归06-cache。最终适配镜像尚未打包，早期恢复快照缺后续修复，不能当成新镜像独立验收。
