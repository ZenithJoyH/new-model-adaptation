# MiniMax-M3.1 / PPU-07 适配总结

## 完成结论与范围

**本次适配已完成，2026-10-08 由用户确认验收收尾。** 完成依据为已实现并验证的模型服务、用户提供且已核验的外部 GPQA 精度结果，以及三组性能结果。精度按用户指定的 **80.9%** 阈值通过；性能数据由用户接受作为本次适配结果，未另行设定或反推性能阈值。

| 范围 | 内容 |
|---|---|
| 模型 | MiniMax-M3.1，W8A8，`MiniMaxM3SparseForConditionalGeneration` |
| 权重 | `/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`，已加载 48/48 shard |
| 平台 / 主机 | T-Head PPU-ZW810E / PPU-07，TP16 |
| 容器 | `minimaxM3.1` |
| 框架 | vLLM + vllm-plugin-FL + FlagGems |
| Host / 容器工作根 | `/mnt/nfs/users/jinghao/minimaxM3.1`，历史检查确认映射至同一存储 |
| 已验证服务方案 | BF16、TP16、最大上下文 204800、最大序列数 64、`FULL_DECODE_ONLY`、API 端口 8025 |
| 启动脚本 | Host / 容器同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh`，用户自行维护和启动 |

本轮只整理本地进展，没有连接远端、重跑评测、修改服务、提交代码或打包镜像。完成范围不扩展到其他平台、模型、图模式或镜像验证。

## 整体进展

| 工作项 | 本次交付进展 | 证据与范围 |
|---|---|---|
| 模型结构与推理链路 | 已完成 | [中文模型分析](../../../../architecture-and-inference.md) |
| 平台环境和源码身份 | 已完成 | [环境分析](../environment/environment-analysis.md)及历史原生身份回执 |
| W8A8 模型适配 | 已完成 | compressed-tensors 映射、split SwiGLU-OAI MoE、PPU prefill top-k workaround；单卡数值、18+3 聚焦测试与 TP16 eager/graph 请求 |
| 图模式和基本推理 | 已完成已测方案 | decode-full 6/6 捕获与变输入 replay；固定简单题十并发 10/10；FULL / FULL_AND_PIECEWISE 限制保留 |
| 204800 上下文 | 已验证支持 | 元数据上限 204800；约 201652 prompt token 请求正确；不代表 64 条满长请求可同时驻留 |
| 多模态与乱码检查 | 已完成已测请求及 ERQA 检查 | 完整预热、图像/OCR/双图/八帧视频请求；外部 ERQA 400 题未检出 U+FFFD。红图答错保留 |
| GPQA 精度 | **通过** | strict-match **168/198 = 84.848484…% ≥ 80.9%** |
| 性能评测 | **已完成并由用户接受** | 三场景、九轮，日志、CSV、请求/token 计数及平均值已核验 |
| 服务启动脚本 | 已提供，用户自行启动 | 历史 204800 启动和请求验证已记录；用户修改版本不冒用旧脚本哈希 |
| 结果归档与本地收尾 | **已完成** | 本总结、模型总览、平台/框架索引及完成字段同步 |

本表描述本次用户验收的适配工作；原生自动化流程保留其实际回执状态，见末节。

## 精度与性能

外部 GPQA 运行于 2026-10-01：198 个唯一样本、168 正确、30 错误，零 timeout、零空响应。用户提供得分 84.84%，文件精确值为 84.848484…%，高于 80.9% 阈值约 3.95 个百分点。配置为 `temperature=1,top_p=0.95,top_k=-1,max_gen_toks=18000`、并发 32；评测器另记录 `do_sample=false`，不能仅凭该字段断言 API 实际采用 greedy。路径、哈希与提取口径见[精度记录](accuracy-external.md)。此前三轮在各自 88% 冻结阈值下的 163/198、164/198、167/198 失败结果保持原样，作为历史对照，不再阻塞本次用户确认的完成结论。

性能运行于 2026-10-05：每场景输出 1024 token、并发 64、每轮 128 请求；三轮排除第一轮，以下为后两轮平均。九轮均各 128 成功、零失败，客户端 profiler 关闭；吞吐为整个服务的汇总值。

| 输入 token | 输出吞吐 token/s | 总吞吐 token/s | 平均 TTFT 秒 | P99 TTFT 秒 | 平均 TPOT 毫秒 |
|---:|---:|---:|---:|---:|---:|
| 4096 | 113.97 | 569.83 | 10.01109 | 31.22951 | 551.12 |
| 16384 | 98.62 | 1676.63 | 63.76699 | 605.99717 | 573.25 |
| 32768 | 170.02 | 5610.64 | 188.16143 | 367.65769 | 152.47 |

完整产物位于 `/mnt/nfs/users/jinghao/minimaxM3.1/test/perf_test/benchmark_results/MiniMax-M3.1`，日志为上层 `perf.log`；文件名、SHA-256、配置与核验范围见[性能记录](performance-external.md)。32K 吞吐较高、16K 尾延迟较长是已测现象；没有同条件基线和历史资源/调度证据，未将其解释为确定的优化收益或回归。

外部 ERQA 为 **228/400 = 57.0%**，400 个唯一题号，回答和推理文本均无 U+FFFD，配置并发 64。未指定 ERQA 阈值，保留实测值。本任务另一次 32 并发、`temperature=1,top_p=0.95,top_k=20,max_tokens=32768` 专项重测为 **230/400 = 57.5%**，零请求错误、零 U+FFFD、22 题触及上限；两轮配置不同，不互相替代。

## 实现、源码与问题处理

最后已有源码审查记录：Plugin `/workspace/vllm-plugin-FL` HEAD `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加任务 diff；vLLM `/workspace/vllm` HEAD `ee0da84ab9e04ac7610e28580af62c365e898389` clean；FlagGems `/workspace/FlagGems` HEAD `6b49cff993956bff8cef495abd84f2acb6a63df6` clean。FlagGems-vllm 两处继承修改未触碰。这些是历史已核验身份，不冒充外部评测时重新采集的指纹。镜像 ID 为 `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`。

参考文件为工作根的 `flaggems-w8a8-oai.patch` 与 `vllm-plugin-fl-minimax-m31-w8a8.patch`。实现位于实际安装 Plugin 的注册、模型兼容 hook、W8A8 quantization 和 MoE dispatch 路径；未修改 vLLM 或通过 PYTHONPATH 切换组件。四个 tracked 文件、三个任务新增文件、继承文件、职责/调用方守卫和回归范围见[源码设计审查](../adaptation/README.md)。当时结论为以该 HEAD 为基准的受限 PR 候选；真正 PR 基线尚未确认，本轮未创建 PR。

| 问题 | 已验证处理与保留限制 | 详情 |
|---|---|---|
| split SwiGLU-OAI 不兼容 | 接入 Plugin 两段 INT8 路径；原 SILU 路径保留；单卡误差在冻结容差内，eager/decode-full 请求通过 | [001](../adaptation/001-w8a8-split-swiglu-oai.md) |
| compressed-tensors mapping | 模型 metadata helper 接入 loader，48/48 shard 加载通过 | [002](../adaptation/002-compressed-tensors-packed-mapping.md) |
| prefill top-k 编译断言 | 仅 PPU/topk=16 固定上游 JIT 的 K128/warps4/stages2；数值和守卫测试通过，编译器内部根因未定位 | [003](../adaptation/003-prefill-index-topk-autotune.md) |
| FULL / piecewise 图覆盖 | 当前后端及编译配置受限，采用已验证 decode-full；不声称 FULL_AND_PIECEWISE 可用 | [004](../adaptation/004-full-graph-backend-coverage.md) |
| GPQA 与预检 | 高难前十题失败保留；固定简单题预检 10/10；最终外部 GPQA 按 80.9% 阈值通过 | [005](../adaptation/005-gpqa-first10-two-errors.md)、[006](../adaptation/006-ten-concurrent-sanity-latency.md) |
| 容量和默认缓存冷启动 | 历史 100K 失败保留，后续验证 204800；按用户要求使用容器默认缓存 | [007](../adaptation/007-context-100k-capacity.md)、[008](../adaptation/008-default-cache-cold-start.md) |
| 多模态预热非法访问 | 同时排除 FlagGems `conv3d,cudnn_convolution` 后完整预热通过，不再需要 skip-mm-profiling；workaround，确切越界条件未定位 | [009](../adaptation/009-context-204800-mm-profile.md) |
| 红图误答绿色 | 五个基本多模态请求均 HTTP 200，4/5 答对；该语义错误尚未定位 | [010](../adaptation/010-red-image-color-error.md) |
| ERQA 乱码 | 原结果 381/400 含 U+FFFD；专项和外部重测未复现；未确证单一产品根因，不虚构代码修复 | [011](../adaptation/011-erqa-garbled-generation.md) |
| 参考图像补丁 | 几何/token 与 NVIDIA 对照 400/400 一致；补丁未应用，像素、资源和整模收益未验证 | [012](../adaptation/012-reference-image-preprocessing-review.md) |

## 服务脚本与交付记录

2026-10-01 历史根脚本 SHA-256 `c03db886fc93600b0ab1202bc70629ec3d66476f4382cdccb2996cbe264d3bdc` 已验证 mode 0755、Host/容器同 inode、语法、端口占用拒绝、完整多模态预热、6/6 decode 图、health 200、短题和约 201652 prompt token 长请求。证据位于工作根：

- `04-runs/service-smoke-204800-full-mm-root-20261001.json`，SHA-256 `2dc9bb269817475c90e2b7ac9c59512e811050fcf525ba2732b936af179efbdc`。
- `04-runs/context-natural-202k-full-mm-root-20261001.json`，SHA-256 `64333785c9348705e26ba74cc117c64185279bc18d52f1e58ca8c04d650cbbe6`。
- `04-runs/mm-requests-204800-full-mm-root-20261001.json`，SHA-256 `e3951305365ca93bee3ac1770c6d12255b1c9df2d232198e3135dcec2d70a2a7`。

用户随后修改脚本并自行启动；最后已有记录的 SHA-256 为 `56e745991d3dcc9878f314f56bcf42155d01c395066e713003e079a3f15c47f1`，日志位于根目录 `service.log`。本轮没有重新取脚本，该哈希不能确认当前文件仍相同。TP8 探索按用户指令在请求验证前停止，最终保持 TP16。

## 完成状态与保留限制

`model.yml.status` 和平台/框架 `project_completion.status` 均为 **complete**，来源为本轮用户验收确认。模型模板“未开始”及当前项目“未完成”的描述已修正。

原生工具字段保留历史事实：框架成熟度 `functional`；原生 acceptance 为 `in_progress`，accuracy 保留旧失败，performance/evidence/summary 尚无原生通过回执。此处 `in_progress` 表示证据链未闭合，不表示本次用户验收仍在进行，也不授权继续评测。未伪造回执、改写历史阈值、升级为 `optimized`、刷新 profile/deployment 哈希或将外部结果追溯绑定到旧 65K 服务。

以下限制作为维护备注保留，**不自动安排新适配或评测**：

- 外部结果缺少原生回执和评测当时源码/服务实例绑定；性能服务端 prefix cache 关闭状态未核验，客户端零 prefix 和脚本注释不能代替。
- 历史 profile v4 与当前 v6 存在差异，本地审计要求复核更高图模式逐级记录、安装导入和容器内交付证据；历史回执仍绑定 65K，不能冒充 204800 的完整原生绑定。
- 用户修改后的脚本日志位置、最小参数及镜像可保留性未按当前 profile 重验；未打包或验证新容器，不声明镜像交付完成。
- FULL_AND_PIECEWISE、红图语义错误、参考预处理补丁、极端多模态和满长并发容量保留上述限制；无其他平台整模兼容性结论。

复盘：有效实现沿 Plugin 已有扩展点接入，vLLM 保持只读；workaround 随上游修复按对应问题的退出条件复验。ERQA 后续定位需同时固定真实图片、生成参数、输出上限及完整样本。历史失败和未测范围继续保留，经验保持模型本地记录，未提升为跨平台通用结论。

本地检查：完成字段、证据链接、YAML/框架 schema、原有源码审查文档 SHA-256 及 `git diff --check` 均通过。`./scripts/audit-workspace --repository-only` 仍返回与本轮前一致的 12 项 profile revision 错误、78 项待复核，未新增失效链接或布局错误；没有用本地审计冒充远端验收通过。
