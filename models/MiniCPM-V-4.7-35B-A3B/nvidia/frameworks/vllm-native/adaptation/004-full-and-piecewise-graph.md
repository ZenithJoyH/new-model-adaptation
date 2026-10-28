# 004：TP2 FULL_AND_PIECEWISE 图模式诊断

## 范围与结论

2026-09-28，用户要求尝试 `FULL_AND_PIECEWISE`。目标仅为 `H100-149` 的
`MinicpmV4.7-35B-native` 容器、GPU 2/3、TP2、2048 上下文和正常前缀缓存。
状态：`diagnostic_verified`。vLLM `0.24.0+cu129` 使用
`--compilation-config '{"mode":3,"cudagraph_mode":"FULL_AND_PIECEWISE"}'`
完成 mixed prefill/decode PIECEWISE 5/5 及 decode FULL 4/4 捕获。
文本、红色图像、两帧视频和诊断性十并发请求均返回预期结果。

## 配置选择

容器内 `vllm/config/compilation.py` 明确要求 PIECEWISE 图使用
`VLLM_COMPILE` 和非空 `splitting_ops`。原来的 `mode=0` 只支持已验收的
`FULL_DECODE_ONLY`；只替换图模式名称无法保证 piecewise 生效。
因此本轮受控变更是耦合的编译/图配置对 `mode=3` +
`FULL_AND_PIECEWISE`，其他模型、拓扑、缓存和服务参数保持一致。
EngineCore 生效配置显示非空的 attention/GDN 等 `splitting_ops`，
图捕获日志记录上述 5/5 与 4/4。该模式使 prefill 得到分段图，
并没有得到 prefill **full** graph；003 的 GDN 限制仍存在。

## 进程操作与原始证据

切换前只读核实旧 API Host PID/PGID `2917445`，命令含精确权重路径、
TP2 和 `FULL_DECODE_ONLY`，同组只含本任务的 API、EngineCore 和 TP0/TP1。
2026-09-28 对该精确进程组执行 `SIGTERM`，验证该组退出、容器原始
`/bin/bash` 保持运行。一次 shell 内建 `kill -- -2917445` 被 `/bin/sh`
拒绝为非法数字，未改变进程；随后使用带精确 cmdline/PGID 断言的
`python3 os.killpg(2917445, SIGTERM)` 完成停止。未停止或重启容器，
未触及其他 GPU 工作负载。

诊断脚本在获批工作根 `01-environment/start-graph-tp2-full-and-piecewise-v1.sh`，
SHA-256 `c23785f940279c0d35786520c2222b9057af8ebae4e325ee983458b6278b2dcf`；
请求探针在 `03-acceptance/full-and-piecewise-probe.py`，SHA-256
`0b261e1ca12d4008d22d0a874907d80aae2a4be71b62ad60d19a36c4e2436787`。
两者的 Host/容器根均为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native`。
原始日志 `04-runs/graph-tp2-full-and-piecewise-v1/service.log` SHA-256
`41736de810d89c0350e1cf656f9289137c6284a824c67734b3ce87b39a5e3b01`；
请求结果 `04-runs/graph-tp2-full-and-piecewise-v1/probe.json` SHA-256
`66373d37fa99ef270b9d8798b57b2af9c0369ff1f4f2f675dea9a476fedee8b7`。
最终健康/模型列表均 200；文本 `17+25` 为 `42`，图像为 `red`，
视频为先红后蓝；三个请求均为 200、stop；混合十并发 10/10 正确。
当前服务 Host PID/PGID `3109477`，命令确认 `mode=3` 与
`FULL_AND_PIECEWISE`，请求后 `/health` 仍为 200。

## 状态与限制

这是一轮用户指定的图模式诊断，不是项目固定 GPQA sanity、正式精度或性能结果。
随后用户明确要求调整根级启动脚本；脚本已改为 `mode=3` 与
`FULL_AND_PIECEWISE`，并以该脚本重新启动 TP2 服务、完成相同的请求复测。
根级脚本新 SHA-256 为
`195fd984d82769e8598f800d1a9d5e9dfd4f0e05b22da5a11caa48589aade662`；
此前的 decode-full 版本备份哈希为
`5c12ac80b434444b124c7c9613ae951f3adbc2a1d8641abc11b0fae02bf85940`。
新服务 Host PID/PGID 为 `3149108`，请求级结果见
[根级脚本验证](../acceptance/full-and-piecewise-launcher.md)。
当前 full 图覆盖的最高级别仍是 decode-full，因为 prefill 只捕获 PIECEWISE；
不能将本轮写成 prefill full graph 通过。正式精度和性能仍按用户上一轮要求暂缓。

2026-09-30 依据用户后续要求精简根级脚本，仅删除已被 XDG 与进程隔离逻辑
覆盖的两个缓存环境变量，最终 SHA-256 为
`1bca4bb0ac4c190cde1b30dc1da289b3361e2ac558340cfac820d8c7829efb54`。
同一 TP2/FULL_AND_PIECEWISE 服务重新启动并完成请求复测，详见
[精简脚本验证](../acceptance/minimal-launcher.md)。

同日再次按用户要求删除多余的缓存目录预创建行，当前根级脚本 SHA-256 为
`d947e59229f8d9b9602ca2530e1e7b5c8511778bfe9b244eb3a1b26e122ae5aa`；
新实例和请求复测见[最终脚本验证](../acceptance/lean-launcher.md)。
