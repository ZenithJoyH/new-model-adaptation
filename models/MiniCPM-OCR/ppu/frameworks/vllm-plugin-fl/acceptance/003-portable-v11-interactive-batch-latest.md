# Portable v1.1 report-2：interactive 与 batch 最新测量

2026-10-26，使用用户当前提供的 `/Users/baai/Downloads/minicpm-ocr-portable-v1.1.tar.gz`，
重新测量 PPU-01 / minicpm-ocr 环境。用户在运行期间缩小范围为 interactive 和 batch；
两场景各完成三轮，最终结果只覆盖这两个场景。保留上次测量记录，不覆盖旧结果。

## 环境与测量边界

- 宿主与容器批准根均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR`，`/mnt` 可写绑定已核验。
  原有 8011、9999 保持运行；按包内要求使用同容器独立 8013 服务、空闲物理 PPU 3。
- PPU-ZW810E 单卡 96 GiB，BF16、FULL_AND_PIECEWISE、TORCH_SDPA；
  max-model-len 262144、max-num-seqs 64、gpu-memory-utilization 0.55。
- 实际 argv 与启动日志均确认 `--no-enable-prefix-caching --mm-processor-cache-gb 0`。
  CPU affinity 192，cgroup CPU/内存均无限额；输入和输出位于批准的 NFS 工作根。
- 使用当前容器的实际安装组件，无 PYTHONPATH 覆盖，无产品代码、权重或现有启动脚本变更。
  PyTorch 2.10.0、vLLM 0.24.0+empty、Plugin 0.0.0+g06014201f.d20261021、
  FlagGems 5.5.0.dev0+g367d19367、FlagTree 0.7.0+ppu3.6。
  四个组件的 Git revision、diff 哈希及状态在运行前后保持一致，既有脏修改保留。
- 当前包是 report-2，仅 README、compare.py 和 checksums.json 相比旧包改变；
  bench.py、数据、请求参数、并发、预热规则逐字节相同。772 项包内文件校验通过。
- 每场景完整负载预热一次后计时两轮；前两轮吞吐 max/min > 1.10，均按规则补一轮，最多三轮。
  请求超时 300 秒，无重试。页面延迟包含接纳后的区域排队、读图/编码、HTTP、后处理及 Markdown 落盘，
  不含未接纳页面的队列等待、布局检测、渲染、裁剪、启动/编译和离线评分。

## 性能结果

吞吐中位数及范围取全部计时轮；P50/P90 和时限内成功比例均按 r1/r2/r3 列出。
页面分位数使用包内 nearest-rank 定义，不对各轮分位数求平均。

| 场景 | 页/区域并发 | 吞吐中位数 [最小, 最大] 页/分钟 | 各轮页面 P50 秒 | 各轮页面 P90 秒 | 各轮时限内成功页比例 |
| --- | --- | ---: | --- | --- | --- |
| interactive，8 页/轮 | 1 / 4 | 7.29 [6.32, 7.60] | 6.63 / 5.89 / 5.34 | 29.88 / 24.85 / 25.99 | 100.0% / 100.0% / 100.0% |
| batch，24 页/轮 | 4 / 16 | 11.59 [9.88, 12.92] | 17.57 / 13.71 / 12.85 | 48.02 / 41.16 / 36.02 | 91.7% / 95.8% / 100.0% |

两个场景各轮完整成功页比例均为 100%，所有计时轮均达到包内操作目标：
interactive 至少 90% 在 30 秒内，batch 至少 90% 在 60 秒内。
interactive 最后两轮吞吐差异 4.35%，稳定；
batch 最后两轮仍相差 11.49%，超过 10%，
故 `all_operational_pass=true`、`all_steady_state_stable=false`。batch 结果不能用于稳定排名，
按方法不再继续补测。

| 场景 | 轮次 | 轮次总耗时 秒 | 成功页/分钟 | 成功区域请求/秒 | 输出 token/秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
| interactive | 1 | 75.90 | 6.32 | 1.88 | 101.59 |
| interactive | 2 | 63.13 | 7.60 | 2.27 | 122.15 |
| interactive | 3 | 65.87 | 7.29 | 2.17 | 117.07 |
| batch | 1 | 145.80 | 9.88 | 3.49 | 183.01 |
| batch | 2 | 124.28 | 11.59 | 4.10 | 214.80 |
| batch | 3 | 111.47 | 12.92 | 4.57 | 239.38 |

选定两场景计时共 **96 页次、1956 次区域请求**，
预热共 32 页次、652 次请求。
这 2608 次请求均非空且 `finish_reason=stop`，失败、超时及 length 截断均为 0。
预热不计入上表。非流式协议未测量 TTFT/TPOT；小规模测量不报告 P99。

## 32 页输出质量

按包内要求使用 interactive-r1 的 8 页加 batch-r1 的 24 页，与包内官方 GT 对齐，
在同一套既有 CPU OmniDocBench v1.6 环境离线评分，没有追加模型请求。

| 指标 | 当前子集结果 |
| --- | ---: |
| Overall ↑ | 97.5245421303 |
| Text Edit ↓ | 0.0195816284 |
| Formula CDM ↑ | 97.1631802721 |
| Table TEDS ↑ | 97.3686089638 |
| Table TEDS-S ↑ | 99.3481203790 |
| ReadOrder Edit ↓ | 0.1427165127 |

32 页均完成匹配，无超时回退；公式 CDM 66 样本、表格 TEDS 22 样本，无 timeout/error/exception。
与历史参考输出 22/32 页逐字相同，输出总字符数 88112，参考 88085，未观察到明显缩短。
没有声明本子集的精度通过阈值，`quality_pass=null`，不以此替代全量精度评测。

## 证据、范围调整与收尾

- 工具根：`/mnt/nfs/users/jinghao/MiniCPM-OCR/03-acceptance/ocr-portable-v11-latest-20261026-1540`。
- 本次结果根：`/mnt/nfs/users/jinghao/MiniCPM-OCR/04-runs/ocr-portable-v11-latest-20261026-1540-r2`。
- 两场景原始轮次：`benchmark/interactive-r{1,2,3}/`、`benchmark/batch-r{1,2,3}/`；
  每轮保存请求、逐页计时、summary 和 Markdown；预热另存。
- 用户缩小范围后，以准确 PID 653218、启动标识 571699790 和 endpoint/输出根校验后发送 SIGINT，
  中止正在进行的 loaded；`user-scope-change.json` 记录该操作。
  loaded 的部分原始产物保留，但不进入本报告统计。
- 原控制程序因客户端被用户取消而保留 `failed` 状态，不将它改成全套完成。
  `benchmark/benchmark-selected-result.json` 是从六个未修改的原生 summary 汇总的选定范围派生报告，
  内含各源文件 SHA-256 和范围调整出处；当前包内 compare.py 生成 `comparison-selected.md`。
  `benchmark/benchmark-selected-with-quality.json` 附加评分证据，原始轮次不变。
- `artifact-verification-selected.json` 独立重算请求/页面完整性、非空 stop、token、P50/P90、吞吐、
  SLO、补测条件、稳定性、评分来源及原服务身份，状态为 `verified_measurement`。
- 临时服务 API PID 632616 正常退出，退出码 0。原 8011/9999 的 PID、argv 和启动标识不变，
  最终健康检查均为 200；容器持续运行。组件前后身份一致，无产品变更。
- 首次启动因临时目录过长触发 Unix socket 107 字符限制，在任何测试请求发出前退出；
  原失败根 `04-runs/ocr-portable-v11-latest-20261026-1540` 保留。
  将本任务 TMPDIR 缩短为 `05-tmp/op1126` 后新建 r2 运行，未修改框架代码。
- 压缩包 SHA-256：`55f5422c86a95c1d91a7e67d765c5bb4b5caabc5dca3d1fc03dee2dfbb35e152`。
- checksums.json SHA-256：`6a34a580e58a109a95bcaae3c9669576503829f4741c95f7fa9b71dfb7c22249`。
- bench.py SHA-256：`2ce4b471d80cd44c484bef52ac8902874ed4b39205612ee3c72d5e532433ec12`。
- checkpoint 身份 SHA-256：`7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`，9 个模型/tokenizer/处理器文件完整校验一致。
- 选定范围报告 SHA-256：`2c8f4d039083df957754b8b48f1499249d2794f9d1d83433797af2ca636fae3f`。
- 服务证据 SHA-256：`cbdfa7eb26026aff2132b3b129759cb45636eb295e909754025a1fd7eec84727`。
- 当前测量只证明选定的固定 32 页应用工作负载；正式 framework 性能验收状态未改变。

## 按用户要求补充四项分位数

从已完成的原始数据只读重算，不重新推理。吞吐以三轮各自的整轮成功页/分钟为 3 个样本；
页面延迟合并三轮 `pages.json` 的逐页 `duration_seconds`，interactive 为 24 页次、batch 为 72 页次，
不含预热。两类分位数均用 nearest-rank：排序后取 `ceil(n*q)` 个样本。

| 场景 | P50 吞吐 页/分钟 | P90 吞吐 页/分钟 | 合并页面 P50 延迟 秒 | 合并页面 P90 延迟 秒 |
| --- | ---: | ---: | ---: | ---: |
| interactive | 7.29 | 7.60 | 6.18 | 24.85 |
| batch | 11.59 | 12.92 | 14.95 | 47.47 |

吞吐 P90 是用户要求的描述性补充，原生包仅报告吞吐中位数和范围；三轮样本下 P90 等于最大值，
不足以代表稳定的长期吞吐分布，batch 原有 11.5% 波动结论保持。
合并页面分位数直接来自逐页数据，不是各轮 P50/P90 的平均值；上文逐轮结果保留。

