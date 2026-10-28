# FlagOS 切换 PPU Flash Attention 后的三场景性能

2026-10-27，PPU-01 / `minicpm-ocr` 完整重跑用户指定 portable v1.1 三场景。视觉 PPU FA2、语言 vendor.thead FA3 已生效；吞吐中位数为 **7.13 / 9.86 / 10.72 页每分钟**，相对切换前完整基线分别下降约 **1.0% / 5.3% / 19.8%**，未观察到端到端提速。三个场景最后两轮均稳定；批量首轮、加压全部轮次未达到包内时限目标，`all_operational_pass=false`。

计时 168 页次、3483 次区域请求，预热 56 页次、1161 次请求，合计 4644 次请求全部成功且无截断。固定 32 页质量子集 Overall **97.5632**，与此前原生环境评分相同，未发现明显输出缩短。此为应用微基准，不签发正式 framework 验收，不变更 `framework.yml`。

## 冻结配置与方法

- 容器 ID `7bad43aab32e6386c34c9e46ec602ab4df955b0198997503886043bed055c6c3`；Host/container 批准根均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR`，可写绑定 dev:inode `41:5457325353` 已核对。
- 保留 PPU5/8015 正常服务及原 8011/9999、原生 8014；在空闲物理 PPU6 / `127.0.0.1:8016` 启动临时测试实例。复制 8015 实际 argv/env，只更换设备、绑定地址/端口、短 TMPDIR，并按包要求设置 `--no-enable-prefix-caching --mm-processor-cache-gb 0`。没有更改现有启动脚本或产品源码，没有 PYTHONPATH 覆盖。
- 模型 `models/merge_rl_mergedp1_7140_hf5_4x`，9 个文件大小与 SHA 和 manifest 一致；checkpoint 身份 `7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`。
- 单卡 PPU-ZW810E 96 GiB、BF16、TP1、上下文 262144、max_num_seqs 64、显存比例 0.55、image/video 4/1、批次 token 预算 8192、FULL_AND_PIECEWISE。实际捕获 mixed PIECEWISE 与 decode FULL。
- 沿用 [Flash Attention 功能验证](004-ppu-flash-attention.md) 的组件与四个 Plugin 文件；vLLM 0.24.0+empty、Torch 2.10.0、flash-attn 2.7.4.post1、flash_attn_3 3.0.0b1。Plugin、FlagGems、FlagGems-vllm、vLLM checkout 的 HEAD/diff/status 和实际 vLLM 安装 Python 文件集合前后不变。
- 实际图像请求后日志出现 `Using installed T-Head flash_attn FA2 for MMEncoderAttention`；语言路由日志为 `Op 'attention_backend' using 'vendor.thead'`。这轮具有视觉真实调用证据，不能只凭 FLASH_ATTN 标签判断。
- 同一 report-2 归档 SHA `55f5422c86a95c1d91a7e67d765c5bb4b5caabc5dca3d1fc03dee2dfbb35e152`；772 文件全量校验通过。checksums SHA `6a34a580e58a109a95bcaae3c9669576503829f4741c95f7fa9b71dfb7c22249`，原版 bench.py SHA `2ce4b471d80cd44c484bef52ac8902874ed4b39205612ee3c72d5e532433ec12`。
- 原版完整测试：各场景一次完整预热、两轮计时，前两轮吞吐差超过 10% 时仅补一次。本次三场景均触发补轮，没有重试、重启服务或复用旧输出。CPU affinity 0–191，cgroup CPU/内存额度均为 max，不主张 CPU 独占。

## 性能与前后对比

吞吐为所有计时轮次的中位数；百分位按每轮页面完成时间的 nearest-rank 计算，不平均跨轮分位数。

| 场景 | 页面/区域并发 | 吞吐中位数 [最小,最大]（页/分钟） | 逐轮页面 P50（秒） | 逐轮页面 P90（秒） | 逐轮时限内成功比例 |
|---|---|---|---|---|---|
| interactive，8 页/轮 | 1 / 4 | 7.13 [6.52,7.54] | 5.99 / 4.69 / 4.68 | 28.04 / 28.54 / 29.03 | 100% / 100% / 100%，30 秒目标 |
| batch，24 页/轮 | 4 / 16 | 9.86 [8.53,10.76] | 18.91 / 14.24 / 14.31 | 62.39 / 51.52 / 49.78 | 87.5% / 91.7% / 91.7%，60 秒目标 |
| loaded，24 页/轮 | 8 / 32 | 10.72 [9.49,11.33] | 42.95 / 32.28 / 32.82 | 95.26 / 83.14 / 74.69 | 75.0% / 87.5% / 83.3%，60 秒目标 |

最后两轮吞吐波动分别为 5.79%、9.16%、5.67%，均满足不超过 10% 的稳定性要求。全部计时页面完整成功，但时限内成功比例至少 90% 才达到包内 operational 目标；不能将完整成功或稳定解释为全部目标通过。

| 场景 | 切换前 FlagOS | 本次 FlagOS PPU FA | 相对变化 | 此前原生环境 | 原生/本次 |
|---|---:|---:|---:|---:|---:|
| interactive | 7.21 | 7.13 | -1.0% | 27.42 | 3.84 倍 |
| batch | 10.42 | 9.86 | -5.3% | 46.67 | 4.73 倍 |
| loaded | 13.36 | 10.72 | -19.8% | 55.89 | 5.21 倍 |

以上均为页/分钟。基线选取[此前稳定的完整三场景](002-portable-v11-performance.md)，不将[最新两场景中不稳定的 batch](003-portable-v11-interactive-batch-latest.md)当作稳定基准。原版 compare.py 已验证旧包与 report-2 仅有汇总说明差异，测量代码、输入及生成参数相同。

三次测量使用 PPU3、PPU6、PPU5，时间不同；原生 vLLM 为 0.23，FlagOS 为 0.24。这里是应用层观察，未做同卡交替控制或 CPU/GPU trace，不能将下降全部归因于单个 FA kernel，也不能证明剩余差距来自某个 GDN/GEMM。可确认这次视觉与语言后端切换没有消除性能 gap；算子级归因仍需独立 profiling。此前原生视觉日志仅证明 FLASH_ATTN 选择标签，缺少当轮视觉 FA2 独立调用证据，该限制继续保留。

页面时间包含 worker 接纳后的区域排队、读图/编码、HTTP、服务处理、后处理与 Markdown 落盘；不含初始页面接纳队列、PDF 渲染/布局/裁剪、服务启动或评分。首次启动 profiling/warmup 141.23 秒；各场景完整预热 P90 为 106.99 / 127.55 / 106.87 秒，均保留且不混入计时结果。非流式请求未测 TTFT、TPOT、P99。

## 质量与审计

评分严格选 interactive-r1 的 8 页及 batch-r1 的 24 页，逐文件 SHA 绑定原始输出，与包内官方 GT 的 32 页一一对应。复用既有 CPU OmniDocBench v1.6 / TeX Live 环境，评分器源码前后 SHA 一致；评分在全部计时结束后执行，没有追加推理。

| 指标 | 本次结果 |
|---|---:|
| Overall | 97.5632326065 |
| Text Edit_dist（越低越好） | 0.0195816284 |
| Formula CDM | 97.2792517007 |
| Table TEDS | 97.3686089638 |
| Table TEDS structure only | 99.3481203790 |
| Reading order Edit_dist（越低越好） | 0.1427165127 |

32 页匹配无回退，66 个 CDM、22 个 TEDS 样本无 timeout/error/exception。包未规定子集质量阈值，`quality_pass=null`，不代替全量精度验收。Markdown 88103 字符，原生 88090、切换前完整基线 88115；与原生逐字相同 24/32 页、最小字符比 0.99867，与切换前相同 25/32 页、最小字符比 0.99780，未见明显缩短。综合分与原生相同不表示所有页面逐字相同。

独立审计重建每页 Markdown，核对请求/页面覆盖和唯一性、响应内容、usage、finish_reason、成功/截断判定，重算吞吐、P50/P90、SLO 和补轮/稳定规则，全部与原始报告一致。

## 证据与服务保留

以下均在 PPU-01 批准根 `/mnt/nfs/users/jinghao/MiniCPM-OCR` 下：

- 工具、包与计划：`03-acceptance/portable-v11-ppu-flash-20261027/`；控制器 `03-acceptance/run_portable_ppu_flash_20261027.py`。
- 本轮输出：`04-runs/portable-v11-ppu-flash-20261027/`；逐页/逐请求记录为 `benchmark/<scenario>-warmup/` 和 `benchmark/<scenario>-rN/`。
- 原始报告 `benchmark/benchmark-result.json` SHA `1aae5d73a3fb0bd6dd6a4444e4d08da170637e49558f77b5162a4c6ab7a3426e`；`artifact-audit.json` SHA `4491c130cc403a0d0413f5804b26e80ee4b49df145ea9f9d5b804d5727a02ac6`。
- 质量 `quality/quality-result.json` SHA `fcfaabf9395b988ae961590a4d2c43e902c29e204cb482629a90b259e2967a3d`，`quality-audit.json` SHA `484757e512a8f55253b20b0b901e9d97206a3a5091454694520a92a89880eb15`。质量引用写入派生 `benchmark/benchmark-with-quality.json`，原始报告未改写。
- 对比 `comparison-summary.json`、原版工具输出 `comparison-all.md`；身份见 `service-evidence.json`、`checkpoint-verification.json`、`component-before/after.json`、`sources-before/after.json`、`attention-runtime-verification.json`。
- `completion.json` SHA `5dfb08ef1c6f6e5e6c3e8ce55a03be7a7cae2fb3d8f89f68cff729c6869fe5b7`，绑定性能、质量、源码、服务与清理证据。

临时 API PID 741715 正常 SIGTERM 退出、返回码 0，8016 已关闭。原 8011/9999/8015 的 PID、start ticks、cmdline SHA 前后及最终核对均未变；8011/9999/8014/8015 health 均 HTTP 200，见 `final-service-health.json`。两个适配容器均持续 running、restart count=0。PPU5/8015 的正常 FA 服务仍保留。没有修改源码、打包镜像、commit/push/PR 或更新正式阶段状态。

本次五份本地记录的链接与空白检查通过。`./scripts/audit-workspace` 仍返回 3 个错误、14 条复核提示，来自既有 XingChen4 链接、GLM 部署指纹及其他模型历史证据，无本次 MiniCPM-OCR 记录错误；未修改无关文件。远端性能与质量结论来自上述原生产物审计。
