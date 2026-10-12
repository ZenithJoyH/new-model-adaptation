# 003：mx-59 三场景端到端优化

2026-10-09–10，在 mx-59 现有 `qwen3.6-35B` 容器中完成用户指定的 MoE 接入与端到端优化。
实际修改已安装 Plugin、FlagGems-vLLM，最终三个场景原生校验通过，正常生产启动脚本已运行。
本轮是适配阶段的局部优化诊断；正式整模精度、镜像新容器验收未执行，不标记框架阶段或
`optimized` 完成。此前迁移和完整入口对照见 [001](001-mx59-moe-flaggems-vllm.md)、
[002](002-full-vs-staged-moe.md)，逐文件设计见[代码审查](../environment/003-optimization-code-review.md)。

## 范围与冻结测试

- 唯一 Host 为 mx-59；Host/container 工作根均为 `/public-flash/jinghao/qwen3.6-35B`，
  同路径 RW bind，stat `53:7692957`。容器 ID
  `6821737fcd966f3026820b1a5d6122125bc5faa0750313771b1a052ce7129867`，保持运行。
- C550 GPU4、5，BF16 TP2，模型 `/public-flash/models/Qwen3.6-35B-A3B`，端口8010，
  保留既有客户端名称 `qwen36-35B-nogdn`；该名称不代表新服务禁用了 GDN。
- 按用户指定 `test/perf_test/vllm_perf.py`：输入4096/16384/65536、输出1024、
  并发64、每场景128请求；基线与最终各3轮，均剔除第一轮，其余两轮取原生均值。
  固定随机长度、ignore-EOS、prefix长度0、前缀缓存关闭，无 profiler，max_model_len262144。
  不缩短长上下文，不用正常服务缓存命中收益替代对照结果。
- 显式性能 Skill 操作为 `full-suite`；bundle SHA256
  `3c46ddd2c4d73b11ca324b230d48429c3d4a40d0c82f56f5b27237d8e81bc9ff`。
  旧 benchmark 保持原样，冻结原生 runner 位于 `03-acceptance/e2e-opt-20261009/`。
  GPU0用于独立诊断；整机并非独占，不将结果扩展到其他硬件/版本。

## 最终端到端结果

输出吞吐单位 tok/s；TTFT、TPOT 单位 ms。所有基线与最终轮次各128成功、0失败，
输入和输出 token 数匹配计划；两个原生 `validate_report` 均返回零错误。

| 输入 tokens | 基线吞吐 | 优化吞吐 | 提升 | TTFT 前→后 | TPOT 前→后 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4096 | 560.05 | 679.54 | +21.3% | 9256.31 → 5472.16 | 103.89 → 88.62 |
| 16384 | 239.44 | 395.51 | +65.2% | 39539.82 → 21471.88 | 222.46 → 139.51 |
| 65536 | 72.00 | 107.29 | +49.0% | 522914.18 → 297502.31 | 256.01 → 241.59 |

结果由相同负载下的算子、路径选择和调度共同产生，不能将总收益全部归因于某一内核。
按指定三场景的输出吞吐选择方案，并非所有尾延迟指标改善：P99 ITL（ms）4K
284.04→538.39，16K1442.86→658.82，64K484.36→1148.93。该现象与较大prefill chunk和decode
共享调度的取舍一致，但未独立归因于某个改动。严格P99间隔SLO需要另行冻结目标权重。

首轮冷路径完整保留但排除：最终4K首轮372.30 tok/s、16K首轮394.26、64K首轮94.35；
不据此宣称冷启动更快。最终测试期间未观察到请求失败或 KV 抢占。

基线原服务 PID120534，显存预算0.8、batch2048、GDN prefill/decode黑名单；
此前 MoE 代码迁移尚未通过服务重启加载。最终对照 PID493142，显存预算0.9、
batch8192、GDN路径启用、无全局strict/黑名单；两者均 FULL_AND_PIECEWISE/capture64。
因此这是用户现有运行服务到最终方案的整体对照。

## 算子与 Plugin 改动

直接修改 `/workspace/vllm-plugin-FL` 和 `/workspace/FlagGems-vllm` 的安装源码。
本轮15文件增量，保留此前 MoE/GDN/attention dirty 修改；逐文件备份、before/after SHA、
原HEAD/status/diff/untracked身份在 `01-environment/e2e-opt-20261009/` 和
`02-issues/e2e-opt-20261009/product-payload-v3.json`，未通过 PYTHONPATH 切换来源。
FlagGems、vLLM、权重及旧参考保持原状态；没有提交、推送或PR。
完整库入口为 `fused_experts_impl`；使用caller buffer时由
`fused_experts_with_workspace` 委托该入口，保持完整MoE流程与调用方buffer所有权。

| 改动 | 实际职责与收益边界 |
| --- | --- |
| 完整 MoE 入口 | MetaX 非量化 FP16/BF16 SiLU、无LoRA/expert-map，通过已安装库完整入口执行。内部仍有 align、两GEMM、activation、sum 等多个GPU kernel；完整函数名不意味着单个launch或必然更快。其他路径沿用既有选择。 |
| MoE tile | 对 BF16 E256、topk8、TP2权重 W1[256,512,2048]/W2[256,2048,256] 的实测 shape 设置有界配置；M9–1024保留收益，M4096–16384使用安全共享内存tile。M1025–4095与更大未测范围不改；M2048退化候选撤回。 |
| Caller workspace/output | 库新增可选caller-buffer ABI；Plugin交换两个modular workspace角色，复用调用方output，消除重复分配和末尾copy。计算前验证size/dtype/device/stride/overlap，多chunk禁止危险alias；旧库和不支持布局在计算前选择旧outplace路径，失败后不重算。 |
| Paged GDN decode | 库内纯Triton融合门控、QK归一化、V-major页状态更新，支持packed projection的strided views并直接写caller out。限定单token、唯一活跃页索引、支持的dtype/layout；null/padding不更新。Plugin保留原生packed类流程，仅在既有dispatch点接线，stateful错误严格传播。 |
| GDN prefill metadata | WY新增可选caller chunk_indices并由既有MetaX fwd转发，修复cu对象不变但metadata变化时identity cache复用旧descriptor的问题；未复制prefill算法或改计算kernel。 |
| Flash Attention | 有限tile/warps/splits诊断未得到稳定改进；保留原生产配置和既有修复。 |

MoE有限tile搜索114组FP32对照通过，复验M64约609→459μs、M512约986→797μs；
这些是诊断数值，端到端结论以上表为准。实际安装原生benchmark的caller-buffer对照
使用同一新tile：graph M64 0.541626→0.514311ms、M512 0.694318→0.659016ms。
GDN相对当前原生packed路径的graph M64仅0.101012→0.099603ms，小batch/eager
没有普遍收益；相对旧adapter的倍数不冒充旧运行服务收益。

## 调度、图模式和缓存

同源码、mem0.8下16K有限筛选各2轮剔除首轮：batch2048为239.04tok/s、
4096为365.78、8192为395.31；均128成功/0失败且原生校验通过。规则为相差≤1%
优先较小batch，实测选择8192；首轮冷开销保留，不进行无界盲调。
mem0.8时KV随batch增大从1,464,677降至1,357,531tokens。基线64K约21active/43waiting、
KV98.5%；最终mem0.9恢复容量到2,066,984tokens，约30active/34waiting，缓解排队。
最终三场景完整对照验证该组合收益；未通过改写vLLM调度源码实现。

按profile优先尝试FULL；backend报告GDN仅支持UNIFORM_BATCH，实际自动调整为
FULL_AND_PIECEWISE。两个TP rank均完成11个piecewise与11个decode-full capture；
后续固定此模式，不声明pure FULL通过。实际attention page1056；独立FA诊断page1024
仅为代表布局，不能替代服务布局证据。

复核发现库SQL/generated cache使用FLAGGEMS_CACHE_DIR，而非XDG。原默认
`/root/.flagdnn`保留，以SQLite只读backup迁入批准根并验证8表行数/内容与integrity；
新服务显式使用 `06-cache/flaggems-service-v6`。该配置下重新通过196项回归与3项
大prefill回归。所有新缓存/TMP指向批准根，未删除旧缓存或清理共享环境。

## 验证与失败保留

- 实际安装路径196项，无skip：Plugin unit26、functional23，库functional147；
  修正缓存配置后再次196通过。包含独立FP32、caller-owned buffer、两次变输入graph replay、
  输出/状态identity、null页、padding字节、非法alias和错误传播。补充4096/8192/mixed
  `[8129]+63*[1]`三个大prefill FP32/eager/replay通过，缓存修正后再次通过。
- 两个TP rank的真实torch trace各命中400次MoE sum、800次MoE GEMM、150次paged GDN，
  以及MetaX chunk prefill和FGV flash splitkv。64decode、8prefill请求全部成功；
  profiler冷路径明显较慢，已停止采集，采集耗时不计入性能对照。
- 原服务/新服务8个短样例均HTTP成功，5个逐字一致，3个措辞变化经检查符合请求；
  序列续写两侧均max128截断，不称完整答案。这些检查不替代正式整模精度。
- 旧M4096共享内存98304>65536与旧prefill变metadata replay失败保留；实际安装后
  `07-bugs/e2e-opt-20261009/result.json`的两个最小复现通过。
- GDN初版能力查询遗漏可选cu默认值，矩阵40通过/5失败；修正后45通过，扩展125通过。
  prefill旧FP32回归3通过/2失败；descriptor转发后5通过，错误回执未改写。
- FA N32/W1约慢5倍，N64/W1共享内存73728超限；后续18组输出/LSE/replay通过，
  64K split16约6648μs、split32约6670μs，无稳定收益，保留原调度。
- 原生graph iter500展开过大，精确停止本任务PID215888；保留中断和失败回执，
  改用原生默认graph iter20/operator iter500后两个benchmark通过，源码未变。
- FlagGems origin/master fetch120s超时，仅停止本任务Git helpers；安装HEAD未变。
  本机核实上游7599dd13与安装c6f46cc9差1431文件，本轮不混入大范围版本升级，
  不声称FlagGems同步或新算子选型完成。库引用的optimization.md/deep_opt.md缺失，
  已搜索并记录，不声称完整G0–G7通过。
- cache/launcher审查时只精确停止尚在等待且无子进程的本任务controllers347159、425769，
  原回执均保留；未停止容器或无关服务。最终native/来源通过后才重启本任务模型服务。
- v7 launcher的端口bind预检查未设SO_REUSEADDR，在旧服务退出后误报Address in use；
  保留finish-v7失败回执及launcher-process.log。v8在独立临时端口复现TIME_WAIT误报，
  增加SO_REUSEADDR并验证通过。v8实际服务ready后，前缀缓存断言失败：安装版vLLM对
  hybrid默认关闭，而Qwen3.5支持显式align模式。v9明确启用prefix/align并重新验证；
  端口检查移至外部收尾流程，最终launcher只含必要环境与exec。两次失败回执保留，
  未改产品源码或原性能回执。

## 最终服务与启动脚本

最终服务API PID **532870**，由容器内部
`/opt/flagos/qwen3.6-35b/start-model.sh`实际启动；Host/container可用副本为
`/public-flash/jinghao/qwen3.6-35B/start-model.sh`，两者SHA256相同：
`b61577129c0c2683a3fe99ae37de3e3de9a1c807f16926c5092e7ae0dfce7adb`。
源码与内部脚本处于容器root filesystem；Host bind副本不作为镜像包含证明。
未请求制作新镜像，fresh-image验证仍待执行；权重及运行缓存依赖已声明外部mount。

最终GPU4/5、BF16 TP2、batch8192、mem0.9、上下文262144、FULL_AND_PIECEWISE/capture64；
无PYTHONPATH、全局strict、黑名单或profiler。模型/Tokenizer为内置类型且无auto_map，
删除无用trust-remote-code参数。端口/名称保留原客户端约定；缓存/TMP环境用于批准根写入，
bytecode关闭保护只读源码，no-enable-log-requests避免记录请求内容，其余必要设置为后端与
FGV attention选择。日志为 `04-runs/service.log`，不把诊断脚本放入启动流程。

安装版vLLM的hybrid默认值关闭prefix；正常生产脚本显式启用前缀缓存和mamba align模式。
该vLLM版本仍将hybrid prefix标为experimental；本轮只验证下述受限场景，不扩大支持声明。
每个4K/16K/64K长度10并发、共30个长请求及2次相同prefix功能检查通过；
重复输出一致，prefix_cache_hits从0增至3168。长输入按token IDs构建并核实usage长度，
没有缩短输入。这些是功能诊断，非追加性能基准或正式精度。

8个正常短例均HTTP成功，6个stop、2个length；数列续写和首都问题均达到max128，
不能将HTTP成功当作完整回答。首都问题补充诊断保留原截断回执，并用max512确认最终
答案Paris（`production-answer-v10/`）；这不改变原固定测试或正式精度结论。
最终生产KV容量2,042,667tokens（7.79x），与关闭prefix的性能服务2,066,984不同。
最终服务PID/startticks/cmd、四组件HEAD/status/diff/untracked和15个修改后SHA再次一致。
上述30个长输入末尾均询问13*17，已核查全部答案为221；空think标签不影响数值。
最终健康检查HTTP200、无运行/等待请求；服务保持运行。

## 原生证据索引

以下相对工作根；原始产物、补丁、完整日志均留在远端，不纳入本地模型目录。

| 内容 | 回执/目录 |
| --- | --- |
| 基线 | `04-runs/e2e-opt-20261009/baseline/native/qwen36-35B-nogdn/20261009_222139_970834/benchmark-result.json` |
| 最终三场景 | `04-runs/e2e-opt-20261009/final-performance-v6/native/qwen36-35B-nogdn/20261010_030532_836166/benchmark-result.json` |
| 比较与launcher | `04-runs/e2e-opt-20261009/service-production-v9/comparison.json`、`04-runs/e2e-opt-20261009/service-production-v9/launcher.json` |
| 最终收尾与正常服务 | `04-runs/e2e-opt-20261009/finish-v9/progress.json`、`04-runs/e2e-opt-20261009/production-check-v9/` |
| 截断补查 | `04-runs/e2e-opt-20261009/production-answer-v10/result.json`，保留原128输出与512补查 |
| 安装与回归 | `01-environment/e2e-opt-20261009/product-applied-v3.json`、`04-runs/e2e-opt-20261009/installed-validation-v4.json`、`04-runs/e2e-opt-20261009/cache-regression-v6/`、`04-runs/e2e-opt-20261009/gdn-large-regression-v6/` |
| trace/筛选 | `04-runs/e2e-opt-20261009/service-full-v4-profile-checkpoint/`、`04-runs/e2e-opt-20261009/service-full-v4/profile/`、`04-runs/e2e-opt-20261009/tune-batches-v6/selection.json`、`04-runs/e2e-opt-20261009/screen-batch-4096-v6/`、`04-runs/e2e-opt-20261009/screen-batch-8192-v6/` |
| 原始失败 | `04-runs/e2e-opt-20261009/moe-confirm/`、`04-runs/e2e-opt-20261009/gdn-matrix/`、`04-runs/e2e-opt-20261009/gdn-prefill-regression/`、`04-runs/e2e-opt-20261009/attn-tiles/`、`04-runs/e2e-opt-20261009/installed-regression-v3/bench-interruption.json` |

原生回执SHA256：基线 `d8560cc52a19b5beb364a9105aba25296207c69cc3cf217a2b2154db4c86aeb7`；
最终 `118e5f5c8df209d9adefb8bd53d3dbae0799cc88554e1cc4bd6a24b243e08894`。整模正式精度、跨平台真实设备、
量化/LoRA数值、多token/speculative/KDA、反向训练与fresh-image未验证。
Framework五阶段继续not_started；局部结果不构成完整适配验收。

本地 `./scripts/audit-workspace` 返回12项其他模型的既有profile revision错误、78项历史
需复核问题，本模型目录没有被报错；未修改无关模型。该检查不执行远端验证，不称全仓audit通过。
