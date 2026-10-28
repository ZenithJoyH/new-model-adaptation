# 014：FlagGems 算子与 Plugin 调用层的端到端优化

## 范围与冻结基线

2026-10-09，用户选择适配阶段的性能优化。范围为 PPU-13 的
`minicpmV4.7-35B`、MiniCPM-V-4.7-35B-A3B、BF16、TP2。
本轮为诊断性能与实现回归，不签发正式性能验收；历史执行模式及精度回执
未重新验证，也不改写 `framework.yml`。

批准宿主/容器根均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`；
现场确认 `/mnt` RW bind、device:inode `41:14016406509`，容器 ID
`145f15078dc1c953d9e136ce595e3185003a6606c28993e30061a2047d3f3653`。
定位与测量期间保留原 8010 服务，交付时重启并验证。性能服务使用空闲 GPU6/7、8011，保持
FULL_AND_PIECEWISE 和图规模 `[1,2,4,8,16,32,64]`，默认上下文 262144。
性能命令显式 `--no-enable-prefix-caching`，现场配置为 False；
非性能服务保持缓存开启。

Plugin 安装 HEAD 为 `aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68`，
继承 013 的 7 个 tracked 修改和 3 个新文件。
FlagGems-vllm 实际 editable 安装 `/workspace/FlagGems-vllm`，HEAD
`31fcc73c76eb41cc003f5890c5faeca24814ba5b`，本轮开始时干净。
普通 FlagGems 仍来自 site-packages，vLLM 保持只读；不设置导入覆盖。

原生诊断产物根为 `04-runs/e2e-opt-20261009-2245/`；
脚本在 `02-issues/e2e-opt-20261009-2245/`，原生性能入口副本在
`03-acceptance/e2e-opt-20261009-2245/`。`baseline.json` 冻结组件
Python 文件哈希、Git 状态、请求与测量配置。性能操作为每个场景分别
`single-scenario`，均先同命令 dry-run，再仅移除 dry-run。
Skill bundle SHA 为 `3c46ddd2c4d73b11ca324b230d48429c3d4a40d0c82f56f5b27237d8e81bc9ff`。
三个场景为 `(1024,256,32,64)`、`(4096,128,32,64)`、
`(1024,256,64,128)`，字段依次为输入、输出、最大请求并发、请求数；
每场景三轮，首轮预热。报告须通过 `perf_common.validate_report`，
profiler 结果独立保留，不混入普通计时。

## 编码前项目真相与契约

| 项目 | 冻结事实 / 计划 |
|---|---|
| 算子与调用链 | `TritonExpertsFL.apply` → CachedOp → vendor.thead → FlagGems-vllm 完整 MoE；decoder attention 使用通用 BF16 FlashAttention |
| 可写范围 | 容器实际安装的 Plugin、FlagGems、FlagGems-vllm；vLLM 和权重只读 |
| 构建 | Python/Triton 变更无需安装另一版本；fresh process 使用相同安装，JIT 按缓存键编译 |
| 验证 | FP32 参考与原 provider 对照，固定 atol=rtol=0.02、NRMS<0.015；eager 与两次变输入 graph replay |
| 活跃形状 | BF16，E256、K2048、local I256、top-k8，M1/8/16/32/64/128/256/1024/4096；辅助小形状及 FP16 守卫 |
| 测量 | GPU event/graph 毫秒、重复轮次中位数；端到端同配置原生报告 TTFT、TPOT、输出吞吐 |
| 超时 | 每轮端到端 1800 秒；profiling 单轮 1200 秒；失败保留，不静默删请求或 token |
| profiler | Torch CPU/CUDA，两个 TP rank；native start/stop，限制采集迭代，不用 trace 时延宣称稳态速度 |
| autotune | 优先测量已有 T-Head GEMM/GEMV 参数，不新增 NVIDIA 内核；若仅修改 host/out 协议，不涉及 kernel tunable 参数 |
| fallback | 保留既有 dispatch；不新增 torch compute fallback；不改变 dtype、量化、采样或评测参数 |

| 输入/输出契约 | 内容 |
|---|---|
| 输入 | contiguous [M,K] FP16/BF16，w1 [E,2I,K]、w2 [E,K,I]、top-k IDs/weights 同形状，同设备；本模型无量化 SiLU |
| 输出 | [M,K]，同 dtype/device；框架预分配 output 必须保持所有权，不允许隐式修改 hidden_states |
| 数值 | 保留激活、路由权重位置、FP32 累加及原舍入协议；不通过放宽容差取得通过 |
| 边界 | 空输入、非法 out shape/dtype/device/layout/alias 在计算前处理；原不支持量化/LoRA/clamp 路径保留 |
| 非目标 | 训练/backward、FP8/INT8、EP/DCP 多 rank、不在目标设备上的整模收益不作声明 |

| 候选路径 | 触发 / 验证方式 |
|---|---|
| Plugin 输出协议 | 若 trace 确认重复 copy，沿已有 dispatch 增加兼容 out 接口，provider 直接写入；不复制框架 backend |
| MoE host 开销 | 核查每层 mem_get_info、分配、转置缓存及 graph 捕获；仅保留有稳定收益且内存语义安全的改动 |
| GEMM/GEMV 调度 | 已有内核的实际 TP2 形状、布局和路由分布；单变量候选、同条件对拍，回归则撤销 |
| 其余计算 | 以整模 trace 占比决定是否继续；不得凭算子名称推断整模瓶颈 |

已阅读目标库 `AGENTS.md`、`workflow.md` 与实际 contribution/workflow 文档。
该 revision 没有 `optimization.md` 和 `deep_opt.md`，同 checkout 的贡献文档
明确缺失时使用 profile→假设→实现→验证→keep/revert 循环；记录此源码文档缺项，
不替换安装或改写其规则。Plugin 当前 dispatch 文档及调用方已核对。

## 当前进度

以下为阶段过程；最终保留方案、整模结果和正常服务回执见后文。
GEMV 候选已按实际非转置布局对拍：M8/16 有局部收益，M64/128 显著回归，
因此不将该候选扩展到大 batch；完整候选结果留在远端。

### 初始基线与热点

| 输入/输出/最大请求并发/请求数 | 输出 tok/s | 平均 TTFT ms | 平均 TPOT ms |
|---|---:|---:|---:|
| 1024/256/32/64 | 591.51 | 2480.07 | 48.66 |
| 4096/128/32/64 | 211.70 | 5555.51 | 108.06 |
| 1024/256/64/128 | 1393.27 | 2218.99 | 37.25 |

三份原生报告通过校验。短输入 32 并发两轮吞吐为 816.34、366.68，
波动较大，因此最终收益必须结合后续基线复测，不直接将冷启动差异算作收益。
两个 TP rank 的短/长输入 trace 各采集 10 次 engine iteration：
长输入 rank0 GPU kernel 总时长中 FlashAttention 约占 43.4%，MoE 17.0%，
通用 mm 15.2%，通信 9.3%。mem_get_info 和 copy 并非主要 GPU 热点。
这些占比仅用于定位，不是端到端时间占比。

### 候选与回归

- MoE GEMM1：仅 BF16、E256/N512/K2048/top-k8、M≤256 使用 BN64/BK128；
  单算子非转置布局约有 7–17% 收益，M>256 保留原调度。
  stage1 的 64 并发整模结果低于初始基线，尚不能独立宣称端到端收益。
- Attention：只覆盖目标 BF16、H8/HK1/D256、paged block544、query≥128、
  KV≤8192 且无 dropout/alibi/softcap/local 的 mha_block_128 分支，改为 BM32/BN64/stages2；
  解码及小 mixed batch 保留旧配置。1024/4096 算子对照约 3.06/3.24 倍，
  FP32 参考、FP16/其他 D 守卫、混合 batch 和变输入 graph replay 共 6 项通过。
  stage2 三组输出吞吐为 1257.07、392.50、1316.62；64 并发波动仍需复测。
- Plugin：沿现有 CachedOp 增加 T-Head 非量化、无 expert_map 的直接 out 协议，
  CUDA/其他分支保留既有调用；旧 FlagGems provider 通过兼容复制保持可用。
  FlagGems-vllm 在计算前验证 out 元数据、部分别名和权重/路由重叠，允许完整输入别名。
  实际 Plugin 调用 CPU profile 确认移除 aten::copy_，旧调用的阴性对照可见该复制。
  9 项库测试、11 项 Plugin 功能测试、17 项 dispatch 单测通过；完整输入别名也测试图重放。

失败的候选、错误测试预期和测试入口路径错误保留原始日志；修正后重新执行实际检查。
库原生 MoE benchmark 的 M1 eager speedup 为 0.64，未满足 0.9 门槛；
不能据此签发算子完整验收，继续作为诊断优化比较。
最终结果、实际 diff、设计审查、复测与正常服务生命周期将在验证后追加。

## 最终保留方案与对照结果

2026-10-10，保留 Attention 目标形状调度与完整 MoE 的 out 协议；撤回
GEMM1 tile 修改。后者只有局部算子收益，整模不同并发结果不稳定。
不保留 GEMV 或 GEMM2 候选，也不将有收益的预填充配置推广到解码。

复测先恢复四个运行时源文件，确认 Plugin 271、FlagGems-vllm 345、
vLLM 1886、普通 FlagGems 2551 个文件与初始运行时哈希相同。
随后恢复最终候选，同 GPU6/7、同服务配置、同三组请求分别重新 dry-run 和执行。
两轮测量取原生平均值，首轮预热；18 份普通计时报告重新校验哈希和 schema。

| 输入/输出/最大并发/请求数 | 基线复测输出 tok/s | 最终输出 tok/s | 增幅 | 平均 TTFT ms：基线→最终 | 平均 TPOT ms：基线→最终 |
|---|---:|---:|---:|---:|---:|
| 1024/256/32/64 | 1130.30 | 1194.70 | 5.7% | 1272.76→1073.69 | 23.36→22.60 |
| 4096/128/32/64 | 213.19 | 389.31 | 82.6% | 5554.69→3004.25 | 106.97→58.64 |
| 1024/256/64/128 | 1135.19 | 1575.60 | 38.8% | 2971.47→1670.06 | 46.72→34.06 |

64 并发存在轮间波动，初始基线为 1393.27，最终相对该基线增幅为 13.1%；
不能把复测的 38.8% 宣称为普遍稳定增幅。长输入两次基线为 211.70/213.19，
最终吞吐与 TTFT 的改善较一致。未测量图像/视频吞吐或长于 8192 KV 的调度收益。

### 整模与算子证据

- 相同 profiling 场景，每个 TP rank 的短输入 `aten::copy_` span 为
  1432→1232，CUDA memcpy 为 821→621；长输入对应为 1414→1214、824→624。
  目标 MoE 输出形状减少 200 次复制，证明真实整模调用走了 out 路径。
  CPU op 数量与 CUDA runtime memcpy 数量分别统计，不能混用。
- 长输入 rank0 FlashAttention kernel 累计为 1203.61→335.18 ms，约为原来的 28%；
  MoE 累计 470.75→469.74 ms。该 trace 中 MoE tile 没有可观的累计改善。
- 最终未改 tile 的 MoE 同进程旧返回+复制 / 直接 out 对照，M1/8/32/64/1024/4096
  graph speedup 约 1.038/1.008/1.004/1.004/1.005/1.006；输出 bitwise 对齐。
  Plugin 收益主要是少一次分配和复制，不将整模总体增幅归因于此小收益。
- 43 项回归通过：库 15、Plugin 功能 11、dispatch 单元 17；另补充目标非因果
  paged attention 的 FP32 参考与变输入图重放，1 项通过。无跳过或容差放宽。

### 实现审查与交付边界

实际产品修改只有四个运行时文件：

| 组件 | 文件 | 变更 |
|---|---|---|
| FlagGems-vllm | `src/flaggems_vllm/runtime/backend/_thead/heuristics_config_utils.py` | 精确形状守卫，BM32/BN64/stages2；其他形状使用原默认值 |
| FlagGems-vllm | `src/flaggems_vllm/runtime/backend/_thead/ops/fused_moe.py` | 兼容的 keyword-only out，验证 shape/dtype/device/layout/alias，复用既有 kernel 的输出 |
| Plugin | `vllm_fl/ops/fused_moe/fused_moe_utils.py` | 保留原 dispatch，T-Head 非量化且无 expert_map 时传框架 output；其他分支仍复制返回值 |
| Plugin | `vllm_fl/dispatch/backends/flaggems/flaggems.py` | 老 provider 的 out 兼容桥，默认无 out 行为保持 |

没有新增 registry、复制 vLLM backend、PYTHONPATH 覆盖或 Torch 算子计算 fallback。
原有量化、EP、LoRA/clamp 路径不在新 out 优化范围内。完整 hidden_states 别名
保留原 inplace 语义，部分别名和权重/路由/偏置重叠在设备查询前拒绝。
原版权头已保留；末次头注释整理逐文件证明 AST 相同。
两个仓库 `git diff --check` 通过；Black/isort/flake8 在容器中不可用，未声称执行这些检查。
普通 FlagGems（含既有视觉修复）与 vLLM 全量源文件复核未改动。

`02-issues/e2e-opt-20261009-2245/current-turn-product.patch` 只记录本轮产品差异，
完整仓库 diff、测试与 benchmark 新文件、源哈希和 inherited 状态另存，未提交 Git。
正常启动脚本及容器内部副本 SHA 保持
`03c096bdd0c7b191544e9a7b733059826d732082d8c03f1589c8650faea23298`。
正式精度评测未重跑，M1 原生算子 gate 和历史 profile revision 未重新签发验收；
不更新 framework.yml 或宣称 optimized。布局 audit 为 12 errors/78 warnings，
目标记录只有既有 framework.yml 的 profile revision 待复核。

### 正常服务与结束回执

2026-10-10 00:25（Asia/Shanghai）复核：容器 ID、image 与启动时间未改变，
容器持续运行。临时 8011 服务及其已识别子进程退出，GPU6/7/8/9 没有遗留进程。
原正常服务 2195726 在空闲状态下停止，只处理其已核验的子进程。
通过原 `start-model.sh` 启动新 API PID **2366220**，start tick **427855489**，
GPU0/1 workers 为 2366985/2366986；其他 GPU 上已有服务 PID 和显存占用保留。

`normal-service-verified.json` 确认 HTTP 200、默认上下文 262144、BF16/TP2、
FULL_AND_PIECEWISE、mixed/decode 均 7/7 捕获，以及三个 vendor.thead provider。
正常服务显式 prefix caching=True，不包含性能专用 profiler 或禁用缓存参数。
`normal-service-smoke.json` 的文本、图片、视频顺序/10 并发以及重复前缀检查
**35/35** 通过，全部 stop、HTTP 200，重复前缀 hit delta 为 **4896**。
这只是正确性冒烟，不等价于 GPQA/ERQA 精度验收。

最终 native 入口为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/04-runs/e2e-opt-20261009-2245/completion.json`；
其中列出两次基线与最终三组报告路径/哈希、服务身份和健康回执。
性能结果来自关闭前缀缓存的 GPU6/7 诊断实例；正常 GPU0/1 实例已验证加载与正确性，
不把诊断计时作为正常实例的直接计时证据。未修改采样或精度评测配置。
