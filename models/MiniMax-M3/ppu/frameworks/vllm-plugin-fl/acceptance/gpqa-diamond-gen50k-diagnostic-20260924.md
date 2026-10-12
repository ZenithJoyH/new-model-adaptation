# PPU-07 MiniMax-M3：GPQA Diamond 50K 全量诊断结果

2026-09-24 在 `PPU-07` 的新代码服务上完成 198 题全量诊断。`exact_match,strict-match` 为 **178/198 = 0.898989898989899**，零超时、零空响应、零样本错误；此分数高于用户本轮指定的 **0.88** 门槛。结合算子、Plugin 测试及 eager/目标 graph 实推，本轮 **PPU-07 新代码重新适配的功能与 GPQA 88 分目标可判定通过**。但本轮配置在启动前冻结的 minimum 是 **0.80**，不能把事后指定的 0.88 反写为原生验收标准。两次 lm-eval 尝试都返回 0，外层 runner 却因配置字段冲突退出码 1，`acceptance-result.json` 状态为 `failed`；这一工具回执及未完成的正式验收门禁仍须如实保留。

## 运行身份与冻结输入

- 模型服务：容器 `minimaxM3-latest-20260924`，ID `274609df1ca78264c1af0327ef1aa255f4e7be1ae164dd5d963fbd73a517f116`；`127.0.0.1:8024`，TP16、BF16、`max_model_len=65536`、prefix caching 开启，显式 `FULL_AND_PIECEWISE`（decode FULL、mixed prefill-decode PIECEWISE）。服务日志：`/mnt/nfs/users/jinghao/minimaxM3-new/04-runs/validation-decode-piecewise-graph-target-20260924.log`。
- 评测容器：`minimax-m3-eval-latest-20260924`，ID `a7727cea25486e9f8eff935d595e808b625dd74d29f9bd7a96de7b28dc48fd19`；FlagEval 镜像 `harbor.baai.ac.cn/flageval/flageval-llmeval:v1`。模型与评测容器的批准工作根均为 `/mnt/nfs/users/jinghao/minimaxM3-new`。
- 源码：Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c`；FlagGems-vllm 运行时为基线 `1f9ac0e0caf3c32111f6be44c8e4d2fef2359546` 加 001 记录的两文件未提交 diff（diff SHA-256 `1acdb40e31b333fd29328574160265fa6051c5b6e7498e7a38d65f418a38a764`）；FlagGems `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`。该同内容修复随后已提交并推送至用户 FlagGems-vllm fork 的 `support-minimaxM3` 分支，提交 `e7a88149c3ca73b23f03f14e9a1bc6b21981015a`；运行容器本身未切换 Git HEAD。
- 冻结配置：`03-acceptance/gpqa-full-c64-gen50k-20260924.json`，SHA-256 `03182d8c03d71759ed9088426e42480c138874122059d2e9f201e9c603ebab20`；`gpqa_diamond_generative_cot`，198 题、64 客户端并发、`max_gen_toks=50000`、seed 42、`allow_timeouts=true`，冻结 strict minimum `0.80`。项目精度 Skill bundle SHA-256 `5ba2c9b96040324baf067405c53ff48528ae463b2dcd06f0a062ce57ac3885ca`。
- 数据集：评测容器的 `Idavidrein/gpqa` / `gpqa_diamond` / `train` 缓存只读映射，Arrow SHA-256 `501f307f9e8bc34041af4120c8eb5a735f0ea29cd83c90167b913651071bb4c4`。评测预检通过。

## 原生结果与失败边界

- 原始根：`/mnt/nfs/users/jinghao/minimaxM3-new/04-runs/gpqa-diamond-c64-gen50k-20260924/`；其中 `exit-code.txt` 为 `1`，`runner.log` 保留全部运行记录。
- 原生回执：`outputs/minimax-m3-ppu07-latest-gpqa-diamond-c64-gen50k/gpqa-diamond-c64-gen50k-20260924/acceptance-result.json`，SHA-256 `328d7ab865cf40bedac082ed9821c573debd6e5035dd1da7712369c21a752066`，`status=failed`。
- `attempt-1` 与 `attempt-2` 各有 396 行（每题两个 filter）、198 个唯一 `doc_id`、198 条 strict 样本、178 条 strict 正确；两次均零 timeout、零错误字段、零空响应。`attempt-2` 原生结果 JSON SHA-256 `0eea9e5905005383d3fec33de1ec6c5fd563c70ad6204898b9b235e2235b4ff8`；样本 JSONL SHA-256 `6045bf0d04d8a8ec8f5b21b9f9616ee6b3f6af43b05ff4ea9649a8b0efaf97d6`。`attempt-2` 原生 strict 值 `0.898989898989899`，与 178/198 一致。
- 失败签名：`use either datasets or legacy dataset_path fields, not both`。配置源文件只使用 legacy `dataset_path`；runner 正规化后同时保留 legacy 字段并生成 `datasets`，结果校验再次检查时拒绝两者并存。两次 lm-eval 进程 `returncode=0`，但外层结果校验失败，不能把 runner 退出码或回执改称通过。实时 score sidecar 末尾的缓存 schema 不匹配也不能覆盖最终 lm-eval JSON。
- 固定前十题是另一次 `max_gen_toks=30000` 的 run，strict `9/10`，不满足逐题全对 sanity。用户知情后授权继续本次**诊断**，并指定 50,000 生成 token；全量分数不能替代该 sanity 结论。
- 2026-09-24 本地只读门禁 `./scripts/adapt-model MiniMax-M3 --platform ppu --framework vllm-plugin-fl --hosts PPU-07 --steps acceptance --acceptance-substeps accuracy --check-only` 返回“accuracy 前置 architecture 未完成”。`framework.yml` 的 architecture/environment/adaptation、execution-mode/sanity 等正式回执尚未完成，performance 和最终最小启动脚本亦未验收。

## 结论与后续

本轮判定 **PPU-07 新代码重新适配的功能与 GPQA 88 分目标通过**，限定为本次诊断结论，不扩展为其他硬件平台或项目正式验收通过。正式验收仍需依顺序完成前置阶段、修复并重新验证十题、修正 runner 配置/校验冲突、在测试前冻结 0.88 的正式阈值并获取 `passed` 原生回执，随后完成 profile 要求的性能、证据与最终启动脚本验证。不得复写本轮失败回执或以 Markdown 代替原生产物。
