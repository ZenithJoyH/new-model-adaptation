# 原生 vLLM 与 FlagOS：固定 32 页 OCR 性能对比

2026-10-26，H100-149。按用户要求使用既有 v1.1 测试包、相同权重和参数测量原生 vLLM，
对比 2026-10-24 的 [FlagOS 首跑结果](portable-performance-v1-20261024.md)。
最终验证为 `verified_complete`。原 8000、8001、8011、8012 及人工启动脚本均保持；
仅新建本任务 GPU4/8013 实例，结束后已停止，GPU4 显存回到 0 MiB，两套原容器继续运行。

## 对比条件

批准工作根 `/public/flagos/jinghao/MiniCPM-OCR/flagos`，下文记为 R。
现场分别验证原生、FlagOS 容器的 `/public:/public` RW，以及 CPU 评分容器的 R 同路径 RW。
原生容器 `minicpm-ocr-vllm-native-allgpu`，ID `0c40733804a719e8d3ea9259cd21fe092eb8f650137305aae3aec602d658aa9b`；
使用既有 `minicpm-ocr-vllm-native:allgpu-public-snapshot-20261021` 环境，未安装或升级软件。
原生 vLLM 没有 FL 平台插件入口，也未安装 Plugin、FlagGems、FlagGems-vllm、FlagTree；
测试子进程明确设置 `VLLM_PLUGINS=''`，没有 PYTHONPATH 或其他产品导入覆盖。

| 条件 | 两边共同设置 |
|---|---|
| 物理设备 | GPU4，H100 80GB HBM3；UUID `GPU-37abecc9-c318-840a-1e8b-3e389dd55035` |
| 权重 | `/public/flagos/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`，逐文件 SHA256 一致 |
| 数值精度/卡数 | BF16，单卡 |
| 服务设置 | max-model-len 262144、max-num-seqs 64、gpu-memory-utilization 0.55 |
| 执行模式 | FULL_AND_PIECEWISE，启动日志核实图捕获 |
| 视觉接口 | `--mm-encoder-attn-backend TORCH_SDPA` |
| 性能缓存 | `--no-enable-prefix-caching --mm-processor-cache-gb 0` |
| 多模态限制 | image 4、video 1；实际测试为单区域图片请求，4x/max_slice_nums 9 |
| 客户端与负载 | 同一冻结 bench.py；32 页、相同 PNG/prompt/逐区域生成参数/调度与预热规则 |

实际服务 argv 从 FlagOS 性能实例的已冻结证据复制。归一化服务别名后，全部 argv 相同；
`MiniCPM-OCR-native` 与 `MiniCPM-OCR-FlagOS` 仅为 API 别名。
原生已有 8000/8001 的默认视觉后端和 8001 的额外 GDN 配置未用于本次新实例；
本轮按用户要求匹配 FlagOS 参数，没有改成另一套原生优选参数。

| 软件 | 原生 vLLM | FlagOS 历史基线 |
|---|---|---|
| vLLM distribution | 0.24.0+cu129 | 0.24.0+empty |
| Torch | 2.11.0+cu129 | 2.11.0+cu129 |
| Transformers | 5.12.1 | 5.12.1 |
| 编译器 | Triton 3.6.0 | FlagTree 0.7.0，提供 Triton 命名空间 |
| FL/Gems 组件 | 未安装 | Plugin、FlagGems、FlagGems-vllm 已启用 |

Plugin editable 元数据不等于其实际 Git HEAD；FlagOS 的准确源码/修改身份沿用历史
`source-identity.json` 及证据索引，不用 distribution 版本字符串替代源码身份。
原生 `_version.py` 记录 base commit `gee0da84ab`；安装的 vLLM Python/so 文件在测量前后全部一致。

## 负载、完整性与性能

单文档场景 8 页，页面/全局区域并发 1/4；日常批量 24 页，4/16；较高负载复用同样 24 页，8/32。
每个场景完整预热一次、正式测两轮；超过 10% 波动才补一轮。本轮所有场景稳定，无需第三轮。
112 个计时页次、2322 个计时请求，全部完整成功，失败、空输出和截断均为 0；
另有 56 个预热页次、1161 次预热请求，同样完整成功。
3483 个原生响应的输入 token 数均与同页同区域的 FlagOS 记录相同，含计时请求 2322 个。
每个响应 ID 唯一，所有预期页面/区域集合、指标和原始响应数量均经验证。

| 场景 | 原生两轮（页/分钟） | 原生中位数 | FlagOS 中位数 | 原生 / FlagOS |
|---|---|---:|---:|---:|
| 单文档 | 35.7744 / 35.0861 | **35.4303** | 14.2765 | **2.4817×** |
| 日常批量 | 74.2567 / 70.2325 | **72.2446** | 23.8689 | **3.0267×** |
| 较高负载 | 85.4828 / 87.2718 | **86.3773** | 28.2022 | **3.0628×** |

| 场景 | 原生两轮页面 P90（秒） | FlagOS 两轮页面 P90（秒） |
|---|---|---|
| 单文档 | **5.2873 / 5.4845** | 11.6290 / 11.7299 |
| 日常批量 | **6.3215 / 6.2268** | 20.0915 / 17.8649 |
| 较高负载 | **9.6552 / 10.3801** | 30.9986 / 31.4287 |

原生所有页面均达到初始 30/60 秒时限，两轮吞吐波动分别约 1.96%、5.73%、2.09%。
含完整预热的原生客户端运行时间 **155.2313 秒（2 分 35 秒）**，其中计时轮次约 100.34 秒；
FlagOS 对应为 447.2519 秒（7 分 27 秒）。两者均不包含冷启动、编译和离线评分。

输出工作量也核对如下，未通过截断或统一缩短输出长度提速：

| 场景 | 原生每轮输出 token | FlagOS 每轮输出 token | 每轮均值差异 |
|---|---|---|---:|
| 单文档 | 7713 / 7713 | 7712 / 7712 | +0.0130% |
| 日常批量 | 26673 / 26683 | 26702 / 26694 | -0.0749% |
| 较高负载 | 26672 / 26681 | 26689 / 26685 | -0.0393% |

## 同一评分环境的小集质量

原生 interactive-r1 的 8 页与 batch-r1 的 24 页，使用相同的官方 GT 和既有 CPU
OmniDocBench 评分环境重新评分。没有对 native 全量 1651 页或各并发档逐轮重复评分。

| 指标 | 原生 vLLM | FlagOS |
|---|---:|---:|
| Overall ↑ | **97.4744570963** | 97.6365813638 |
| Text Edit ↓ | 0.0195816284 | 0.0196177922 |
| Formula CDM ↑ | 97.0129251701 | 96.8968537415 |
| Table TEDS ↑ | 97.3686089638 | 97.9746695699 |
| Table TEDS-S ↑ | 99.3481203790 | 99.9541809851 |
| Reading order Edit ↓ | 0.1427165127 | 0.1427165127 |

原生 Overall 低 0.1621242675 个百分点，主要是表格项降低；文本、公式项略高或更好，
阅读顺序相同。原生 66 个公式 CDM、22 个表格 TEDS，评分超时/错误/异常均为 0；
32 页匹配无 quick_match/页面超时回退。这不是逐字相同或全量精度等价的结论。

## 证据与限制

原生使用 2026-10-26 实测，FlagOS 使用 2026-10-24 的既有实测，没有重跑或改写历史结果。
这是相同设备和共同参数下两套完整推理栈的应用比较，包含原生算子、FlagGems、FlagTree等差异，
没有通过本轮数据把性能差距归因到某个特定算子。未做算子 profiling 或额外优化。
这是缓存布局下的有限并发整页 OCR 比较，不包含 PDF 渲染/布局检测，也不代表吞吐极限或长期 SLA。
继续保持正式框架阶段状态，不生成正式性能验收回执，不作 `optimized` 结论。

原生与 FlagOS 容器继续运行，原 8000/8001/8011/8012 的宿主 PID、启动时间和 argv 前后相同。
人工脚本 SHA256 仍为 `ab1239fa7729e8d532916b8c6feb4574cc0dccc78f3aa0cc8dceccbaf2a65d32`。
仅停止经 PID/启动时间/进程组核实的新建原生 8013；没有修改产品源码、测试包、脚本或已有服务。

- 冻结包 checksums.json：`ed1e5132f12d3e3754032a1d0e5e4c95e59a8c9476b996d889125511942a4184`。
- 权重文件集合身份：`7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`。
- 既有 FlagOS 索引：`e6e5d45383f945e94f1f6105c3a54f14a38ec47d97fe2727ca1dd5af14419a8d`，本轮重新核对。
- 新原生比较索引：`7fdd957510f8b4060d76b4584bfc280a7e2861895b98177c09102401407e4aa9`。
- 控制/校验脚本：`R/03-acceptance/ocr-native-v1.1-20261026/`。
- 原始结果根：`R/04-runs/ocr-native-v1.1-h100-20261026/`。

结果根中的 `comparison-result.json`、`evidence-index.json` 为完整验证与索引；
`measurement/` 保存逐轮指标、每个响应和页面输出；`native-install-before.json`、
`native-install-after.json`、`service-evidence.json`、`cache-policy-evidence.json`
保存实际安装/服务/缓存身份；`protected-before.json`、`protected-after.json`、
`service-preservation.json`、`worker-cleanup.json` 保存原服务及脚本保持证据。
`quality-summary.json` 与 `quality-current/result/` 保存官方小集评分和逐元素结果。

现有 `compare.py` 可直接读取原生与 FlagOS 两个 `measurement/benchmark-result.json` 横向汇总。
本地审计的原有 XingChen4 失效链接与其他模型历史警告未处理，不影响本轮独立验证。
没有提交、推送或创建 PR。
