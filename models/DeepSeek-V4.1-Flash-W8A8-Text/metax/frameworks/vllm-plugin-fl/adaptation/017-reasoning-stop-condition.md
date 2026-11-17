# GSM8K停止词与reasoning冲突

2026-11-05，Plugin v35 / FGV v43 / FG clone v3，FULL、TP8/PP2、async ON、prefix on，服务v22。这里修正评测生成配置，不修改模型实现、第三方评测代码或评分器。

完整任务v1于742/1319条API响应后被主动终止，未产生可接受的完整分数。补充原始API日志健康检查发现14条最终content为空、reasoning非空，均为 `finish_reason=stop`、`stop_reason="Q:"`，并非超时或length截断。原GSM8K completion式任务的 `until: ["Q:", "</s>", "<|im_end|>"]` 会在思考过程引用题头时立即截断，阻止最终答案生成。配置预检和此前8题工具试跑未覆盖该触发条件，不能据HTTP成功或正常stop宣布输出健康。

在批准根 `04-runs/invalid-full-v1-stop-collision-20261105/` 保存全部14条空最终响应、对应原请求日志及精确进程终止记录。仅向CPU评测容器内、本任务完整脚本/config参数及pid namespace一致的llmrun进程发送SIGTERM；原生终态退出143，时间2026-11-04T22:48:01.112311+00:00，evaluator源码前后一致。原任务/config、原始响应日志及部分缓存保留，不重写为完成或通过。两台适配容器、FlagEval容器和v22模型服务仍运行、health200。

同题C4对照在 `04-runs/stop-collision-probe-v1-20261105/`：通过实际原生OpenAI payload factory构造请求，仅比较stop列表是否含Q:。John买鞋题原设置在11 tokens复现Q:停止、最终null，移除Q:后正常回答360（148 tokens）；Kylie题两设置这次均正常回答50，原完整运行中的失败仍保留，不声称原设置每次必失败。两条新设置均正常结束、最终内容非空，报告passed且live_original_collision_reproduced=true；这些是协议诊断，不是任务精度分数或PP确定性证明。

独立新任务 `gsm8k_cot_zeroshot_v41_reasoning_stops` 只移除字面Q:生成停止词，保留 `</s>`、`<|im_end|>` 及原生EOS处理。原YAML SHA-256 `70bddfe968df3ffa2f270ab31ff9420fb814f063e0fdc209e9af934b6a9c0d6c` 未变；新YAML位于 `03-acceptance/gsm8k-v41-reasoning-stops-20261105/`，SHA-256 `3191221e9bbb887f93c9b8ec84fc95fe84365e8cca503a83168912bdf8c421c6`。严格deep compare确认其余task配置、目标、scorers和filters不变；原生TaskManager逐题核对全部1319条文档及实际渲染prompt字节相同。canonical test rows SHA-256仍为 `32c548f08195e19e33408b844dd7be6aa4bcae457d957bc05909ff4bd4a00595`，渲染contexts SHA-256 `3a1a97b56adcd0f8b5d2a1701c2f5d5492762c2bab5f858ab049205cb03bcf95`。证明位于 `04-runs/gsm8k-reasoning-stop-prepare-v2-20261105/result.json`。

准备新的完整v2运行，保持全1319题、C8、thinking/high、temperature0、top_p1、max_gen32768、seed20261104、timeout7200、每API一次尝试、无任务重试和原0.95门槛。容量依据可复用同字节输入及相同最大生成预算；另采fresh API/PP观察和新服务绑定、冻结新配置与cache/run身份。不会把旧部分输出混入新运行，也不对空答案做离线补分。v2已通过原生预检并冻结启动，配置SHA-256 `5a4518ed89484afd983962a6e2e42738368b374b356d5583339046d7f486d3f5`；新run_id为 `v41-gsm8k-full-v2-20261105`，原生输出位于 `04-runs/flageval-native/deepseek-v41-text-gsm8k-c8-reasoning-stops-full/v41-gsm8k-full-v2-20261105/`。尚无最终分数。

本故障没有PP死锁证据；原15组async ON/OFF对照仍按其原范围成立。正式适配/验收状态保持未通过，公开固定依赖、高精度比较及最终源码门禁不因此豁免。

最新结果：用户已要求将唯一未完成题计错，v2的1318份缓存经原生请求键核对并保留，独立汇总1171/1319=88.78%，未达原95%门槛。原生评测客户端已结束，保留退出143及原始证据；模型服务与容器继续运行。先前“仍在运行/无最终分数”描述为历史阶段，当前结论见[末题计错汇总](../acceptance/accuracy-cutoff-summary.md)。该自定义截止汇总不提升正式验收或证明PP覆盖之外的正确性。
