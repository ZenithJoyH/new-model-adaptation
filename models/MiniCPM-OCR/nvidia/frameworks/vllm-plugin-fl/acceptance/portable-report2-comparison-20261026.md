# report-2 测试包：当前原生与 NV-FlagOS 性能对比

2026-10-26，H100-149。按用户指定的本机 `/Users/baai/Downloads/minicpm-ocr-portable-v1.1.tar.gz` **重新推理测试两套当前环境**，并使用新版compare汇总本轮新结果。所选操作为完整三场景应用 `full-suite`，不生成正式框架性能回执，不修改阶段状态。

原生交互、批量、较高负载的吞吐中位数分别为 **34.62 / 67.97 / 85.49 页/分钟**，NV-FlagOS为 **16.47 / 26.92 / 29.65 页/分钟**。交互与较高负载的原生吞吐分别为FlagOS的 **2.10 / 2.88倍**；FlagOS批量最后两轮波动16.98%，不作稳定排名。两边全部页面达到包内初始时限目标，不能据此称为性能持平或优化完成。

## 测试包与固定条件

- 输入归档SHA-256：`55f5422c86a95c1d91a7e67d765c5bb4b5caabc5dca3d1fc03dee2dfbb35e152`。
- 包内 `checksums.json` SHA-256：`6a34a580e58a109a95bcaae3c9669576503829f4741c95f7fa9b71dfb7c22249`；逐文件完整校验通过。
- report-2相对旧v1.1只修改README、compare.py与对应校验清单；实测代码、manifest、图片、GT、参考输出集合及哈希均一致。去除README/compare后的规范化清单身份为 `57958783438ed2d7f682c631b69ec8a0b5510a0202cb23ebb46a6d4d9990a5a9`。本轮两边均使用同一个新包。
- 同一GPU4 H100 80GB，UUID `GPU-37abecc9-c318-840a-1e8b-3e389dd55035`；原生后FlagOS顺序使用8013，单卡BF16。独立性能服务启动前核实GPU4空闲。
- 同一权重 `/public/flagos/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`；逐文件校验的规范化身份 `7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`，与包内要求一致。
- 公共参数：上下文262144、max-num-seqs64、显存比例0.55、TORCH_SDPA、FULL_AND_PIECEWISE；性能服务实际使用 `--no-enable-prefix-caching --mm-processor-cache-gb 0`，关闭profiler。进程argv、实际环境、有效启动日志和健康端点均取证；不是生产8012的缓存配置。
- 原生容器 `minicpm-ocr-vllm-native-allgpu`；FlagOS容器 `minicpm-ocr-flagos-public`，均核实 `/public:/public` RW。包与运行结果均位于批准工作根。
- FlagOS加载已有 `slice-blacklist.env` 与 `ocr-tuning-cache.env`：`VLLM_FL_FLAGOS_BLACKLIST_APPEND=slice`，复用 `06-cache/ocr-slice-blacklist-20261026/persistent` 调优库；未清空。实际算子记录不含FlagGems slice，仍含FlagGems attention。复用各自既有编译缓存；不将这些缓存当作跨硬件通用缓存。
- 两边实际安装身份在本轮开始/结束分别采集并逐项一致；Plugin、FlagGems、FlagGems-vllm记录实际源路径、Git HEAD/status与文件哈希，vLLM记录Python/so完整哈希。没有升级依赖、修改源码或使用PYTHONPATH覆盖。

| 组件发行包元数据 | 原生 | NV-FlagOS |
|---|---|---|
| vllm | 0.24.0+cu129 | 0.24.0+empty |
| torch | 2.11.0+cu129 | 2.11.0+cu129 |
| transformers | 5.12.1 | 5.12.1 |
| triton | 3.6.0 | 无独立triton发行包元数据；FlagTree见下 |
| vllm-plugin-fl | 未安装 | 0.0.0+ga696859b9 |
| flag_gems | 未安装 | 0.0+g8200f71f5.d20261020 |
| flaggems-vllm | 未安装 | 0.3.0.dev1 |
| flagtree | 未安装 | 0.7.0 |

Plugin发行包版本字符串可能滞后于当前Git源码；实际源码身份以本轮installed-before/after中的HEAD、status和文件哈希为准。

## 协议与结果

固定32页，交互8页、批量24页互不重复；较高负载复用批量24页。页面并发/全局区域上限分别为1/4、4/16、8/32，每页最多4个区域同时请求。每个场景完整预热一次，计时两轮；前两轮吞吐max/min超过1.10时仅补一轮，按最后两轮判断稳定性。沿用300秒请求超时、不重试、不丢弃慢轮次、自然EOS及原生成参数。

页面延迟包含区域排队、读图/编码、HTTP、服务处理、原后处理与Markdown写入；不含页面worker接纳前的等待。吞吐为每轮整体成功页/分钟。P50/P90为每轮页面延迟的nearest-rank分位数，单位秒；没有把吞吐中位数当作单页P50或平均不同轮的分位数。

| 场景 | 原生吞吐中位数 | FlagOS吞吐中位数 | 原生/FlagOS | 原生稳定性 | FlagOS稳定性 |
|---|---:|---:|---:|---|---|
| 交互 | 34.6160 | 16.4662 | 2.1022 | 稳定 | 稳定 |
| 日常批量 | 67.9746 | 26.9246 | 2.5246 | 稳定 | 不稳定，仅描述性比值 |
| 较高负载 | 85.4926 | 29.6482 | 2.8836 | 稳定 | 稳定 |

吞吐单位为页/分钟。FlagOS批量最后两轮max/min为1.1698，较高负载为1.0214，交互为1.0704；原生三个场景均小于1.10。完整轮次如下，斜杠依次对应r1/r2/r3：

| 环境 | 场景 | 吞吐各轮，页/分钟 | 页面P50各轮，秒 | 页面P90各轮，秒 |
|---|---|---|---|---|
| 原生 | 交互 | 34.8592 / 34.3727 | 1.0866 / 1.0617 | 5.3549 / 5.6283 |
| 原生 | 日常批量 | 66.7732 / 69.1759 | 2.8003 / 2.5302 | 6.5838 / 6.8071 |
| 原生 | 较高负载 | 83.2553 / 87.7299 | 4.4773 / 3.2091 | 11.1088 / 9.5260 |
| NV-FlagOS | 交互 | 15.9067 / 17.0258 | 3.0399 / 2.4248 | 8.9385 / 9.0008 |
| NV-FlagOS | 日常批量 | 26.9246 / 24.2738 / 28.3952 | 5.5806 / 7.2346 / 5.8780 | 16.7192 / 16.6584 / 14.8167 |
| NV-FlagOS | 较高负载 | 32.7881 / 29.0271 / 29.6482 | 10.6752 / 12.2050 / 10.7919 | 27.9960 / 29.7563 / 27.9440 |

全部计时轮次的页面完整成功率和包内SLO成功率均为100%，交互时限30秒、批量/较高负载60秒。这些是项目初始目标，不是行业标准。FlagOS批量不稳定如实保留，`all_current_stable=false`，没有继续无限补测。

| 环境 | 计时请求 | 预热请求 | 计时页次 | 预热页次 | 含预热的客户端耗时 |
|---|---:|---:|---:|---:|---:|
| 原生 | 2322 | 1161 | 112 | 56 | 155.1513秒 |
| NV-FlagOS | 3340 | 1161 | 160 | 56 | 498.4633秒 |

总计 **7984次区域请求**，其中5662次计时、2322次预热；共384个页次，独立测试页面仍为32页。失败、空输出、截断均为0。两边轮数不同，不能将含预热总耗时比值当作加速比；启动/编译和离线评分均不计入上述客户端耗时。

每轮请求集合和页集合与manifest严格对齐，响应ID无重复，usage和响应字段一致；每页Markdown存在且字符数匹配。两边每个区域的输入token数在所有轮次一致。各场景输出token总数如下，未通过缩短max_tokens或强制输出长度提速：

| 场景 | 原生各轮输出token | FlagOS各轮输出token |
|---|---|---|
| 交互 | 7714 / 7713 | 7712 / 7713 |
| 日常批量 | 26670 / 26669 | 26664 / 26668 / 26676 |
| 较高负载 | 26674 / 26668 | 26672 / 26663 / 26671 |

## 统一32页质量筛查

各取interactive-r1的8页与batch-r1的24页，使用同一已有CPU评分环境、包内官方GT和相同评分配置；未挑选最高分轮次。两边各66个公式、22个表格，无评分超时、错误或异常，32页matching无超时回退。

| 指标 | 原生 | NV-FlagOS |
|---|---:|---:|
| Overall ↑ | 97.4344601991 | 97.6751708773 |
| Text Edit ↓ | 0.0195816284 | 0.0195816284 |
| Formula CDM ↑ | 96.8968537415 | 97.0129251701 |
| Table TEDS ↑ | 97.3646897006 | 97.9707503067 |
| Table TEDS-S ↑ | 99.3481203790 | 99.9541809851 |
| Reading order Edit ↓ | 0.1427165127 | 0.1427165127 |

质量存在小幅差异，不声称逐字相同、统计等价或全量1651页正式精度通过。性能与质量记录分别保存，不用操作时限目标替代精度验收。

## 原生证据与保留状态

H100-149远端结果根：

`/public/flagos/jinghao/MiniCPM-OCR/flagos/04-runs/ocr-report2-h100-20261026/`，以下记为O。

控制根为同工作根 `03-acceptance/ocr-report2-20261026/`；不可变包位于 `06-cache/ocr-report2-20261026/minicpm-ocr-portable-v1.1/`，归档保留为其父目录的 `input.tar.gz`。

- `O/comparison-result.json`、`O/comparison.md`：校验后的两方结果及新版compare原生汇总。
- `O/{native,flagos}/measurement/`：全部预热/计时请求、逐页耗时、Markdown、轮次摘要、run身份与benchmark-result。
- `O/{native,flagos}/service-evidence.json`、`service.log`、`checkpoint-identity.json`、`installed-{before,after}.json`：现场进程、有效配置、权重及实际安装身份。
- `O/flagos/deployment-configs.json`、`oplist.log`、`tuning-{before,after}.json`及数据库快照：实际黑名单、算子派发和调优库状态。
- `O/{native,flagos}/quality-summary.json`、`quality-current/result/`：官方GT固定32页质量结果、公式/表格及matching异常统计。
- `O/protected-{before,after}.json`、`preservation.json`、`final-verification.json`、各自`cleanup.json`：原8012进程/PID/start ticks/argv及脚本保持、临时实例退出的证据。
- `O/evidence-index.json` SHA-256：**`1ebfed0c0d05eec03ad3272310d6dff08151188565c233099483d977b6add7e3`**。最终重新执行验证器，逐一验签结果及控制文件后读取摘要；冻结文件完整校验通过。

收尾8012 health200，原进程身份和argv未变；人工 `start-model.sh` SHA-256仍为 `ab1239fa7729e8d532916b8c6feb4574cc0dccc78f3aa0cc8dceccbaf2a65d32`。GPU4显存0MiB，8013无监听，两原容器继续运行。未修改产品源码、依赖、测试包或用户启动脚本，未提交推送，不更新framework.yml或宣称optimized。

本地结构审计没有MiniCPM-OCR条目；仓库原有XingChen4失效链接及其他模型历史告警保留。三份本轮Markdown记录的空白检查通过。
