# Hy4-preview GPQA 80K 全量轮失败结果

## 运行身份

- Host：`PPU-07`。
- 服务实例：`PPU-07:550e93f0ba4c:2724059:155832651`，TP16、100K、
  `FULL_DECODE_ONLY` graph。
- 评测：GPQA Diamond 198 题、并发 32、thinking/high、`temperature=0.9`、
  `top_p=1`、`top_k=-1`、`max_gen_toks=80000`。
- FlagGems / Plugin / vLLM：
  `bca444b8569294e7d4e4deff7ddfec7f05682033` /
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 运行目录：
  `/mnt/nfs/users/jinghao/hy4-preview/05-runs/gpqa-full-graph-c32-high80k-t09-20260908-1710/`。
- 总评测时间：5184.8141 秒；runner 最终返回 1。

## 正式结果

`lm_eval` 自身返回 0 并生成 result/sample，但验收契约因 195 个 timeout/无效项将任务标为失败：

| 项目 | 结果 |
|---|---:|
| 原始/有效题数 | 198 / 198 |
| 服务崩溃无效项 | 195 |
| strict | 3/198，1.5152% |
| flexible | 1/198，0.5051% |
| receipt | `failed` |

以上百分比不能解释为模型真实精度：只有 3 条请求在服务退出前得到实际响应，其余 195 条因
EngineCore 退出而被 runner 计为 timeout/refusal。三条真实响应的 strict 结果为：

| doc_id | target | 模型抽取答案 | strict |
|---:|---:|---:|---:|
| 0 | D | D | 正确 |
| 2 | B | B | 正确 |
| 4 | A | A | 正确 |

因此现有证据是 3/3 strict 正确，没有确认的模型错答。doc 0、4 的 `flexible-extract` 为
`[invalid]`，是因为结尾使用裸字母 `D`/`A` 而该过滤器偏好 `(D)`/`(A)`；doc 2 恰好被抽为
`(B)`，所以 flexible 仅 1/3。这是过滤规则差异，不是这三题的语义答案错误。

## 服务退出签名

- 18:06:13 前服务仍以约 118.8 generation token/s 运行，22 running、10 waiting，KV usage
  已升至 98.5%；18:06:23 降至 32.9 token/s，18:06:33 降为 0。
- 18:07:16 至 18:35:18 共记录 32 次 shared-memory broadcast block 等待。
- 18:36:15 EngineCore fatal：`TimeoutError: RPC call to sample_tokens timed out.`。
- fatal scheduler dump：22 running、10 waiting、KV usage `0.9849350649350649`、1 次 preemption；
  21 个请求各调度 1 个 decode token，一个恢复请求需重算 8171 tokens，单步总量 8192 tokens。
  多数请求已生成约 16,204 tokens，恢复请求已生成 15,700 tokens。
- 当前容器仍 alive，但 API、EngineCore 和 TP worker 均已退出，8010 不可用；最终 `ppu-smi`
  显示 16 张卡均为 0%、1 MiB，无残留模型进程。
- 本轮日志计数：SQLite lock 0、bool slice 0、OOM 0、illegal memory 0、work sequence 0、
  `sample_tokens` timeout 1。

这与问题 018 上一轮的负载演化一致，但本轮把恢复步从 4441 tokens 推高到 8171 tokens，且
单步正好达到 8192。现有证据高可信支持“长输出使 KV 接近满载，preemption/recompute 形成
超大混合步骤，某个 TP worker 在模型执行或采样路径超过 1800 秒”这一触发链；仍缺少卡住 rank
的 stack，不能指认具体 Plugin dispatch、FlagGems kernel 或 collective。

`max_gen_toks=80000` 不是已经证明的根因：服务在请求约 16K 输出时就退出，远未达到 80K；
但较高上限允许更多长序列同时累积，确实放大了 KV 与重算压力。继续增加 EngineCore timeout
不符合停止条件，因为吞吐已连续 30 分钟为 0。

## 证据

- `acceptance-result.json`：SHA-256
  `a1194c8a5ef4a5b1367d8a701f38f06a6c6e70a22be3a07f72cfc4d75ba36173`。
- result：SHA-256
  `425f34fb9c8b8bf3deb56c30647e5a8e0ba805fbdbe5ab17b2ecfe9a2b504075`。
- samples：SHA-256
  `25813089af2a1eac80c8018162971d64e3cd1e80ce6a619f2d46238e7363c200`。
- 完整路径由该 run 的 `acceptance-result.json` 记录；本地不复制原始输出。

## 判定与下一步

- 正式 accuracy：`failed`；正式 performance 继续为 `not_started`。
- 先不要直接恢复 c32/80K。下一受控诊断应在新服务上固定同一题集/seed，从能完整结束的较小
  在途集合开始，并在首次 preemption 前后采集各 TP rank stack、8192-token 步骤的算子进度和
  PPU 状态；若出现 rank 异常或 work 序号分叉，立即转为对应最小复现。
- 本轮仅做只读诊断，没有重启服务、清理进程、修改远端文件或续跑评测。
