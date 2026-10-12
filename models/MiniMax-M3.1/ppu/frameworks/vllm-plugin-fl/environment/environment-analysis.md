# PPU-07 / MiniMax-M3.1 W8A8 环境与适配差距

核对日期：2026-09-29；目标 SSH alias `PPU-07`，容器 `minimaxM3.1`（ID `1ac783da3c60aea237f5f64a0721c3f33c71b0218a317f0677e54619ec2634d1`，运行中）。镜像为 `harbor.baai.ac.cn/flagos-inner-models-release/minimaxm3-pp001-gems5.4.0-tree0.6.2-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-2.1.1-rbd225:202609281651`，image ID `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`。容器保持运行，不允许为了安排资源而重启。

## 工作根与资源

用户指定的 host root `/mnt/nfs/users/jinghao/minimaxM3.1` 为真实路径，设备号/inode `41:29130276076`。容器有 `/mnt:/mnt` bind，container root 同路径，容器内 `stat` 为同一 `41:29130276076`；权重路径 `/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929` 两侧为 `46:1142349`，只读引用。根目录原有两份用户参考补丁，不能覆盖或迁移。`/mnt/cpfs` 权重不是工作根，不写入。

`PPU-07` 为 16 张 PPU-ZW810E，每张 96 GiB；观测驱动 `2.1.1-rbd225`、HGGC `13.0`、PPU-SMI `1.28`。检查时 16 张卡各约占用 84.4 GiB，归属旧 `minimaxM3-latest-20260924` 容器（ID `274609df...`）中的 `VLLM::Worker_TP0..15`，其中 TP0 host PID `1926733`。这是旧 M3 任务服务，本次不能擅自停止；整模 TP16 验证依赖该服务释放资源。`minimaxM3.1` 容器内尚无其自身的 vLLM 服务进程。PPU 进程状态须在每次测试前重新核对。

## 源码与包身份基线

| 组件 | 现有安装/源码 | Git HEAD 与工作树 | 变更边界 |
| --- | --- | --- | --- |
| vLLM | import `/usr/local/lib/python3.12/site-packages/vllm`；源码 `/workspace/vllm`，`0.24.0+empty` | `ee0da84ab9e04ac7610e28580af62c365e898389`，tracked clean | 只读；后续需再次核对无变化 |
| Plugin FL | editable import `/workspace/vllm-plugin-FL/vllm_fl`，包 `0.3.0rc2.post1+g29712e42d` | detached `cafe6363c8c3de5ba4693b91643089c17b3ab87c`；四个继承的 `.orig` 未跟踪文件 | profile 声明的产品可写树；不覆盖继承文件 |
| FlagGems | editable import `/workspace/FlagGems/src/flag_gems`，包 `5.4.0rc2.post1+g4d9c34775` | `master`/`origin/master`，`3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85`，clean；尚未同步 | 需单独授权快进同步；本 profile 不允许把补丁直接写进 FlagGems 产品树 |
| FlagGems-vllm | editable `/workspace/FlagGems-vllm` | `1f9ac0e0caf3c32111f6be44c8e4d2fef2359546`；两处继承的 tracked 修改 | 与本次参考补丁无直接目标；保持原状 |

Plugin 目标源码没有专属 `AGENTS.md`；已读其 README、量化 adapter、聚焦测试及项目 Plugin 贡献标准。Plugin 的正常入口是现有模型注册与 W8A8 adapter/dispatch，不应从模型公共热路径绕开。`main`/`origin/main` 在容器内都指向 `29712e42dba86680577aef9f2f6b5b7f04050a89`，但 PR base 尚未确认，不能据此推定交付基线。

## 参考补丁与差距清单

用户给的 host/container 同路径参考文件：`flaggems-w8a8-oai.patch`，SHA-256 `b67df100fecde963d6312de65fa8578f70e733f61ed7c35ecbb7f09942ca1a06`；`vllm-plugin-fl-minimax-m31-w8a8.patch`，SHA-256 `9de164804ee05d3cd983e94762e55f9a6250848a0f8d284d05c46a018b61bff5`。两份补丁都可在当前相应 checkout 中通过 `git apply --check`，这只证明文本可应用，不证明设计或运行通过。

| 位置/阶段 | 当前差距与候选层级 | 验证 |
| --- | --- | --- |
| compressed-tensors 装载 | M3.1 的文本五路 QKV/index 与视觉三路 QKV 需正确 packed mapping；选择模型 adapter 中受 checkpoint/config 限定的兼容路径 | 先查 metadata 与参数映射，再做小权重/完整装载，守卫未命中测试 |
| Dense/shared/routed MoE | 当前 Plugin 的 FlagGems W8A8 adapter 仅接受 `silu`；M3.1 需要 split layout `SwiGLU-OAI` 的 alpha/beta/clamp 传递 | 数值对照、shape/dtype、eager、graph capture/replay；保持其他模型 `silu` 路径 |
| FlagGems 算子 | 当前 checkout 没有参考补丁中的 `swigluoai_uninterleave` 枚举/实现；先完成获授权同步并重查相容算子；缺失时按 profile 在 Plugin 内建 Triton 实现，经现有 adapter 选择 | 独立算子数值与 graph；Plugin 路径、miss 路径及其他 backend 隔离 |
| Vision RoPE / LM head | 参考补丁含 partial vision RoPE 兼容和 BF16 head 路径；需先复现当前 PPU 问题再决定最小修复；其中 GPTQ/W8A16 示例不属于此 W8A8 checkpoint | 视觉 78/80 维边界、文本推理、无量化 head、其他模型回归 |
| 稀疏 attention / TP16 | 当前 vLLM 已有 MiniMax M3 模型结构，但 all-layer MSA、PPU Triton 和 TP16 graph 尚未在本 checkpoint 验证 | 静态映射、eager、优先 full graph，再按证据决定是否可退至 decode-full |

检索了 `docs/troubleshooting/` 和 MiniMax-M3 历史 issue。旧 M3 的 SwiGLU-OAI、graph 和 GPQA 记录是候选假设，当前模型权重量化、RoPE theta、MTP 与稀疏层分布不同，不能直接复用结果。当前没有复现 TP `sample_tokens` 超时签名，也没有 shape-aware dispatch 的 ContextVar/RLock 签名；如发生，应按完整症状和 revision 重新比对。

配置声明最大位置 1,048,576，按 profile 的初始启动规则计算 `min(1,048,576, 50,000)=50,000`，待实际 service 配置落地并验证参数。非性能服务的 prefix caching 必须保持开启；性能专用服务才显式使用 `--no-enable-prefix-caching`。

当前 `framework.yml` 的 deployment fingerprint `0477a3d77545118ff413e0053bc05eb4a10c58756d026d145290b3668920e2dd` 是本次**未启动服务基线**的规范化 JSON SHA-256，涵盖容器/image ID、config/index SHA、四组件 HEAD、tracked diff SHA、目标 Host、计划 TP16/50,000 context。它不是运行服务身份；FlagGems 同步、Plugin diff、启动配置或设备状态变化后必须现场重核并重新绑定，不能只改哈希。

环境身份原生证据位于 host/container 根目录下 `01-environment/identity-baseline-20260929.json`（SHA-256 `fe023de7c4a33b0e3655cbc17a3d6144091f761aeca232ac52dd5caacf8018c4`）及 `04-runs/env-baseline-20260929/framework-check.json`（SHA-256 `587fd8e472c8d908b4774392115209b2e6c1260eaf085fb67b0abcc402f7885b`）。两者均由 Ansible 单 Host 写入，经 host 与 `minimaxM3.1` 容器 SHA 相同验证；`--check --diff` 在写入前通过。此回执仅证明当前环境基线身份，不证明设备可用、整模加载或适配完成；后续实际部署身份变化必须按契约重新验证环境。

随后仅在 editable Plugin checkout 新增 W8A8 metadata helper 和对应测试，helper SHA-256 为 `0cf4c5a5dfec46b1c75765a34b6e9d57c790909139d1aa535ed25ff4a693d71c`。当前部署指纹重新计算为 `feea17306fc097c762b525fe00e2918410727b292b11783866930b0d5f946883`，所以前述基线回执**已失效**。对当前准确身份重新核对后，写入 `01-environment/identity-after-metadata-20260929.json`（SHA-256 `22c2a97963f3107f7d9c3e92f47ca7f1883aedd5da327ee3c25342a5d3f6e3de`）及 `04-runs/env-after-metadata-20260929/framework-check.json`（SHA-256 `966e9b841490dc00dd0b32623e7888ef47a3c77b79177155d8ceb69c442f32fd`），host/container 哈希一致。当前环境回执只证明未启动服务且新增 helper 的身份；待 FlagGems 同步与 Plugin 后续实施后，必须再次现场核对并生成新回执，不能复写历史回执或只刷新本地 hash。

## 2026-09-30 同步、资源释放与重新核实

用户明确允许只快进同步 FlagGems 和停止旧 `MiniMax-M3` 推理服务。Ansible 在 `PPU-07` 确认 FlagGems `master` 干净、跟踪 `origin/master` 且原 HEAD 是其祖先，随后 `git pull --ff-only origin master` 将 `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85` 更新到 `6b49cff993956bff8cef495abd84f2acb6a63df6`，结束时仍干净。未直接应用 FlagGems 参考补丁。先核实旧服务 host PID `1916867` 的完整 M3/8024 命令和旧容器 cgroup，再执行 `/usr/bin/kill -TERM 1916867`；8024 端口关闭，旧容器 `minimaxM3-latest-20260924` 保持运行。之后 `./scripts/accelerator-check --limit PPU-07` 返回 PPU 查询成功，卡 0–3 均为 1 MiB/0% 的空闲状态；整模启动前还须核对全部 16 卡。

FlagGems 新 HEAD 的 `fused_experts_impl` 仍对激活作 `activation == "silu"` 断言；它虽有 `SWIGLUOAI` 枚举，却按普通 SiLU 处理且没有 `swigluoai_uninterleave` 的 alpha/beta/clamp 参数。Plugin 的现有两段 W8A8 GEMM 与 `swigluoai_uninterleave` dispatcher 已在 PPU 上做真实设备对照：`07-bugs/ppu-moe-repro-20260930.py` SHA-256 `d02f1b3a8ea4d7b387b6e8f818e4f8d484624d4f0785d1502ed17331a7b0507c`，`04-runs/ppu-moe-repro-20260930.log` SHA-256 `6129af516826635b853a0c96369f44a5b34f1de5bd185e9e691be3a0ff982841`；激活最大绝对误差 0，非零专家最大输出 7.71875、相对 FP32 参考最大绝对误差 0.15650。另有 `04-runs/plugin-tests-20260930.log` SHA-256 `aae4bf4edf62622b80df95217fcb848a9acb23d5e57190fc061661823af3a195`，18 项通过。它们证明单卡小形状算子，并不代替 TP16 整模验证。

在当前真实 Plugin diff 与 6 个未跟踪文件、FlagGems/FlagGems-vllm/vLLM HEAD 和 diff、模型配置与索引 SHA、容器/image ID、TP16/50k 计划参数上重新采集规范 JSON 指纹 `54fa39437e4336f556bc1b8cca3bc2fa7b3d3dcf85f26d85556e6ec5fb66194c`。`01-environment/identity-after-integration-20260930.json` 的 host SHA-256 为 `64231e83fe8cb65184fadb9853187c858a8ddd15b7f11e30d82bc9c2fd7c0ee7`；容器内核实相同工作根 inode `41:29130276076`、48 个分片均存在、45,856 个权重名、vLLM 和 FlagGems clean、Plugin HEAD 未改变。此新身份使前两轮环境回执失效；它没有把适配或服务验收判为通过。

初次 TP16 eager 诊断脚本为 host/container 同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/01-environment/start-eager-20260930.sh`，SHA-256 `7981416605bbcb7a7b4ef63f8abd38fe07e726566d23b1906801451286b7b5b3`，`bash -n` 已在容器通过。端口为 127.0.0.1:8025，指定 16 张 PPU、bfloat16、PPU 历史兼容的 128 block、`--max-model-len 50000`（模型配置 1,048,576 与 profile 上限取小）、8192 batched tokens、32 并发、0.90 显存使用上限、开启 prefix caching，并仅在此诊断轮次 `--enforce-eager`。脚本把临时文件限定于 `05-tmp/`、缓存限定于 `06-cache/`、日志限定于 `04-runs/`；SDK/MPI 与单机 TP 通信环境沿同机已运行配置，待服务实测后逐项审查是否仍必要。此脚本不是最终 `start-model.sh`，graph 和服务就绪仍待验证。

## 2026-09-30 服务首试后的环境身份变更

首轮 eager 已加载 48/48 分片，但首个真实 prefill 请求在上游 `index_topk` PPU Triton 编译断言失败，见 [003 问题](../adaptation/003-prefill-index-topk-autotune.md)。Plugin 由此新增仅命中 PPU MiniMax-M3 家族 `topk=16` 的固定上游 JIT 启动守卫及聚焦测试，未修改 vLLM；前述 `54fa3943...` 环境身份因 Plugin diff 和新测试文件变化已失效，不可沿用其通过回执。

第二轮 eager 脚本 `01-environment/start-eager-topk-20260930.sh`，SHA-256 `370a9d71af1c0dffca37c6e47ef4007884eb402d8b07557f19299fa557c17d1c`，参数除日志文件外与首轮相同。TP16 服务加载 48/48 分片，`/v1/completions` 首个固定请求 HTTP 200，但裸提示产生语义错误的重复文本；该结果仅证明通路可执行。改用模型聊天模板的 `/v1/chat/completions`，同一 `1+1` 请求首次在 169.904 秒返回 `</mm:think>2`，热态复测 5.54 秒返回相同答案，分别记录于 `04-runs/eager-chat-20260930.json`（SHA-256 `867f00c932aa36de7436b594322e957aefa7678340044e99d81ae96cb944cfd8`）与 `04-runs/eager-chat-warm-20260930.json`（SHA-256 `fc6b732964eb479df67f058248865e14e6e45faf67656e7577fb06852a4118f0`）。两次各 159 个 prompt token、3 个 completion token，HTTP 200 且服务存活。`1+1` 只能作为最小功能与语义检查，不能推出 GPQA 精度；输出前的 `</mm:think>` 标记留待正式输出健康检查。

只停止本任务 eager API host PID `2410570`（完整 M3.1/8025/`--enforce-eager` 命令与当前容器 cgroup 均经 Ansible 核对），随后 8025 关闭、16 张卡约 1 MiB/0%，`minimaxM3.1` 容器保持运行。`FULL` 首试脚本 `01-environment/start-graph-full-20260930.sh`，SHA-256 `0a9e79a34e239146f9169b39beb8ca9e65c4555fd164eed661dec7beadec7424`，相同模型/TP/50k/缓存参数改用 `--compilation-config '{"cudagraph_mode":"FULL","cudagraph_capture_sizes":[1,2,4,8,16,32]}'`。生效配置最初确为 FULL，但当前 M3.1 的 MiniMaxM3SparseBackend 与 MiniMaxM3IndexerBackend 均只声明 `AttentionCGSupport.UNIFORM_BATCH`，vLLM 自动改为 `FULL_DECODE_ONLY`；6/6 decode FULL 图捕获完成。该服务真实聊天请求 1.701 秒返回 `</mm:think>2`，回执 `04-runs/graph-full-requested-chat-20260930.json` SHA-256 `7fafadd7eb43ed7d78a480b3f0d246f652ab6f05d7806545cc4d64003fb5d2c5`，服务仍存活。FULL 的阻断及后续显式 decode-full 验证应记录在适配和执行模式验收中，不能把此自动降级称为 FULL 通过。

当前适配容器 ID、镜像和 host/container root 映射未变；新增 Plugin 修改后的最终 deployment fingerprint 须再次现场采集，并以新 run ID 绑定原生环境回执。此前所有历史身份只供过程追溯。

已在当前 Plugin diff/未跟踪测试与 helper 均固定后重采集 `01-environment/identity-after-topk-20260930.json`，SHA-256 `54a303b65c08ac377eaa871d615c8f9509c5f8362616e7d25772fe8d37c77c37`；部署指纹 `803853bb265fc97fbeb3f1cac74f34e6ae20832624a5fb4a8ba71668d2087915`，Plugin tracked diff SHA-256 `eb6a48112f6b07a5e0fc456feb9571f967b2cdf927dca7253b3c8af7400db6fe`。现场校验 48 个分片、45,856 个权重名、root inode `41:29130276076`，vLLM/FlagGems 仍 clean。须以这一身份和本文最新 SHA 生成并验证新原生环境回执；文件存在本身不代表环境阶段已重新通过。

## 2026-09-30 65,536 上下文精度重测的环境再确认

用户要求提高生成上限，原 50,000 context 无法容纳 60,000 输出。模型 `text_config.max_position_embeddings=1048576`；首轮 GPQA 198 题提示最长 2,606 token，故新服务采用 `--max-model-len 65536`，生成上限 60,000，提示加输出仍有余量。Host/容器根目录仍同 inode `41:29130276076`；FlagEval 容器相同映射，适配容器 ID `1ac783da3c60aea237f5f64a0721c3f33c71b0218a317f0677e54619ec2634d1` 始终运行。新采集的 `01-environment/identity-ctx65k-20260930.json` SHA-256 `3fc9bccc17fec5f723f1111eb01e227f1c3a0f852c5daec1a523c01bb654a0e5`，deployment fingerprint `f37fdc7e9b8677ab2a057b6c7df886fe556e7f941a034857dfd2ccca96643afd`；四组件 HEAD、Plugin 实际 diff 与模型 config/index 没有变化，只有计划上下文容量由 50,000 升至 65,536。旧环境回执绑定旧指纹，不能代表当前服务。

仅停止本任务旧图服务 host PID `3459830`：Ansible 先核对模型、8025 端口、50k/`FULL_DECODE_ONLY` 参数、准确容器 cgroup 和旧评测退出文件，然后发送 TERM；端口关闭、容器仍运行。65k FULL 首试启动脚本 `01-environment/start-graph-full-ctx65k-20260930.sh` SHA-256 `7ba3924d59e5ab7b2dbc3df22f4a9def3a62f977dc4e55579fb678595ff3148e`。它在加载 48/48 后经历较长初始化，最终健康 200、6/6 decode 图捕获；`04-runs/graph-full-ctx65k-service-20260930.log` 再次给出两个 MiniMax 后端不支持 FULL 并自动降为 `FULL_DECODE_ONLY` 的准确签名。仅停止该首试 host PID `1315506`，容器仍运行。随后以 `01-environment/start-graph-decode-full-ctx65k-20260930.sh` SHA-256 `e7ff2288264cbf37b02f32d532c1c431fc143206825878f5a5b61dada0ade9bf` 启动显式 `FULL_DECODE_ONLY`；日志 `04-runs/graph-decode-full-ctx65k-service-20260930.log` 核实 65,536 context、48/48、6/6 capture、prefix cache enabled 和 API 就绪，无再次降级。服务实例 `ppu07-m31-container1ac783da-api2291878-start345908995-cmd8ee48233f293f954`，health 200，真实聊天和变输入图 replay 通过；十并发简单题 10/10。该服务用于当前 60k 精度重测，仍不是完成后的最终 launcher。
