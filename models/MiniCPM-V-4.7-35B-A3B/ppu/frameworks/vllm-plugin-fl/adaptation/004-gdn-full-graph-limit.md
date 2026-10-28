# 004：PPU-13 的 GDN backend 阻断 prefill 全量图

## 元数据

- 状态：`verified`（当前 GDN backend 限制；采用 decode-full 缓解）
- 首次出现及最后验证：2026-09-29
- 模型：`MiniCPM-V-4.7-35B-A3B`，权重配置 SHA-256
  `3973e7ad0bd9f96887341cb134173118b0e445695014a73e736de48e9a9b5646`
- 平台与 Host：平头哥 PPU，`PPU-13`，设备 0/1，TP2
- 容器：`minicpmV4.7-35B`，镜像
  `sha256:52536a088a055b2c24cdfca21d0ea9e8d68c1f5f82fee7a40f7ec8f72e4a`
- Plugin HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319` 加当前未提交
  4.7 adapter/平头哥视觉修正；FlagGems 包 `5.3.5`；vLLM `0.24.0+empty`
- 执行模式与负载：服务启动时请求 `FULL` graph，实际前缀缓存关闭；
  该值当时未核出，故本轮仅为诊断证据，见[005](005-prefix-cache-effective-default.md)。

## 现象与证据

由已验证的 eager 基线只改变执行模式：移除 `--enforce-eager`，增加
`--compilation-config '{"mode":0,"cudagraph_mode":"FULL"}'`；模型、源码、
TP2 设备、50,000 token、视觉 data 模式及当时实际关闭的前缀缓存均不变。
试验脚本在
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/01-environment/start-graph-tp2-full-v1.sh`，
宿主机与容器路径相同，SHA-256
`0c1d3a7e6dc0ffb1997cdd76340f5790204c1c26f02830e50f47c0f844934544`。
日志在 `04-runs/graph-tp2-full-v1/service.log`，缓存独立放在
`06-cache/graph-tp2-full-v1/`。

17/17 shard 加载后，TP0/TP1 均于 12:28:13 报：
`CUDAGraphMode.FULL is not supported with GDNAttentionBackend backend
(support: AttentionCGSupport.UNIFORM_BATCH); setting cudagraph_mode=FULL_DECODE_ONLY`。
随后日志完成 `Capturing CUDA graphs (decode, FULL): 4/4`，服务 `/health`
返回 200。因此请求 full 图不等于实际 prefill full 图；当前图级别准确记为
`decode-full`。固定启动日志快照为
`04-runs/graph-tp2-full-v1/startup-capture.log`，SHA-256
`eb5ca836c6e3b3024375818c67b1b2760f084311923d3fc0fa72f4ca64cebdd6`。

## 已有经验与受控比较

同一 checkpoint 的 NVIDIA vLLM 原生记录
`models/MiniCPM-V-4.7-35B-A3B/nvidia/frameworks/vllm-native/adaptation/003-gdn-full-graph-limit.md`
报告相同 GDN `UNIFORM_BATCH` 限制。该记录的硬件、框架 profile 和源码不同，
只是候选假设；本次两名 PPU Worker 的原始日志重新确认了同一限制。
基线 eager 服务 `04-runs/eager-tp2-sdpa-data-product-v2/` 的文本、红图、蓝图
最小请求已通过，不能替代 graph 验证。

切换前确认本任务 API PID `713629`、EngineCore `714402`、TP0/TP1
`714687`/`714688` 和 eager 启动脚本 SHA-256
`bb76fd3ce2ed284e3b511e9a8891d7676c283ded83807ec76638cbade86b864f`；
单 Host Ansible 向该 API 发 TERM，确认上述四进程退出，再启动试验实例。
适配容器未停启，设备 2 上的其他服务未操作。

## 验证、限制与下一步

本轮 graph 文本 `42`（31.567 秒）、红图“红色”（218.085 秒）、蓝图“蓝色”
（0.551 秒）、红蓝两图“红色 蓝色”（157.199 秒）、红蓝两帧 MP4
“红色，蓝色”（9.525 秒）均 HTTP 200 且 `finish_reason=stop`。原生响应位于
`04-runs/graph-tp2-full-v1/`，五个结果 SHA-256 分别为
`9e6259a91b92f8593e01d47c0be52ed02ba66c508a0392b4d884143cb1eeba8c`、
`2b3341884a41d9b41034e61dfcdc28d307a0eb39a7d4dba30c10cb49f6f330ef`、
`d49e9e7230e7f380315f69894536d6cabade6a95616c13e60bedee1de56c9214`、
`8577bed214ce5398acebfe2ef452f06251e377887c47ddbd97f9149ed27a4055`、
`46a4fe6e40b39e34bbd4f0cb44d0929ba6ed6df8b017f4e4af12cb532fa67bfc`。
视频输入留在 `05-tmp/graph-full-v1/red-blue.mp4`，SHA-256
`a51b2a39385acf22e54626d8f40dc3f047711c3b8c81b98becf41e9d588faed9`。

**prefill full graph 被 GDN backend 阻断**，而 decode-full 的图捕获和上述诊断请求
通过。该轮缓存实际关闭，不能据此签发正式执行模式回执；须在显式开启缓存
的新实例重新验证。若限制仍在，按 profile 可选择最低允许级别
`decode-full`，正式回执记录完整 `graph_fallback`，不能写成 full graph 通过。

2026-09-29 新实例使用
`01-environment/start-graph-tp2-full-v2-cache-on.sh`，SHA-256
`002bd11a6ce5ee732b8966850c2a5b4a2a3cb5a429c1397a7ff84ffd01cf8562`；
API PID `977709`，EngineCore PID `978482`，TP0/TP1 PID `978767`/`978768`。
启动命令显式 `--enable-prefix-caching`，EngineCore 生效值为 `True`。
与前轮保持其他核心参数相同并再次请求 `FULL`，两个 rank 在 13:39:50 均报告
同一 `GDNAttentionBackend`、`UNIFORM_BATCH` 限制并设为
`FULL_DECODE_ONLY`；decode 图 4/4 捕获完成，`/health` 为 200。
该实例的文本、红图、蓝图、红蓝两图、红蓝两帧 MP4 依次回答 `42`、
“红色”、“蓝色”、“红色 蓝色”、“红色，蓝色”，均 HTTP 200 且
`finish_reason=stop`。对应耗时为 31.22、219.513、0.549、12.818、
152.688 秒；单次请求不构成性能分布。五个原始结果位于
`04-runs/graph-tp2-full-v2-cache-on/`，SHA-256 依次为
`af09aaa6d077b66c2bf8cb5a54ff18971066a6e259e7568e1cca4f092d24f2da`、
`674c6603ca7c32faf7751eeca935833e930e60f44599197ac3bb8f9a38b2ae09`、
`941d827466fc63c5559a17e865d4f6b290a7d814bef4ebc3bccb1e2dc20a0e50`、
`3e7fb90a378f59ac9255f7885e8ce2dfba84f80384c8f4278cfd6e4c108d4f51`、
`6aebb3361a9876babaaf2a95bac79cc926104fc846d94752ce1d1e82517cf365`。
固定日志 `04-runs/graph-tp2-full-v2-cache-on/startup-capture.log`
SHA-256 `7b8839ee460c18dbdf0d0a90c63fe8e84f1ad545d2908d1c336291bcd80a2f27`，
含双 rank 降级警告与 4/4 捕获。视频输入仍在
`05-tmp/graph-full-v2-cache-on/red-blue.mp4`，SHA-256
`a51b2a39385acf22e54626d8f40dc3f047711c3b8c81b98becf41e9d588faed9`。

需要 backend 在同一模型、PPU、revision 上具备 prefill 全图能力并经独立重测，
才能退出该降级。FlagGems 源码同步未授权，当前未改动该仓库。
此次只验证短输入；高分辨率切片、长上下文和稳定性仍待验收。知识库处理状态：
`local-only`，后续复盘再判定是否推广。
