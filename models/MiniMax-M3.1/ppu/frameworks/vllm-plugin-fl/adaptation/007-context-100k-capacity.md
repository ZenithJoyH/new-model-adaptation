# 007：100k 上下文与 64 并发服务容量尝试

## 元数据

- 状态：`hypothesis`；首次及最后验证 2026-09-30。
- Host `PPU-07`，容器 `minimaxM3.1`（ID `1ac783da3c60aea237f5f64a0721c3f33c71b0218a317f0677e54619ec2634d1`，镜像 `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`）；Host/容器同路径工作根 `/mnt/nfs/users/jinghao/minimaxM3.1`。
- 模型 `/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`，16 张 PPU-ZW810E、BF16、128 block、8192 batched tokens、0.90 显存上限、prefix cache enabled、显式 `FULL_DECODE_ONLY` 与 1/2/4/8/16/32 六个图捕获尺寸。
- Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加已记录任务 diff，vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`，FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`；本问题未修改产品源码。

## 问题现象及证据

用户要求将根目录 `start-model.sh` 改为 `--max-model-len 100000 --max-num-seqs 64`，并询问能否移除 `VLLM_PLUGINS`、`TMPDIR`、XDG/Triton/Torch 缓存变量。最初 100k/64 脚本 SHA-256 `860aee228046c3873ff78ea0166cbd8d17f8362f4024740dd712c9ddfc371fbb`，API 启动后 `/health` 200、`/v1/models` 显示 100000、6/6 decode 图捕获；KV 缓存为 1,134,143 token，100k 请求理论最大驻留约 11.34 条。两道不同算术题均返回 128 个 NUL 字符，`04-runs/service-smoke-100k-s64-20260930.json` SHA-256 `1e10f418da17f63b6b0285d6fe54f5f3a81430b5aadb988a98c378de2ec145cd`，测试回执失败。日志 `04-runs/start-model.log` SHA-256 `cbe912d77e91a9a942d6d952054c193b148c02c0a456488c9e80de3630456586`。这次启动时曾在权重加载后发送 TERM，进程未退出而继续启动，故 NUL 结果可能受该信号干扰，不单独用于归因。

对照 100k/32 脚本 `01-environment/start-graph-decode-full-100k-s32-20260930.sh` SHA-256 `bfaa0a277395fccee7730235ed41278f07a53cccd76bcdcd8c72151c62e9bd9e` 在初始化时由 TP12 首报 PPU Triton `illegal memory access`，栈进入 FlagGems `add_func_tensor_scalar_kernel_rank_1` 与 `determine_available_memory`；未开放 API。日志 `04-runs/service-100k-s32-20260930.log` SHA-256 `defbeceaf9820bea49fa38f3e8a854a1fad418600faceaacd7b904ed9f91928f`。

现场源码 `/workspace/FlagGems/src/flag_gems/utils/code_cache.py:22-42` 显示 FlagGems 生成代码默认落在 `/root/.flaggems`，不受 `XDG_CACHE_HOME`、`TRITON_CACHE_DIR`、`TORCH_EXTENSIONS_DIR` 控制。为将新缓存限定在批准根下，后续脚本增加 `FLAGGEMS_CACHE_DIR=/mnt/nfs/users/jinghao/minimaxM3.1/06-cache/flaggems`，未删除或移动原有缓存。在此新缓存下，同一 100k/64 启动脚本保存在 `01-environment/start-graph-decode-full-100k-s64-cache-20260930.sh`，SHA-256 `167beedb7244294f0da5c07abb964d896f5173d0ce3a934515efd4413c05505b`；启动时 TP2 先在 PPU `linear_kernel` 报非法内存访问，后续多个 rank 报同类错误及 NCCL 等待，API 未就绪。日志 `04-runs/start-model-service.log` SHA-256 `d951aaa94b58593e038ffafef97aed37dcde147d33584e0221d49c54e21291a1`。

## 已有经验匹配与诊断

既有[TP sample_tokens 超时条目](../../../../../../docs/troubleshooting/distributed-sample-tokens-timeout.md)的第一故障是推理阶段 rank 序列分歧，本次第一故障发生在服务初始化阶段的 PPU 内存访问，签名不匹配；不提高 RPC 超时。当前可验证事实是 100k 相关尝试未取得正确可用服务，而 65k/32 与 65k/64 在同一新缓存设置下可用。异步 PPU 错误的首报堆栈可能并非实际越界指令；尚无能把问题唯一归因于上下文长度、并发上限或某个算子的受控最小复现。

## 受控尝试

| 轮次 | 相对基线变量 | 设置与路径 | 结果 |
|---|---|---|---|
| 基线 | 既有通过配置 | 65,536/32，`01-environment/start-graph-decode-full-ctx65k-20260930.sh` | 既有 6/6 decode 图及真实聊天通过 |
| A | 上下文与并发按用户要求同时增大 | 100,000/64，最初根脚本；原缓存默认 | API 就绪但两题均为 NUL；因初始化阶段 TERM 干扰，仅作失败现象 |
| B | A 中仅并发上限 64→32 | 100,000/32，`01-environment/start-graph-decode-full-100k-s32-20260930.sh` | TP12 非法内存访问，API 未就绪 |
| C | 基线只加 FlagGems 独立缓存并重验 | 65,536/32，`01-environment/start-graph-decode-full-65k-s32-cache-20260930.sh` SHA-256 `cfa3d5dfeb208f7dcbfeac21bb0742d2a39b4c5c896537a3be1a198d46444892` | 6/6 decode 图、健康 200、两题实际回答 `2`/`5`；修正 thinking 标签解析后的报告 `04-runs/service-smoke-65k-s32-cache-v2-20260930.json` SHA-256 `df21fc0527327472ec44aa4b8c7c82b86b0354260a233d0f19eb405ada4afcb9` 通过；首版解析报告保留为误判证据 |
| D | C 中仅并发上限 32→64 | 65,536/64，`01-environment/start-graph-decode-full-65k-s64-cache-20260930.sh` SHA-256 `62832fe0450e362b4c4fc659a4a2ef61df85c2f6774325d3b9f076daf1e8c52a` | 6/6 decode 图、KV 1,234,432 token、健康 200、两题正确；`04-runs/service-smoke-65k-s64-cache-20260930.json` SHA-256 `8888dd089adec60a9ab7c1b645ea05014202e0c59ab53105c6e0e6527041cbab` 通过 |
| E | D 中上下文 65,536→100,000 | 100,000/64，独立 FlagGems 缓存，脚本 SHA-256 `167beedb...` | 初始化阶段 PPU `linear_kernel` 非法内存访问；API 未就绪、没有精度回执 |

## 处理、验证与限制

2026-10-01 曾将根目录 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh` 改为不显式设置插件与缓存环境变量的 65,536/64 脚本，SHA-256 `6d2ef6cdda2c07e92f5af4862ed99a3786a0843bbeaa2c082337869494198186`；该版本现另存于 `01-environment/start-graph-decode-full-65k-s64-defaults-20261001.sh`。当时 Host/容器相同 inode `29236466205`、mode `0755`、容器 `bash -n` 及占用端口退出码 1 已验证；它独立冷启动并通过 6/6 decode 图捕获、健康与两题实际回答，见[问题 008](008-default-cache-cold-start.md)。当时 `max-num-seqs 64` 是调度上限，KV 缓存容量只相当于约 18.84 条满 65,536-token 请求；64 batch 的图捕获未验证，捕获尺寸止于 32。正式 GPQA 精度仍低于阈值，不因两题通过而变更验收状态。

服务操作均通过单 Host Ansible、在精确 PID/命令/cgroup 核对后执行。旧 65k/32 API host PID `1662197` TERM 后退出，容器保持运行。首次 100k/64 API host PID `768130` 在初始化期间 TERM 未使其退出；就绪后第二次 TERM 退出。100k/32 初始化失败后进程自行退出。第二次 100k/64 API host PID `2093010` TERM 等待 180 秒未退出；核实其独立进程组 `2093010` 全部 19 个成员只含本任务 API、EngineCore、16 workers 与 resource tracker，并核对同一容器 cgroup 后向该组发送 TERM。API/多数 worker 退出，剩余 5 个 TP worker 和 1 个 tracker 经再次核对准确 PID、角色、进程组与 cgroup 后单独 KILL；随后全部退出，16 张 PPU 回到约 1 MiB/0%，适配容器始终运行。各轮 `docker exec -d -w /mnt/nfs/users/jinghao/minimaxM3.1 minimaxM3.1 bash <准确脚本路径>` 启动，未修改或重启容器本体。

处理分类：`FLAGGEMS_CACHE_DIR` 为当时运行产物范围修正；65k/64 为当时容量回退/mitigation；100k 失败根因未证实。后来在 204800/64、容器默认缓存服务上，曾用 vLLM `--skip-mm-profiling` 绕过启动多模态预热并通过文本长上下文验证；再经双算子排除，当前根脚本已恢复完整多模态预热，详见[问题 009](009-context-204800-mm-profile.md)。这些后续成功不证明原 100k 报错的确切根因，也不证明多模态或 GPQA 精度。vLLM/Plugin/FlagGems 源码本轮未改，其他模型与平台未验证，知识库处理状态 `local-only`。
