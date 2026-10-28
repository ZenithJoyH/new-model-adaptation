# 004：GDN backend 使 FULL graph 请求降为混合 PIECEWISE

## 元数据与签名

- 状态：`mitigation verified`（FULL 降级及显式 decode-full 最小推理已验证；后续验收待验证）
- 日期：2026-09-28
- Host/容器/权重：`H100-149` / `MinicpmV4.7-1B` / `/data/models/MiniCPM-V-4.7/weights/1b`
- 栈：Plugin `3a27a6fb2d514cdf55c00481bf813225dac63319` 加未提交 4.7 shim，FlagGems `da6727e38f6f8eedef6cba43695a87b4996f9eca`，vLLM wheel `0.24.0+cu129`
- 模式：单卡 GPU1、BF16、TP1、max model len 50000、正常 prefix caching；进程级 FlagGems attention 过滤见 [003](003-flaggems-cudnn-attention.md)

## 事实与证据

已核实的本框架运行以 `compilation_config={"cudagraph_mode":"FULL"}` 请求
prefill 与 decode 全图。`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/04-runs/full-graph-v1-20260928/run.log`
中的最终 EngineCore 配置确认为 `CUDAGraphMode.FULL`，随后明确记录
`CUDAGraphMode.FULL is not supported with GDNAttentionBackend backend
(support: AttentionCGSupport.UNIFORM_BATCH); setting cudagraph_mode=FULL_AND_PIECEWISE`。
实际捕获为 mixed prefill-decode `PIECEWISE` 3/3、decode `FULL` 2/2。
文本与纯红单图请求均完成并得到合理简短输出，进程退出码 0；这次运行不能
记为 full graph 通过。原始日志 SHA-256
`269ae025284d0062d7ffb0741aeb9c071fb0eac8bc4da3a5b6f581efe16f4808`。

同模型权重的独立原生容器记录
`models/MiniCPM-V-4.7-1B/nvidia/frameworks/vllm-native/adaptation/003-gdn-fullgraph-limit.md`
呈现相同的 GDN backend 降级签名，但容器、框架、产品代码和 FlagGems 路径不同；
本次已在 Plugin 栈上重现降级，因此该历史记录只是受控比较来源，不替代后续
显式 decode-full 的证明。`docs/troubleshooting/shape-aware-dispatch-fullgraph-contextvar-rlock.md`
涉及 Python Plugin dispatch 与 Dynamo 的另一类首次失败组件，此处未观察到该签名。

## 显式 decode-full 对照与退出条件

只改变 graph 模式为 `FULL_DECODE_ONLY`，其余模型、GPU、prefix cache、
资源参数和 attention 过滤保持一致。有效 EngineCore 配置仍为
`CUDAGraphMode.FULL_DECODE_ONLY`，只捕获 decode `FULL` 2/2，无 mixed PIECEWISE
降级记录；文本和纯红单图均完成，进程退出码 0。原始记录为
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/04-runs/decode-full-v1-20260928/run.log`，
SHA-256 `6e03d1380c6d7fd72753a3edcb5fe67ce54bb4ea781bdd61fce437575ea94da2`。
这证明当前本 Host 的最小执行模式级别是 `decode-full`；后续十并发功能检查
和根级 launcher 实启也已通过，见 [功能报告](../acceptance/functional-validation.md)。
正式精度、性能验收尚未执行，不能称为完整 graph 验收。
若未来 GDN backend 支持
mixed FULL，应在本栈重新请求 FULL，并重做后续验收。

模型 shim 的 decode delta 修正后，保持该 graph 配置再次验证文本与单图，
decode FULL 捕获 2/2 且请求完成；`04-runs/decode-full-v2-delta-fix-20260928/run.log`
的 SHA-256 为 `de2430de7b9def2938388a3cc5ed859d929112077360615d0e9a9cad33277a94`。

## 2026-09-28 显式 FULL_AND_PIECEWISE 服务验证

用户要求打开该图模式后，先确认同一服务实例在容器内的 API PID `10413`、
模型路径、端口 8308、`FULL_DECODE_ONLY` 参数，以及运行中/排队请求均为 0。
仅向该任务 PID 发出 `docker exec MinicpmV4.7-1B kill -TERM 10413`；
原端口关闭后，用容器内
`01-environment/start-service-full-and-piecewise-20260928.sh` 在同一端口、GPU1
启动。脚本 SHA-256 为
`8cc4a6b39dc1210ad352d119ee3a32b00ee2d861de52dfe4b9a0aa4f84908bf8`，
Host/容器哈希一致，`bash -n` 通过；与根级 launcher 的服务参数相同，
只将 graph mode 显式设为 `FULL_AND_PIECEWISE`，并写入独立日志目录。
原适配容器及其他服务未停止或重启。

新 API PID `11048`、EngineCore PID `11260`。`04-runs/full-and-piecewise-service-20260928/service.log`
记录最终 EngineCore `CUDAGraphMode.FULL_AND_PIECEWISE`、正常前缀缓存、
mixed prefill-decode `PIECEWISE` 捕获 11/11、decode `FULL` 捕获 7/7。
`/v1/models` 返回目标 ID 和权重路径。复用
`03-acceptance/service_smoke.py` 的文本 42 与红图 API 请求，两项 HTTP 200、
`finish_reason=stop` 且内容符合预期；原始日志
`04-runs/full-and-piecewise-smoke-20260928/run.log`，SHA-256
`4295cc337ab696c45baf4fe8e4a1aaa56eff411c465147ab52af23081bccb2fc`。

这是按要求开启该模式的首次独立运行。它的 prefill 仍为分段图，
因此不等同于 profile 的 `full` graph 验收；正式精度和性能也未运行。
此时根级脚本仍为 `FULL_DECODE_ONLY`，SHA-256 为
`ca544ac90cacb1c6b7fccf82e8585490af10d8c4c91e7e1a8ddf68bc79531ae8`。

## 2026-09-28 根级启动脚本同步

用户随后明确要求同步模型服务启动脚本。先核对根级
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/start-model.sh`
仍为上述旧 SHA-256；由精确旧版重建对照，新文件只将
`--compilation-config` 的 `cudagraph_mode` 从 `FULL_DECODE_ONLY` 改为
`FULL_AND_PIECEWISE`。Ansible `--check --diff` 显示唯一这一行变化，
随后写入并通过 `bash -n`、Host/容器哈希与 inode 一致性验证。
新 SHA-256 为
`b7221238606a5f193a8ec0153332328e6e1b9ecedf7cf7da28c99ca45eb729b6`；
Host/容器设备号:inode 均为 `45:232998688002`，权限 0755。

实启前确认独立服务的 API PID `11048`、目标模型/端口/图模式，
运行中和排队请求均为 0；仅向该 PID 发出
`docker exec MinicpmV4.7-1B kill -TERM 11048`。端口关闭后，通过
`docker exec -d -w /public/flagos/jinghao/MiniCPMV4.7-1B/flagos MinicpmV4.7-1B /usr/bin/bash /public/flagos/jinghao/MiniCPMV4.7-1B/flagos/start-model.sh`
重新启动本任务服务；适配容器保持运行，其他服务未操作。
现 API PID `11580`、EngineCore PID `11792`，物理 GPU1、TP1、正常前缀缓存。
`04-runs/model-service/service.log` 的 14:23 新启动段确认最终
`CUDAGraphMode.FULL_AND_PIECEWISE`，mixed prefill-decode `PIECEWISE` 捕获
11/11、decode `FULL` 捕获 7/7；`/v1/models` 返回正确模型与权重。
根级脚本实启后的文本 42 与红图 API 请求均通过、`finish_reason=stop`；
原始记录 `04-runs/full-and-piecewise-root-launcher-smoke-20260928/run.log`，
SHA-256 `2a3dc0a63be5f4c9cb0939803d1f113ef3d90a07df8212f5d68f9c41747b4cd5`。

按用户要求，根级脚本现在会稳定复现这一配置；prefill 仍是 PIECEWISE，
不能按 profile 的 `full` graph 子步骤或正式验收通过处理。正式精度、
性能及原生回执未执行，`framework.yml` 状态保持未通过。

知识库处理：`needs-validation`，尚未提升为跨模型知识。
