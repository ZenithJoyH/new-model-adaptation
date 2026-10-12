# GPQA c64-t1800 的21个 TIMEOUT 标记诊断

2026-09-04，只读核验 PPU-13 / glm5.3-flash 服务对应的
flageval_llmeval-jinghao 评测容器。模型、镜像和代码基线沿用
`015-timeout1800-validation-20260904.md` 与 `../acceptance/gpqa-full-20260904.md`。
未改远端源码、配置、响应或缓存，未发起推理，未重跑或重启。

## 已确认的直接原因

从 c64-t1800 的 runner.log 解析全部198条原始API响应，正常stop177条，length21条。
21条全部 completion_tokens=30000、finish_reason=length、message.content=null，
但 message.reasoning 非空（57565–139716字符）。保留的 usage 与21个失败doc_id
逐一唯一匹配。它们成功返回了JSON，不是网络或服务执行计时超时。
请求耗时1659.36–2546.27秒（27.66–42.44分钟），均未到7200秒。
1800秒是单次worker执行RPC等待上限，不是完整请求生成时长上限；请求总耗时超过
1800秒并不代表RPC超时。

链路：30000-token生成上限耗尽 → 仍只有reasoning、没有最终content →
`LocalChatCompletion.parse_generations`只读取content，得到None →
并发结果展开将None改成`<TIMEOUT>` → evaluator将该题记零并设置timeout=true →
llmrun按allow_timeouts=false拒绝本轮有效性校验。

- `/app/lm_eval/models/openai_completions.py:163–172`：读取message.content，不取reasoning；
  OpenAIChatCompletion继承该实现。
- `/app/lm_eval/models/api_models.py:436–452`：先取得并记录JSON响应，再解析答案，保留usage。
- 同文件759–769：答案None转换为TIMEOUT；这不是答案字母过滤器导致。
- api_models.py SHA256 `493c667142263338f93894adf5638403269081b8329579eac1a64eda70383720`。
- openai_completions.py SHA256 `83cb3d92d08feaf919b91562a3aeab5055b52873eed729845f37c33a2370e38e`。

## 重复与乱码检查

21条reasoning均无Unicode替换字符U+FFFD；所检查的尾部是可读的英文、公式或
生物序列，不像编码乱码。此检查不是模型数值正确性的证明。
存在过度推敲和部分明确重复，但不能把全部21条都说成相同文本死循环。

| doc_id（0起算） | 时间/秒 | 输出表现 |
|---|---:|---|
| 168 | 1829.75 | 完全相同的长段落最多39次，连续20词片段最多82次，明确重复 |
| 75 | 2356.21 | 相同长段落最多5次；末尾表示已选答案后又继续重新考虑 |
| 157 | 2033.12 | 相同长段落最多3次，末尾仍在两个选项间推敲 |
| 27 | 2018.77 | 没有重复20词片段，但持续重新审视化学反应，截断在句中 |
| 120 | 2546.27 | 最长请求，仍在分析立体构型，content为空 |

重复统计口径：按空白分词后的滑动20词窗口，及按双LF切分、去首尾空白后长度
至少80字符的完整段落；统计每题内最大出现次数，不是错误率或自动分类阈值。

全部doc_id：27,32,64,71,74,75,76,79,81,88,90,94,120,127,130,145,147,157,168,170,185。
请求ID、时间、字符数、重复统计可由
`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/diagnose-ppu13-gpqa-timeout-markers.yml` 只读重现；原始文本留在远端runner.log。

## 结论与边界

应将此前“21个超时请求”修正为“21个长推理截断、空最终答案，被评测误标为超时”。
未触发本轮已配置的7200秒客户端计时超时；此前服务日志核验无RPC超时/退出。
再调大时间超时不会解除30000-token截断。增加token预算可能帮助部分题，但对重复
生成不能保证有效，且会增加成本；当前没有更改预算、采样或评分。
是否由模型固有长思考、采样设置、数值误差或适配路径引起，尚无对照实验证据。
没有确认新的FlagGems算子缺陷，不应臆造算子复现或直接归因于PPU。

固定原始评分仍strict163/198=82.32%、flexible62/198=31.31%，未通过88分。
不能把reasoning中出现的候选答案拿来事后重评分，也不能按177题子集替代全量验收。
下一步若获授权，应先对代表题保存完整reasoning/finish_reason做单变量复现与对照，
再决定调整生成预算或排查数值路径；本次只完成诊断。
