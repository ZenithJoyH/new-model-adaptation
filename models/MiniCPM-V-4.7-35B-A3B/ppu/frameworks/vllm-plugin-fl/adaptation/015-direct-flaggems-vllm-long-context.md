# 015：恢复原调度并直接替换 FlagGems-vllm 调用

## 范围与现场基线

2026-10-10，用户要求直接用 FlagGems-vllm 替换原 FlagGems 调用，不修改
Plugin 的 dispatch 逻辑，并指出长输入性能下降。范围为 PPU-13 的
`minicpmV4.7-35B`、MiniCPM-V-4.7-35B-A3B、BF16/TP2；阶段 3 修复及诊断性能，
不重新签发正式精度/性能验收。

现场容器 ID、image、启动时间及 `/mnt` RW bind 与 014 一致，宿主/容器批准根
均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，device:inode `41:14016406509`。
Plugin 和 FlagGems-vllm 实际 editable 路径、HEAD 未改变；继承 013/014 的修改。
用户已调整根脚本为服务名 `MiniCPM-V-4.7-35B-A3B-ppu-nomm-opt`、关闭 prefix cache，
正常/性能配置分别绑定；保留用户已完成的 CSV，未完成的旧 32K 运行单独标注。

原生快照/备份分别保存在 `04-runs/direct-flaggems-vllm-20261010-1223/`
与 `02-issues/direct-flaggems-vllm-20261010-1223/`。vLLM/普通 FlagGems 全量文件哈希
已冻结；这两个组件只读。隔离算子诊断使用空闲 GPU8/9；完成回归检查后，按 PID、
启动 tick、命令及子进程树核验并停止本任务 GPU0/1 服务及旧性能客户端，
在原 GPU0/1、8010 端口复测。其它服务和容器保持运行。

## 已确认的回归与编码前方案

用户 CSV 位于 `test/perf_test/benchmark_results/`；相同 64 并发、128 请求、
输出 1024 tokens，三轮去首轮后的摘要：

| 输入 | nomm 输出 tok/s | nomm-opt 输出 tok/s | 平均 TPOT ms：原→当前 |
|---|---:|---:|---:|
| 4096 | 1354.66 | 1315.82 | 39.68→42.89 |
| 16384 | 484.46 | 98.73 | 105.62→542.78 |

32K 当前尚在运行，不能将不完整结果作为结论。旧 CSV 只有历史计时和场景，
不含完整源码/服务身份回执，不替代可追溯的同实例受控复测。

原 013 引入了完整 MoE 的 THead fast path 和 vendor provider；这超出了用户现在
明确的集成要求。计划撤回这些本任务引入的注册/选择修改，保留原有 CachedOp、
policy、registry、平台配置及 staged MoE 路径；在原 FlagOS backend 的计算接口替换库调用。
Attention 复用已有 AttentionFLBackend/metadata/cache/out 协议，不再添加 vendor 子类。
factory 曾在中间实验直接返回 Flash backend，随后完整恢复 HEAD；最终仅使用已有
`VLLM_FL_USE_FLAGGEMS_ATTN=1` 选择既有 backend。policy、factory 和注册逻辑均不修改。

长输入嫌疑：014 的 BF16 H8/HK1/D256、block544 调优仅覆盖 KV≤8192，
16K/32K chunked prefill 会落回 BM128/BN32/stages3。隔离 graph 对照初步显示
16K 约148→44.6ms、32K 约347→95.4ms，数值对旧实现对齐；仍需独立 FP32 参考、
两次变输入 graph replay 及整模计时。禁止将单算子比值当作端到端收益。

契约：模型 dtype、权重、采样、TP、上下文及 FULL_AND_PIECEWISE 和七个图规模保持；
验证调用实际命中、框架输出所有权、prefill/decode/mixed、cache 写入、原非目标路径。
只保留有对照证据的算子配置，未量化及其它平台测试范围明确披露。
新性能操作选择用户提供的三个场景组成 `full-suite`，使用项目原生 runner、三轮去首轮、
相同 dry-run 命令；所有性能实例显式 `--no-enable-prefix-caching`，正常服务恢复 cache 开启。

## 进度

Plugin 已恢复原注册、factory 和 MoE 分支，只修改三个原计算接口文件。原 `fused_experts`
CUDA fast path 的 gate 不变；PPU 沿 staged 路径调用 `invoke_fused_moe_triton_kernel`。
已有 attention 开关启用 AttentionFLBackend，实际 Flash 函数直接从 FlagGems-vllm 导入。
没有新的 vendor 类或 per-op 覆盖项；cache 写入仍调用原 FlagGems 实现。

47 项检查通过：Plugin 实际 staged MoE/attention 数值及 graph 11 项、调度和非目标
guard 单元检查 15 项、库回归 19 项、长 mixed/boundary FP32 参考及变输入 graph 2 项。
当前启动原生三场景性能复测，尚不能据此宣布端到端性能修复。

GPU0/1 中间复测的 4K 三轮完成，去首轮输出吞吐 1286.13 tok/s、TPOT 44.42ms，
低于历史 1354.66/39.68ms。16K 在 mixed 阶段仍表现为 prompt 约 6.5–11.5K tok/s、
generation 约 40–62 tok/s；未完成整轮，不据此给出场景最终吞吐。
已停止该中间实例并保留 `prefill-guard-stage/`，进一步诊断混合批次的 GQA 计算浪费。

### 混合批次补充方案（实现前）

| 项目 | 内容 |
|---|---|
| Active set | 总 query 8192：一条8129-token prefill + 63条1-token decode；H8/HK1/D256，paged block544，KV16K/32K；另测纯 prefill/decode |
| Evidence / comparator | FlagGems-vllm Flash 公共函数与库内现有 GQA paged 在线 softmax kernel 的隔离 graph event 对照；后者只作候选，不预先声明生产链路 |
| Writable / readonly | 仅库内已安装源码和对应测试可改；Plugin调度、vLLM、普通FlagGems保持；先 probe，命中数值和收益后再决定实现 |
| Semantics / validation | BF16、bottom-right causal、页表/变长序列、caller-owned out；固定FP32容差，两次变输入图、跨页及非目标守卫；纯计时与服务性能不重叠 |
| Risk / fallback | 避免将单query当大M矩阵、重复读取共享KV；LSE、量化、bias/local、其它平台保留原入口，不改采样或服务batch配置 |

完整 28 组隔离对照通过。候选采用库内 `ops/triton_unified_attention.py` 的
`_paged_attn_fwd` 计算内核（GQA 分组、FP32 在线 softmax），不调用 vLLM attention。
prefill/mixed 使用 BM32/BN64/stages2，decode 使用 BM16/BN32/stages2：
mixed16K 83.28→26.63ms、mixed32K 174.47→62.18ms；decode16K 3.21→1.43ms、
decode32K 6.14→2.76ms、decode4K 0.97→0.43ms。对原 Flash 的 NRMS≤0.00276。

据此在既有 `_thead/fused/attention.py` 添加 BF16 paged Flash helper，由库公共 Flash
API 的 THead/BF16 条件调用；未更换 Plugin backend 或借助其调度选 kernel。
不新增/复制计算 kernel、不修改 NVIDIA 路径。LSE、非因果、dropout、local、alibi、
其它 dtype/形状、CP 继续原实现。普通 graph 捕获的 max-K 可能为 262144，
故新分支不能依赖 34816 上限；实际迭代由 GPU `seqused_k` 控制，必须补验捕获
长 max-K 后重放短/长/零长度序列及非连续页表。FP32 容差保持不变。

最终 66 项回归全通过：库 40 项（其中 16 个非目标特性/错误守卫、两个动态图元数据、
一个跨设备上下文），Plugin 真实数值/图/缓存/cascade 11 项，原调度与 MoE 公共 API
guard 15 项。首轮守卫测试误将非零 `num_splits` 的原拒绝行为预期为普通计算，
保留失败日志于 `gqa-tests-attempt1/`，改为验证原 `RuntimeError`；FA3 保留原 Python 链路的错误。
没有放宽数值容差、跳过测试或改变 dtype。

`final-source.json` 冻结 Plugin 270/库345 个运行 Python 文件、HEAD、当前 diff 与两份
启动脚本；八个调度/注册/config 文件逐项与 Plugin HEAD 原文相同。vLLM 1886、
普通 FlagGems 2551 个文件仍与现场基线一致。最终三场景计时使用原 GPU0/1，结果如下。

## 最终诊断性能结果

最终原生 `full-suite` 完成九轮，1152/1152 请求成功、0失败；三轮均纳入失败检查，
摘要只平均第二、第三轮。每轮总输出 131072 tokens、总输入严格等于场景长度×128，
性能实例实际关闭 prefix cache，计时期间无 profiler 或其它本任务 GPU probe。
`direct-perf-validated.json` 经原生 `validate_report` 检查无错误；结果报告：
`04-runs/direct-flaggems-vllm-20261010-1223/perf/MiniCPM-V-4.7-35B-A3B-ppu-nomm-opt/20261010_132139_372834/benchmark-result.json`。

| 输入/输出，c64/n128 | 历史 nomm tok/s | 退化 nomm-opt tok/s | 修复 tok/s | 对历史变化 |
|---|---:|---:|---:|---:|
| 4096/1024 | 1354.66 | 1315.82 | 1532.71 | +13.14% |
| 16384/1024 | 484.46 | 98.73 | 594.22 | +22.66% |
| 32768/1024 | 196.79 | 未完成 | 269.62 | +37.01% |

| 输入 | 历史→修复 平均 TTFT ms | 历史→修复 平均 TPOT ms |
|---|---:|---:|
| 4096 | 7822.36→4497.33 | 39.68→37.23 |
| 16384 | 26484.11→19975.08 | 105.62→87.36 |
| 32768 | 76788.56→51938.92 | 248.66→184.39 |

三场景均恢复并高于所给历史均值；16K 相比退化结果约 6.02 倍。
历史 CSV 没有原始完整源码/部署绑定，本表属于同设备、同场景的历史参照，
未将它包装成原始源码重建后的受控 A/B 或正式验收。没有更改权重、dtype、TP、
服务上下文、graph 配置或模型默认采样配置。新 runner 显式固定 random 长度范围和
prefix 长度为0，仍调用原生 `vllm bench serve`；与 legacy 客户端的完整命令分别保留。

根级脚本和容器内部交付副本均移除 PER_OP，新增现成的 attention 开关；保留必要的
设备/黑名单、缓存归属、MM processor 元数据保护和用户要求的图配置。
正常脚本开启 prefix cache，性能专用命令显式关闭，两种配置分别验证。
根/内部脚本 SHA-256：`74a4e9e5da5c9b2ec341a02d7015cd790e14648a08074a635158560cb00c0d42`。
正常根级脚本已实际启动，API PID `2537572`、start tick `432857640`，GPU0/1、8010；
2026-10-10 14:23:34 +08:00 最终检查 `/health=200`、默认上下文262144、prefix cache开启，
进程没有 `VLLM_FL_PER_OP` 或 `PYTHONPATH`。PIECEWISE 与 FULL decode 各7/7；
文本/图片/视频顺序请求、各10并发及两次长前缀复用共35/35正确、HTTP200、正常stop，
前缀命中新增4896 tokens，检查前后 PID/tick/cmd identity一致。
`normal-complete.json`、`normal-service-smoke.json`、`final-live-check.json` 保存回执；
Plugin270、FlagGems-vllm345个运行源码哈希与冻结版本一致，八个调度文件与HEAD一致，
vLLM1886、普通FlagGems2551个文件与现场基线一致；两仓库diff检查及两个脚本语法检查通过。
性能报告SHA-256：`d3dd577e2f34d6f178627b236645fdf670cf3d25371d16b7d83dbf005714d68a`；
35项请求报告SHA-256：`c7f3b9e64a6f5a3d44855d0a0615e2575ce8b0a7c8b477e68c64bafedcbc3348`。
容器内部交付副本位于无bind mount的`/workspace`，正常服务运行、性能实例已按身份停止。
这些请求属于定向功能回归，不能代替正式数据集精度或完整验收。

本轮不重跑 GPQA/ERQA、未验证实际 262144-token 负载、未构建或测试新镜像。
`framework.yml` 的正式回执与状态不更新。工作区审计仍为既有12个 profile revision
错误、78项复核提示；没有将其视为远端成功证明。

### 算子修改前冻结表

| 项目真相 | 内容 |
|---|---|
| Current op / source | BF16 paged FlashAttention；FlagGems-vllm HEAD 31fcc73c；PPU staged MoE 的既有 invoke API |
| Editable | `_thead/heuristics_config_utils.py`、既有 `_thead/ops/__init__.py` 导出；对应测试 |
| Read-only | vLLM、普通 FlagGems、已有参考/原生性能 runner；旧快照与 probe 结果保持 |
| Build | Python/Triton 修改，无 wheel/native rebuild；AST、fresh import、JIT |
| Validation | FP32 参考，atol=rtol=0.02、NRMS<0.015；eager、warmup、两次变输入 graph replay |
| Benchmark / active set | graph GPU event 毫秒越低越好；BF16 H8/HK1/D256、block544、chunk4096/KV16K/32K、decode64/KV17K/33K |
| Aggregation / timeout | 三批 event 的中位数，端到端三轮去首轮；算子900秒、性能每轮21600秒 |
| Profiler | 沿用已确认可用 Torch CPU/CUDA；本轮优先 shape/config 命中与 event 对照，不混 profiler 与普通计时 |
| Autotune | 仅 THead 已有 heuristic 配置与 public API 导出，无新增 NVIDIA kernel；NVIDIA autotune 无变更，豁免新增配置 |
| Fallback | 不增加 Torch compute fallback；已有 dtype/特性守卫保持 |

| 对齐契约 | 内容 |
|---|---|
| Reference / device | 已安装 Torch 2.10 FP32 masked QK-softmax-V，THead PPU CUDA 接口 |
| Inputs | BF16 Q[total_q,8,256]、KV[pages,544,1,256]、int32 table/cu/seq；last stride1 |
| Outputs | 同 Q shape/dtype/device，保持 caller-owned out；可选 LSE 与原接口一致 |
| Dtype / accumulation | 只扩展既有 BF16 调优守卫，FP16及其它维度保留原实现；原 FP32 累加与 BF16 输出舍入 |
| Semantics | bottom-right causal mask；因果/非因果、mixed、paged 协议保持；NaN/Inf语义不变，未另作全矩阵验证 |
| Autograd / unsupported | 推理 forward；训练、量化、EP/DCP 多rank及其它设备整模不声明；原报错及原能力范围保持 |
| Reference-only Torch | 测试与 probe 的参考/输入生成/graph mutation；不进入生产配置或导出代码 |

| 路径 | 实现 / 验证 / 风险 |
|---|---|
| Existing early/unsupported | 不修改函数、参数、空输入处理或错误行为 |
| Target prefill | 同 BF16 H256 paged守卫，实测后扩展 KV 上限；三种候选对照与 FP32/graph；风险为长长度回归 |
| Decode / other shape | 保持已有配置，单独计时避免将 prefill 配置推广至 decode |
| Staged MoE public export | 将既有 THead invoke 导出给库 runtime，原 Plugin 调度调用不变；验证两 GEMM、路由、输出所有权及变输入 replay |

## 用户后续性能与 profiling 归因（2026-10-10）

本次仅只读分析 PPU-13 同容器；未运行新 benchmark、未修改产品或服务。
当前 Plugin270、FlagGems-vllm345个运行源码哈希仍与本轮冻结版本一致。
用户已将根级脚本改成关闭前缀缓存并配置 Torch profiler，按当前文件记录，
未恢复或覆盖该脚本；上面的正常服务回执仅代表14:23时的历史检查。

用户新结果位于原`test/perf_test/benchmark_results/`，n128文件时间戳
`20261010_143455`，三轮去首轮的4K/16K/32K输出吞吐为1541.12/595.63/269.74 tok/s，
相对历史nomm为+13.76%/+22.95%/+37.07%，与上面独立诊断复测接近。
`20261010_152903`的4K/n64文件包含`Run3(SUCCESS)+profile`，其SUMMARY来自该轮，
没有将它混入无profiler的n128吞吐比较。

对比`profile/vllm_profile`与`profile/vllm_profile_opt`的两份rank摘要：

| rank0项目 | 原记录 | opt记录 | 解读 |
|---|---:|---:|---|
| attention kernel累计 / calls | 7.751s / 10570 | 5.465s / 10570 | kernel_unified_attention变为_paged_attn_fwd，累计减少2.286s |
| attention kernel平均 | 733.327us | 517.019us | 降低29.50% |
| fused_moe_kernel平均 / calls | 235.194us / 84560 | 236.591us / 84440 | +0.59%，无明显收益 |
| vllm::moe_forward_shared CUDA total | 5.755s | 5.755s | 共享专家没有收益 |
| vllm::unified_attention_with_output Self CUDA | 2.890s | 1.429s | 框架范围标记仍保留原名字，不代表底层仍调用vLLM kernel |

rank1同样为attention733.523→516.979us，MoE235.319→236.591us。
rank1 all-reduce约27.594→44.736us，说明通信和profile扰动也存在；
不从汇总百分比签发每项变更的精确端到端贡献。graph、框架scope和子kernel
有包含关系，不能将它们的CUDA时长相加。当前profiling关联4K/n64场景，
不视作16K/32K的完整trace归因，也未加载约1GB压缩的完整trace。

准确调用链：既有Plugin AttentionFLBackend → 公共
`flaggems_vllm.flash_attn_varlen_func` → 库内新增THead BF16/layout/feature守卫 →
`flash_attn_varlen_bf16_paged` → 库已有`ops/triton_unified_attention.py::_paged_attn_fwd`。
复用的是既有私有Triton计算kernel，未新写attention数学内核，也未调用库的
`triton_unified_attention`公共wrapper或vLLM的kernel。
新增helper只做元信息守卫、out复用/必要分配、设备上下文和launch配置，
不做Torch gather/transpose/精度转换或额外计算kernel；GQA逻辑打包在既有kernel内部。
decode BM16/BN32、prefill/mixed BM32/BN64、warps4/stages2为本轮实测配置。

需要区分比较基线：原vLLM unified本身已有GQA共享KV，不能把相对nomm的收益说成
新增GQA带来的收益；源码差别包括直接3D序列索引省去二分定位、较精简的计算路径、
当前形状的tile配置。此前退化的通用Flash按head处理，复用GQA内核才同时消除了
共享KV重复读取与mixed单query的大M浪费。逐项贡献尚未做控制消融。
MoE仍走Plugin两GEMM staged流程并接收原config，align/topk/activation/sum不变；
完整fused_experts的SiLU/direct-sum/out等优化没有在当前PPU流程自动生效，
不能将库来源替换本身宣称为MoE优化。后续MoE需围绕实际热点另做测量与优化。

profile摘要rank0旧/新SHA-256分别
`f8263a69247d22b9fb0a476b2bd82b9042bad14c2ba3778449f71ec326966dda`、
`baf5526c4c69d514ee431cafd5ccfc048c28bf17cf43c9e7b91aa6e59c1ea350`；
rank1分别`55731de2ea0f73a8007873a7c476e2322c896a84273b4e796030c12b1acde350`、
`11c8b229c65fd2d6bb4c4a5df514eb23f0077f3e3dbf766b9d99ca0c21cb8376`。

## 2026-10-12：MoE 与 Flash 分别的收益复核

本次为只读历史结果分析，没有执行新消融、修改源码或重启服务。
PPU-13 / minicpmV4.7-35B 身份和 /mnt 映射仍一致。当前 Plugin270 个运行
Python 文件与本轮 final-source.json 完全相同；库345个文件仅
ops/triton_unified_attention.py 增加后续 int64 地址修复，其余优化未变。

### 已直接测得的区别

重新读取四份 profiler_out_{0,1}.txt，其 SHA 与上一节完全相同。
4K/n64 profiling 的 kernel 平均值如下；这是 CUDA kernel 指标，不是单独
开启某项优化的整模吞吐。图/框架 scope 与子 kernel 不可相加。

| 算子 / rank | 原平均 μs | 优化平均 μs | 耗时变化 |
| --- | ---: | ---: | ---: |
| Attention / 0 | 733.327 | 517.019 | -29.497%（1.418倍） |
| Attention / 1 | 733.523 | 516.979 | -29.521%（1.419倍） |
| fused_moe / 0 | 235.194 | 236.591 | +0.594% |
| fused_moe / 1 | 235.319 | 236.591 | +0.541% |

Attention 两轮每 rank 均10570次。MoE 次数84560→84440，故以单次平均比较，
不能用总时长或占比替代。rank0 shared expert CUDA total 仍5.755s，
rank1 5.530→5.540s，同样无明显收益。MoE GPU 占比增大包含 Attention
加速后总量变化，不能视为 MoE 性能改善或严重回归。

源码确认当前仍按原 Plugin 的 CUDA-only guard 选择完整 fused_experts；
PPU 使用原两段 GEMM 路径，经 CachedOp 调用库的
invoke_fused_moe_triton_kernel。完整 MoE 的直接 out 协议不在该实际路径中。
早期 moe-out-probe.json 的独立 graph 加速为 M1 1.03794倍、M8 1.00824倍、
M32/64 1.00371/1.00388倍、M1024/4096 1.00489/1.00623倍，
不能给当前整模计入这些收益。GEMM1 早期 tile 候选已撤回。

Flash 独立 gqa-mixed-probe.json 中，通用 FlagGems-vllm Flash→最终 GQA
helper 的 mixed16K/32K 中位数83.282→26.629ms、174.471→62.179ms，
分别3.128/2.806倍；decode4K/16K/32K 为2.253/2.248/2.222倍。
这里的基线是曾退化的通用 Flash，与上表原 vLLM unified 的比较口径不同。
原 vLLM unified 已有 GQA，当前相对它的收益不能归因于“首次支持 GQA”。

### 最新仍可访问的整模结果

用户结果目录现为 benchmark_results/MiniCPM-V-4.7-35B-A3B-base 与
benchmark_results/MiniCPM-V-4.7-35B-A3B-opt；前述 nomm 名称目录当前不存在。
base 文件时间戳20261005_091423，opt 为20261012_092552。逐文件检查三轮均
128成功，输入总数=输入长度×128，输出总数=1024×128，三轮去首轮重算：

| 输入/输出，c64/n128 | base 输出 tok/s | opt 输出 tok/s | 相对提升 |
| --- | ---: | ---: | ---: |
| 4096/1024 | 1381.260 | 1538.735 | 11.401% |
| 16384/1024 | 485.055 | 597.050 | 23.089% |
| 32768/1024 | 196.815 | 270.750 | 37.566% |

这属于跨日期历史参照；旧 base 没有完整部署/源码绑定，不声明严格受控 A/B。
此前原生9轮报告仍可读取，SHA仍为d3dd577e2f34d6f178627b236645fdf670cf3d25371d16b7d83dbf005714d68a。
新旧 CSV 基线不同，不能将上一节1354.66等数字混入此次已访问文件的计算。

现有证据支持：Flash有明确 kernel 加速，MoE 调用来源替换没有表现出明显
kernel 加速；整体收益主要由 Flash 改进解释，这是基于路径和 profiling 的推断。
还没有同配置“双方原始、仅MoE替换、仅Flash优化、两者启用”的四组消融，
因此不能精确报告每项独立带来的整模百分比，不能简单相加或将 MoE 写成精确0%。
原始路径：profile/vllm_profile/、profile/vllm_profile_opt/，
04-runs/e2e-opt-20261009-2245/moe-out-probe.json 和
04-runs/direct-flaggems-vllm-20261010-1223/gqa-mixed-probe.json，
全部位于批准根 /mnt/nfs/users/jinghao/MiniCPMV4.7-35B。
