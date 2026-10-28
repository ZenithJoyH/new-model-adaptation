# 008：迁移 35B 的 FlagGems-vllm paged Flash 优化至 1B

## 范围与实施前计划（2026-10-12）

用户选择 PPU-13 / minicpmV4.7-1B / vllm-plugin-fl 的定向优化迁移与回归。
批准根为宿主和容器同路径 /mnt/nfs/users/jinghao/MiniCPMV4.7-1B；
现场 /mnt RW bind、device:inode 41:12343819932 与历史记录一致。
容器 a8861de7fe73、镜像 f222f9a173b3，保持运行。
Plugin aa4228e、FlagGems-vllm 31fcc73c 均为实际 editable 安装，迁移前干净。
vLLM 和普通安装 FlagGems 保持只读，不设置 PYTHONPATH。

当前用户在 GPU2 / 8000 跑基线性能，服务 PID 507425；该实例使用原 TRITON_ATTN。
待修改的 Flash backend 未被该实例选中。验证使用已核实空闲 GPU3，
不改变正在执行的请求或用户 benchmark。源容器仅只读。

### 项目真相表

| 字段 | 冻结事实 / 计划 |
| --- | --- |
| Current op | 已验证 35B 公共 Flash API → THead BF16 helper → 库内 _paged_attn_fwd；迁移至 1B 的 H8/HKV2/D256 |
| Editable | 已安装库 ops/attention.py、_thead/fused/attention.py、ops/triton_unified_attention.py；Plugin impl/attention.py；相关维护测试及批准根启动配置 |
| Read-only | vLLM、普通 FlagGems、Plugin dispatch/registry/factory/config；源容器、已有用户 benchmark 和原始结果 |
| Build | Python/Triton 修改，无 native rebuild；AST、fresh import、实际 JIT |
| Validation | 公共 API 和真实 Plugin eager/graph；FP32 bottom-right causal 参考，atol=rtol=0.02、NRMS<0.015；两次变输入 replay |
| Benchmark | 隔离 GPU event graph 毫秒，旧实现/新实现同输入中位数；仅诊断算子收益，不签发整模验收 |
| Active set | BF16 H8/HKV2/D256，单 token decode、跨页 prefill、mixed、4K/16K/32K；连续和混合 interleaved KV；实际页大小需再次绑定服务 |
| Aggregation | 显式预热，三批 event 中位数；逐形状列出，不将算子倍率当端到端收益 |
| Timeout | 功能/算子检查 900 秒；服务初始化 1200 秒 |
| Profiler | Torch CPU/CUDA 可用；本轮以真实 API 命中、launch 参数、数值和 event 为证据，计时不重叠 profiler |
| Autotune | 沿用已验证 THead tile，不新增 NVIDIA kernel/config；GQA4 独立验证，未满足条件使用原路径 |
| Fallback | 无新增 Torch compute fallback，非目标特性保留原实现及报错 |

### 对齐契约表

| 字段 | 内容 |
| --- | --- |
| Reference | 实际安装 Torch 2.10 FP32 QK/softmax/V；公共 Flash API 的 bottom-right causal 协议 |
| Device/backend | THead PPU，经 CUDA 接口；实际安装 FlagGems-vllm |
| Inputs | Q[total_q,8,256]，paged K/V[pages,page_size,2,256] BF16；int32 cu/seq/table；末维 stride1 |
| Outputs | 同 Q shape/dtype/device，保留 caller-owned out 和 padding；连续/交错缓存 |
| Dtype matrix | 新分支仅 BF16；FP16、INT8、其他维度不扩展 |
| Accumulation | 原 FP32 在线 softmax 累加，BF16 输出 |
| Semantics | 因果、变长、页表及零长度；非因果/LSE/local/bias/CP/dropout 保留原路径 |
| Autograd | 推理 forward；requires_grad 不进入专化 |
| Unsupported | 训练、量化、其他平台和新 TP 形状不声明支持或收益 |
| Reference-only Torch | 仅测试参考、生成和变输入；生产 helper 仅元数据、empty 和 kernel launch |

### 实现路径表

| 路径 | 条件 | 实现 / 验证 / 风险 |
| --- | --- | --- |
| 原路径 | 非 THead、非 BF16、其他 shape 或特性 | 原公共 Flash API；守卫阴性及原错误 |
| 35B 既有路径 | H8/HKV1/D256、block544 | 复用源容器已验证 helper，保留行为 |
| 1B 新路径 | H8/HKV2/D256、实际页大小 | 同一 helper 按 GQA4 参数化 grid/packing；独立参考和图，防止只复制 GQA8 常量 |
| 长页偏移 | int32 物理页表、元素偏移越界 | 同步 PR #908 的 tl.int64 提升，避免既有非法地址 |
| Plugin | 已有 FlagOS Flash backend | 仅替换库函数 import 和 encoder 不兼容的冗余参数；原调度保留，已有开关启用 |

源方案参考 [35B 问题 015](../../../../../MiniCPM-V-4.7-35B-A3B/ppu/frameworks/vllm-plugin-fl/adaptation/015-direct-flaggems-vllm-long-context.md)。
本次不提交 Git、不创建 PR，不重跑完整精度；既有正式回执与 framework.yml 不刷新。
原生快照位于批准根 04-runs/flash-attention-migration-20261012/baseline.json，
备份及一次性工具位于 02-issues/flash-attention-migration-20261012/。

## 验证与交付

### 保留实现与设计审查

实际新增运行时差异仅四个文件：Plugin 的
`vllm_fl/dispatch/backends/flaggems/impl/attention.py` 改从 FlagGems-vllm
导入公共 Flash 函数，并移除 encoder 调用中不兼容的冗余 `s_aux`；库的
`ops/attention.py` 接入既有 THead BF16 特性守卫，`_thead/fused/attention.py`
复用同一 helper，按实际 KV heads 参数化 GQA 分组、grid 与页大小；
`ops/triton_unified_attention.py` 同步已验证的 int64 页偏移修复。

1B 的适用缓存形状为 `[pages,288,2,256]`，原 35B `[pages,544,1,256]`
守卫保留。decode BM16/BN32、prefill/mixed BM32/BN64，warps4/stages2；
不新增数学 kernel、算子注册或 NVIDIA tuning。没有迁移 MoE、修改 Plugin
dispatch/registry/factory/config，未新增 Torch 计算或数据转换；helper 中
仅有元数据、empty 分配、设备上下文和原 kernel launch。

Plugin HEAD 仍为 `aa4228e`，库 HEAD 仍为 `31fcc73c`，修改前两树干净。
最终 AST 和 `git diff --check` 通过；未声称执行 Black/isort/flake8。
运行源码冻结确认 Plugin270/库345 中只改变上述四个文件，vLLM1886 与
普通 FlagGems2551 个 Python 文件完全未变。目标路径、保留路径和特性守卫
已有下述验证，可保留此次局部迁移；跨平台实际执行和新 TP 形状未验证。

### 算子与实际模型验证

- 最终 1B 测试 **36/36** 通过：32 项公共入口/真实 Plugin、两种缓存布局的
  FP32 参考及两次变输入图重放，另 4 项 GQA4 大物理页偏移（decode/prefill、
  连续/交错、变页面 replay、末槽 NaN 掩码）。大偏移测试没有 skip。
- 兼容性测试 **30/30** 通过，含原 35B 形状及 16 项非目标特性/原错误。
  单卡诊断未选择跨设备上下文测试，不能宣称该项已在 1B 重验。
- 首轮公共入口 16 项通过，但 Plugin 测试误将单卡拓扑字段视作类属性，
  初始化失败；随后在独立测试实例补齐 `dcp_world_size=1`，保留失败日志，
  完整复测通过。生产代码与数值容差没有因该失败而调整。
- GPU3 标准 LLM 进程内模型检查，正常前缀缓存开启、FULL_AND_PIECEWISE，
  两类图各51/51，实际 checkpoint **12/12** 简单数学/红蓝图片结果正确，
  全部 stop。六个 full-attention 层实际为 AttentionFLImpl，KV cache
  `[2,23274,288,2,256]`，stride `[147456,294912,512,256,1]`；临时进程中
  仅记录元数据的 helper 包装确认 **18 次**真实专化命中，未改磁盘源码。
  该检查不是完整精度评测，也不是 HTTP 十并发验收。
- 第一轮多进程 LLM 已完成图捕获，但 `apply_model` 拒绝序列化检查函数，
  未进入请求验证；保留 `model-probe.log`。第二轮使用标准 InprocClient，
  没有启用不安全序列化，完成上述验证。诊断进程退出后 GPU3 无遗留进程。

测试文件：`/workspace/FlagGems-vllm/tests/test_flash_attention_thead_1b.py`，
SHA256 `7377716676ee66515675301d3a42af8616e42fda96dd57507124e9b6a3278429`。
原生日志/XML/退出码见远端本轮 `gqa4-tests-final.*`、`compatibility-tests.*`；
实际模型回执为 `model-probe-v2.json`，证据总入口为 `completion.json`。

### 隔离性能（GPU3）

同输入、同设备，BF16 H8/HKV2/D256、interleaved block288；三批 GPU event
计时取中位数。原路径根据当前 vLLM 实际配置选择 3D decode（threshold64、
splits16）及 2D prefill/mixed。全部形状 NRMS<0.015，无 profiler 同时运行。

| 场景 | 原 vLLM ms | 新 Flash ms | 加速比 |
| --- | ---: | ---: | ---: |
| decode64/KV4K | 0.791 | 0.727 | 1.088 |
| decode64/KV16K | 2.941 | 2.832 | 1.039 |
| decode64/KV32K | 5.821 | 5.736 | 1.015 |
| prefill4×1024/KV4K | 7.815 | 3.546 | 2.204 |
| mixed8192/KV16K | 55.002 | 29.765 | 1.848 |
| mixed8192/KV32K | 126.818 | 66.216 | 1.915 |

第一轮仅比较 2D 的结果单独保留，最终比较以
`operator-benchmark-actual-baseline.json` 为准。以上是算子诊断，
不代表整模端到端收益。当前没有重新执行优化后的整模性能或完整数据集精度。

### 当前服务与脚本

待用户现有三场景基线全部结束后，核验每个 Run3 为128成功、客户端已退出、
服务 running/waiting=0，按 PID/tick 精确停止旧 API507425 和其两个子进程。
仅修改现用根脚本：新增既有 `VLLM_FL_USE_FLAGGEMS_ATTN=1`，新日志放到
本轮 `04-runs/`，保留用户设备2、8000端口、服务名、默认上下文及图配置。
用户现用脚本是性能启动配置，继续显式关闭前缀缓存；不把它当作正式验收的
正常缓存最终交付脚本。旧基线 CSV 和 service.log 均保留。

2026-10-12 11:31 +08:00 核验新 API **538632** / tick **449110747**，
8000端口、服务名 `MiniCPM-V-4.7-1B-base`、上下文262144、健康200；
FlagOS provider 仍为 `default.flagos`，两类图各51/51。
实际进程无 PER_OP/PYTHONPATH；根脚本可执行、语法通过，SHA256
`6ae454a7a05107cddc1537095f767ea4f68dc8b9f111b45b6c46d6d17da32cc1`。
容器始终运行，临时 GPU3 已释放，其他服务未停止或重启。

完整产物根：`/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/04-runs/flash-attention-migration-20261012/`。
`completion.json` SHA256
`2b39bb57d86b6fb9f95515669527864b6c1385897533725f2ec5524592c754a5`；
其中绑定源码文件集、测试、服务、脚本与算子结果。
当前安装产品位于容器内部 `/workspace` 和 site-packages，启动脚本仍在
既有 /mnt bind；未打包或测试新镜像，不声明镜像交付验证。
本轮不提交 Git、不改正式回执或 framework.yml，不标记整体 optimized。
本地 workspace 审计仍有12项既有 profile revision 错误、78项历史复核提示；
目标目录仅有既有 framework.yml 的 revision 待复核，本轮新增 Markdown 没有布局错误。
