# 验收计划

对象 `PPU-01` / `qwen3.8-flash`，BF16 文本，TP8 设备 8–15，maxlen 65536，端口 8038。
1. eager和FULL_DECODE_ONLY graph各完成最小推理，记录精确配置和结果。
2. 此后全部使用graph。固定8并发，7个短算术/字符问题及1个长背景简单问题，逐一检查答案，记录实际并发、延迟/吞吐、PPU利用率/显存；correctness和performance review都通过后方可进入精度。
3. FlagEval v1 容器执行仓库 `test/Accuracy_test/llmrun.py`；先 `--preflight-only`，再执行 198 题完整 GPQA Diamond。按用户 2026-09-11 的要求将客户端并发设为 64；服务保留已验证的 `max_num_seqs=32`，多出的请求由服务队列承接。为覆盖旧轮次 22 个达到 30000-token 上限的样本，将 `max_gen_toks` 提高到 60000，与服务 maxlen 65536 配套。在获取任何正式结果前将通过条件固定为 strict-match ≥88%（至少 175/198 正确）、198 题完整且错误/超时为 0；不接受缺样本、异常退出或只完成子集。模型卡 91.7 仅作参考，不能视作本机结果。
4. 全量精度满足通过条件后，才使用test/perf_test中的vllm_perf.py模型专用副本做固定graph配置性能测试；case不能超过50000上下文。当前公共test/nccl_test仅有mthreads脚本，PPU通信需专用wrapper并说明其来源/范围。
5. 汇总证据与所有未通过项，完成复盘。视觉/MTP/量化/PP/EP不凭文本结果宣称支持。
