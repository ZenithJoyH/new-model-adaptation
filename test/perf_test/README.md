# 性能测试入口

五个公共入口均调用 `perf_common.py`，只测量已运行的服务，不部署、配置或重启服务。
正式性能验收仍须通过工作流前置检查；成功报告不自动更新平台状态，也不代替服务身份、
健康状态和执行模式的现场证据。执行前还须核实目标设备、服务和其他现场负载。

| 入口 | 客户端 / 协议 | 默认 runs / skip-first | 默认 case 集合 |
| --- | --- | --- | --- |
| `vllm_perf.py` | `vllm bench serve` / completions 或 chat | 3 / 1 | 5 个输入长度档位 |
| `sglang_perf.py` | `python -m sglang.bench_serving` / native `/generate` | 3 / 1 | 同上 |
| `vllm_profile.py` | vLLM，测量轮次按选择开启 profile | 3 / 2 | 4096,1024,64,64 |
| `sglang_profile.py` | SGLang native，测量轮次按选择开启 profile | 2 / 1 | 4096,1024,64,64 |
| `all_perf.py` | vLLM，兼容批量入口 | 5 / 1 | 9 个原有批量 case |

## 显式请求配置

```bash
python3 test/perf_test/vllm_perf.py \
  --model <真实服务模型名> --tokenizer <真实tokenizer路径或标识> \
  --host 127.0.0.1 --port 8010 --endpoint /v1/completions \
  --max-model-len 50000 --output-dir /tmp/current-benchmark \
  --case 1024,1024,64,128 --case 4096,1024,64,128
```

- 非性能测试必须保持前缀缓存开启。所有性能测试和 Profiling 均要求切换到性能专用服务
  配置，并在被测服务启动命令中加入 `--no-enable-prefix-caching`；不得将它写入通用 graph
  参数。先从该服务实例的生效启动配置和启动日志中核实该准确参数及关闭状态，在 runtime
  的 `service.prefix_caching.performance.verification` 中记录本轮服务实例的非敏感
  证据引用。正式回执会绑定该准确参数、证据和服务实例；benchmark 客户端不会自行修改或
  重启模型服务。客户端固定 `--random-prefix-len 0` 不代表服务端缓存已关闭。
- `--model`、`--tokenizer`、`--max-model-len` 必填。上下文预算必须来自当前服务核实结果，
  不是脚本探测值。每个 case 的输入长度 + 输出长度必须在预算内；重复或超预算 case
  在任何请求发出前拒绝，不自动删减套件。
- `--case INPUT,OUTPUT,CONCURRENCY,NUM_PROMPTS` 可重复，并替代默认集合。
  `--enable-all` 显式选择 11 个 case，不能与 `--case` 同用。
  默认集合包含长上下文工况，较短上下文服务应显式选择可运行 case。
- vLLM 的 endpoint 以 `/completions` 结尾时选择 `vllm` backend，以
  `/chat/completions` 结尾时选择 `openai-chat`，允许 API 代理前缀；拒绝其他协议、URL、
  查询参数或 fragment。SGLang 只支持 native `/generate`，不转发 vLLM 专属参数。
- `--runs`、`--skip-first` 调整轮次；`--run-timeout` 为每次子进程时限，默认 21600 秒。
  `--dry-run` 只展示命令，不发请求、不创建结果，也不生成可用于验收的报告。
- `all_perf.py` 另兼容 `--input-len`、`--output-len`、`--concurrency`、`--num-prompts`；
  后三项要求同时给出 `--input-len`，此组参数不能与 `--case` / `--enable-all` 混用。

## 失败判定与工况边界

任何一次（包括不计入平均值的 warmup）非零退出、超时、启动失败、成功请求数不符、
显式 failed requests 非零、关键指标缺失/重复/非有限/非法，均使 case 失败。
失败 case 不生成 `SUMMARY` 或 `PROFILE_SUMMARY`，任一失败使 CLI 非零退出。
缺失可选 peak throughput、failed requests 不伪造为 0；若出现非法值则拒绝。
SGLang 的额外 E2EL 指标按其输出保留；未出现则不臆造，不将此适配器用于 AISBench。

随机长度范围固定为 0.0，vLLM 显式固定请求 prefix 长度 0 并 ignore EOS，SGLang native
使用其 ignore EOS 默认行为。还要求生成 token 总数等于请求数 × 固定输出长度：
输出极少却退出 0 不再视为完整工况。vLLM 在缺少 API usage 时可能重新分词；计数不符
表示工况/计数契约尚未验证，不直接证明服务错误。聚合计数仍不证明每条请求长度、
实际并发、chat template 额外 token、模型正确性或服务真实上下文上限。

参数/文本格式按 [vLLM v0.24.0 CLI](https://docs.vllm.ai/en/v0.24.0/cli/bench/serve/)、
[vLLM 计数实现](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/benchmarks/serve.py) 和
[SGLang v0.5.10 客户端](https://github.com/sgl-project/sglang/blob/v0.5.10/python/sglang/bench_serving.py)
核对，未实际运行这两个版本或其他硬件。使用现场版本前须核对帮助/输出；格式变化会
明确失败，应增加对应版本测试后适配，不能删除校验来获得通过。

## Profiling 与普通性能分开

profile 入口默认只 profile 最后一个测量轮次；可用 `--profile-runs first|last|all` 选择
测量轮次，warmup 永远不 profile。`--no-profile` 明确禁用后按普通性能运行。

开启 profile 时要求已有、客户端可见且属于当前服务/任务的 `--profile-dir`；脚本不会
配置 profiler 或创建服务侧目录。每个 profile 轮次必须产生新建或内容变化的 JSON / gzip
Chrome trace，包含实际带时间的事件；仅有旧 trace、空 trace 或任意新 JSON 均不能通过。
新 trace 复制到本轮产物目录并核验摘要，防止后续运行覆盖。输出目录必须在 trace 树外。
多进程/TP 服务仍需现场确认全部目标 rank 的 trace 与归属；目录中的其他并发任务必须隔离，
文件新鲜度本身不构成服务身份或完整 rank 覆盖证明。

普通测量只写 `SUMMARY`，profile 测量只写 `PROFILE_SUMMARY`，两者不混合平均。
因此默认 profile 入口通常只有 profile 汇总，不能冒充未启用 profiler 的基线。

## 可复验报告与部署

每次实际套件运行使用新目录：`<output-dir>/<模型标签>/<时间含微秒>/`，生成
`benchmark-result.json`、逐 case CSV、所有轮次的 stdout/stderr 与 profile trace。
默认根目录为已忽略的 `test/perf_test/results/`；不要提交原始输出或完整 trace。
解析、请求或采集失败会保留失败报告；存储层异常/进程被强制终止可能导致无完整报告，
不得把残留 CSV 当作通过证据。

报告 schema 1 的主要字段：

- `kind: benchmark-result`、整体 `status/errors`、UUID `run_id`、带时区 `created_at`、
  `producer` 实现文件名和 SHA256；时间为套件完成后的报告创建时间。
- `request` 保存 engine/backend、完整服务/请求身份、上下文预算、case、runs/skip-first、
  超时、profile 配置、输出根目录及 Python 可执行路径。
- `cases` 按请求顺序保存每个 case 的状态、全部 `runs`（含 warmup）、普通/profile 汇总。
  每 run 保存编号、状态、真实退出码或 null、指标、校验错误、实际命令、stdout/stderr/trace 引用。
- `artifacts` 列出报告目录内的相对路径和 SHA256；CSV 也有独立引用。

复用 API 为 `from perf_common import validate_report`，调用
`errors = validate_report(report_dict, report_json_path)`。返回空列表才是本契约下的可复验通过：
验证每个 case/每次 warmup、rc、预算、命令、指标与 stdout 一致性，重算平均值和 CSV，
核验全部引用与字节摘要并拒绝越界路径。验证只读，不执行进程、HTTP 或远端命令。
模型薄 wrapper 可调用 `vllm_perf.main(argv)`；repo 外部署至少同时复制 wrapper、
`vllm_perf.py` 与 `perf_common.py`，不能只复制旧单文件脚本。

这是一致性/完整性检查，不是签名或独立服务证明；需要可信报告来源和绑定本轮报告
摘要的现场服务证据。未知历史 CSV 不自动升级为 schema 1，通过标签也不等于通过报告。
本次验证仅为本地 mock 回归，不重新评定任何历史模型或平台的验收状态。

本地回归（不连接服务）：

```bash
.venv/bin/python -B -m unittest discover -s test/workflow_test -p 'test_performance*.py' -v
```
