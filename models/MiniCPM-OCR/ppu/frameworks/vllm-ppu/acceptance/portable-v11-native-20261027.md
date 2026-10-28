# PPU 原生 vLLM：portable v1.1 三场景结果

2026-10-27，按用户指定的 `minicpm-ocr-portable-v1.1.tar.gz` 完整运行 interactive、batch、loaded 三场景。全部计时页完整成功，全部轮次 SLO 成功率 100%，无失败或截断请求，三个场景最终两轮均满足吞吐波动不超过 10% 的要求。32 页官方 GT 子集评分完成，综合分 97.5632；包未规定质量通过阈值，`quality_pass=null`。

这是测试包定义的应用微基准，不签发本 experimental profile 的正式框架精度/性能回执，不更新 `framework.yml` 或标记 `optimized`。

## 服务与输入

- Host：`PPU-01`；容器：`minicpm-ocr-ppu-native`，ID `c7761d51cd375b946bdad104c97ea8c80837e282f86edf1099e713e75b27de82`。
- 镜像：`egslingjun-registry.cn-wulanchabu.cr.aliyuncs.com/egslingjun/inference-xpu-pytorch:26.04-v2.1.0-vllm0.23.0-torch2.10-cu130-20260710`。
- Host/container 批准根均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR/ppu-native`，现场核验同一可写绑定目录。父目录只读，模型文件未修改。
- 模型：`/mnt/nfs/users/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`；服务别名 `MiniCPM-OCR-PPU-native`。
- 用户明确选择保留原 PPU4/8014 服务，在空闲 PPU5/8015 启动临时实例。临时实例复制原服务实际参数和环境，仅更换设备、绑定地址/端口，增加测试包要求的 `--mm-processor-cache-gb 0`；原服务已关闭前缀缓存。保留用户性能启动入口，不修改根级 `start-model.sh`。
- 临时实例：单张 PPU-ZW810E 96 GiB、BF16、TP=1，`FULL_AND_PIECEWISE`；运行日志记录视觉和语言注意力选择原生 `FLASH_ATTN`，未强制 `TORCH_SDPA`。后续 FlagOS 启用工作复现了 OOT 默认路由可使视觉 backend 标签与实际计算不同，因此这里的视觉日志只能证明选择，尚无本次原生视觉计算的独立 FA2 调用记录；吞吐与质量测量数字不变。MMEncoderAttention 本身始终启用，不将该差异错误归因于全局 custom_ops none。
- 生效配置：上下文 262144、`max_num_seqs=64`、`gpu_memory_utilization=0.55`、image/video 上限 4/1；默认 chunked prefill，`max_num_batched_tokens=8192`。前缀缓存关闭，MM processor cache 为 0 GiB。
- 软件：vLLM `0.23.0+v0.2.0.ppu2.1.0`、Torch `2.10.0`、Transformers `5.8.1`、Triton `3.5.0+gitcc5446cf`、flash-attn `2.7.4.post1`、flashinfer-python `0.6.8.post1+v0.1.0.ppu2.1.0`。未修改安装组件，vLLM Python 文件集合运行前后哈希一致。
- 客户端运行在服务本机容器内，CPU affinity 0–191，cgroup CPU/内存上限为 `max`，不主张宿主 CPU 独占。
- 本机下载包与复用的远端历史包逐字节哈希相同。归档 SHA-256：`55f5422c86a95c1d91a7e67d765c5bb4b5caabc5dca3d1fc03dee2dfbb35e152`；checksums.json SHA-256：`6a34a580e58a109a95bcaae3c9669576503829f4741c95f7fa9b71dfb7c22249`；全部 772 文件校验通过。
- 原版 bench.py SHA-256：`2ce4b471d80cd44c484bef52ac8902874ed4b39205612ee3c72d5e532433ec12`。先 dry-run，再运行同一未修改的完整测试包。
- checkpoint 的 9 个文件大小和 SHA 均与 manifest 相符；规范化身份 `7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`。权重 model.safetensors SHA-256：`83f4e433b044fd23f9ea7eb3acbc7d59e4fe11a1fdf3c3129b7021d0ab4f8fd4`。

## 性能

每场景完整预热一次，再计时两轮；interactive 前两轮吞吐比约 1.121，按包规则仅补一次第三轮，最后两轮比约 1.098，满足稳定性要求。无重试、服务重启或沿用已有输出。共 56 预热页次、120 计时页次，1161 次预热区域请求和 2465 次计时区域请求。

| 场景 | 页/轮 | 页面/全局区域并发 | 吞吐中位数 [最小,最大]（页/分钟） | 逐轮页面 P50（秒） | 逐轮页面 P90（秒） | SLO 成功率 |
|---|---:|---|---|---|---|---|
| interactive | 8 | 1 / 4 | 27.42 [24.97,27.98] | r1 1.40；r2 1.87；r3 1.48 | r1 6.02；r2 6.22；r3 6.17 | 每轮 100%，30 秒目标 |
| batch | 24 | 4 / 16 | 46.67 [46.36,46.99] | r1 3.45；r2 3.66 | r1 9.97；r2 9.66 | 每轮 100%，60 秒目标 |
| loaded | 24 | 8 / 32 | 55.89 [55.34,56.44] | r1 5.53；r2 5.51 | r1 16.06；r2 15.92 | 每轮 100%，60 秒目标 |

吞吐中位数取所有计时轮次的整轮成功页吞吐；P50/P90 采用每轮页面延迟的 nearest-rank 分位，不平均跨轮分位数。页面延迟从页面 worker 接纳到 Markdown 写入完成，包含区域排队、图片读取/base64/JSON、HTTP、服务处理和原生后处理，不含初始接纳队列等待、PDF 渲染、布局检测、裁剪、模型启动/编译和评分。非流式测试未测量 TTFT、TPOT 或 P99。

独立审计逐轮核对请求/页面 ID 完整性与唯一性、响应文本、usage、finish_reason、逐页成功判定和 Markdown 重建，重算吞吐、分位数、SLO、失败/截断数及补轮/稳定规则，均与原始报告一致。

## 质量

取本次 interactive-r1 的 8 页与 batch-r1 的 24 页，逐文件 SHA 绑定原始推理输出，与包内 `ground_truth.json` 的 32 页一一对应。使用此前同一 CPU OmniDocBench v1.6 环境，未重跑模型请求。评分器源文件前后哈希一致。

| 指标 | 本次值 | 参与页数 |
|---|---:|---:|
| 综合分 overall_notebook | 97.5632 | 固定 32 页子集 |
| 文本 Edit_dist（越低越好） | 0.019582 | 31 |
| 公式 CDM | 97.2793 | 14 |
| 表格 TEDS | 97.3686 | 15 |
| 表格 TEDS structure only | 99.3481 | 15 |
| 阅读顺序 Edit_dist（越低越好） | 0.142717 | 32 |

32 页匹配均完成；66 个公式 CDM 样本、22 个表格 TEDS 样本无超时、异常或错误，无 quick-match/page timeout fallback。综合分按评分器 notebook 口径计算，不等同于“32 页全部识别正确”；此覆盖不同负载的子集也不代表全量精度或生产流量。包内 `reference/` 只用于历史差异定位，不作为官方 GT。

本次 Markdown 共 88090 字符，历史参考为 88085 字符；25/32 页逐字相同，各页最小字符数比为 0.99808，未出现明显输出缩短。

## 原生产物与服务保留

以下路径均在 PPU-01 的批准根下：

- 工具及冻结计划：`03-acceptance/portable-v11-native-20261027/`，其中 `plan.json` SHA-256 为 `626b23899e23a1ef1c637a0b8f61d3c19f011c95d325e4385ff32d68231bfe27`。
- 本轮输出根：`04-runs/portable-v11-native-20261027/`。
- 原始性能报告：`benchmark/benchmark-result.json`，SHA-256 `1e926ab53f4c3ba4dc11c49cfeff9b1a8678c552076fc917d8ee86c2abd6af48`；服务绑定 `benchmark/run.json` SHA-256 `c498a3d49bbcb6635b0c016df0d46abdd46e5a790e746bea6854b315211e9b9c`。
- 原始逐请求/逐页日志及 Markdown：`benchmark/<scenario>-warmup/`、`benchmark/<scenario>-rN/`。
- 服务、输入和源码身份：`service-evidence.json`、`startup.log`、`checkpoint-verification.json`、`component-before.json`、`component-after.json`。
- 性能独立审计：`artifact-audit.json`；质量：`quality/quality-result.json`、`quality/result/predictions_quick_match_run_summary.json`、`quality/prediction-provenance.json`、`quality-audit.json`。
- 质量结果 SHA-256：`763d220e57f4fdb5ab63d3d900b58e7a81732e033ee266fc09ce5cfa08163354`；性能审计 SHA-256：`c8d2fd442197f49e6c63e223e54fc4fa4e959b57ea963205491c9042af2b94fe`；质量审计 SHA-256：`bd2ef231d1338d007103d2cdbca1a4e0c0fd133741f0043ff5945792f51f1656`。
- 原始性能报告保留 runner 的初始 quality pending 字段；评分后的派生报告为 `benchmark/benchmark-with-quality.json`，汇总 `comparison-with-quality-v2.md`，完成绑定与哈希清单为 `completion.json`。首次派生汇总因 compare.py 要求旁置 run.json 而失败，失败日志保留；仅调整派生报告位置后重新汇总，未重测或改写原始性能/质量结果。
- 临时 API PID 82458 正常 SIGTERM 退出，返回码 0，8015 已关闭。原 API PID 80811 的 PID、start ticks、boot ID、cmdline SHA 前后一致，8014 健康检查 HTTP 200；容器保持运行，restart count 为 0。证据见 `cleanup.json`、`original-service-before.json`、`original-service-after.json` 及独立审计。

评分依赖只读使用 `/mnt/nfs/users/jinghao/MiniCPM-OCR/03-acceptance/omnidocbench-9999-20261023/` 下的 score-env、OmniDocBench-v1.6 和 TeX Live。评分输出、临时文件和缓存均放在本工作根的 `04-runs/`、`05-tmp/`、`06-cache/`。未打包新镜像，本记录不构成镜像部署验证。

本地执行 `./scripts/audit-workspace`，返回既有的两处 XingChen4-29B-A4B 失效链接错误及其他模型的 9 条历史复核提示，无本次 MiniCPM-OCR 新增记录错误；未修改无关文件。远端结果的完整性结论来自上述原生产物审计。
