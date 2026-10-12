# 011：ERQA 图文评测生成乱码与超长推理

## 元数据

- 状态：`hypothesis`；首次与最后验证：2026-10-02。
- 模型：`/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`；Host `PPU-07`；容器 `minimaxM3.1`，镜像 `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`。
- Plugin `/workspace/vllm-plugin-FL` HEAD `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加既有任务 diff；FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`。本问题诊断未改这三个产品源码。
- 当前服务：用户启动的 TP16、BF16、`max_model_len=204800`、`max_num_seqs=64`、`FULL_DECODE_ONLY`、prefix cache enabled、端口 8025；2026-10-02 `/health` 200。用户修改的 Host/容器同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh` SHA-256 `56e745991d3dcc9878f314f56bcf42155d01c395066e713003e079a3f15c47f1`，本次未覆盖、未停启服务或容器。

## 问题现象与原始证据

用户提供同一批 400 题输出：Host 工作根 `max3.1_erqa_nv.json` 为其他 NVIDIA 机器的对照，SHA-256 `f48c9df64e3a0434d437a265098f907603bce73b36b07b58e6d6d332a14e4`；`max3.1_erqa_ptg.json` 为当前 PPU-07 服务，SHA-256 `b93ea0b82b463554f301127d46b296970a6cf94f6733012d0fdb9c167df67a91`。两份 JSON 均可解析，400 个 ID/题干逐项相同；但原始请求采样参数、图片字节及评测命令没有随 JSON 保存，因此这不是已冻结参数的跨平台数值对照。

| 统计 | NVIDIA 对照 | PPU-07 |
|---|---:|---:|
| 输出含 Unicode 替换字符 `�` | 0/400 | 381/400 |
| 有 `</mm:think>` | 393/400 | 146/400 |
| 有 `Answer: [A-D]` | 395/400 | 80/400 |
| completion tokens 中位数 | 1499.5 | 24523.5 |
| 到达 32768 token 上限 | 7/400 | 128/400 |

PPU-07 的 `ERQA_1` 原输出在 27002 token 后结束，含 182 个 `�`、未闭合推理、无答案行；`ERQA_10` 达到 32768 上限，含 233 个 `�`、无答案行。`ERQA_118` 则是正常且正确的 `Answer: C`，故不能说全部图片请求失败。错误文本往往在第一次 `�` 前已混入无关词和语言，替换字符是生成失稳的一个表现，而不能仅凭字符现象判定 JSON 编码损坏。

## 数据与复现

官方 [ERQA 仓库](https://github.com/embodiedreasoning/ERQA) 发布含图片字节的 `data/erqa.tfrecord`；[FlagEval/ERQA 数据集](https://huggingface.co/datasets/FlagEval/ERQA) 的固定 revision `6bf393250b0981c3f6dd77eb58b6d6879038633f` 含相同 400 题及 `images` 列，可通过 Hugging Face dataset-server 的 `rows` API 获取图片 URL。远端三个已检查 FlagEval 容器内没有发现 ERQA 图片，因此从官方数据集取 `ERQA_1`、`ERQA_10`、`ERQA_118` 四张真图，保存于 Host/容器同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/03-acceptance/erqa-diagnostic-20261002/`，manifest SHA-256 `f3470f3a6a35845a90eef90dfea3e2ca4a428858f13ed5ed5da4b36e2000d6e0`。一次性请求程序 `02-issues/erqa-repro-20261002.py` SHA-256 `f7f2b251e523f33a2e9fd0a804e2a14c9e8e284900ae4f7b44778c9bd5f25db3`，把原 JSON 题干中的 `<image N>` 替换为对应图片 data URL，通过本地 OpenAI Chat API 请求；`ERQA_1` 的 364 prompt tokens 与用户 PPU 原结果完全相同。程序与图片均不在产品源码树中。

## 已有经验与诊断

- [问题 005](005-gpqa-first10-two-errors.md)的 GPQA text-only 采样对照也显示参数可能影响长推理，但数据集、模态、服务上下文和错误签名不同，不能直接复用其分数结论。
- [问题 010](010-red-image-color-error.md)说明已有纯红图视觉误判，然而其输出没有乱码、在 greedy 512 token 内结束；本问题不能仅据多模态共性归因于视觉前处理。
- [问题 009](009-context-204800-mm-profile.md)是启动 dummy 多模态预热中的 `conv3d` 非法内存访问；本问题服务健康、请求 HTTP 200，故目前没有相同失败签名。
- 当前事实支持“采样尾部范围与长推理失稳相关”的假设；还没有证明是哪一个采样参数、量化算子、图 replay 或视觉特征的根因。原评测确切请求配置缺失，不能把这次复现当成对原评测配置的逐位重放。

## 受控请求与验证

下表请求同一 PPU 服务，均为原题及官方原图。除了采样设置和输出上限，未改模型、源码或服务。结果在 `04-runs/`，下列为文件 SHA-256。

| 题目与设置 | 结果 | 报告 SHA-256 |
|---|---|---|
| `ERQA_1`，`temperature=0,max_tokens=8192` | HTTP 200；364 prompt、8192 completion；无 `�`，但未闭合推理、无答案 | `685c3039db65342149b98f5273164da5e096de93ac7662adb816950036034e51` |
| `ERQA_1`，`temperature=1,max_tokens=8192` | HTTP 200；364 prompt、8192 completion；前约 200 字符开始无关词/多语言片段，1 个 `�`，无答案 | `e895ad6fd25908b44c73518422c6521262d5bae64588370e91a17fa9bc85bda6` |
| `ERQA_1`，`temperature=1,top_p=0.95,top_k=20,max_tokens=8192` | HTTP 200；无 `�`，但本次随机样本达到上限、无答案 | `94ae91f764d7ed6cda90c67225d3a2d1b2b9a4128f976a8d092eb4b84104f0f8` |
| `ERQA_10`，同上限及三采样参数 | HTTP 200；540 completion，正常停止；无 `�`、`Answer: C`，与标注一致 | `7544b89c2493fa5d0a67d92a97d727989ec371ad753851e949a0097c555386e9` |
| `ERQA_118`（两图），同上限及三采样参数 | HTTP 200；1326 completion，正常停止；无 `�`、`Answer: C`，与标注一致 | `0ddef0648d0967002697d5e524b70a7405028ef502d9fddca541338efe54d099` |

`ERQA_1` 在原评测的 32768 token 上限下又做三项对照：

| 采样参数 | 结果 | 报告 SHA-256 |
|---|---|---|
| `temperature=0` | 9686 token，正常停止，无 `�`，`Answer: C`，与标注 A 不符 | `6bb34309f069f703cd9707d2b399d92c46491600e3405659aa7bf6756dddbe06` |
| `temperature=1`，未设 `top_p/top_k` | 29462 token 后停止，271 个 `�`，推理未闭合，无答案行 | `917535d25b0a660fbac491d8f22dca2355e35f1c212c9c4b60a00db4674e6b8c` |
| `temperature=1,top_p=0.95,top_k=20` | 3741 token，正常停止，无 `�`，`Answer: A`，与标注一致 | `7a7b3621048318eb1e0d761bdb31ac05ac8bb403e53a6f90ec245ef07d2055c6` |
| `temperature=1,top_k=20` | 5413 token，正常停止，无 `�`，`Answer: A`，与标注一致 | `9feeafd7f58053d7fa1298d51ea40f0c9aa27c647fc30f56d18c5456d89d18cd` |
| `temperature=1,top_p=0.95` | 580 token，正常停止，无 `�`，`Answer: C`，与标注 A 不符 | `94b52c59716b1d02b74db7101509694c6f23ea075d4621c9294ceba94cee350c` |

同一三参数设置在 8192 上限的一次随机样本仍触顶，说明单次随机结果不能保证所有题目。完整 32768 上限的无约束请求重现了与用户原 `ERQA_1` 相同的乱码、无答案及约 27k–30k token 后停止签名；受限采样在同一上限正常回答。单独 `top_k` 与单独 `top_p` 的这一次请求都没有 `�`，不能从现有样本认定其中一个参数独自消除乱码；两者得到不同答案，也不能从单题断言整体准确率。请求结束后服务 `/health` 200、适配容器仍运行。

## 2026-10-02 全量 ERQA 复测

按用户指定，在同一用户启动的 PPU-07 服务上以 **32 并发**完成 [FlagEval/ERQA](https://huggingface.co/datasets/FlagEval/ERQA) 固定 revision `6bf393250b0981c3f6dd77eb58b6d6879038633f` 的 400 题、630 张真图。请求固定为 `temperature=1,top_p=0.95,top_k=20,max_tokens=32768`，`stream=false`，逐请求超时 7200 秒，不重试；题干沿用用户 `max3.1_erqa_ptg.json` 中的 400 个原文，图片按原文 `<image N>` 标记插入。全量数据的 `manifest.json` 位于 Host/容器同路径 `03-acceptance/erqa-full-temp1-p95-k20-c32-20261002/`，SHA-256 `224cfd3a6a0181d4a468a48cdc02b74b3993635ba1034c7f1f278260dc657817`；冻结配置同目录 `config.json`，SHA-256 `31fc250548b61d3704d8c7698bb23881a103ca558db13beadcf12839797051ad`。一次性客户端 `02-issues/erqa-full-eval-20261002.py` SHA-256 `fb1913483501db139034f71dfbc658b9be22f559ef7bf4f684c5fd4164442dde`；没有放入产品源码树。

运行于 2026-10-02 10:31:07–12:36:02 UTC。`04-runs/erqa-full-temp1-p95-k20-c32-20261002/summary.json` SHA-256 `2ee727748123fc2d1b4e041bc36d10178ed8d77912f061c674dbb650a1e78ab9`，同目录 `responses/` 保留 400 个逐题完整回复，启动日志为 `04-runs/erqa-full-temp1-p95-k20-c32-20261002.log`。独立重读全部文件，核对 400 个唯一 ID 与数据清单、请求参数、最后一个独立 `Answer: [A-D]` 行及汇总，结果一致：

| 统计 | 本轮结果 |
|---|---:|
| 正确率 | **230/400 = 57.5%** |
| 含替换字符 `�` | **0/400** |
| HTTP 200 / 请求错误 / 超时 | 400 / 0 / 0 |
| 有标准答案行 / 闭合 `</mm:think>` | 380 / 378 |
| `finish_reason=length` 且达 32768 token | 22（其中 19 无答案行、3 答对） |
| `finish_reason=stop` 但无答案行 | 1 |

未答题和触顶题均保留在 400 的分母中。服务开始及结束时 `/v1/models` 均返回 `MiniMax-M3.1`、`max_model_len=204800`，服务未被本轮停启。用户原 PPU 文件在同一严格答案提取口径下为 48/400 正确、381/400 含 `�`；原评测的采样参数和图片字节未保存，因此 **不能**把 57.5% 与 12% 差异严格归因于某个采样参数。另一机器的原 NVIDIA 文件为 239/400 正确、无 `�`，也不是同配置受控对照。

## 处理、限制与下一步

- `temperature=1,top_p=0.95,top_k=20` 已在当前 PPU 服务的整套真图 ERQA 请求上验证为**零替换字符的客户端缓解配置**；分数仍有 170 题未得分，其中 20 题没有标准答案行，不能称模型精度问题完全修复。不要把该采样配置写进面向所有用户的服务启动脚本。
- 原评测命令、参数和图片字节仍需评测方补齐，之后才能做严格单变量对照；建议保存每次请求参数、图像 SHA、结束原因和题目级答案。22 个触顶样本可进一步分析是否需要更高生成上限，以及更高上限对分数和乱码的影响。
- 这轮没有足以支撑 Plugin/FlagGems 产品代码根因修复的定位证据，故未修改源码、用户脚本或服务。当前结论限于用户运行的 TP16/`FULL_DECODE_ONLY` 服务及该冻结客户端配置；不外推至 eager、其他图模式或跨平台。ERQA 此轮是专项诊断，不改变既有 GPQA 正式精度门禁和 `framework.yml` 状态。
