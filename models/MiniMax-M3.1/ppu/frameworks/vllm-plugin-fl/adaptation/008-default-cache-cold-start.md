# 008：容器默认缓存下的首次启动较慢

## 元数据

- 状态：`hypothesis`；首次出现与最后验证时间：2026-10-01。
- 模型：`/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`。
- 平台与 Host：T-Head PPU，`PPU-07`；容器 `minimaxM3.1`，ID `1ac783da3c60aea237f5f64a0721c3f33c71b0218a317f0677e54619ec2634d1`，镜像 `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`。
- Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加已记录任务 diff；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`；FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`。本轮未修改产品源码。
- 执行模式与负载：TP16、BF16、65,536 上下文、`max-num-seqs=64`、prefix cache enabled、`FULL_DECODE_ONLY`，图捕获尺寸 1/2/4/8/16/32；启动后两道变输入聊天。

## 问题现象

用户要求只保留适配好的平台插件，并让临时文件和缓存直接使用容器默认位置。`importlib.metadata` 在容器中列出唯一外部平台插件 `fl -> vllm_fl:register`；general 组还有 `fl -> vllm_fl:register_model` 及 vLLM 自带的两个 LoRA resolver。当时根目录脚本 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh` SHA-256 `6d2ef6cdda2c07e92f5af4862ed99a3786a0843bbeaa2c082337869494198186` 移除了 `VLLM_PLUGINS`、`TMPDIR`、`XDG_CACHE_HOME`、`FLAGGEMS_CACHE_DIR`、`TRITON_CACHE_DIR`、`TORCH_EXTENSIONS_DIR`；实际 API 进程环境均无这六项。该历史版本现保留为 `01-environment/start-graph-decode-full-65k-s64-defaults-20261001.sh`；当前根脚本及 204800 验证见[问题 009](009-context-204800-mm-profile.md)。默认位置包括容器内 `/root/.cache`、`/root/.flaggems` 和 `/tmp`；启动前容器文件系统可用约 14 TiB。

启动日志 `04-runs/model-service.log` 显示 08:09:18 自动发现 `fl`、08:09:26 激活；08:13:37 加载完 48/48 权重后，EngineCore 每分钟记录共享内存广播等待，API 一度不可用。进程组内核实有多个 `ppu-llc` 编译进程，16 个 worker 均存活，PPU 有计算活动；08:24 左右完成 6/6 decode 图捕获，08:25:07 API 启动完成，`/health` 200。初次观察中误将编译等待视为停滞，不能把这些等待日志当作死锁证据。

## 已有经验匹配

| 条目 | 相同点 | 差异 | 本次决定 |
|---|---|---|---|
| `docs/troubleshooting/distributed-sample-tokens-timeout.md` | 均可能出现等待提示 | 该条目的首故障为推理期 TP `sample_tokens` 分歧与 RPC 超时；本次发生在启动编译期，worker 存活且最终就绪 | 签名不匹配，不提高 RPC 超时 |
| [问题 007](007-context-100k-capacity.md) | 同容器、同模型 | 本次为 65k/64 且最后通过；没有观察到 NUL 输出或非法内存访问 | 仅作独立启动现象记录 |

## 诊断与假设

已验证事实：默认插件发现自动激活 `fl`；根脚本与 API 进程均未设置上述六项；该次冷启动经历较长的 PPU 编译，之后服务和两题推理正常。2026-09-30 带独立缓存的同参数启动约 4 分钟进入图捕获，本次从插件发现到 API 完成约 15 分 49 秒。两次缓存路径、缓存热度和时间不同，本次又一次去掉六项，**尚不能**唯一归因于某个缓存变量、缓存命中率或插件发现机制。没有首个失败 rank 或可复现异常。

## 受控尝试

| 轮次 | 设置 | 准确位置与结果 |
|---|---|
| 基线 | 显式 `VLLM_PLUGINS=fl` 和工作根缓存，65k/64 | `01-environment/start-graph-decode-full-65k-s64-cache-20260930.sh` SHA-256 `62832fe0450e362b4c4fc659a4a2ef61df85c2f6774325d3b9f076daf1e8c52a`；6/6 图、两题通过，报告 `04-runs/service-smoke-65k-s64-cache-20260930.json` |
| 本次 | 用户要求一次去掉六项 | 根目录 `start-model.sh` SHA-256 `6d2ef6cdda2c07e92f5af4862ed99a3786a0843bbeaa2c082337869494198186`；约 16 分钟启动、6/6 图、健康 200、两题通过；报告 `04-runs/service-smoke-65k-s64-defaults-20261001.json` SHA-256 `d903c4a500b617f9f69c7826c08079bfcbfa2b7068fb6d72b1ed9f06556dae0e` |

## 处理和验证

处理分类：诊断。未清理、搬动或删除已有容器缓存；未修改 Plugin、vLLM、FlagGems 或模型权重。根脚本由单 Host Ansible 校验旧 SHA、`--check --diff` 后替换，Host/容器同 inode `29236466205`、mode `0755`、容器 `bash -n` 通过。先核实旧 API host PID `2567362` 的命令与容器 cgroup，再发送 TERM，旧进程退出，容器继续运行；随后由新根脚本启动 host PID `286735`。新服务初始化超过 12 分钟时，对该 PID 发送过一次 TERM，90 秒内未退出；进一步核实其同容器进程组正在运行 `ppu-llc` 后未再发送信号。该进程随后完成启动并保持运行，容器未重启或停止。

两道实际回答 `2`/`5`，报告 `passed=true`、HTTP 200；`/v1/models` 的 `max_model_len=65536`，有效启动参数含 `max_num_seqs=64`、prefix cache enabled，日志显示 6/6 `FULL_DECODE_ONLY` 图捕获。端口被占用时再次调用根脚本退出码 1，原服务仍健康。因启动过程中收到 TERM，这一轮可作为功能与配置验证；不能据此估计无干扰的冷启动耗时或正式精度。正式 GPQA 精度门禁仍未通过。

## 限制与经验沉淀

- 若要比较启动性能，应在独立且已核实的缓存状态下，每次只改一项变量，记录编译进程、缓存热度与图捕获耗时；不以本轮约 16 分钟作为稳定性能结论。
- 此项无需 Plugin 实现、FlagGems 同步或 `07-bugs/` 复现；其他模型与平台未验证。设计审查及 PR 范围不因本次运行配置变化而扩大。
- 知识库处理状态：`local-only`；没有足够的跨模型证据可提升为通用故障条目。
