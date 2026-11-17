# 验收状态

PR整理后的当前实例：`v41-pr-cleanup-restored-v1-20261105`。只修改测试/docstring/算子描述及测试资产路径，数值运行时不变；隔离GPU的13项真实回归通过后，已恢复同一64/FULL/TP8/PP2/V2/async ON/prefix ON脚本，原生生效配置未变，恢复后8项文本输出及独立审阅通过，health200。三仓PR候选材料已准备，完整流程仍未通过，原始失败与限制见[016](../adaptation/016-final-source-review.md)。旧64实例身份与16精度记录保留历史，16原契约记录在[seq64报告](max-num-seqs64.md)，不复用旧PID绑定。

当前服务：按用户要求将 `max_num_seqs` 从16改为64，[有界验证通过](max-num-seqs64.md)，实测引擎同时运行64条序列。8项原生sanity及独立审阅通过，另140条诊断请求完成，0请求错误/HTTP超时/OOM/抢占。服务保持FULL、TP8/PP2、async ON、prefix ON，使用新脚本SHA-256 `364d18c989f8ce0e5e1406e714eb79cd8586af95487512b6c39aaf9845f9bce9`；64配置完整精度未重跑，正式验收未提升。以下v22/16脚本和得分保留为历史证据，不冒充当前64的完整验收；正式服务契约已按当前64脚本与参数重冻结。

最新结果：按用户要求暂不处理GSM8K低分；[GPQA Diamond完整198题、32客户端并发测量](gpqa-c32.md)已结束。用户明确授权13条异常全部计错，完整分母得分strict-match为171/198＝86.3636%，达到用户随后指定的86%门槛；flexible-extract为60/198＝30.3030%，见[计分汇总](gpqa-score-summary.md)。该得分对应引擎16序列、其余排队；另按用户要求开展[max_num_seqs=64验证](max-num-seqs64.md)。原始GSM8K结果及未完成的正式状态保留。

2026-11-05：最终候选v22在两机运行，FULL、TP8/PP2、async ON、prefix on。共享脚本与文本服务契约已冻结，8项并发文本sanity及其独立审阅通过原生结果检查。完整GSM8K v1在742/1319题时因任务Q:停止词截断思考、产生14条空最终答案而终止；原配置、响应和失败终态保留，无可接受完整分数。仅移除该冲突停止词的新任务通过1319条输入及评分不变核对，v2已保留1318份有效缓存，按用户要求将唯一未完成题计错，独立汇总1171/1319=88.78%，未达到原95%门槛，见[得分记录](accuracy-cutoff-summary.md)。本轮评测客户端已结束，原生退出143终态及原始数据保留；该汇总不冒充未修改的完整原生结果。停止词诊断见[017](../adaptation/017-reasoning-stop-condition.md)。正式性能尚未测量。

正式流程状态仍未通过：公开跨仓库固定依赖（plugin:D3）、高精度模型质量比较（plugin:H9）和最终源码审查尚未完成。上述诊断及原生测量不能替代这些门禁，也未据此提升framework状态。当前计划与配置见[评测计划](evaluation-plan.md)。

v21完成同权重eager/FULL执行对照，各rank实际重放至少两次；三个生成token概率对照最大绝对误差1.4305046533991117e-6，未外推全量logits或高精度基线。FULL未降级。v19/v20的15组PP2异步ON/OFF请求均正确且正常完成，此范围内未复现额外异步问题。最新证据见[诊断记录](../adaptation/015-output-health-and-pp-async.md)。

原v22/16配置的ROOT/start-model.sh与两机内部 `/opt/deepseek-v41-runtime/start-model.sh` 字节一致，历史SHA-256为 `58583a1e64346d5e40ebfba0620f78706add35ce22cfc11ad662acc3ccaaee6d`；现64脚本身份以上述更新为准。正常/精度开启前缀缓存，性能仅用同脚本 `--performance` 关闭。验收绑定本次两台实际容器、目标权重与组件身份，不复用其他V4/V4.1平台结果。

以下保留2026-11-04的阶段记录，当前结论以上述2026-11-05更新为准。

2026-11-04：模型类/真实配置解析、两机注意力链、真实16 rank构造与完整文件头映射已通过；
开发eager-service-v4按用户要求暂停，工具准备完成后用户已恢复服务与评测。
v5完成权重加载后在初始化被CPU clone错误分发阻塞；该问题的修复通过两机各64项测试，
v8/v9已完成TP8/PP2、prefix on下async on/off对照，均可启动但真实请求不健康；async off同字节首token也不稳定。详见[诊断记录](../adaptation/015-output-health-and-pp-async.md)。正式验收尚未开始。
102的[FlagEval工具环境](../environment/flageval-tooling.md)已准备并通过CPU依赖、客户端、
原生runner及本地缓存检查；GSM8K完整训练7473/测试1319条已逐行核对，服务预检和正式评测待执行。
后续正式精度选型可参考指定checkpoint自带README中的GSM8K等质量说明，不能将其SGLang/EvalScope
报告当成本次vLLM/MetaX结果。原说明使用thinking/high、max_tokens=256000；当前50000上下文候选
不支持照抄该输出预算，正式计划必须明确生成长度、解析/过滤、完整任务和预先冻结阈值及其适用差异。
