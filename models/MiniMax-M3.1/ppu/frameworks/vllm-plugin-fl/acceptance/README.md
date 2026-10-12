# 适配验收索引

**本次适配已完成，2026-10-08 用户确认验收。** 当前交付结论和完整进展见[适配总结](adaptation-summary.md)。

| 项目 | 本次验收结果 | 记录 |
|---|---|---|
| GPQA | **168/198 = 84.8484% ≥ 80.9%，通过**；零 timeout、零空响应 | [外部精度](accuracy-external.md) |
| 性能 | **已完成并由用户接受**；4K/16K/32K 三场景九轮、零失败；输出吞吐 113.97/98.62/170.02 token/s | [性能数据](performance-external.md) |
| ERQA | 228/400 = 57.0%，回答和推理无 U+FFFD；未指定阈值 | [外部结果](accuracy-external.md) |
| 模型服务与收尾 | TP16、204800、64、decode-full；脚本已提供，由用户自行启动；本地总结和完成字段已同步 | [总结](adaptation-summary.md) |

项目完成依据为用户验收及已核验的外部结果。原生回执、历史版本绑定和交付形式的限制继续如实记录；原生工具字段未伪造为全项通过，不自动安排新评测。

## 历史原生验收与服务记录

下文保留当时的 88% 阈值、失败、脚本哈希、服务状态和门禁判断，不能作为本次最新项目进展。当前外部精度采用用户指定的 80.9% 阈值；本轮用户已确认精度与性能结果足以完成适配。

**2026-10-01 14:58 状态变更：**下文 SHA-256 `c03db886...` 的根脚本及服务证据为历史已验证版本。用户修改后的 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh` SHA-256 是 `5bd834658772572f5ebc39ff56be5bb168ca9cf255d8cd299e56fb7120aca124`，仍为 TP16/204800/64，但日志改写到根目录 `service.log`，不满足 `04-runs/` 约束，尚未取得新版本的最终启动脚本验收结论。用户将自行启动；本任务启动的服务已退出，8025 空闲，容器仍运行。TP8 探索性服务曾启动并报告 KV cache 411520 tokens、完整多模态预热和 6/6 decode 图；用户叫停后未做 TP8 请求验证或改变最终 TP16 配置。

当前 Host `PPU-07` 的[执行模式](execution-mode.md)已通过 `decode-full`；[固定十并发简单题预检](sanity.md)10/10 正确、服务健康，原生回执在 `/mnt/nfs/users/jinghao/minimaxM3.1/04-runs/service-sanity-no-monitor-20260930/framework-check.json`。Diamond 原始前十道高难题另有 8/10 失败诊断，保留在原始运行目录，不当作简单题预检，也不删去正式数据集题目。

[正式精度](accuracy.md)已运行 Diamond 198 题并完成样本校验，但严格匹配为 163/198 = 0.8232323232，低于冻结阈值 0.88，原生回执明确失败。失败后两轮固定十题单变量采样诊断分别得 3/10 和 8/10，未找到可替换原始冻结配置的可信依据，详见[问题 005](../adaptation/005-gpqa-first10-two-errors.md)。在精度达标前，性能、证据汇总、最终启动脚本和复盘均不得标记通过。[验收计划](plan.md)保留原始冻结配置及失败路径。

用户要求增大生成上限后的[60k 全量重测](accuracy-gen60k.md)已完成：新服务 65,536 上下文、`decode-full` 图与十并发预检通过；198 题样本合同有效、零 timeout，但 strict **164/198 = 0.8283**，仍低于冻结的 0.88。旧 45k 的 163/198 仅净增 1 题，新轮次 34 道错误中 26 道未触及 60k 上限。两轮失败证据与状态均保留；精度门禁仍阻止正式性能和证据汇总。

用户指定 MiniMax-M3 采样参数的[全量对照](accuracy-sampling.md)已完成：`temperature=1,top_p=0.95,top_k=20,max_gen_toks=60000`，题集、服务、32 并发、0.88 阈值与 60k greedy 轮次相同。原生样本合同有效、零 timeout，strict **167/198 = 0.8434**，比 greedy 净增 3 题但仍未达标；17 题转对、14 题转错。精度门禁仍阻止正式性能和证据汇总。

根目录脚本位于 Host/容器同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh`，2026-10-01 核对 mode `0755`、同 inode `29236341840` 和 SHA-256 `c03db886fc93600b0ab1202bc70629ec3d66476f4382cdccb2996cbe264d3bdc`。该脚本独立启动 204800/64 服务，自动加载 `fl`、完整多模态预热、6/6 decode-full 图捕获、API 健康 200、模型元数据上限 204800。两题报告 `04-runs/service-smoke-204800-full-mm-root-20261001.json` SHA-256 `2dc9bb269817475c90e2b7ac9c59512e811050fcf525ba2732b936af179efbdc`；约 201652 prompt tokens 的长请求报告 `04-runs/context-natural-202k-full-mm-root-20261001.json` SHA-256 `64333785c9348705e26ba74cc117c64185279bc18d52f1e58ca8c04d650cbbe6`，均正确。脚本语法、映射和占用端口拒绝通过，验证后服务仍健康。默认预热触发 FlagGems 3D 卷积 PPU 非法内存访问；同时排除 `conv3d,cudnn_convolution` 后可完整预热，根脚本已去掉 `--skip-mm-profiling`，证据与限制见[问题 009](../adaptation/009-context-204800-mm-profile.md)。最终服务五个多模态请求均 HTTP 200，答案 4/5 正确；红图误答见[问题 010](../adaptation/010-red-image-color-error.md)，报告 `04-runs/mm-requests-204800-full-mm-root-20261001.json` SHA-256 `e3951305365ca93bee3ac1770c6d12255b1c9df2d232198e3135dcec2d70a2a7`。100k 历史失败证据保留在[问题 007](../adaptation/007-context-100k-capacity.md)。`framework.yml` 绑定的环境、执行模式、预检和全量精度原生回执均来自此前 65k 配置；本轮 204800 是单独的容量与多模态请求验证，尚无该配置的正式全量精度回执，不替代冻结的 GPQA 精度、性能或正式证据汇总。精度门禁仍未通过，不标记整项验收完成。
