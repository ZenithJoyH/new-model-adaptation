# 007：用户改写脚本的 Plugin 导入与独立运行条件

## 元数据

- 状态：`open`（Plugin 导入已解决，但用户再次改写的当前根目录脚本缺独立运行保护与目录约束）。首次验证：2026-09-30；最后验证：2026-10-01。
- 模型 / 平台 / Host / 容器：MiniCPM-V-4.7-35B / NVIDIA H100 / `H100-149` / `MinicpmV4.7-35B`。
- 组件：Plugin 基础 HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319` 加未提交 4.7 适配；FlagGems `da6727e38f6f8eedef6cba43695a87b4996f9eca`；vLLM `0.24.0+cu129`。
- 本文的 `<root>` 指已核实宿主机与容器同路径的 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`。
- 目标：`/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/start-model.sh`；用户早期候选 SHA-256 `b3bf5abd0353e7ad35747e822f43204684569c4bc17206ac5dc4978522998284`，2026-09-30 根目录脚本 SHA-256 `4e4982c7ef9c447c0e2759e569c46d31da9931e224a3aae675aeebe343a9ec51`，2026-10-01 前一版精简脚本 SHA-256 `4fefbc52ecf4fd9cccd359823fb96f117ab7387563eb2125f18a857f3adb316c`，当前用户再改脚本 SHA-256 `88ff63628fbdb5f0c863e46bc36a962b070b756346a475c0e2ff64244d284bb1`，权限均为 `0755`；GPU 4/5、TP2、`FULL_AND_PIECEWISE`、端口 8021；当前有效上限为 262,144 token。

## 问题现象和已有经验

用户候选的 `bash -n` 通过，但安装前全新容器进程的 `vllm_fl` 解析为镜像内旧 namespace，缺少 `register` 与 4.7 adapter。这与[问题 001](001-editable-plugin-import-shadowing.md)同签名。按用户要求在原有 `/vllm-workspace/vllm-plugin-FL` 上执行 `pip install --no-index --no-deps --no-build-isolation --no-cache-dir --no-compile --force-reinstall --config-settings editable_mode=compat -e /vllm-workspace/vllm-plugin-FL` 后，`direct_url.json` 确认为 editable，新进程 `PYTHONPATH=None` 时解析到适配后的源码，`fl` entry point 自动激活。

安装解决导入问题后，用户候选仍依赖调用方指定工作目录和缓存环境：相对 `./service.log`、无 GPU 占用检查、无逐进程 Triton 缓存隔离。测试前核实旧端口 8019 服务 PID `29991` 空闲并只停止该任务服务；容器保持运行。共享 Triton 缓存的两次实际启动在 Parastor 上都以 `Errno 16` 失败，详见[问题 003](003-triton-cache-concurrency.md)。安装逐进程缓存钩子并只改变缓存隔离后，候选完成启动和 6/6 图文、10/10 并发验证；这证明参数组合可运行，但由调用方补齐的环境不是用户候选自身的能力。用户候选曾删掉 `--mm-processor-cache-gb 0`；本次短图文通过不能排除既有 canvas M-RoPE 缓存尺寸风险，因此最终脚本恢复该约束。100,000 token 极限长度仍未请求验证。

## 诊断与受控尝试

| 轮次 | 变量 | 结果 |
| --- | --- | --- |
| 历史精简脚本 | 端口 8019、50,000 token、editable Plugin 路径和受控缓存 | 实际启动、图捕获、图文 6/6、十并发 10/10；见[服务验证记录](../acceptance/service-validation-2026-09-30.md) |
| 当前脚本语法 | 只读 `bash -n` | 通过；不证明异步 `nohup` 子进程就绪 |
| 安装前全新容器环境 | 只读 Python 模块解析 | `PYTHONPATH=None`，`vllm_fl` 仅来自旧 namespace，`has_register=False`、4.7 适配模块不存在 |
| editable 重新安装 | 只改安装形式为 `editable_mode=compat` | `vllm_fl.__file__` 与 adapter 均解析到 `/vllm-workspace/vllm-plugin-FL/`，无需 `PYTHONPATH` |
| 用户候选，共享 Triton 缓存 | `<root>/04-runs/user-script-8021-100k-20260930T135248Z/` 与 `<root>/04-runs/user-script-8021-100k-fresh-cache-20260930T1408Z/` | TP worker 分别在初始化和模型 warmup 时遇到 `triton/runtime/cache.py:143` 的 `Errno 16`，API 未就绪 |
| 用户候选，逐进程缓存 | `<root>/04-runs/user-script-8021-100k-pid-cache-20260930T1416Z/` | TP2 两类图各 51/51 捕获，8021 API 就绪，图文 6/6、十并发 10/10；调用方仍需提供工作目录与缓存环境 |
| 2026-09-30 根目录脚本 | `<root>/04-runs/service-full-piecewise-tp2-20260930T144750Z-38048/` | 无 `PYTHONPATH` 直接启动，PID `38060`，两类图各 51/51，`/health` 和 `/v1/models` 为 200，图文 6/6、十并发 10/10；详见[服务验证](../acceptance/service-validation-installed-plugin-2026-09-30.md) |
| 2026-10-01 前一版精简脚本 | `<root>/04-runs/service-full-piecewise-tp2-20261001T000842Z-41084/` | 删除冗余分支和显式 dtype；PID `41096`，两类图各 51/51，`/health` 和 `/v1/models` 为 200，图文 6/6；本轮未重复十并发，见[精简验证](../acceptance/launcher-simplification-2026-10-01.md) |
| 2026-10-01 用户当前原文脚本 | `<root>/04-runs/user-current-script-20261001T002902Z-43939/` | 先核实并停掉空闲的前一版 PID `41096`，再原文执行；新 PID `43939`，有效 maxlen 262,144，两类图各 51/51，API 200，图文 6/6。脚本缺占用保护，日志原写根目录并手动归档，编译缓存落 `/root/.cache/vllm/`；详见[新脚本验证](../acceptance/user-revised-launcher-validation-2026-10-01.md) |

上述服务停启都先核实 PID、命令行、空闲指标和 GPU 4/5。前一版脚本的占用拒绝逻辑在端口 8021 活动时实测通过；用户当前脚本没有这个逻辑，尚未按需恢复。用户早期候选原文保留在 `<root>/04-runs/user-script-8021-100k-pid-cache-20260930T1416Z/start-model.pre-final.sh`；当前用户脚本在根目录，本轮未停止或重启容器。

## 根因、处理与限制

根因分两层：原有 editable 安装形式让旧 namespace 抢先解析；用户候选还依赖外部工作目录与缓存设置，没有防止占用 GPU。前者以 `editable_mode=compat` 重装 Plugin 修复；后者由最终脚本固定根目录、端口和 GPU 占用检查、运行日志与缓存位置，并使用容器内条件性 `.pth` 钩子为各进程隔离 Triton 缓存。脚本显式 `unset PYTHONPATH` 并验证钩子有效，不通过环境路径指定 Plugin。保留用户的端口 8021、100,000 token、TP2 和 `FULL_AND_PIECEWISE`，恢复有模型正确性依据的 `--mm-processor-cache-gb 0`。缓存钩子 SHA-256 `1bc91fb4822188496e394c12aa7039ffaa8300b23a1af05ae1445031deac1f5e`；容器重建后需重新安装并核验，脚本会在它失效时拒绝启动。

以上是前一版脚本的处理；用户本次再改脚本没有保留占用保护、日志/缓存目录与逐进程 Triton 缓存变量。原文脚本虽成功启动并通过 6/6 图文，本轮缓存实际落在容器 `/root`，因此不构成对先前 Parastor 共享缓存竞态的反证。262,144 token 极限长上下文、正式精度、性能、视频及 active profile 的完整 full graph 仍未完成；知识库状态 `local-only`。未改动 Plugin、vLLM 或 FlagGems 源码。
