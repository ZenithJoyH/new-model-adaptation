# 跨平台轻量整页 OCR 性能基准 v1.1：H100-149

## 范围与协议

用户选择固定 32 页、三个场景、每场景两轮的可复用比较方案，并要求在 H100-149 首跑，
保留当前 8012 与人工启动脚本。本次属于应用场景微基准，不是正式框架性能验收；
不补跑未选择的适配阶段，不更新 framework.yml 状态。

已读取远程操作入口、性能 Skill/项目契约、执行记录及当前 profile。
所选场景为完整应用 suite；性能 Skill 指纹为
`3c46ddd2c4d73b11ca324b230d48429c3d4a40d0c82f56f5b27237d8e81bc9ff`。
仓库原生 perf_common 的 INPUT/OUTPUT case 生成随机文本，无法表达本次完整页面及区域调度；
按用户明确要求新增独立的应用 benchmark，不冒充 `adaptation-native-performance/v1` 正式回执。

维护代码位于 `test/ocr_perf/`：bench.py（标准库 HTTP 客户端、调度、计时和统计）、
build_bundle.py（一次性构建冻结数据包）、compare.py（相同包哈希比较）、
test_bench.py（模拟服务集成测试）和 README.md。未修改 vLLM、Plugin 或算子组件。

固定 32 页计时集采用 2 种语言 × 4 种正文/公式/表格组合 × 4 个历史输出 token 负载分位，
另保留 2 页不参与基准的诊断数据。使用已有缓存布局和裁剪，不重跑布局检测。
所有页面保留完整区域，按历史 HTTP trace 的 PNG 哈希、prompt、max_tokens 逐一匹配请求。
历史未被 vLLM 0.24 OpenAPI 声明的 no_repeat_ngram_size 不进入 v1 请求协议，
不声称各后端一致执行这个字段；其余逐区域参数固定。

| 场景 | 每轮页面 | 每轮区域请求 | 页面并发 | 全局区域上限 | 初始 P90 目标 |
|---|---:|---:|---:|---:|---:|
| interactive | 8 | 143 | 1 | 4 | 30 秒 |
| batch | 24 | 509 | 4 | 16 | 60 秒 |
| loaded | 24 | 509 | 8 | 32 | 60 秒 |

基本规模 112 页次、2322 次计时请求。每场景以同一批页面和并发完整重放一次作不计时预热，
共 56 个预热页次、1161 次预热请求；基本调用总数为 3483。
两轮成功页吞吐 max/min > 1.10 时仅补测该场景一轮，原始轮次全部保留；
最终两轮仍超 10% 则标记不稳定，不继续补测或宣称稳定排名。
以成功页/分钟、逐页 P50/P90、时限内完整成功页面比例为主；失败/空输出/截断单列。
固定并发闭环，页面延迟从 worker 接纳开始至 Markdown 写入完成，含区域排队和 HTTP。
尚未接纳页面的客户端队列等待不含在单页延迟内；不能据此宣称固定到达率下的在线容量。
30/60 秒为项目初始目标，不是行业通用标准；小样本不报告 P99 或统计等价结论。

## 冻结输入和部署

批准远端根为 `/public/flagos/jinghao/MiniCPM-OCR/flagos`，下文记为 R。
现场验证容器 `minicpm-ocr-flagos-public` 的 `/public:/public` 为 RW，容器 ID 为
`7b125058368e142f4010df941e7020c3b26874a6552ec2a862a3286f9a6286f5`。
CPU 评分容器 `minicpm-ocr-eval8012-20261023` 仅把 R 映射为同路径 RW，单独核实映射。

- 冻结包：`R/06-cache/minicpm-ocr-portable-v1.1.tar.gz`，32,735,715 字节。
- 本机交付：`/private/tmp/minicpm-ocr-portable-v1.1.tar.gz`，两端生成的 SHA256 相同。
- 包 SHA256：`c09ba314d45a9817c992584afee8bc5712dd8a4501b8d0f2ecd1ea2451368084`。
- 包内 checksums.json SHA256：`ed1e5132f12d3e3754032a1d0e5e4c95e59a8c9476b996d889125511942a4184`。
- checkpoint 文件集合的规范化身份：`7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`。
- 官方 GT 原文件 SHA256：`a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496`。
- 工具/控制记录：`R/03-acceptance/ocr-portable-v1.1-20261024/`。
- 最终试跑目标：`R/04-runs/ocr-portable-v1.1-h100-20261024/`。

独立测试服务使用空闲 GPU4、端口 8013、BF16、FULL_AND_PIECEWISE，
其余模型、262144 上下文、64 max-num-seqs、0.55 显存预算及 TORCH_SDPA 与原 8012 一致。
独立命令增加 `--no-enable-prefix-caching --mm-processor-cache-gb 0`，不改人工 launcher。
结束时只停止任务新建的性能进程组，适配容器与 8012 保留。

## 实现验证与保留问题

本机三个模拟 HTTP 集成测试通过，覆盖 503 不自动重试、空输出/截断计失败、
完整样本分母、文件哈希损坏拒绝及完整场景预热先于计时执行。构建时 34 页用原 HTTP 响应重新后处理，
Markdown 与历史原生结果逐字相同。

首次独立实例启动失败，尚未发送压测请求：长 TMPDIR 加 UUID 使 ZMQ IPC 路径超过 107 字节。
原始失败保留在 `R/04-runs/ocr-portable-h100-20261024/`；
仅将本任务临时目录缩短至 `R/05-tmp/p24` 后，用新 run `-r2` 重试。
没有修改推理组件、启动脚本或现有服务。

v1.0 初次完整试跑保留在 `R/04-runs/ocr-portable-h100-20261024-r2/`。
两页预热不足，交互前两轮吞吐为 6.58、13.46 页/分钟，批量前两轮为 16.71、22.83 页/分钟。
因此修订为 v1.1 的完整场景预热；页面、请求及生成参数未改。v1.0 结果不与 v1.1 混排。
v1.1 启动复用本任务生成的编译缓存，关闭的请求/前缀/多模态缓存保持关闭；
预热和启动均不计入正式测量。中央 CPU 评分结束后才开始新测量，避免任务互相干扰。

## 首跑结果

2026-10-24，最终验证为 `verified_complete`。三个场景均测两轮，最后两轮波动均不超过 10%，
无需补测第三轮。包含完整预热的客户端运行时间 **447.2519 秒（7 分 27 秒）**；
纯计时轮次合计约 290.27 秒，其余为预热及客户端控制开销。启动、编译和离线评分另计。

| 场景 | 两轮成功页/分钟 | 吞吐中位数 | 两轮单页 P90（秒） | 时限内成功页 |
|---|---|---:|---|---|
| interactive | 13.9503 / 14.6027 | **14.2765** | 11.6290 / 11.7299 | 100% / 100% |
| batch | 23.8571 / 23.8807 | **23.8689** | 20.0915 / 17.8649 | 100% / 100% |
| loaded | 26.9109 / 29.4934 | **28.2022** | 30.9986 / 31.4287 | 100% / 100% |

2322 个计时区域请求完整，失败 **0**、空输出 **0**、截断 **0**，112 个计时页次全部成功。
另有 1161 个预热请求，三个完整预热场景均成功且无截断。各场景均达到初始 30/60 秒目标。
最后两轮吞吐 max/min 波动分别约 4.68%、0.10%、9.60%；这是有限并发负载，不能声称测得吞吐上限。

### 同一官方标注与 CPU 评分环境的小集质量筛查

使用 interactive-r1 的 8 页和 batch-r1 的 24 页，官方 GT 共 32 页。
历史参考为此前 8012 全量运行中相同 32 页的输出，经同一原生评分器重新评分，
不是复现包提供的全量参考分数。v1.1 的 8 页 Markdown 与 v1.0 当前输出不同，
因此实际重新评分了 v1.1 全部 32 页，没有直接复用当前输出的旧分数。

| 指标 | v1.1 当前输出 | 同页历史输出 |
|---|---:|---:|
| Overall ↑ | 97.6365813638 | 97.6828492617 |
| Text Edit ↓ | 0.0196177922 | 0.0193904695 |
| Formula CDM ↑ | 96.8968537415 | 97.0129251701 |
| Table TEDS ↑ | 97.9746695699 | 97.9746695699 |
| Table TEDS-S ↑ | 99.9541809851 | 99.9541809851 |
| Reading order Edit ↓ | 0.1427165127 | 0.1427165127 |

Overall 差值为 -0.0462678979 个百分点。66 个公式 CDM、22 个表格 TEDS，
超时/错误/异常均为 0；32 页 matching 没有 quick_match 或页面超时回退。
质量筛查完成，不宣称逐字一致、统计等价或正式精度通过；小集结果不替代 1651 页精度结论。

### 保留状态与证据

GPU4/8013 仅为本任务独立实例，已按核实的进程身份停止，GPU4 显存回到 0 MiB。
原 GPU3/8012 的 PID、启动时间、argv 和 launcher 前后相同，收尾 models/health 可用。
人工脚本 SHA256 仍为 `ab1239fa7729e8d532916b8c6feb4574cc0dccc78f3aa0cc8dceccbaf2a65d32`。
容器和已安装组件文件保持，未提交或推送代码。

现场启动配置确认前缀缓存禁用、多模态处理器缓存为 0；安装的 vLLM
`renderers/base.py:667` 在这两个条件同时成立时使用每请求 UUID 标识图片，
防止跨轮复用视觉编码结果。具体分支及源文件哈希保存在 cache-policy-evidence.json。
重复请求的响应 ID 也逐项核实互不重复。

最终远端证据位于 `R/04-runs/ocr-portable-v1.1-h100-20261024/`：

- `final-verification.json`、`evidence-index.json`：完整请求/页面、评分来源、源码和服务保留复核。
- `measurement/benchmark-result.json`、`measurement/run.json`：每轮原始指标、稳定性与运行身份。
- `measurement/*/requests.jsonl`、`pages.json`、`pages/*.md`：所有响应、逐页耗时及输出。
- `service-evidence.json`、`cache-policy-evidence.json`、`service.log`：实际性能配置与缓存证据。
- `quality-summary.json`、`quality-current/result/output_quick_match_run_summary.json`：小集官方评分。
- `original-8012-before.json`、`original-8012-after.json`、`service-preservation.json`：受保护服务和脚本。

证据索引 SHA256：`e6e5d45383f945e94f1f6105c3a54f14a38ec47d97fe2727ca1dd5af14419a8d`。
这里只完成所选应用基准及小集筛查，未生成正式框架性能回执或推进优化状态。

本地 audit-workspace 复查无 MiniCPM-OCR 条目；整体仍因原有 XingChen4 链接失效退出 1，
并保留 DeepSeek-V4.1-Flash/Hy4-preview 历史记录警告。本次未修改这些无关内容。
