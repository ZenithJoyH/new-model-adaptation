# 9999 服务的 OmniDocBench v1.6 数据集测量

2026-10-23，用户手动启动 PPU-01 / `minicpm-ocr` 的 9999 服务后，授权使用本地
`/Users/baai/Downloads/mergedp1_7140_hf5_eval_repro.tar.gz` 评测精度。本次仅测量该服务，
不启动、停止或重启模型服务。此记录不是 framework 正式验收回执。

## 已验证的服务与输入

- 服务：`http://127.0.0.1:9999`，served name `MiniCPM-OCR-FlagOS`。
- 权重：`/mnt/nfs/users/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`。
- API PID `137905`，`CUDA_VISIBLE_DEVICES=2`；实际启动使用
  `FULL_AND_PIECEWISE`、`TORCH_SDPA`、max model len 262144、max num seqs 64、
  GPU memory utilization 0.55，prefix caching 开启。
- 容器 `/mnt` 由宿主机 `/mnt` 可写绑定；本次工具、输入、结果均在已批准的
  `/mnt/nfs/users/jinghao/MiniCPM-OCR` 编号目录中。
- 输入包 SHA-256：`d48499e4f91dd25fa60f79749a899273e0bc949f917efd463ea26bd56b1124b2`。
- 包不含 GT；补充[官方固定 revision](https://huggingface.co/datasets/opendatalab/OmniDocBench/commit/d386947f7fc3bafdcd756c8485845a2f43a19875)
  `d386947f7fc3bafdcd756c8485845a2f43a19875` 的 `OmniDocBench.json`，SHA-256
  `a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496`。
  已在本地逐项核对 GT 与包内 layout 的 1651 个页面 ID，一一对应。

## 已完成的预检

- 评测所需图像参数请求返回 HTTP 200。
- 从同一输入包选取 3 页，使用包内原始 OCR 客户端：3 页成功，0 页失败，
  36 次 OCR 请求全部成功，failed blocks 为 0；总耗时 95.87 秒。
- 独立 CPU 评分环境位于本次评测目录，未修改模型服务的 Python 依赖。
  Python 3.11.17，评分器直接依赖按包内版本安装；补充固定
  `datasets==2.21.0`、`pyarrow==17.0.0`、`huggingface-hub==0.26.5`，
  解决最新 PyArrow 与评分器要求的 NumPy 1.24.4 不兼容问题。评分模块导入通过。
- TeX Live 2026、ImageMagick 7.1.1-47、Ghostscript 10.08.0；CJK/gkai、
  upgreek、mathcolor 和 PDF 光栅化自检通过，确认红/绿像素实际生成。
- 包内 CDM 实现校准通过：英文、中文公式自匹配 F1 均为 1.0，不同公式负例 F1 为 0.0。

## 全量运行计划与证据

远端工具根：`/mnt/nfs/users/jinghao/MiniCPM-OCR/03-acceptance/omnidocbench-9999-20261023`。
远端结果根：`/mnt/nfs/users/jinghao/MiniCPM-OCR/04-runs/omnidocbench-9999-20261023`。

`evaluation-plan.json`、`full.yaml`、`score.yaml` 冻结本次设置。单服务使用
16 页并发、每页 4 个裁剪请求，最多 64 个在途请求；HTTP timeout 900 秒，
请求总等待预算 1800 秒。沿用包内提示词、预计算 layout/crop、4x、max slice nums 9、
temperature 0.01、top p 0.001、top k 1、repetition penalty 1、no repeat ngram size 100。
使用包内评分代码，quick match process workers 8，超时 300/420 秒，TEDS/CDM workers 8。

预检证据：`smoke/run_meta.json`、`smoke/runtime/crop_timing.jsonl`、
`smoke/per_page_metrics.jsonl`、`render-selftest/result.json`。
全量结果以 `run-state.json`、`coverage.json`、`accuracy-result.json` 和原生
`score/result/*_run_summary.json` 为准。输入包首次整文件传输中断，已改为校验分块传输。

全量输入已在远端完成 SHA-256、页面 ID 和裁剪文件完整性校验。
2026-10-23 15:43:47（北京时间）开始全量推理，容器内控制 PID `188130`、
评测 PID `188137`。17:40:55 进入评分阶段，已验证 1651/1651 页、30594 次 OCR 请求成功，
0 页失败、0 个失败裁剪，另有 2144 个非 OCR 区域按流程跳过。输出 4255691 字符；
有 1 页组装 Markdown 为空，保留在全量评分内。该页 `layout.blocks=[]`，GT 仅含
1 个 figure 与 9 个 text_mask，未发生 OCR 请求失败。

## 全量结果

2026-10-23 17:59:23（北京时间）原生评分及汇总完成。推理约 1 小时 57 分钟，
评分约 18 分钟；这些是本次数据集运行耗时，不是性能验收结果。

| 指标 | 本次 PPU / 9999 | 包内历史参考 |
| --- | ---: | ---: |
| Overall ↑ | **96.4217365011** | 96.4243326522 |
| Text Edit ↓ | 0.0316201177 | 0.0310593503 |
| Formula CDM ↑ | 98.0501467307 | 98.0771766667 |
| Table TEDS ↑ | 94.3770745448 | 94.3017563187 |
| Table TEDS-S ↑ | 96.5644202668 | 96.5036025315 |
| ReadOrder Edit ↓ | 0.1271793869 | 0.1265897983 |

Overall 比参考低 0.0025961511 分。原生页级分母分别为 text 1557、formula 313、
table 458、reading order 1638；页面匹配总数 1651。CDM 2352 个样本、TEDS 665 个样本，
均无 timeout/error/exception case。

页面匹配有 2 个 quick-match 300 秒超时回退，page timeout 为 0；保留原始回退结果，
未更改超时配置重算或挑选较高分：

- `newspaper_0b1bb8d03b4287eb95f67b68c2cf9f92_1.jpg`：参考也有该回退。
- `docstructbench_enbook-zlib-o.O-17208435.pdf_57.jpg`：比参考新增的回退。

原生评分回执：
`/mnt/nfs/users/jinghao/MiniCPM-OCR/04-runs/omnidocbench-9999-20261023/score/result/output_quick_match_run_summary.json`。
紧凑结果 `accuracy-result.json`、汇总 `summary.txt`、覆盖率 `coverage.json`、
完整阶段日志 `infer.log` / `score.log` 均在同一结果根。

结束后重新核验 1651 份预测 SHA-256、73 份评测源码 SHA-256、3 份冻结配置/输入校验记录，
全部一致；GT 和已修复 FlagGems 文件哈希也一致。服务 API PID `137905` 及启动时间标识未变，
`/health` 为 200。评测过程中未启动、停止或重启模型服务。

## 比较边界

包内 96.4243 是历史参考结果。其原生评分回执记录 Python 3.10.16、TeX Live 2025、
Ghostscript 9.55.0，与包内安装脚本建议的 TeX Live 2026 及本次环境不同。
另有 1 页新增的匹配超时回退。因此本次是针对当前 PPU 服务的新测量，
不能将分数差异全部归因于推理后端，也不据此声明逐页输出或评分环境完全相同。
未变更 framework 正式验收状态。
