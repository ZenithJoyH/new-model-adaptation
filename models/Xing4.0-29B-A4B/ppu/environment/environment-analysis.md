# Xing4.0-29B-A4B PPU 环境分析

## 目标与工作区

- SSH Host：`PPU-13`；连通性检查解析到
  `bm-aliyun-wlcb-zonea3-c-810e-96g-10-13`。
- 容器：`xing4_0`，2026-09-16 核实时处于 running，只有容器守护进程与
  `sleep infinity`，没有模型服务或 PPU 计算进程。
- 镜像：
  `harbor.baai.ac.cn/flagos-inner-models-release/xingchen4-pp001-gems5.3.5-tree0.6.2-cxnone-plugin0.0.0-vllm0.24.0-cp312-pt210-hggc130-x64-2.1.1-rbd225:202609141006`。
- 权重：`/mnt/cpfs/models/Xing4.0-29B-A4B`，仅作只读输入。
- 批准工作根：Host 与容器均为 `/mnt/nfs/users/jinghao/xingchen4`。容器将 Host
  `/mnt` 以读写方式映射到 `/mnt`，现场以 device/inode 验证两侧目标为同一目录。
- 新过程产物使用 `01-environment/`～`07-bugs/`；已有 `optimize/`、`profile/`、
  `test/` 等历史目录保持原样，不迁移、不改写。
- 非敏感原始快照：
  `/mnt/nfs/users/jinghao/xingchen4/01-environment/environment-snapshot-20260916.txt`。

## 硬件与主机资源

- 16 张 `PPU-ZW810E`，每张 98,304 MiB；采集时每张仅 1 MiB、utilization 0%，
  `ppu-smi` 未发现运行进程。
- PPU-SMI 1.28，driver `2.1.1-rbd225`。
- Host kernel：Alibaba Linux 8 系列内核
  `5.10.134-16.3.al8.x86_64`；容器为 Ubuntu 24.04.2 x86_64。
- Host/容器可见 192 CPU，内存 2.0 TiB、采集时可用约 1.9 TiB，无 swap。
- NFS 工作盘约 14 TiB、可用 9.4 TiB；CPFS 权重盘约 21 TiB、可用 15 TiB。
- 本任务先沿用旧适配的 TP4/PP1/EP1 假设；这只是候选拓扑，必须由新权重真实加载、
  collective、prefill/decode 和 graph 测试验证。

## 运行时与源码身份

| 组件 | 当前身份 | 状态与边界 |
|---|---|---|
| Python | 3.12.3 / GCC 13.3.0 | 容器运行时 |
| PyTorch | 2.10.0 | PPU 镜像提供 |
| FlagTree | `0.6.2a1+ppu3.6` | PPU 编译/图执行依赖 |
| vLLM | `0.24.0+empty`，HEAD `ee0da84ab9e04ac7610e28580af62c365e898389` | `/workspace/vllm`，detached、clean；全程只读 |
| vllm-plugin-FL | `0.0.0+g0ef3d87a7.d20260909`，HEAD `0ef3d87a728f33ce12ea623eda84a018ad81ca6d` | editable import 指向 `/workspace/vllm-plugin-FL`；允许的产品修改位置 |
| FlagGems | `5.3.5.post1.dev53+gf0d154f14`，HEAD `3f2989283fb6212fc5e18dba6a52826c0bc02285` | `/workspace/FlagGems`，`master...origin/master`、clean；适配集成前执行 fetch + fast-forward-only pull |
| FlagGems-vllm | 0.1.0，HEAD `bbc94043fd35f357e3e41350adce62246ec6d569` | `/workspace/FlagGems-vllm`，detached；本轮除非证明确有接口缺口，否则只读 |

Plugin 起始状态是 detached HEAD，且含任务开始前的继承改动：5 个 CI/build 文件只有
mode 变化，`vllm_fl/dispatch/config/thead.yaml` 增加已有 FlagOS blacklist。本轮不重置、
不覆盖这些修改；新增差异必须单独列出。Plugin 内没有额外 `AGENTS.md` 或贡献指南，已读取
其 dispatch README、`pyproject.toml` 和仓库级贡献策略。

## 当前能力与缺口

1. 当前 Plugin 只注册 `XingChen4ForCausalLM` / `model_type=xingchen4` / reasoning
   parser `xingchen4`；新权重要求 `Xing4_0ForCausalLM` / `xing4_0`。
2. 既有 `vllm_fl/models/xingchen4.py` 已经使用 DeepSeek-V2 MLA/MoE 和 Plugin
   `mhc_pre`/`mhc_post` dispatch，并可直接加载 `hc_fn`、`hc_base`、`hc_scale`；因此无需
   在模型文件内引入 PR #57135 的进程级 `USE_FLAGOS`。
3. 新入口应直接映射 `hc_mult`、`hc_sinkhorn_iters`、`hc_eps` 和 clamp 字段，严格接受
   新权重键；不为旧 `mapping_weight`/`alpha_*` 协议增加 fallback。
4. 现有实现约束 BF16、4 streams、PP1、非 DSA、非 speculative。新权重配置满足这些
   条件；DSA/MTP/量化仍应显式拒绝或跳过，不能因 PR #57135 含相应代码便声称已支持。
5. 新模型最大长度为 262144；若启动初始服务，按项目规则使用 `--max-model-len 50000`。
   该值不是长上下文通过证明，不允许进一步静默缩小以绕过资源或 graph 问题。

## 修改归属与验证计划

- 模型/config/registry/parser 身份属于 Plugin model/config 扩展点；mHC、MLA、MoE 算子
  继续通过既有 dispatch/backend 路径，不修改共享 vLLM。
- 保留旧模型注册，新增独立 `xing4_0` 入口；新入口自身不包含旧权重兼容逻辑。这样既符合
  用户“不需要旧权重兼容”的要求，又不会无理由删除容器中已有模型能力。
- 先同步 clean、tracked 的 FlagGems `master`，再核对现有 mHC/MLA 算子；若已有兼容实现，
  只补 Plugin 接入或模型协议，不新增 Triton kernel。
- 增量验证顺序：无设备 import/注册与 config → 严格 loader 静态/小对象测试 → mHC focused
  eager 数值 → graph capture/replay → 新权重最小初始化/加载 → 最小生成或服务 bring-up。
- 影响矩阵至少覆盖新 `Xing4_0` 命中、旧 `XingChen4` 注册仍存在、其他模型未命中守卫、
  PPU eager/graph。缺少其他平台硬件时只记录未验证，不推断跨平台支持。

## 环境结论

Host、容器、权重、工作根映射、设备空闲状态和 editable Plugin 源码身份已经核实，具备进入
adaptation 的基础条件。FlagGems 在同步前仍只代表采集时 revision；Plugin 脏树中的既有
修改必须作为 inherited diff 保护。正式 acceptance 未获本轮授权，因此 adaptation 成功也只
能形成局部功能证据，不能把平台标为 `functional` 或 `optimized`。
