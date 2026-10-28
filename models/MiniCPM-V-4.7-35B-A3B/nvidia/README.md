# MiniCPM-V-4.7-35B-A3B / nvidia

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)

当前 framework 记录：

- [vllm-plugin-fl](frameworks/vllm-plugin-fl/README.md)（由旧 35B 目录合入，v2 `blocked`）。
- [vllm-native](frameworks/vllm-native/README.md)（v2；历史结论不自动成为新门禁通过）。

`platform.yml` 的 legacy 平台状态和版本来自原生 vLLM 历史记录，不代表 Plugin 状态；当前状态分别查看各自 `framework.yml`。

## 原生 vLLM 平台说明（历史原文）

- Inventory group：`nvidia`；查询工具：`nvidia-smi`。
- 本轮框架：[vllm-native](frameworks/vllm-native/README.md)；TP2，物理 GPU 2、3。
- 2026-09-28 功能状态：eager 与 decode-full graph 下的文本、图像、视频请求通过；
  正式精度和性能尚未执行。
- 当前用户指定的 `FULL_AND_PIECEWISE` 已写入根级启动脚本；用该脚本重启后的
  TP2 服务通过文本、图像、视频和十并发复测，详见
  [根级脚本验证](frameworks/vllm-native/acceptance/full-and-piecewise-launcher.md)。
- 2026-09-28 历史脚本的 Host 与容器路径均为
  `/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，SHA-256
  `195fd984d82769e8598f800d1a9d5e9dfd4f0e05b22da5a11caa48589aade662`。
  2026-09-28 核对两侧哈希一致、可执行、容器内 `bash -n` 通过；
  脚本启动的服务 `/health` 返回 200，已验证端口占用保护。
- 2026-09-30 首轮精简脚本仍使用同一 Host/容器路径，SHA-256
  `1bca4bb0ac4c190cde1b30dc1da289b3361e2ac558340cfac820d8c7829efb54`。
  仅去除两项冗余缓存环境变量；容器内语法、路径映射、脚本启动就绪、
  文本/图像/视频与十并发 10/10 已验证。见[精简脚本验证](frameworks/vllm-native/acceptance/minimal-launcher.md)。
- 2026-09-30 二次精简后的最终脚本 SHA-256
  `d947e59229f8d9b9602ca2530e1e7b5c8511778bfe9b244eb3a1b26e122ae5aa`，
  再删除多余的缓存目录预创建行。脚本启动、图捕获、文本/图像/视频及十并发
  10/10 再次验证，见[最终脚本验证](frameworks/vllm-native/acceptance/lean-launcher.md)。
- 详细结果与限制见 [功能验证](frameworks/vllm-native/acceptance/functional-validation.md)。
- 用户随后将根级脚本改为 8020 与默认 262144 上下文；2026-09-30 实测遇到
  Triton `EBUSY`，8020 未就绪；见 [005](frameworks/vllm-native/adaptation/005-user-launcher-startup-blocked.md)。
- 按用户纠正仅恢复 Triton 进程缓存隔离后的历史根级脚本，Host/容器路径均为
  `/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，SHA-256
  `67d496ce89a943a8b8d53a12fc0056ce513e1f54c935a8d67049af59e17cee40`。
  用户纠正后仅增加 Triton 进程缓存隔离，没有恢复 2048 长度、batch/seq
  上限、编译 `mode=3` 或其他缓存变量。`bash -n`、两侧哈希、GPU 2/3 TP2、
  8020 健康检查、文本/图像/视频及十并发 10/10 通过；图捕获为
  prefill PIECEWISE 51/51、decode FULL 51/51。详见
  [仅 Triton 隔离验证](frameworks/vllm-native/acceptance/triton-only-8020-launcher.md)。
- 2026-10-01 当前脚本仍在上述 Host/容器同路径，SHA-256
  `8243f7ce5faf16543941c633e305b7e4e29cb655a0bf0ea2a6f3d973eea58d48`。
  仅将全局 `export PYTHONPATH` 改为 vLLM 命令级设置，保留用户最新的
  后台启动及日志方式。重启后健康检查 200，PIECEWISE/decode FULL
  各 51/51，文本请求答 `42`，Triton 缓存目录仍按进程分离。
  见 [命令级 PYTHONPATH 验证](frameworks/vllm-native/acceptance/command-scoped-pythonpath.md)。

## Plugin 平台说明（旧 35B 目录历史原文）

- Inventory group: `nvidia`
- Hardware query: `nvidia-smi`

当前目标为 `MinicpmV4.7-35B` 容器中的 35B-A3B 权重，使用
[`vllm-plugin-fl`](frameworks/vllm-plugin-fl/README.md) profile。工作根为
`H100-149:/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`，容器内同路径；
启动脚本的宿主机与容器路径映射已核实；2026-10-01 改动前两侧设备号与 inode
同为 `45:213708828429`。

当前可执行模型服务脚本在宿主机与容器中均为
`/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/start-model.sh`，SHA-256
`88ff63628fbdb5f0c863e46bc36a962b070b756346a475c0e2ff64244d284bb1`，
2026-10-01 已从容器内按用户原文实际启动并验证。Plugin 以 editable 方式安装，
不依赖 `PYTHONPATH`；GPU 4/5、TP2、`FULL_AND_PIECEWISE`、默认 262,144 token、
端口 8021 的服务 PID `43939` 保持运行。mixed prefill/decode 分段图和 decode
全图各 51/51 捕获；`/health` 与 `/v1/models` 均返回 200，图文 6/6 通过。
日志与结果在
`/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/user-current-script-20261001T002902Z-43939/`；
详见[用户新脚本验证](frameworks/vllm-plugin-fl/acceptance/user-revised-launcher-validation-2026-10-01.md)。
脚本仍缺端口/GPU 占用保护，且默认缓存不在 `06-cache/`，尚不能作为最终可重复启动器。
上一版脚本的结果见[精简验证](frameworks/vllm-plugin-fl/acceptance/launcher-simplification-2026-10-01.md)。
2026-09-30 旧脚本的十并发 10/10 结果见[历史服务验证](frameworks/vllm-plugin-fl/acceptance/service-validation-installed-plugin-2026-09-30.md)。

用户改写候选、安装对照和缓存失败的处理见[问题 007](frameworks/vllm-plugin-fl/adaptation/007-user-edited-launcher-self-containment.md)。
分段 prefill 不满足当前 profile 的正式 full graph 验收要求；极限长上下文、视频、
正式精度和性能尚未执行。此前端口 8019 脚本的历史验证保留在
[旧服务记录](frameworks/vllm-plugin-fl/acceptance/service-validation-2026-09-30.md)。
