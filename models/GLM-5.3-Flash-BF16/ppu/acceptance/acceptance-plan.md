# 适配验收计划与证据

除执行模式验收外，后续验收全部使用已通过的 `graph` 模式配置。

## 4.1 执行模式验收

- [x] `eager` 模式完整服务可以运行
- [x] `graph` capture/replay 模式完整服务可以运行
- PPU-13 / glm5.3-flash，镜像与 source revision 见 `../environment/runtime-config.yml`。
- 相同 TP16/50K/seq32：eager job `j207365825255.119975`，graph job
  `j81575656851.250206`，均返回 0；输入“计算 1+1，只输出数字答案。”，
  temperature 0、max_tokens 128，最终 content 严格为 `2`，finish_reason stop。
- eager 9.3908 秒，graph 2.3154 秒，均 23 输入/51 输出 tokens，包含思考 tokens。
- graph 采用 breakable FULL_AND_PIECEWISE，1/2/4/8/16/32 各档完整捕获；
  不使用 torch.compile，部分路径保留 eager 区段。后续验收均使用此 graph 服务。
- 命令见 `../adaptation/service/start_glm53_{eager,graph}.sh`；
  日志 `/workspace/glm53-adaptation-runtime/{eager,graph}/service.log`。
- 验证时间：2026-09-04 07:54:43，容器 running/RestartCount=0，vLLM clean。

## 4.2 八并发小批量精度与性能验证

- [x] 固定简单请求全部正确
- [x] 无错误、超时或明显性能异常
- 并发数：8
- 请求集与预期：`graph_sanity.py`，8 个简单算术固定问题、Barrier+8 workers。
- 通过条件：8/8 正确、无错误、每请求低于 60 秒、聚合输出至少 20 tokens/s、
  16 卡显存和利用率采集成功。吞吐下限参考已验证单请求约 22 tokens/s，
  是发现明显退化的保守 sanity 门槛，不是正式性能指标。
- 执行 wrapper：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/run-ppu13-glm53-graph-sanity.yml`；两轮均通过。
  首轮 33.51、重复轮 71.86 输出 tokens/s；完整小结果见 `graph-sanity-results.md`。

## 4.3 全量精度测试

最新状态 `in_progress`：padded physical slot 根因修复与 graph c8 sanity 通过后，
2026-09-06 15:59（UTC+8）启动新的隔离正式轮。运行目录为
`/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-kpool-slot-fix`；
198 题、客户端 c64、独立空缓存，固定原始 strict-match ≥0.88 且不允许 timeout。
runner PID 17033；启动时实际观测 27 running + 37 waiting，随后 32 running + 32 waiting。
服务健康且尚无旧 illegal-memory-access 签名。未完成前不把阶段分数当正式成绩，
不启动性能测试。完整记录见 `gpqa-full-20260906.md`。

以下 blocked / c64-t1800 内容均是历史失败轮，保留作对照，不代表当前轮状态。

以下为启动历史：c64-t1800轮12:20:30预检通过，graph PID314202，先完成2937-token两次验证及
并发8 sanity（job j675029313951.1522012）。12:20:58正式启动，runner12171，
64并发、198题、无旧缓存，当前in_progress。以下blocked描述为旧c64轮历史。

当前状态 blocked：11:55:27确认c64 runner退出、exit.code=1。EngineCore错误及连接
失败导致102个TIMEOUT响应，11:50:32结果校验失败；无有效全量成绩，根因待诊断。
未自动重跑或修改服务，定时监控已结束。

- [x] 使用 `test/Accuracy_test/llmrun.py`
- [x] 使用适用的 FlagEval 镜像
- [x] `--preflight-only` 通过
- [ ] 样本数、输出文件、指标和通过标准已核实
- 用户已确认 88 分门槛；固定原始 strict-match >=0.88，198 唯一题目完整、无超时，
  同时报 flexible-extract。不四舍五入放宽门槛，不事后选择更高指标。
- 只读核实了已有 `flageval_llmeval-jinghao`：正确 v1 镜像、host network、
  Python 3.10.20、lm_eval、GPQA 缓存目录存在，能够访问当前 graph 模型。
  首轮8并发已按用户要求主动停止，保留日志和缓存；新64并发轮11:19:12预检通过，
  实际198题及服务可用，11:19:16在独立c64目录后台启动，runner PID11453。
  使用独立缓存，模型服务seq32保持不变，64客户端请求可排队；不启动正式性能测试。
  详见 [全量运行记录](gpqa-full-20260904.md)，没有重启该评测容器或模型容器。

## 4.4 正式性能与通信测试

- [ ] 全量精度已经通过
- [ ] 使用 `test/perf_test/` 完成性能测试或 profiling
- [ ] 需要时使用 `test/nccl_test/` 完成通信验证
- 基线、变量、指标和结果：

## 4.5 验收证据完整性

- 服务模式、容器、镜像、命令、配置、环境和结果路径：
- 未完成项和阻塞项：
