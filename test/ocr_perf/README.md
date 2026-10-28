# MiniCPM-OCR 跨平台轻量性能测试 v1.1

适用于相同 MiniCPM-OCR checkpoint 的 OpenAI Chat 服务。客户端只需 Python 3.10+ 标准库，
不依赖 CUDA、vLLM、FlagOS 或某一厂商。测试的是固定缓存布局下的整页 OCR 服务链路，
不是 MLPerf，也不生成本仓库正式框架验收回执。

## 固定工作负载

32 页计时样本：中英文 × 正文/公式/表格/公式和表格 × 四个历史输出 token 负载分位。
8 页交互集、24 页批量集互不重复；另保留 2 页不参与基准的诊断数据。完整页面保留所有区域，
不裁去慢区域，不强制固定输出长度，不忽略 EOS。实际页面 ID、图片和请求参数在 manifest.json。
这是刻意覆盖不同负载的比较集，不是生产流量占比估计，也不能替代全量精度评测。

| 场景 | 页/轮 | 页面并发 | 每页区域并发 | 全局区域上限 | 初始 P90 目标 |
|---|---:|---:|---:|---:|---:|
| interactive | 8 | 1 | 4 | 4 | 30 秒 |
| batch | 24 | 4 | 4 | 16 | 60 秒 |
| loaded | 24 | 8 | 4 | 32 | 60 秒 |

每场景先完整重放一次该场景负载作为不计时预热，然后测两轮。预热覆盖同一批图像形状、
序列长度和并发，不能仅用少量其他图片替代。两轮成功页吞吐 max/min > 1.10 时仅补一轮。
基本规模为 112 计时页次加 56 预热页次，共 3483 次区域调用；预热不计入吞吐和延迟。
零吞吐也会补一轮，保留原失败。
最后两轮波动仍超过 10% 时报告 steady_state_stable=false，不继续无限补测，也不据此作稳定排名。
请求超时 300 秒，不重试、不重启服务、不沿用已有输出。小规模仅报告 P50/P90，不以 P99 排名。

页面延迟从被有限数量的页面 worker 接纳开始，至整页后处理和 Markdown 写入结束。
包含区域排队、PNG 读取/base64/JSON、HTTP、模型服务处理及原生后处理；不含客户端尚未接纳
页面的队列等待。这是闭环固定并发测试，不宣称固定到达率下的在线容量。
吞吐计时从首个页面提交到最后一页完成；失败和超时耗时留在总时间及延迟分布中。
PDF 渲染、布局检测、裁剪提取、启动/编译、离线精度评分不计时。

成功页面要求所有应识别区域返回非空文本且 finish_reason=stop，并生成非空 Markdown。
length 截断保留并单列，不能计为完整成功页。操作目标还要求全部页面成功且至少 90% 在时限内。
30/60 秒仅为本项目初始目标，并非行业标准。quality_status 单独报告，操作目标通过不等于精度通过。

## 每个平台的运行步骤

1. 解压固定包。提供完全相同的模型/tokenizer/处理器文件，BF16 为默认对比档位；
   量化、不同 checkpoint、不同切片配置必须另列，不能混排。
2. 使用独立性能服务。在有效命令中关闭前缀缓存；vLLM 使用
   `--no-enable-prefix-caching --mm-processor-cache-gb 0`。关闭额外请求/结果缓存。
   模型常驻与预热允许，优化后端和图模式可随平台不同，必须披露。默认单卡，多卡单独报告。
3. 现场检查实际进程、启动日志和设备，创建服务证据 JSON。不要仅凭意图填写 false。
   证据至少包括 endpoint、prefix_caching=false、mm_processor_cache_gb=0、非空 verification，
   另记录模型文件哈希、GPU/卡数、dtype、引擎及组件版本、图模式、实际 argv、进程身份。
   本 v1 档位要求 dtype="bfloat16"、gpu_count=1，checkpoint_identity_sha256 必须等于
   manifest 对 checkpoint_files 排序、紧凑 JSON 序列化后的 SHA256；必须实际核对各模型文件。
4. 在服务本机运行，客户端 CPU/内存不受限且无其他任务争用同一 GPU。

```sh
python3 bench.py --bundle /absolute/path/minicpm-ocr-portable-v1.1 --dry-run
python3 bench.py --bundle /absolute/path/minicpm-ocr-portable-v1.1 \
  --endpoint http://127.0.0.1:8013 --model MiniCPM-OCR-FlagOS \
  --service-evidence /absolute/path/service-evidence.json \
  --label H100-BF16-1GPU --output /absolute/path/new-results
python3 compare.py /absolute/path/new-results/benchmark-result.json
```

只需要更换 endpoint、服务别名、平台标签、证据和结果路径；数据及调度不变。
需要 API key 时通过 OCR_BENCH_API_KEY 环境变量传入，不写入包或结果。
客户端忽略环境网络代理，不进行隐式重试。此版本为非流式请求，不报告未经测量的 TTFT/TPOT。

## 质量与跨平台比较

保存每次响应、usage、finish_reason、逐页结果、完整 Markdown、两轮指标和输入哈希。
统一把各平台的 32 页输出交给同一个已有 OmniDocBench 评分环境：interactive-r1 的 8 页加
batch-r1 的 24 页，与 ground_truth.json 对齐；不要把不同平台的公式渲染依赖差异算作模型差异。
reference/ 是此前 H100 全量精度运行的 Markdown，只用于差异定位，不是官方 GT。
与官方标注的精度检查尚未完成时，报告必须保留 pending，不声称质量通过。

先检查质量与完整性，再逐场景比较成功页/分钟和页面 P90；在达到目标的场景中比较吞吐。
报告中同时披露模型/权重哈希、设备/卡数、软件版本、实际配置、包哈希、每轮结果和波动。
compare.py 拒绝比较不同包哈希。吞吐提高但输出明显缩短时应检查质量，不直接认定平台更快。

## 构建与来源

build_bundle.py 只在准备机使用，额外需要 Pillow，输入为已验证的原始复现包、全量结果、
原始请求轨迹及官方 GT。图片使用与原客户端相同的 RGB→PNG 编码，与原 HTTP trace 的图片哈希、
prompt 和 max_tokens 逐一匹配。后处理直接提取原复现包的纯 Python 函数并记录源文件哈希；
构建时要求 34 页重新合成 Markdown 与历史原生结果逐字相同。
历史请求中未被 vLLM 0.24 OpenAPI 声明的 no_repeat_ngram_size 不进入本版本协议；
不声称各后端会一致执行该字段。其余逐区域生成参数冻结，不自动调整。

只分发数据子集与必要评测函数，原始许可和来源说明见 SOURCE-NOTICE.txt；不包含模型权重、密钥、
服务器专用路径或启动脚本。checksums.json 覆盖包内文件，运行前逐项校验。

v1.0 首次 H100 试跑显示两页预热不足：交互前两轮吞吐为 6.58、13.46 页/分钟，
批量为 16.71、22.83 页/分钟。因此正式横向比较采用 v1.1 的完整场景预热。
旧数据包和初次试跑保留，不能与 v1.1 混排。
