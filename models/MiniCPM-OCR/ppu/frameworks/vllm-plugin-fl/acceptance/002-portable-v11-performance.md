# Portable v1.1 整页 OCR 性能测量

2026-10-26，按用户指定的
`/Users/baai/Downloads/minicpm-ocr-portable-v1.1.tar.gz` 执行全部三个场景。
这是固定 32 页工作负载的应用级测量，不是正式 framework 性能验收；不代表生产流量分布，
不改变正式阶段状态，不报告未测量的 TTFT/TPOT/P99。

## 服务与方法

- PPU-01 / `minicpm-ocr`，宿主与容器工作根均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR`，
  `/mnt` 可写绑定已现场核验，容器保持运行。
- 现有 8011、9999 服务开启缓存，按包内方法另起同容器 PPU 3 / `127.0.0.1:8013` 临时性能服务。
  PPU-ZW810E 单卡、BF16、`FULL_AND_PIECEWISE`、`TORCH_SDPA`，max model len 262144、
  max num seqs 64、GPU memory utilization 0.55，沿用现有模型及已安装组件。
- 显式 `--no-enable-prefix-caching --mm-processor-cache-gb 0`，实际 argv 与启动日志核实两类缓存关闭。
  未修改 vLLM、Plugin、FlagGems、FlagGems-vllm 或现有启动脚本，没有导入路径覆盖。
- CPU affinity 192，cgroup CPU/内存均无额度限制。输入/输出在已批准 NFS 工作根，
  页面计时包含客户端读取、编码、HTTP、服务处理、后处理与 Markdown 落盘。
- 每个场景完整重放一次预热，不计入结果；计时两轮，吞吐波动超过 10% 时至多加一轮。
  请求超时 300 秒，不重试、不沿用旧输出。交互场景触发第三轮，其余场景各两轮。

软件版本：PyTorch 2.10.0、vLLM 0.24.0+empty、Plugin `06014201f8ea8cd7092a56a945d8fc7998c5a46c`、
FlagGems `367d19367880eaf8843449abe11db4cfb7d47e03`（保留已验证索引修复）、
FlagGems-vllm `db220e684094896c0e4a038bb2a44ab6e8c95aea`、FlagTree 0.7.0+ppu3.6。
各组件运行前后 revision、diff 哈希及状态一致，既有修改保留。

## 结果

吞吐取所有计时轮的中位数与范围；P90 列逐轮列出，采用包内 nearest-rank 定义。

| 场景 | 页/区域并发 | 页/分钟中位数 [范围] | 各轮页面 P90 秒 | 时限内成功页比例 | 目标 |
| --- | --- | ---: | --- | --- | --- |
| interactive，8 页/轮 | 1 / 4 | 7.21 [6.51, 7.52] | 28.60 / 25.05 / 25.21 | 100% / 100% / 100% | 达到 30 秒目标 |
| batch，24 页/轮 | 4 / 16 | 10.42 [9.99, 10.85] | 47.59 / 48.21 | 91.7% / 91.7% | 达到 60 秒目标 |
| loaded，24 页/轮 | 8 / 32 | 13.36 [13.02, 13.71] | 72.61 / 71.04 | 87.5% / 87.5% | 未达到 60 秒目标 |

三个场景最后两轮吞吐波动分别为 4.36%、8.54%、5.32%，均满足包内稳定性要求。
计时轮共 120 页次、2465 次区域请求；预热 56 页次、1161 次区域请求。
全部 3626 次请求非空返回且 `finish_reason=stop`，没有失败、超时或 length 截断。
所有计时页面成功；加压场景因时限内比例不足 90%，`all_operational_pass=false`，
不能将更高吞吐解释为所有目标通过。

## 32 页质量复核

严格使用 interactive-r1 的 8 页与 batch-r1 的 24 页，对包内官方 `ground_truth.json` 评分，
未挑选最快轮输出。使用既有同一套 CPU OmniDocBench v1.6 环境：Python 3.11.17、
TeX Live 2026、ImageMagick 7.1.1-47、Ghostscript 10.08.0。

| 指标 | 子集结果 |
| --- | ---: |
| Overall ↑ | 97.6195685197 |
| Text Edit ↓ | 0.0190522653 |
| Formula CDM ↑ | 97.3953231293 |
| Table TEDS ↑ | 97.3686089638 |
| Table TEDS-S ↑ | 99.3481203790 |
| ReadOrder Edit ↓ | 0.1427165127 |

32 页匹配无超时回退，CDM 66 样本、TEDS 22 样本均无 timeout/error/exception。
参考 Markdown 是历史模型输出，不能作为官方 GT：本次 23/32 页与其逐字相同，
总字符数 88115，参考为 88085，未观察到以明显缩短输出换取吞吐的情况。
没有声明子集精度通过阈值，`quality_pass=null`，不以该子集替代此前 1651 页全量测量。

## 身份、证据与收尾

- 压缩包 SHA-256：`c09ba314d45a9817c992584afee8bc5712dd8a4501b8d0f2ecd1ea2451368084`。
- 包内 checksums 清单 SHA-256：`ed1e5132f12d3e3754032a1d0e5e4c95e59a8c9476b996d889125511942a4184`。
  772 项输入文件逐项校验一致。
- checkpoint 身份 SHA-256：`7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`，
  9 个模型/tokenizer/处理器文件的大小和完整 SHA-256 均与包内要求一致。
- 工具与冻结设置：`/mnt/nfs/users/jinghao/MiniCPM-OCR/03-acceptance/ocr-portable-v11-20261026`。
- 完整结果根：`/mnt/nfs/users/jinghao/MiniCPM-OCR/04-runs/ocr-portable-v11-20261026-r2`。
  原生性能报告 `benchmark/benchmark-result.json`；`benchmark/benchmark-with-quality.json` 是附加已验证质量引用的派生报告，
  原始报告保留不变。逐请求/页面/轮次原始记录、`service-evidence.json`、`artifact-verification.json`、
  `quality/quality-result.json` 和评分原生回执均保留。
- 原生性能报告 SHA-256：`d129f68f06ed1d58a838f91350af1246d15a4ac955b1bfa92fc5d2ec066a1c98`。
  服务证据 SHA-256：`413f248622ef21bb43c6dd94262aa3ee649a59b4af147199d7531d7e4257a4ed`。
- 初次预检因容器无宿主 `ppu-smi` 路径退出，未启动性能服务；改为宿主采集设备证据后使用新 run r2。
  原失败记录保留在 `04-runs/ocr-portable-v11-20261026`，未混入计时数据。
- 临时性能 API PID 521300 正常退出，退出码 0。原有 API PID 126184 / 137905 的 argv 和启动标识未变，
  8011、9999 最终 `/health` 均为 200。容器未停止或重启。
- 已逐项复核请求/页面完整性、非空输出及 stop、token 计数、P50/P90、吞吐、SLO 比例、补测条件、
  稳定性及质量预测来源哈希，均与原生记录一致。正式 framework 性能验收仍未执行。
