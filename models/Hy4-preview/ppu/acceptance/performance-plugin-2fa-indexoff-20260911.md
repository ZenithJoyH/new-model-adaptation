# Hy4-preview Plugin 2fa / index 黑名单版正式性能测试

## 范围与身份

- Host：`PPU-07`；容器：`hy4`；模型：`/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`；served
  model：`hy4`；endpoint：`http://127.0.0.1:8010/v1/completions`。
- Plugin：`2fa5f1816fe0e9a08fd66f515c5de28e9c8199e2`，仅保留经授权的
  `vllm_fl/dispatch/config/thead.yaml` 通用 `index` blacklist；FlagGems：
  `bca444b8569294e7d4e4deff7ddfec7f05682033`；vLLM：
  `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 通用最终 launcher：`/mnt/nfs/users/jinghao/hy4-preview/start-model.sh`，SHA-256
  `6bf2e151423f65f860d6f7e45e164e29ee99ca0de656cdd32150cf6bffd02748`。
- 性能服务 launcher：
  `/mnt/nfs/users/jinghao/hy4-preview/01-environment/service-plugin-2fa5f18-fgbca-indexoff-perf-noprefix-20260911/start.sh`，
  SHA-256 `9c927561113b18797289f3f34adeaedb8df8fec90ffd8ccf1b3728ab6dc314bd`。
  它从通用 launcher 派生，只替换独立 service run/cache id，并恰好加入一次
  `--no-enable-prefix-caching`；语法、批准路径、敏感赋值 0、破坏性命令 0 已核对。

## 工具与工况

工具目录：
`/mnt/nfs/users/jinghao/hy4-preview/03-acceptance/perf-full-default5-plugin2fa5f18-indexoff-20260911/`。

- `vllm_perf.py`：`58324a69699296287473d150cb67f84928a03232b7f89df5fe6963e5c6c937d8`
- `perf_common.py`：`e150daf92a5103dd33548ae57a789cab34f006f3895bd7effe971fde98dadc17`
- `perf_acceptance.py`：`3f4934026e193a797d3af445951ac8d29729b246bd6579dff16082daa84875c1`

使用仓库 `vllm_perf.py` 默认五工况，每项为 `INPUT,OUTPUT,CONCURRENCY,NUM_PROMPTS`：

1. `1024,1024,64,128`
2. `4096,1024,64,128`
3. `16384,1024,64,128`
4. `32768,1024,64,128`
5. `65536,1024,64,128`

每个工况 3 轮、首轮为不计入平均的 warmup，单轮 timeout 21,600 秒；固定随机长度比例 0、prefix
长度 0、ignore EOS。最大输入加输出为 66,560，小于当前服务 100,000 context。dry-run 已通过，
展开的 15 个命令均使用同一 endpoint、tokenizer 和完整工况，没有发请求或生成验收报告。

## 服务切换与运行位置

原精度服务 PID 467407 在 health 200、命令和模型身份核实后，仅向该 API 进程发送 SIGTERM；旧端口
关闭后确认 `hy4` 容器仍运行，再启动性能 profile。容器未停止、重启或删除。性能实例为
`PPU-07:550e93f0ba4c:2617179:184975667`，启动命令中的
`--no-enable-prefix-caching` 恰好一次。该实例完成模型加载和 graph capture、health 200 后启动正式
runner；runner PID 2619354，controller PID 2619355。

- 服务日志：
  `/mnt/nfs/users/jinghao/hy4-preview/04-runs/service-plugin-2fa5f18-fgbca-indexoff-perf-noprefix-20260911/service.log`
- 性能输出根：
  `/mnt/nfs/users/jinghao/hy4-preview/04-runs/perf-full-default5-plugin2fa5f18-indexoff-20260911/`
- 临时目录：`/mnt/nfs/users/jinghao/hy4-preview/05-tmp/perf-full-default5-plugin2fa5f18-indexoff-20260911/`
- 缓存目录：`/mnt/nfs/users/jinghao/hy4-preview/06-cache/perf-full-default5-plugin2fa5f18-indexoff-20260911/`

## 实际结果

| 工况 | 三轮状态 | 有效汇总 |
|---|---|---|
| `1024,1024,64,128` | SUCCESS / SUCCESS / SUCCESS | 每轮 128 成功、0 失败；输出 `37.40 tok/s`，总 `74.81 tok/s` |
| `4096,1024,64,128` | SUCCESS / SUCCESS / SUCCESS | 每轮 128 成功、0 失败；输出 `10.45 tok/s`，总 `52.23 tok/s` |
| `16384,1024,64,128` | TIMEOUT / TIMEOUT / TIMEOUT | 每轮均达到 21,600 秒上限，无有效性能汇总 |
| `32768,1024,64,128` | TIMEOUT / TIMEOUT / TIMEOUT | 每轮均达到 21,600 秒上限，无有效性能汇总 |
| `65536,1024,64,128` | TIMEOUT / OPERATOR TERMINATED / NOT RUN | 第 1 轮达到 21,600 秒上限；第 2 轮长时间无完成后按用户决定终止；第 3 轮未运行。场景级标记 TIMEOUT |

原始 CSV、stdout、stderr 和 error JSON 均保留且未改写。2026-09-14 09:49:26 +08:00 按用户指令
停止性能测试，runner 最终 `exit.code=143`。场景级终态记录为：

`/mnt/nfs/users/jinghao/hy4-preview/04-runs/perf-full-default5-plugin2fa5f18-indexoff-20260911/performance-final-status.json`

该终态文件 SHA-256 为 `dc6a3d20454c84a86ae6f14f8883b6cb9c47f6a132a12b0a37be7f12b5f574d5`。

停止前 `65536` 第 2 轮曾显示 6 个请求运行、58 个等待；终止客户端进程树后实时 `/metrics` 为
`num_requests_running=0`、`num_requests_waiting=0`。API PID 2617179 未停止，health 仍为 200；
`hy4` 容器未停止、重启或删除。当前仍是 prefix-cache-disabled 性能专用服务，后续任何非性能测试
前必须切回通用 `start-model.sh` 对应的正常 prefix-cache-enabled profile。

## 当前判定

状态：`failed`，并按用户决定停止后续性能测试。只有前两档成功；三个长上下文档均按场景标记为
timeout，未满足完整工况、零失败和正式报告校验条件。没有生成或伪造 compact performance receipt，
不能将平台状态标记为 `optimized`。

精度前置采用用户明确接受的 strict 90.91% ≥ 87% 业务判定；doc_id 81 单条 timeout、runner exit 1
和缺少原生 accuracy passing receipt 仍是已接受限制，本性能测试不会隐藏或改写它们。
