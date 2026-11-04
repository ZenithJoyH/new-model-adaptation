# 适配验收计划与状态

2026-11-03最新范围：用户暂停本轮精度评测，未发起GPQA；正常TP16/PP1 FULL_AND_PIECEWISE服务已恢复，健康接口与一次简短生成通过，见[当前启动记录](../adaptation/020-tp16-pp1-startup.md)。本次启动检查不更新正式执行模式、sanity或精度通过状态。

2026-11-03功能范围：双机TP16/PP1的FULL_AND_PIECEWISE已打通，实际97次decode FULL及1次短prefill PIECEWISE；最简共享脚本重启后的2文本+1图像内容均通过原生校验器与独立审阅，服务保留运行。两机各242项单元和16项GPU图回归通过，TP16通信图200次变输入重放通过。该功能验证没有完成当前源码的正式eager/graph logprob对比、GPQA、性能或镜像验收，整体不晋级functional/optimized，见[精确来源与最终回执](../adaptation/020-tp16-pp1-startup.md)。当前捕获上限16 token，较长prefill按原生NONE运行。

2026-11-02结构调整的64+7项回归，以及此前旧a6的PIECEWISE、2文本+1图像结果均为历史；旧实例已由上述11-03新来源实例替换。旧三请求约235/289/163秒，不作为当前性能基线。正式GPQA、性能及镜像交付保持暂停。

2026-11-01历史：当时stream、编译产物和通信重建仍在定位，外部DeepSeek占用16卡，服务未就绪；后续恢复见[定位与证据](../adaptation/020-tp16-pp1-startup.md)。以下10-28结果属于历史版本，不能覆盖当前来源。

10-28历史范围为mx-101/mx-102的vllm-plugin-fl v7、证据契约v2。阶段3源码审查、
[execution-mode](execution-mode-final-v14.md)及[四并发sanity](sanity-final-v14.md)的原生gate
均已通过；GPQA Diamond198已完成，逐题核实174/198＝87.8788%，达到用户最新85%门槛。
新的正式离线回执及双机gate尚未封存，已按用户要求暂停；详见[当前精度与暂停记录](accuracy-current-state-v18.md)。性能和镜像实际推理验证待完成。

执行模式验收在运行前冻结 `max_abs_error=0.05`：固定确定性请求的生成token和文本必须一致，
图模式与eager比较对应token的自然对数概率最大绝对误差不超过0.05；不同输入至少两次实际
replay，另核实有效图档位和capture。原GPQA门槛0.88保留在原配置，用户后续批准的新门槛为0.85。正式GPQA生成
参数计划temperature1.0/top_p0.95/max_gen_toks60000，最长实际输入2901、上下文65536；
实际KV容量420810 tokens；4路×(最长输入2901+最多生成60000)=251604，均不超过65536。
最终并发冻结为4，原生FlagEval容器按完整198题执行，超时计错误，API/eval重试均为0。
只执行一轮共享的整模型评测，不把两Host的回执误计为396题。

10-28历史服务小集合与正式验收使用批准根的同一 `start-model.sh`，普通启动保持prefix开启，
只有 `--performance` 关闭prefix。最终为显式full-and-piecewise，FULL的原生能力阻塞和
逐级回退证据保留。根脚本SHA为a9ccaa4159df8790dd8c7c1833913e239d3f55ba347a65976cf6be29ba6b6626，
10-28的101 API与102 headless进程/通信连接有对应历史取证。清洁适配镜像已封装并通过两机静态核验，镜像实际推理验证待完成。

精度原生工具使用独立冻结的`03-acceptance/native-tools-pipeline-v1-20261028`，归档SHA
c9caa6c10a830d8f5092b76dd337ff1cf252e66b0dd14402e8c64e4d52ff06cd；
原51文件bundle及历史回执不改写，性能runner保持原冻结字节。
GPQA配置`03-acceptance/gpqa-final-v14.json`已冻结到framework计划；运行
`04-runs/glm-gpqa-final-v14-20261028/`有预检和journal，实际native结果目录为
`04-runs/accuracy-results/glm53-metax-final-v14/glm-gpqa-final-v14-20261028/`。
随附中间计分助手未识别v2数据集描述符，错误保留；不改变正在运行的runner/配置，
只读进度监视另见[016](../adaptation/016-gpqa-progress-display.md)。中间数字不作为正式通过证据。
