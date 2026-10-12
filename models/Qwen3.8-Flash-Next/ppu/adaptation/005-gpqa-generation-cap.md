# 005：GPQA 长推理达到生成上限

## 元数据

- 状态：`open`
- 首次出现时间：2026-09-06 07:29:34 UTC
- 最后验证时间：2026-09-06
- 模型：Qwen3.8-Flash-Next，配置 SHA256 `889658f2508e8c61d409b02e70e0d78d8d4452ec65aaafbe129805d213d2e74b`
- 平台与 Host 别名：PPU / `PPU-01`
- 容器名称与镜像：`qwen3.8-flash` / `glm5.3-flash-ppu13-snapshot:20260904-215131@sha256:7755ef5656bd33703eb7c3c81fb6b2099b154284ba582488861f5ec99e3f7b30`
- Plugin / FlagGems / vLLM revision：`2b2fe95…` / `34bd6d6…` / `ee0da84…`
- 执行模式与负载：graph、TP8、GPQA diamond 198题、并发32

## 问题现象

- 198/198请求写入缓存，服务未崩溃、健康200、零抢占；评测耗时17368.614秒。
- 22个回复达到 `max_gen_toks=30000`，`finish_reason=length`，旧runner将其记为 `<TIMEOUT>`。
- lm-eval strict 为0.838383（166/198），低于预设0.90；非上限样本为166/176，但子集比率不能替代正式指标。
- 旧runner重试后产生两组结果文件和每组396行/198唯一样本；最终rc=1。该历史运行没有新版
  `acceptance-result.json`，不能作为正式通过证据。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [003 TP sample_tokens超时](003-tp-sample-tokens-timeout.md) | 都出现“超时”字样 | 本次worker持续前进、无RPC退出、无通信序号分叉，实际是生成长度截断 | 高 | 明确排除继续增加RPC timeout；诊断生成上限 |

## 诊断与假设

已验证：模型声明最大上下文262144；当前服务50000；22个响应均达到30000生成上限且请求仍正常返回。
当前假设：提高生成预算后，其中一部分会输出最终答案并使完整分数提高。尚未验证这些样本是否会在
60000前自然结束；若继续达到上限，可能存在推理循环，不能无限增大预算掩盖。

## 受控尝试

|轮次|唯一变量|基线|本次设置|命令或准确位置|结果|结论|
|---|---|---|---|---|---|---|
|0|基线|—|max-model-len50000、max_gen_toks30000|`acceptance/accuracy-index-progress.json`及远端唯一输出目录|22项到达上限，strict166/198|正式失败|
|1|服务上下文|max-model-len50000|max-model-len65536|下方服务切换命令；其他启动参数不变|PID1360924于20:33:43就绪，graph模型ID通过；最小推理返回2、2.546秒；容器持续运行|服务容量和最小正确性通过|
|2|子集生成预算|max_gen_toks30000|max_gen_toks60000|固定轮次1服务，只重跑22个上限样本|已启动，远端目录 `/evaluation/diagnostics/capped22-max60000-20260906`|运行中|

执行入口与边界：

```bash
./scripts/playbook -i inventory/hosts.yml /tmp/qwen38-maxlen65536-service.yml
./scripts/playbook -i inventory/hosts.yml models/Qwen3.8-Flash-Next/ppu/acceptance/inspect-capped-samples.yml
./scripts/playbook -i inventory/hosts.yml /tmp/qwen38-capped22-rerun.yml
```

轮次1只向从 `/workspace/qwen38-adaptation-runtime/graph-timeout1800-index-c1/launch.json` 精确读取的
API PID及其本任务子进程发送信号，验证退出后在容器外临时目录
`/workspace/qwen38-adaptation-runtime/graph-maxlen65536-c1` 以原参数启动，仅将
`--max-model-len 50000` 改为 `65536`。容器不停止、重启或删除。轮次2从旧评测结果精确选择
`finish_reason=length` 的22个唯一样本，使用新独立缓存/输出路径和 `max_gen_toks=60000`。

## 根因

- 已验证根因：当前失败门禁的直接原因是22项达到30000生成上限并被标为超时，同时完整strict低于90%。
- 当前缺失证据：这些长推理是有效但预算不足，还是不会自然终止的重复/循环。

## 解决方法或 Workaround

- 当前为诊断，不是正式解决方案；不改vLLM或Plugin源码。
- 临时过程代码只放在容器 `/workspace/qwen38-adaptation-runtime/` 和控制端 `/tmp`。
- 完整正式验收仍需新版正式契约、完整198题、并发至少32、零超时及strict至少90%。

## 验证结果

- 最小回归、eager、graph和数值结论：待轮次1/2完成后补充。
- 子集结果不更新 accuracy 为passed，也不启动正式性能。

## 限制与下一步

- 65536处于模型声明范围，服务已经完成权重加载、graph捕获、模型ID和最小推理验证；长生成
  子集仍在运行，尚不能据此
  判断KV长程稳定性或最终准确率。
- 若60,000仍有截断，停止继续增大并检查生成内容是否循环；若全部自然结束且答案有效，再以相同
  graph配置和新版正式契约完整重跑198题。

## 经验沉淀

- 知识库处理状态：`local-only`
- 候选知识库条目：需先验证长生成诊断结果，不提前推广。
