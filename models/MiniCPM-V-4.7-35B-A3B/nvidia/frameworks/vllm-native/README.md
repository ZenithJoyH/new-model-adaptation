# MiniCPM-V-4.7-35B-A3B / NVIDIA / vllm-native

记录于 2026-10-12 显式升级为 evidence v2 / profile v3。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

2026-09-28 至 2026-10-01 于 `H100-149` 的 `MinicpmV4.7-35B-native` 容器直接适配
vLLM `0.24.0+cu129` wheel，依用户要求使用 GPU 2、3 的 TP2。真实 17-shard
权重已加载；eager 与 graph 的文本、红色单图、红蓝两帧视频均返回预期答案。
当前根级脚本以 `FULL_AND_PIECEWISE` 与正常前缀缓存运行；
该脚本启动的 8020 实例就绪，`/health` 为 200。
十个混合并发诊断请求曾全部完成。当前路径、哈希和请求结果见
[命令级 PYTHONPATH 验证](acceptance/command-scoped-pythonpath.md)。
`framework.yml` 的当前部署指纹为
`04853be964c0768e8af1937e8f3d2ae3ea63185f7723608ce2a61e9326808426`；
环境、适配和 execution-mode 回执位于
`04-runs/framework-functional-pythonpath-scope-20261001/`，原架构记录保持有效。

已解决的模型接入问题是 4.7 注册、Qwen3.5 MoE 和 canvas M-RoPE，见
[001](adaptation/001-native-registration-and-moe.md)。共享 Triton cache
在本 Host 上以进程隔离缓解，见 [002](adaptation/002-parastor-triton-cache-race.md)。
GDN backend 限制 prefill full graph，当前最高已验收的 full 图覆盖级别是 decode-full，见
[003](adaptation/003-gdn-full-graph-limit.md)。

用户随后指定的 `FULL_AND_PIECEWISE` 已在同一 TP2 容器服务中实际启动并
通过文本、图像、视频与十并发诊断：prefill PIECEWISE 5/5、decode FULL 4/4。
先前服务和根级脚本均使用此配置；详细身份和结果见
[004](adaptation/004-full-and-piecewise-graph.md) 及
[根级脚本验证](acceptance/full-and-piecewise-launcher.md)。

历史二次精简版的脚本 SHA-256 为
`d947e59229f8d9b9602ca2530e1e7b5c8511778bfe9b244eb3a1b26e122ae5aa`，
其回归结果见[精简脚本验证](acceptance/lean-launcher.md)。

2026-09-30 用户自行调整根级脚本，其历史 SHA-256 为
`eb0a9ac33ee26eba21ee3c02edba1adc5f7e02467d46bbfd6acca2c993a1bf52`。
原样配置改用 8020 和默认 262144 上下文，在图捕获时遇到 Triton 共享缓存
`EBUSY`，未达到服务就绪；见 [005](adaptation/005-user-launcher-startup-blocked.md)。
失败测试进程已结束，历史用户脚本已备份。随后过度恢复了资源上限和其他
缓存变量，其历史验证见[8020 恢复验证](acceptance/recovered-8020-launcher.md)。
用户纠正后的历史根级脚本在 Host/容器同路径
`/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，
SHA-256 `67d496ce89a943a8b8d53a12fc0056ce513e1f54c935a8d67049af59e17cee40`。
它恢复用户原始 vLLM 参数，只增加 Triton 进程缓存隔离；
默认长度 262144、batch token 上限 8192，未显式设置编译 `mode=3`。
容器内 `bash -n`、Host/容器哈希、端口占用保护与设备分配均通过。
仅停止本任务旧 8020 服务后，用该脚本重新启动 8020，图捕获完成；
prefill PIECEWISE 51/51、decode FULL 51/51。文本、图像、视频及十并发
10/10 回归通过。Triton 缓存位于 `06-cache/triton-processes/`，其他缓存
按用户要求未调整；启动日志显示 vLLM AOT 缓存使用 `/root/.cache/vllm`。
适配容器保持运行。这一脚本的完整复测记录见
[仅 Triton 隔离验证](acceptance/triton-only-8020-launcher.md)。

2026-10-01 用户再次调整根级脚本，保留相同 vLLM 参数与 Triton 隔离，
改用后台运行并把日志写到工作根的 `service.log`。本轮仅移除
`export PYTHONPATH`，改为在 `nohup vllm serve` 命令前设置该变量，
以免影响启动 shell 的其他命令；vLLM 和 worker 仍能加载进程级隔离钩子。
当前根级脚本 SHA-256
`8243f7ce5faf16543941c633e305b7e4e29cb655a0bf0ea2a6f3d973eea58d48`。
重启后 8020 健康检查 200、PIECEWISE 51/51、decode FULL 51/51，
文本 `17+25` 返回 `42`；两 rank 的 Triton 缓存仍按 PID 分开。
准确 diff、服务身份和限制见
[命令级 PYTHONPATH 验证](acceptance/command-scoped-pythonpath.md)。
用户脚本的持续日志仍在工作根顶层，其他缓存沿用镜像默认路径；
若要满足最终 launcher 的路径规范，需在独立后续变更中处理。

本轮仅完成用户要求的请求级功能检查。固定 GPQA sanity、正式精度、性能和
完整验收未执行；实际长上下文、复杂图像切片、其他模型运行回归和长时稳定性
尚未验证。后续应先冻结正式数据集及阈值，再按 profile 顺序进行验收，
并在可用 Git 源码形式中整理可维护贡献。没有提交、推送或创建 PR。

2026-10-03 另在同一 8020 服务上完成 FlagEval MM-Eval ERQA 两组诊断性全量对照：
显式 `top_p=0.95,top_k=20` 为 202/400，未传这两项为 201/400；
两组均有 400 条记录，分别有 5、3 条评测客户端错误计零。FlagEval 排除
reject 后显示 51.14% 和 50.63%；采样随机且净差仅 1 题，尚不能认定稳定收益。
镜像身份、完整配置、逐题路径和失败记录见
[ERQA FlagEval 双配置诊断](acceptance/erqa-flageval-nv-sampling-20261003.md)。
