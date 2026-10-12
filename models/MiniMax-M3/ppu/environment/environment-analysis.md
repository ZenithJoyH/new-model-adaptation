# MiniMax-M3 / PPU-13 推理环境分析

核对日期：2026-09-15。目标仅为 `PPU-13` 上运行中的 `minimaxM3` 容器；未检查或声明其他 PPU Host 可用。

## 1. 目标身份与工作边界

| 项目 | 已核实值 |
|---|---|
| SSH Host alias | `PPU-13` |
| 远端 hostname | `bm-aliyun-wlcb-zonea3-c-810e-96g-10-13` |
| 适配容器 | `minimaxM3`，container ID `7ffdd70d18de9aadfda32f63ba49b42a7b95fb335cc08aa49234f4db6ec180a9`，状态 running |
| 容器镜像 | `harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`；image ID `sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f` |
| 模型路径 | host/container 均为 `/mnt/cpfs/models/MiniMax-M3`，只读引用 |
| 批准工作根 | host `/mnt/nfs/users/jinghao/minimaxM3` → container `/mnt/nfs/users/jinghao/minimaxM3` |
| 映射证据 | Docker bind `/mnt:/mnt`，RW；两侧 `readlink -f` 均解析为同一绝对路径 |
| 网络/IPC | host network、host IPC；启动前必须重新确认端口与服务身份 |

已在批准根下创建 `01-environment/`、`02-issues/`、`03-acceptance/`、`04-runs/`、`05-tmp/`、`06-cache/`、`07-bugs/`。后续 Python bytecode、XDG、Triton、临时文件和 FlagGems oplist 分别定向到 `06-cache/`、`05-tmp/` 与 `01-environment/`。源码不复制到工作根；Plugin 只在现有 editable checkout 修改，vLLM 始终只读，FlagGems 只在既有 checkout 按规定同步。

## 2. 硬件、系统与资源

| 项目 | 结果 |
|---|---|
| Accelerator | 16 × `PPU-ZW810E`，每卡 `98,304 MiB`，容器内 `torch.cuda.device_count()==16` |
| Driver/runtime | `PPU-SMI 1.28`，driver `2.1.1-rbd225`，HGGC `13.0`，PyTorch 报 CUDA runtime `13.0` |
| 当前占用 | 16 卡均约 `1 MiB`、利用率 0%，`ppu-smi` 无运行进程 |
| vLLM platform | `vllm_fl.platform.PlatformFL`，`vendor_name=thead`、`device_type=cuda`、device capability `8.0` |
| CPU | 2 × Intel Xeon Platinum 8575C，96 physical cores / 192 logical CPUs，2 NUMA nodes |
| Host memory | 2.0 TiB，总可用约 1.9 TiB，无 swap |
| 工作根存储 | NFS4 `/mnt/nfs`，14T 总量、约 9.5T 可用 |
| 模型存储 | CPFS `/mnt/cpfs`，21T 总量、约 15T 可用 |
| OS/kernel | Ubuntu 24.04.2，Linux `5.10.134-16.3.al8.x86_64` |

模型索引声明 809.47 GiB 权重 bytes。TP16 粗分约 50.6 GiB/rank，在 96 GiB/rank 上有静态余量；但这未包含视觉塔复制、main/index KV cache、activation、graph pool、collective 和编译 workspace。配置最大位置 1,048,576，依据项目规则初始 `--max-model-len` 固定为 `50000`，同时保留足够 `gpu-memory-utilization` 余量；若内存失败，应诊断真实分配而不是继续缩短上下文。

## 3. 软件栈与源码身份

| 组件 | 版本/路径 | Git 基线与状态 |
|---|---|---|
| Python | 3.12.3 | 容器系统解释器 |
| PyTorch | 2.10.0，CUDA 13.0 | PPU vendor build |
| Triton | 3.6.0 | active backend 为 PPU；首次探测提示 replay benchmarker 缺失并退回 event timing |
| FlagTree | `0.6.2a1+ppu3.6` | 安装包 |
| vLLM | `0.24.0+empty` | `/workspace/vllm`，HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`，detached、clean；安装 direct URL 指向该目录但不是 editable，import spec 指向 site-packages |
| vllm-plugin-FL | `0.3.0rc2.post1+g29712e42d` | editable `/workspace/vllm-plugin-FL`，`main`/`origin/main`，HEAD `29712e42dba86680577aef9f2f6b5b7f04050a89`，clean |
| FlagGems | package metadata 仍显示 `5.4.0rc2.post1+g4d9c34775` | editable `/workspace/FlagGems`，已从同步前 `4d9c3477548fe9ae968fc042b09d32b179860026` 以 `git pull --ff-only origin master` 快进至 `be05ef1db6758adca7a18de3bf529c18a6ac9a87`，`master...origin/master`、clean；editable 源码 revision 以 Git 为准 |
| transformers | 5.8.1 | checkpoint 配置记录 4.52.4，vLLM 使用自有 MiniMax-M3 config 适配 |
| flashinfer | 已安装 | `flashinfer.norm` 的 `gemma_rmsnorm` 与 `gemma_fused_add_rmsnorm` 已在 `(1,128)`、`(7,128)`、`(4,6144)` 上完成 PPU eager 数值验证，graph capture/replay 也已通过 |
| torchvision | 0.25.0 | 安装且 module spec 可见 |
| Native Plugin extension | `vllm_fl._C` spec 不存在 | 当前 Plugin 是 Python-only 安装；需确认 MiniMax 自定义 op 应由何层提供 |
| Toolchain | GCC 13.3、CMake 4.4.2、Ninja 1.13、vendor `nvcc` 13.0 | 只用于既有源码的必要构建/测试，不授权改 vLLM |

基线采集时三个 checkout 均无 tracked/untracked 变更。正式修改前仍须重采一次；每轮完成后对比 vLLM HEAD/status，任何 vLLM 变化都使适配失败。Plugin README、`vllm_fl/dispatch/README.md`、`tests/README.md` 与适配 gate 说明已阅读；当前设计要求通过既有 registry/dispatch/backend 路径接入，vendor 依赖惰性加载，测试覆盖 guard miss、可选依赖隔离、eager 与 graph。

## 4. 当前模型路径与平台行为

- vLLM registry 已原生注册 `MiniMaxM3SparseForCausalLM`、`MiniMaxM3SparseForConditionalGeneration` 与 `MiniMaxM3MTP`，PPU 因 `device_type=cuda` 且不是 ROCm 会选 `vllm.models.minimax_m3.nvidia` 分支。
- Plugin 的 `thead.yaml` 默认 `prefer: flagos`，目前 FlagGems blacklist 为空；普通 attention backend 可经 `vendor.thead` 调用 PPU `flash_attn_3`。
- MiniMax-M3 的 sparse attention/indexer 是模型自管理 backend，不走 Plugin 的通用 `attention_backend` 选择；非 SM100 会走 vLLM 自带 Triton kernels。
- `PlatformFL.check_and_update_config` 对普通 CUDA-like 模型默认 block size 为 16，而 MiniMax-M3 sparse main/index backends只声明支持 block size 128。首轮配置必须显式使用 `--block-size 128`，并通过构造与 cache 初始化验证，不能依赖默认值。
- `torch.ops._C.fused_minimax_m3_qknorm_rope_kv_insert` 在基线环境中实测不存在；同步后 FlagGems 也没有同名或接口兼容实现。其 `fused_deepseek_v4_qnorm_rope_kv_rope_insert` 使用不同张量宽度、缓存布局与模型语义，generic `sparse_attn_triton` 也不满足 MiniMax 的 paged main/index cache contract，不能复用。当前缺口已由 Plugin 的 `vendor.thead` dispatch、精确 `_C` ABI bridge 与 Plugin-owned 两阶段 Triton 实现覆盖，算子级 eager/graph 回归通过，仍待整模服务验证。
- `flashinfer.norm` 的符号、数值执行和 graph replay 已在 PPU 上验证；这只覆盖 Gemma RMSNorm 本身，不能替代整层 residual/attention/MoE 链路验证。
- 当前容器内无 vLLM/API/EngineCore 进程，`ppu-smi` 无计算进程。检测到的 21001/21002/9500 等监听不是本适配服务，不能停止。新服务启动前应选择空闲端口并记录 PID、命令行、容器 ID、端口与启动时间形成 service instance ID。

## 5. 初始适配差距与实施计划

| ID | 组件/调用链 | 现状与所有权 | eager/graph 风险 | 计划的最小验证 |
|---|---|---|---|---|
| G01 | config/registry/loader | vLLM 已提供，Plugin 只负责平台与 runtime hook；vLLM 只读 | import 可能在自定义 op 或可选依赖处失败；spawn 注册需幂等 | config parse、registry inspect、dummy model construct、权重名映射覆盖 |
| G02 | `fused_minimax_m3_qknorm_rope_kv_insert` | 当前 `_C` symbol 缺失；先在同步后的 FlagGems 与 Plugin extension 点检索，若无兼容实现则 Plugin-owned custom op/Triton | 涉及 5 路 fused projection、norm、partial RoPE、两种 cache insert、out buffer 和 in-place alias，必须 graph-safe | 固定 seed reference；dense/sparse、无 cache/有 cache、padding slot、BF16、TP head mapping；eager + capture/replay |
| G03 | Gemma RMSNorm/fused add+norm | vLLM 当前直接调用 FlashInfer；平台归属应在 Plugin vendor/backend 或兼容 hook，不能在模型名热路径散布例外 | kernel ABI、in-place alias、graph capture | 单独 norm/add-norm BF16 vs FP32 reference，空/边界 shape，replay 两次变输入 |
| G04 | MSA indexer + sparse attend | vLLM common Triton 实现，FlagGems 是否有兼容实现待同步后确认 | block 128、top-16、KV/index cache、eager break、PPU Triton 编译 | 小 shape PyTorch reference、prefill/decode、跨块/padding、eager/graph outer replay |
| G05 | dense GQA/FA3 | Plugin `vendor.thead` 已有普通 FlashAttention backend | GQA KV head 复制、cache layout、graph | 第 0–2 层 attention 组件与 paged cache，TP16 representative |
| G06 | SwiGLU-OAI/MoE | vLLM FusedMoE + Plugin/FlagGems dispatch；128 experts/top-4/shared expert | alpha/beta/clamp、FP32 router、expert mapping、collective 一致性 | activation reference、router top-k、单层 MoE、shared+routed combine、TP16 eager/graph |
| G07 | vision/video | vLLM vision tower 与 processor 已有；PPU kernel覆盖未知 | dynamic grid、3D RoPE、patch merge、DP encoder、graph bucket | 文本-only 先通过，再单图、短视频；不由文本结果推断多模态 |
| G08 | service/parallel/cache | 初始 TP16/PP1，block 128，max len 50000；prefix cache 保持开启 | 权重约 50.6 GiB/rank，graph pool 和 KV 余量待实测 | 先 import/构造/组件，再最小权重 load、eager service、graph service |
| G09 | reasoning/tool parser | vLLM 已有 MiniMax-M3 parser | special token、流式边界、截断 | 固定模板的 thinking enabled/disabled/adaptive 与 tool call schema |
| G10 | MTP/speculative | checkpoint 含 7 个 module，普通 loader 跳过 | cache/index metadata 与 verify batch 尚未验收 | 非 speculative 主链通过后独立评估；首轮不宣称 MTP 可用 |

修改层级优先级为：复用 vLLM 已有模型语义 → 通过 Plugin 既有 platform hook/dispatch/backend 提供 PPU 能力 → 同步后的 FlagGems 兼容算子 → 必要时 Plugin-owned Triton/custom op。不得直接修改 vLLM，不得把 PPU 例外推广到其他 vendor，不得用 broad exception fallback 掩盖 OOM、collective 或部分 cache 写入后的失败。

## 6. 验证顺序与当前结论

验证顺序固定为：注册/import → 单算子数值 → cache/indexer/attention/MoE 组件 → 最小模型构造 → TP16 权重加载 → eager 最小推理 → graph 最小推理 → 服务与验收。每个实质问题进入 `adaptation/NNN-*.md`，原始输出留在远端 `04-runs/`，一次性诊断代码留在 `02-issues/` 或 `05-tmp/`。

环境阶段结论：`PPU-13`、容器、工作根映射、16 卡资源、模型身份、软件栈和三个源码边界已核实，具备开始适配的条件；已确认的首要 blocker 是缺少 MiniMax-M3 fused QK-norm/RoPE/cache-insert 自定义 op。环境就绪不等于模型已加载或功能通过。
