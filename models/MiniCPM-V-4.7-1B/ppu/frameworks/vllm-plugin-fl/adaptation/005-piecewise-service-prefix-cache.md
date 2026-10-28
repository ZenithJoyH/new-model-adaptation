# 005：混合图服务的前缀缓存默认值与启动脚本收敛

## 元数据

- 状态：`resolved`；首次出现 2026-09-30，最后验证 2026-10-01。
- 模型：MiniCPM-V-4.7-1B；平台与 Host：T-Head PPU、`PPU-13`；容器：`minicpmV4.7-1B`，镜像 `sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f`。
- Plugin 基线 `3a27a6fb2d514cdf55c00481bf813225dac63319` 加本任务差异；FlagGems checkout `80d0000d93dad55320df06687eb088a5b6dad07d`，运行包 5.3.5；vLLM checkout `ee0da84ab9e04ac7610e28580af62c365e898389`，运行包 0.24.0+empty。此次未修改三棵产品源码。
- 模式与负载：PPU2、TP1、BF16、50,000 上下文、32 个最大序列、普通服务前缀缓存开启，显式请求 `FULL_AND_PIECEWISE`。仅做启动与最小连通性检查，未跑精度测试。

## 问题现象与经验匹配

用户要求启用 `FULL_AND_PIECEWISE` 并只保留必要启动参数。已有 [003](003-gdn-full-graph.md) 证明当前 GDN backend 只能捕获 mixed prefill-decode PIECEWISE 11/11、decode FULL 7/7；这与本次图配置的预期一致，也意味着它不能冒充 profile 的正式 `full` 图验收。

第一次从简化脚本启动时，省略 `--enable-prefix-caching` 后，有效启动日志显示 `enable_prefix_caching=False`。虽然读到的 cache 配置类默认值为 true，实际 CLI 服务配置覆盖了该值。此前正常服务显式开启缓存，省略参数改变了服务行为。已有排障记录没有与当前 CLI 默认值、vLLM 版本和图模式同时匹配的条目，故以当前实例日志为准。

## 尝试、受控比较与根因

第一轮同时切换图模式和精简脚本，是用户指定配置的首次启动，不把它当作单变量因果试验。第二轮以第一轮为基线，只恢复前缀缓存开关；两轮有效配置的差异验证了该开关在当前服务入口的必要性。

| 轮次 | 相对上一轮的变化 | 启动脚本 SHA-256 | 有效设置与结果 |
|---|---|---|---|
| 1 | 相对旧服务改为显式 `FULL_AND_PIECEWISE`，并省略显式 TP1、BF16 和前缀缓存参数 | `6d694134cceeb3688980387bf77e5b5699c55521138e4fbca30d5554f3683c00` | 图捕获完成；TP1/BF16 仍为预期，前缀缓存变成 false。首个服务 PID `161985`，原始日志在 `04-runs/service-20260930T062703Z-161985/server.log`。 |
| 2 | 仅恢复 `--enable-prefix-caching` | `05d58e0c4398024e1299e0c004776d11268ff8977f1a351623604c5647b3d7ea` | 前缀缓存 true；TP1/BF16 不变；mixed prefill-decode PIECEWISE 11/11、decode FULL 7/7；API 就绪。 |
| 3 | 按用户要求继续收敛脚本前置部分，不改模型 CLI 参数 | `987e41159f925e27d6f548804896ae60aadf71f851efe5cce81f36b5249682bb` | 移除容器标记检查、PID 文件、无管道时的 `pipefail`、重复的 `cd` 错误处理与缓存子目录预建。`XDG_CACHE_HOME` 指向 `06-cache/` 后，删去重复的 `VLLM_CACHE_ROOT`；vLLM 当前安装源码表明其默认值仍为 `06-cache/vllm`。Host/容器同一文件、SHA、权限、容器内语法均已核对；没有重启服务，尚未由 v3 真实启动。 |

根因限于已验证的 CLI 有效默认行为：在这个 vLLM 运行包和服务入口中，省略前缀缓存开关会得到 false。没有证据支持修改 vLLM 默认值或推断其他版本行为。

## 解决与服务操作

当时的 v3 脚本为 Host/容器相同路径 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/start-model.sh`，SHA-256 `987e41159f925e27d6f548804896ae60aadf71f851efe5cce81f36b5249682bb`。当时环境、日志、临时目录和缓存限于批准根目录；显式 CLI 参数只保留监听接口、模型 ID、远程模型代码许可、上下文与容量边界、前缀缓存开关和图模式。TP1 与 BF16 从 v2 有效配置得到，不再显式重复。`HF_HOME` 指向当时动态模块缓存，Triton、TorchInductor、FlagGems 的专用缓存路径和 `TMPDIR` 防止默认写入批准根以外；端口及 PPU 空闲检查防止占用共享服务或设备。没有 Plugin/vLLM/FlagGems 产品改动或回归测试文件；一次性连通性代码位于远端 `02-issues/piecewise-service-smoke-v1.py`。

只对本任务已启动的旧服务做精确 PID、启动 tick、命令哈希和空闲请求检查后停止：原 `FULL_DECODE_ONLY` PID `109945` 的记录在 `04-runs/decodefull-product-v2-20260929/stop-for-piecewise-result.json`；第一次混合图 PID `161985` 的记录在 `04-runs/service-20260930T062703Z-161985/stop-for-prefix-correction.json`。两个服务进程均已退出。适配容器没有停止、重启或移除，也未碰其他工作负载。当前服务 PID `163348`，启动 tick `346617306`，命令 SHA-256 `d35033e64a4f4b8e820245e5af99a992d024efd0261b6267fb16ed756cd6ff9c`。

## 验证与限制

先前 v2 服务的原始日志为 `04-runs/service-20260930T063926Z-163348/server.log`；其启动完成后，`CUDAGraphMode.FULL_AND_PIECEWISE`、`enable_prefix_caching=True`、`dtype=torch.bfloat16`、`tensor_parallel_size=1` 均得到确认。最小文本与 224 像素红图请求均 HTTP 200、产生 completion token、finish reason 为 stop，前后 `/health=200` 且进程身份不变；结果 `04-runs/service-20260930T063926Z-163348/smoke-result.json`，SHA-256 `74e99dbd4b468090c8eb271ed515ef5a1679332bc631a2e38386f411be356864`。写入 v3 后，PID `163348` 当时仍在运行且 `/health=200`；这是脚本更新未中断服务的证据，不是 v3 的真实启动验证，也不证明答案正确或图 replay 的长期稳定性。

## 去掉前置区块的临时启动实验（2026-09-30）

按用户后续要求，临时入口 `02-issues/bare-launch-experiment-v1.sh` SHA-256 `7bb22f8b7c94ca21b9071419e8b8a337db9cd43ebaf9dfe0369a2ac67103d044` 只保留 `cd`、`CUDA_VISIBLE_DEVICES=2` 和原模型 CLI 命令，删除脚本内的字节码/缓存/临时目录设置、端口与显存预检、运行目录与日志重定向。测试前精确核对任务服务 PID `163348`、启动 tick `346617306`、命令 SHA-256、子进程及 running/waiting 均为零，然后发送 SIGTERM；停服回执在 `04-runs/service-20260930T063926Z-163348/stop-for-bare-experiment.json`。容器未停止、重启或移除。

容器原始环境只有 `HOME=/root` 和 `PYTHONDONTWRITEBYTECODE=1`，没有其余被删除的缓存/临时变量；`/root/.cache`、`/root/.triton` 和 `/tmp` 并非批准工作根映射。为使临时实验不越界，外层 `docker exec` 单独注入 `HOME=/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/06-cache/bare-launch-experiment-v1` 与 `TMPDIR=/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/05-tmp`，并把标准输出重定向到 `04-runs/bare-launch-experiment-v1-20260930/server.log`。脚本本身没有这些设置。若直接在原始容器环境执行同一精简脚本，默认缓存会写入 `/root`，临时文件写入 `/tmp`，标准输出也不会按本工作区约定保存；本次没有进行这种越界写入实验。

实验服务 PID `165004`，启动 tick `349320673`，命令 SHA-256 `d35033e64a4f4b8e820245e5af99a992d024efd0261b6267fb16ed756cd6ff9c`。启动日志显示正常前缀缓存、TP1/BF16 和 `FULL_AND_PIECEWISE`，mixed prefill-decode PIECEWISE 11/11、decode FULL 7/7；API `/health=200`。无评分文本和 224 像素图片各一次均 HTTP 200、产生 token、finish reason `stop`，结果 `04-runs/bare-launch-experiment-v1-20260930/smoke-result.json` SHA-256 `066c2a3336b0d314b22d7d6bcf69c43bcffc1843a07acad8279f8d8136f80bab`，八项连通性检查均通过，`formal_accuracy=false`。这是启动与基本连通性结果，不是精度或正式性能验收。

该次隔离默认缓存新建约 278 MB；EngineCore 初始化日志为 557.82 秒，首个文本请求 19.124 秒，图片请求 92.019 秒。与复用旧缓存的启动不能构成单变量性能比较，不把这些时长推广为稳定性能结论。实验服务在请求结束、running/waiting 为零后按精确 PID 退出，回执 `04-runs/bare-launch-experiment-v1-20260930/stop-result.json` SHA-256 `109c6bcb54a65bff0697fefd2922dab739ecd4bad71bbf226716ce5789d51d1a`。随后从已实际验证的 `01-environment/start-model-full-and-piecewise-v2.sh` 恢复独立服务，当前运行目录 `04-runs/service-20260930T143311Z-215294/`，API PID `215294`、`/health=200`。根目录 `start-model.sh` 仍为 v3 SHA-256 `987e41159f925e27d6f548804896ae60aadf71f851efe5cce81f36b5249682bb`，本次未改它；v3 尚未真实启动验证。

正式 execution-mode 与 sanity 的原生回执仍对应此前 `decode-full` 服务。当前用户指定混合 PIECEWISE 运行模式不满足 profile 的正式 `full` 或 `decode-full` 最低通过级别，因此不能据此重签执行模式、精度或最终 summary。用户已暂停精度测试；精度首次 GPQA 严格匹配失败和后续性能阻塞保持原状。若后续恢复正式验收，应先切回符合 profile 的图级别并重新核对前置身份与证据。此次问题只需服务配置修正，不提出产品 PR；知识库处理状态 `local-only`。

## 容器默认缓存脚本与用户修改脚本（2026-10-01）

用户明确要求缓存直接留在容器中后，根目录 v4 脚本移除显式缓存/临时环境、目录预建、端口和显存预检，以及运行目录变量；设备仍绑定 PPU2，日志仅重定向到 `04-runs/`。v4 SHA-256 `0bd75d0621bb91f460c05c400dbf7397b607c1d88636e4a289bfa6b4b3d99b48`，实际启动 API PID `216706`。日志确认默认 vLLM 编译缓存 `/root/.cache/vllm/torch_compile_cache/`、前缀缓存 true、mixed PIECEWISE 11/11、decode FULL 7/7 和 API 就绪。文本与图片各一次不计分请求通过，回执 `04-runs/container-cache-smoke-v1-20261001/result.json` SHA-256 `1adba50e7df178eb4d51655ba4cc0862ff81fd8a486a4069df4756d68b8e66ed`。这验证了用户要求的容器内缓存，不构成正式精度或性能结论。

用户之后亲自修改根目录脚本为 `nohup vllm serve`、端口 `8000`，删去显式 `--max-model-len 50000` 与 `--max-num-seqs 32`，日志写到工作根 `service.log`；当前 SHA-256 为 `b8248ed0dcf1775b0e6840713568bc4e693c1287b0e47a850d1269b996b992a7`。对旧任务服务 PID `216706` 做启动 tick、命令哈希、子进程、空闲请求及新端口空闲检查后精确停服，回执 `04-runs/user-launcher-test-20261001/stop.json`。用户脚本真实启动 API PID `246468`，当前 `/health=200`。有效最大上下文 `262144`、TP1、BF16、前缀缓存 true、mixed PIECEWISE 51/51、decode FULL 51/51；初始化耗时 `474.17` 秒。文本与图片最小请求均通过，回执 `04-runs/user-launcher-test-20261001/smoke-result.json` SHA-256 `6fef16275abdaf89fce24775231e520128e99c562a33b5f42ef63fd48c87d7b8`。PPU2 启动后占用 `94283/98304 MiB`，余量约 4 GiB。根目录 `service.log` 不符合项目 `04-runs/` 日志约定，运行中未移动它；用户脚本的 `nohup` 返回也不代表 API 已就绪，需独立健康检查。详细路径、映射和验证见 [启动脚本验证](../acceptance/launcher-precheck.md)。
