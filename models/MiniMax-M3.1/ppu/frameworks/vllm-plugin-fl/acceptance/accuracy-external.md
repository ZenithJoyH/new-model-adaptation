# 外部 GPQA 精度评测通过记录

2026-10-08，用户确认已通过外部评测完成当前 MiniMax-M3.1 / PPU-07 / vllm-plugin-fl 服务的 GPQA 精度验收。

| 项目 | 用户确认结果 |
|---|---:|
| 数据集 | GPQA |
| 用户提供得分 | **84.84%** |
| 文件复核得分 | **168/198 = 84.848484…%**（strict-match） |
| 通过阈值 | **80.9%** |
| 高于阈值 | 3.94 个百分点 |
| 外部精度验收结论 | **通过** |

用户确认后，2026-10-08 在 PPU-07 只读核验了用户提供的外部文件，未重跑评测或修改服务。原始运行统计记载时间为 2026-10-01 07:46:24–08:16:13，未注明时区，`status=success`、中断次数为 0。任务为 `gpqa_diamond_generative_cot`，数据集 `Idavidrein/gpqa` / `gpqa_diamond`，0-shot、无 limit；原始及有效样本数均为 198。

样本文件包含两个 filter 各 198 行，共 396 行，不是 396 道题。独立复算 strict-match：doc_id 0–197 完整且无重复，168 正确、30 错误，零 timeout、零空响应、零含 U+FFFD 替换字符的响应，与报告完全一致。另一提取口径 flexible-extract 为 71/198（35.8586%），不混用为用户指定的 strict-match 验收分数。

## 配置及来源

报告内保存 task 配置与 runner 配置；日志也确认合并后的生成配置：`temperature=1.0, top_p=0.95, top_k=-1.0, max_gen_toks=18000, max_model_len=204800, do_sample=false, until=["</s>"]`，并发 32，模型名 `MiniMax-M3.1`，API 端口 8025。`do_sample=false` 是评测器记录值；未检查这轮评测器的请求构造代码，不能据此断言服务端实际使用 greedy。17 道样本的 completion token 数达到或超过 18000；记录该事实，不剔除样本。此轮与历史 `top_k=20,max_gen_toks=60000` 评测的配置不同。

以下路径均位于 PPU-07，只读访问；未复制原始产物到本地模型目录。

| 产物 | 绝对路径 | SHA-256 |
|---|---|---|
| GPQA 报告及嵌入配置 | `/mnt/nfs/users/lxj/outputs/llm-outputs/MiniMax-3.1_pingtouge/gpqa_diamond_generative_cot/MiniMax-M3.1/results_2026-10-01T08-16-11.908798.json` | `62b18eaa815de4d1d6f5901bb72d31f2c97553615caa34367dbbdb37f480fef8` |
| GPQA 样本 | `/mnt/nfs/users/lxj/outputs/llm-outputs/MiniMax-3.1_pingtouge/gpqa_diamond_generative_cot/MiniMax-M3.1/samples_gpqa_diamond_generative_cot_2026-10-01T08-16-11.908798.jsonl` | `1cf28d0982173fb1ff26398c4a748d5e9dd385369b41786540a5a87464b08203` |
| GPQA 运行统计 | `/mnt/nfs/users/lxj/outputs/llm-outputs/MiniMax-3.1_pingtouge/gpqa_diamond_generative_cot/eval_stats_gpqa_diamond_generative_cot.json` | `6b70933de46b6af179f75420f911a49fdaec6e261f8b32106e40885d4c966154` |
| GPQA 日志 | `/mnt/nfs/users/lxj/outputs/llm-outputs/MiniMax-3.1_pingtouge/gpqa_diamond_generative_cot_llmeval.log` | `8511d03b2f9f026ef30b167ce7ce770cfd5ca587a95a2f2481f3d1ba13856992` |

## 同批提供的外部 ERQA 结果

目录 `/mnt/nfs/users/lxj/outputs/vlm-outputs/minimax3.1_ptg/erqa` 中的结果报告为 **57.0%**。独立复算 `erqa_evaluated.json` 为 228 正确、172 错误，400 个唯一 question_id；`erqa.json` 同为 400 个唯一 question_id，两份文件的 answer/reason 字段均无 U+FFFD，answer 均非空。任务配置为 `FlagEval/ERQA` test、`num_workers=64`、`retry_time=1`，与 GPQA 记录的 endpoint 主机及 8025 端口相同。提供的 task 配置未包含生成参数，不能将 GPQA 参数或本任务此前 32 并发参数套用到它。没有提供 ERQA 通过阈值，本记录只核验结果，不作 ERQA 通过判断；也不与本任务此前 230/400 的独立运行混同。

| ERQA 产物（上述目录内） | SHA-256 |
|---|---|
| `erqa_result.json` | `b485995cf04e94488207b06df43bcecafb84f6ce9453d3bddf83fdd107bc8ab6` |
| `erqa_config.json` | `ce2b9950d6b2b468a57b6600ab308f16bfd0c435942d8065f7ba0259b025e9e6` |
| `task_info.json` | `5bebafa7133f7f6a67f1cf04e446a02918c978de04d9407e2714ff47b89f6547` |
| `erqa_evaluated.json` | `266324166c26d8ad053b20e95752a26cb585ab721fc266410af247cb865ed662` |
| `erqa.json` | `cd6a77eee1a2638f0c8492fd4e3e7588619dabc6cbb653253ac08cb49d3a4664` |

## 验收范围

80.9% 是用户指定的本轮外部验收阈值，记录于 2026-10-08；未发现它被冻结于原始外部运行报告，因此不追溯声称它是当时 runner 的冻结阈值。此前项目原生评测按各自冻结的 88% 阈值判定失败，其配置、分数和失败回执保持历史原样。本次外部精度验收判定通过；`framework.yml` 的 `external_accuracy` 保存该决定及已核验文件引用。

外部目录未提供项目原生 `acceptance-result.json` / `framework-check.json`，也没有评测时源码 revision/diff、graph 模式、prefix cache 或 service_instance_id 的绑定。不能用模型名和端口代替服务版本身份，也不把历史 65k deployment fingerprint 绑定到本轮。原生 `workflow.acceptance.substeps.accuracy` 保留历史失败判定，尚未取得可替换它的原生验收回执。

此记录确认外部精度通过；性能见[性能记录](performance-external.md)。2026-10-08 用户在提供两类结果后明确确认适配完成，项目完成状态及保留限制统一见[适配总结](adaptation-summary.md)。外部验收不伪装成项目原生回执。

本地校验：YAML 解析、分数复算及历史原生状态保留检查通过，`git diff --check` 通过。2026-10-08 的 `./scripts/audit-workspace --repository-only` 返回 12 项 profile revision 错误、78 项待复核；其中本工作区仍绑定 profile v4，而当前 profile 为 v6，必须复核证据，未为消除审计错误而修改版本或刷新历史绑定。审计未执行远端验证；上述外部文件检查由独立的只读 SSH 操作完成。
