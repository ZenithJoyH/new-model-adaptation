# 优化服务的三项全量精度测量

## 范围与配置

2026-10-10，按用户要求评测 PPU-13 的 `minicpmV4.7-35B` 容器内
8010 服务，模型为 `/mnt/cpfs/models/MiniCPM-V-4.7-35B-A3B`。
使用 GPU 0、1，TP2、BF16、前缀缓存开启，`FULL_AND_PIECEWISE`，
图大小为 1、2、4、8、16、32、64，两类图均完成 7/7 捕获。
此次是全量精度测量，`formal_acceptance=false`，未更新 profile 正式验收状态。

| 配置 | GPQA Diamond / MATH-500 | ERQA |
| --- | --- | --- |
| temperature / top_p / top_k | 1.0 / 0.95 / 20 | 沿用原配置：1.0 / 0.95 / 20 |
| 并发 | 32 | 32 |
| 输出长度 | `max_gen_toks=null`，使用服务剩余上下文预算 | `max_tokens=30000` |
| 服务总上下文 | 262144 | 262144 |
| 重试 | API、任务重试均为 0；客户端等待 7200 秒 | 原生最多 5 次；每次 HTTP 等待 300 秒 |

模型启动配置与 generation config 没有显式输出 token 上限，故 LLM 配置
保留 JSON `null`，不是字符串 `"None"`。原生 LLMEval 的 seed=1234 保留。
执行顺序为 MATH-500 → ERQA → GPQA；各组使用新响应缓存或关闭响应缓存。
本次服务由记录的 8010 argv 恢复；用户另行修改的根级启动脚本未作为本轮启动入口。

## 评测环境与输入

- PPU-13：`flageval-minicpm-accuracy-20261010-1623-v3`，复用
  `harbor.baai.ac.cn/flageval/flageval-llmeval:v1` 及实际安装的 `/app` 原生代码。
- PPU-01：`flageval-minicpm-erqa-20261010-1623`，复用
  `flageval/mm-eval:v0.3.8_1`，实际安装 `flagevalmm 0.3.5`，
  `/app` Git HEAD 为 `63c8c28bad8cb41c0a3a3056b53f3031fb6db1ab`。
- 两个节点均使用用户批准的绝对工作根目录
  `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，共享 NFS 映射已核对。
  LLMEval 的 SQLite 响应缓存位于评测容器 tmpfs。
- GPQA 198 题、MATH-500 500 题通过原生离线预检查。
  ERQA 使用此前 Minimax 评测的冻结 manifest 和 630 张 JPEG，
  revision 为 `6bf393250b0981c3f6dd77eb58b6d6879038633f`，全部图片哈希重验通过。
  数据在 `/mnt/nfs/users/jinghao/minimaxM3.1/03-acceptance/erqa-full-temp1-p95-k20-c32-20261002`，只读使用。

| 输入 | SHA256 |
| --- | --- |
| GPQA 原始 Arrow | `501f307f9e8bc34041af4120c8eb5a735f0ea29cd83c90167b913651071bb4c4` |
| MATH-500 原始 JSONL | `35dc41080a3680858b27fa7e0533d2d547825316fc5dafe5d316f4ccc5a06132` |
| ERQA manifest | `224cfd3a6a0181d4a468a48cdc02b74b3993635ba1034c7f1f278260dc657817` |

## 原生全量结果

| 数据集 / 原生指标 | 正确 / 全量 | 分数 |
| --- | --- | --- |
| GPQA Diamond：`exact_match,strict-match` | 160 / 198 | **80.81%** |
| GPQA Diamond：`exact_match,flexible-extract` | 140 / 198 | 70.71% |
| MATH-500：`exact_match,none` | 481 / 500 | **96.20%** |
| ERQA：原生 BaseEvaluator | 206 / 400 | **51.50%** |

LLM 每题及原生结果的分数一致；GPQA 有两组过滤器，共 396 行，但只有 198
个题号。两组共享生成回复。MATH 有 500 行、500 个题号。两项均无最终超时、
错误或空回复，API `stop` 分别为 198、500，`length` 均为 0，未发现替换字符乱码。

ERQA 有 400 个题号、400 条成功 HTTP 回复；原生重新计分与已保存结果一致，
无被拒绝样本、空答案、替换字符乱码或长度截断。平均输出 654.2275 tokens，
最大输出 5342 tokens。视觉 attention 首轮编译引起 24 次 HTTP 超时，
由原生重试恢复，共 424 次尝试；这些失败尝试保留在证据中。

## 修复与核验边界

首次运行 `accuracy-opt-20261010-1623` 的 GPQA 长请求触发页偏移 int32
溢出，服务退出。首次 GPQA 严格结果也是 160/198，但包含 1 个失败占位；
后续 MATH 的 500 个连接失败不是模型精度。原轮失败证据完整保留。
实际安装的 FlagGems-vllm 内核现将物理页号提升为 int64，前后复现及 4 项
随机参考、图重放测试通过，见 [016 修复记录](../adaptation/016-paged-attention-address-overflow.md)。
重跑全部三项后服务保持健康，结果绑定修复后的源码；不据此宣称分数提升。

核验工具的两项错误已纠正并保留旧失败记录：JSONL 按物理文件行读取，
避免 Unicode 行分隔字符被错误拆行；ERQA 按 400 个题号和原生编码请求的
多重集合核对，避免将 `ERQA_162` 与 `ERQA_264` 的相同题干、图片误判为漏题。
ERQA 因此有 399 种请求内容、400 次有效推理。原生提示词、提取和评分代码未改动。

完成时核对 Plugin 270 个文件、FlagGems-vllm 345 个文件、vLLM 1886 个文件、
普通 FlagGems 2551 个文件；除已冻结的页号提升外，均与本轮基线一致。
vLLM 保持只读，Plugin 的 dispatch 逻辑沿用原优化版本，无 `PYTHONPATH`
或 `VLLM_FL_PER_OP` 覆盖。LLM 的 6 个输入/原生代码文件及 MM 的 7 个
原生代码文件在结束后重新核对一致。8010 健康检查为 200，运行和等待请求均为 0。

## 证据位置

远端工作根目录下，新轮 ID 为 `accuracy-opt-recovery-20261010-1733`：

- 配置及控制文件：`03-acceptance/accuracy-opt-recovery-20261010-1733/`，
  含 `math-config.json`、`erqa-config.json`、`gpqa-config.json`。
- 完成汇总：`04-runs/accuracy-opt-recovery-20261010-1733/verified-summary.json`。
- 分项核验：同目录的 `math-verified-summary.json`、`erqa-verified-summary.json`、
  `gpqa-verified-summary.json`；均包含原生结果及逐题文件的绝对路径和 SHA256。
- 原生 LLM 文件分别位于同目录模型子树的 `llm-math/math_500/attempt-1/`
  和 `llm-gpqa/gpqa_diamond_generative_cot/attempt-1/`；原生 ERQA 文件在 `mm/erqa/`。
- 原生关键结果 SHA256：MATH `c9e3ab64252ebd89fd7ffd541635c27e52cfc14de10ab3c12f7f98dee54ef616`；
  GPQA `c35cf34b32335ef4c94bd2258b42619039fc91735815cb02023dc1b32cdee066`；
  ERQA `6e70554676fa97040c451dbe42505bab92f0aebd969e94ccf539b508aea4374b`。
- 源码/运行身份：`fixed-source.json`、`source-final-git.json`、`service-ready.json`、
  `service-postflight.json`；原生代码结束检查为 `llm-source-postflight.json`、
  `mm-source-postflight.json`。实际 Git 元信息与逐文件内容指纹分开保存。
- 核验规则修正：`erqa-verifier-correction.json`、`erqa-verification-v2.log`；
  原始核验失败日志和回执保留，不作为本轮完成依据。

本记录只证明上述实际服务、源码与配置的全量精度测量，不替代正式验收阈值、
镜像打包或端到端性能验收。

本地 `audit-workspace --repository-only` 返回 1；当前 profile revision 变更导致
既有 `framework.yml` 证据需复核。本轮新增 Markdown 未报告布局错误，
该审计不能用于声明正式验收通过，既有状态文件保持原样。
