# 006：默认 thinking 使十并发短题输出截断

## 元数据和签名

- 状态：`mitigated`；2026-09-28，`H100-149` / `MinicpmV4.7-35B`，GPU 4、5，TP2。
- 组件：checkpoint 的 `tokenizer_config.json` chat template 与 OpenAI chat 请求参数；Plugin 基础 HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`，vLLM wheel `0.24.0+cu129`。
- 执行模式：`FULL_DECODE_ONLY`，前缀缓存开启，`max_num_seqs=8`，客户端并发 10，算术和纯色图各五题。

首轮 `04-runs/graph-decode-full-tp2-20260928/sanity10.json` 的 10/10 最终答案正确，但从冷混合批量开始耗时 276.31 秒，有效同时运行峰值 8、排队峰值 2。同一服务、同一输入的重复轮 `sanity10-repeat.json` 耗时 35.251 秒，其中 2+2 样本在 256 completion tokens 后以 `finish_reason=length` 截断，最终只留下思考文本；9/10 正确。这是正式 sanity 的失败，不能把正文中出现数字 4 当成最终回答。

## 受控比较与原因

目标权重的 chat template 在 `add_generation_prompt` 时，默认以打开的 `<think>` 开始；传入 `enable_thinking=false` 则输出空思考段并进入最终回答。当前 vLLM OpenAI chat 协议接受 `chat_template_kwargs`，无需改动共享服务或只读权重。只改变该请求字段后，同一 2+2 题在 0.513 秒内以 `finish_reason=stop` 直接返回 `4`。再以同一服务、同一十题、相同 token 上限，仅加入 `chat_template_kwargs: {enable_thinking: false}`：`sanity10-no-thinking.json` 为 10/10 正确、零截断/错误，29.551 秒；实际运行峰值仍为 8、排队 2。

该对照证明截断与默认 thinking 路径相关，不能推出所有长任务都应关闭 thinking；正式精度的任务配置和阈值必须单独冻结。关闭 thinking 改变生成 token 数，不可把两轮总吞吐直接当成模型性能提升。当前请求级缓解适用于短答案 sanity；无权重或 Plugin 源码修改。

后续只将 `max_num_seqs` 从 8 提高到 10，保留 TP2、`FULL_DECODE_ONLY`、请求和 GPU 4、5。混合十题首次 297.227 秒、重复 37.753 秒；纯文本十题首次 64.242 秒、重复 1.306 秒。四轮均 10/10 正确，重复轮观测到引擎同时运行峰值 9、排队峰值 0。原始结果保存在 `H100-149:/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/graph-decode-full-tp2-seqs10-20260928/`。这验证了十客户端并发在该配置下没有排队，但不能把峰值 9 解释为十个请求同时处于引擎运行态，也不能以冷启动时间作为正式性能结果。该服务已按归属进程停止并确认 GPU 4、5 释放。

## 限制与退出条件

验收要逐题检查最终答案、`finish_reason=stop`、完整样本数和超时。若后续正式任务需要推理链，必须选足够的输出预算并以冻结配置验证分数；不得用短题无 thinking 的结果替代正式精度。当前 workaround 的退出条件是默认模板短题不再无界展开并通过相同十并发回归，或按用途明确区分 thinking 配置。知识库处理：`local-only`。
