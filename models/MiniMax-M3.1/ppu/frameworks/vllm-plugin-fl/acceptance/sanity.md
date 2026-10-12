# PPU-07 MiniMax-M3.1 服务小批量预检

2026-09-30；Host `PPU-07`、`minimaxM3.1` 容器、`decode-full` 图服务，实例 `ppu07-m31-container1ac783da-api565730-start344462218-cmd6e6c40f30ebf73c5`，部署指纹 `803853bb265fc97fbeb3f1cac74f34e6ae20832624a5fb4a8ba71668d2087915`。正常服务保持 prefix cache enabled，API 为 `127.0.0.1:8025`，运行前后 `/v1/models` 与 `/health` 可用。适配容器始终运行。

## 固定简单题的服务预检

依据 profile 的“10 并发、固定简单 GPQA 类题目、逐题全对、输出健康及明显性能异常检查”，在任何请求前固定四选一科学题及答案：Host/容器同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/03-acceptance/service-sanity-20260930/manifest.json`，SHA-256 `0863b924195c07a0cb3afc3da9b81960c738358cf3b3c016576f2af84a497d73`。脚本同目录 `run.py`，SHA-256 `6a909f680dda69a301ef4538b382694470360a524820b9fb0343e165a0f61207`；用 Python 标准库请求现有 OpenAI Chat API，barrier 同时提交十题，`temperature=0,top_p=1,max_tokens=128`，并采集 PPU 利用率/显存。`04-runs/service-sanity-20260930/report.json` SHA-256 `2ca11c7a61e96a28e1b392c375e7cc329c516c5280ada5b843541c45c6995793`：10/10 正确，HTTP 200、`finish_reason=stop`，零超时/异常；70.103 秒、0.1426 请求/秒；PPU 采样最大利用率 100%，每卡显存约 86,705→86,729 MiB。此轮 0.5 秒一次的 `ppu-smi` 监控可能影响性能。

只移除请求期间的 `ppu-smi` 高频轮询，保持十题、答案、10 并发、服务实例与采样参数不变：`03-acceptance/service-sanity-20260930/run-no-monitor.py` SHA-256 `21c4ffde00f34b6df49690af01f7b4c46dba8bd5de371d7de8ef42834d4a5ba5`；`04-runs/service-sanity-no-monitor-20260930/report.json` SHA-256 `95243965293eab473ddc9e79295ec5f90c541c8aefc09f49c15139f832f512ee`。结果 10/10 正确、HTTP 200、正常停止，48.299 秒、0.2070 请求/秒；请求前后每卡显存约 86,729 MiB，服务健康。监控轮询约增加 21.8 秒，不能解释全部延迟。

进一步只将并发从 10 改为 1，题目和服务不变，按相同题序串行执行：`03-acceptance/service-sanity-20260930/run-c1-control.py` 与 `04-runs/service-sanity-c1-control-20260930/report.json`，后者 SHA-256 `3e9a7cd6d0e191b0b977b9fd48a0a01d90f83a9ebc95a9cec8bca7193d37a669`。仍 10/10 正确，耗时 34.551 秒、0.2894 请求/秒。十并发相对串行吞吐较低，需在正式性能场景继续量化；两轮均无超时、OOM、异常或服务失活，当前没有预先冻结的服务预检吞吐阈值，尚不能将其判定为已证实的异常回归。服务预检的逐题正确、输出健康与明显故障检查通过；此结论不等同于正式性能验收。延迟诊断见[006](../adaptation/006-ten-concurrent-sanity-latency.md)。

## GPQA Diamond 前十题的独立失败诊断

原先用 Diamond 原始前十题充当小批量预检，不符合 profile 对“简单请求”的要求；失败仍保留。固定 manifest `03-acceptance/gpqa-first10-20260930/manifest.json` SHA-256 `3f3ecc9ff72d071faebdd4000bf56fb63290081e4f2f0f5f02361d459fb8fbdd`，配置同目录 `config.json` SHA-256 `15d8449eaeffa31af77db81b546ed1edecb1d1fa08ce8611bfa8f58a3ebc9732`。原生运行 `04-runs/m31-gpqa-first10-c10-gen45k-20260930/` 完整 10 题，strict 8/10，零 timeout/请求错误；`sanity-verification.json` SHA-256 `9a7a1b9ab5f03f2f8e95bb2cd7f0d58c06ce8ea546ed7a79795d69acfda024ad` 明确标 `failed`。`doc_id=8` 目标 C、过滤后 B，生成恰好 45,000 token 且没有最终答案；`doc_id=9` 目标 D、过滤后 A，生成 10,515 token 后选错。既有 MiniMax-M3 同题第 8 题在 30,000 token 截断但输出 D；不能凭相似症状归为同一实现缺陷。见[005](../adaptation/005-gpqa-first10-two-errors.md)。这两道高难题不会从数据集中删去；正式 Diamond 198 题仍按原计划完整计分，指标阈值仍为冻结的 strict ≥0.88，具体结果待正式运行。

## 判定与限制

小批量服务预检在 PPU-07 已通过：固定 10 并发简单题逐题全对、输出健康、无已证实的阻断性性能故障。第 8、9 题失败是模型精度风险，必须由正式完整样本及冻结阈值判定；正式评测尚未运行，不得预先推断通过。未验证视觉请求、旧 M3 或其他平台。性能量化、正常服务恢复后的最终 launcher、完整证据与总结仍待后续步骤。

## 65,536 上下文服务重复预检

2026-09-30，新 decode-full 服务实例 `ppu07-m31-container1ac783da-api2291878-start345908995-cmd8ee48233f293f954`、prefix cache enabled，沿用原固定简单题 manifest SHA-256 `0863b924195c07a0cb3afc3da9b81960c738358cf3b3c016576f2af84a497d73`，10 并发逐题全对、HTTP 200、无超时/请求错误，耗时 7.55 秒、1.3245 请求/秒，前后服务健康。原生报告 `04-runs/service-sanity-ctx65k-20260930/report.json` SHA-256 `5eeb7869c61d665f3c1c6311f40754fee3e5b5bb4a2f757ec198afb9fd0c0824`，脚本 `03-acceptance/service-sanity-ctx65k-20260930.py`。这轮使用新服务容量，延迟变化不能与旧服务单变量归因；正式性能仍待精度达标后运行。
