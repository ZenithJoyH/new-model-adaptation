# MiniMax-M3.1 / PPU-07 / vllm-plugin-fl

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。 **2026-10-08 用户确认的完成结论保持 complete，不自动继续评测。**

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

**当前项目进展：已完成，2026-10-08 用户确认验收。** 已实现 W8A8 适配和 TP16 服务，用户提供的精度与性能文件已核验并归档；完整进展、实现、问题处理、服务配置及保留限制见[适配总结](acceptance/adaptation-summary.md)。

| 项目 | 本次结果 |
|---|---|
| 服务方案 | TP16 / BF16 / 204800 上下文 / 64 序列 / FULL_DECODE_ONLY |
| GPQA | **168/198 = 84.8484% ≥ 80.9%，通过** |
| 性能 | 4K/16K/32K 输入、1K 输出、64 并发，输出吞吐 **113.97 / 98.62 / 170.02 token/s**；三场景九轮均零失败，用户接受 |
| ERQA | 外部 **228/400 = 57.0%**，回答和推理文本均无 U+FFFD；本任务另一次专项复测为 57.5%，两轮独立保留 |
| 本地状态 | 模型 `status: complete`，平台和框架 `project_completion.status: complete` |

[精度记录](acceptance/accuracy-external.md) · [性能记录](acceptance/performance-external.md) · [验收索引](acceptance/README.md) · [源码审查](adaptation/README.md)

框架 `status: functional` 是能力成熟度；原生验收字段保留历史回执状态，不冒充 `optimized` 或原生全项通过。本次用户确认的完成结论已单独落到结构化进展字段；原生证据、profile 版本及交付形式差异作为总结中的维护限制保留，不再表示当前任务尚未结束。

## 历史过程与验证记录

以下是各日期的原始观察和当时结论，其中“当前”“未完成”“端口空闲”等仅指记录当时。项目最新结论以上述完成状态及适配总结为准。

**2026-10-03 图像预处理补丁审查：**远端 `minimax-m31-reference-image-preprocessing.patch` 尚未应用，当前服务不受影响。补丁提出的 2016 长边、168 短边及 28 像素对齐公式，在 ERQA 400 题、630 张图片上预测的 image token 数与原 NVIDIA 服务记录 **400/400 一致**，总 prompt token 差也 **400/400 一致**；CPU 子进程的图片处理和计数检查通过。它可补齐已测图片的几何/token 差异，但像素数值、TP16 服务启动、资源占用及精度收益尚未验证。补丁会全局修改共享 MiniMax M3 处理器，并把最大图片 dummy 的视觉 token 上界提高 9 倍，因此不直接投入当前服务。证据和适用范围见[问题 012](adaptation/012-reference-image-preprocessing-review.md)。

**2026-10-02 ERQA 诊断与全量复测：**用户提供的原 400 题 PPU-07 结果中，381 题包含替换字符 `�`。已取得固定版本的 [FlagEval/ERQA](https://huggingface.co/datasets/FlagEval/ERQA) 全套 630 张真图，沿用原 400 道题干，在用户运行的 TP16 服务上以 **32 并发**、`temperature=1,top_p=0.95,top_k=20,max_tokens=32768` 完成重测：**230/400（57.5%）正确，0/400 含替换字符 `�`，400/400 HTTP 200，22 题触及输出上限**。逐题文件与汇总已独立核对；完整结果 `04-runs/erqa-full-temp1-p95-k20-c32-20261002/summary.json` SHA-256 `2ee727748123fc2d1b4e041bc36d10178ed8d77912f061c674dbb650a1e78ab9`。原评测参数和图片字节缺失，故不能把这次数值改善严格归因于单个采样参数；它是 ERQA 专项诊断，不改变 GPQA 正式精度门禁。服务未停启，用户脚本、Plugin、vLLM、FlagGems 均未修改；配置、限制及可复现路径见[问题 011](adaptation/011-erqa-garbled-generation.md)。当前服务脚本 SHA-256 `56e745991d3dcc9878f314f56bcf42155d01c395066e713003e079a3f15c47f1`，其日志仍写工作根 `service.log`；本轮不将其认作已完成最终 launcher 验收。

**2026-10-01 14:58 当前状态：**用户原位修改根目录 `start-model.sh`，SHA-256 为 `5bd834658772572f5ebc39ff56be5bb168ca9cf255d8cd299e56fb7120aca124`。新脚本仍为 TP16/204800/64，却把日志写入工作根 `service.log`，不符合本工作区 `04-runs/` 目录约束；以下 `c03db886...` 的完整启动及请求验证均为修改前版本，不自动证明新脚本通过最终检查。用户要求自行启动；本任务启动的 TP16 进程已退出，8025 空闲，容器仍运行。应待用户版本的实际服务与日志路径核验后再更新正式脚本结论。TP8 单变量探索已证明 48/48 分片、完整多模态预热、6/6 decode 图和健康接口可启动，但只有 411520 tokens KV cache；按用户指令在请求验证前停止，未切换最终 TP16 配置。

2026-09-30 在 `PPU-07` 的 `minimaxM3.1` 容器上核实目标 W8A8 权重、48/48 shard、TP16 PPU 拓扑、同 inode 的 Host/容器工作根和 editable Plugin。用户授权后 FlagGems 干净快进至 `6b49cff993956bff8cef495abd84f2acb6a63df6`；旧 MiniMax-M3 推理服务单独停止，旧及当前适配容器始终运行。模型架构、当前 Plugin 修改后的原生环境身份回执已通过验证。

Plugin 实现了 M3.1 compressed-tensors 映射、split SwiGLU-OAI INT8 MoE 路径，以及仅 PPU/topk=16 的上游 prefill top-k 固定 JIT workaround。单卡数值、18+3 项聚焦测试及 TP16 eager 真实聊天通过。FULL 图首试被 vLLM 两个 MiniMax 后端自动降为 decode-full；显式 `FULL_DECODE_ONLY` 完成 6/6 图捕获，三个变输入聊天输出正确。精确配置、日志、哈希、限制和退出条件见[适配问题索引](adaptation/README.md)。

[验收计划](acceptance/plan.md)冻结 GPQA Diamond 198 题、strict ≥0.88。当前适配、执行模式和[固定简单题小批量预检](acceptance/sanity.md)取得 PPU-07 原生通过回执，状态为 `functional`，正式图级别 `decode-full`。全量精度三轮均有完整有效样本、零 timeout：初始 45k greedy [163/198](acceptance/accuracy.md)，65k 服务 60k greedy [164/198](acceptance/accuracy-gen60k.md)，相同服务与 60k 上限的 MiniMax-M3 采样参数 `temperature=1,top_p=0.95,top_k=20` [167/198](acceptance/accuracy-sampling.md)。最高 84.34% 仍低于 88%；新采样轮次相对 60k greedy 有 17 题转对、14 题转错，不能将低分全部归因于生成上限。十并发简单题旧服务无轮询耗时 48.3 秒，相比串行 34.6 秒；新 65k 服务重复预检 10/10、健康正常。真正 PR 目标分支待准备 PR 时确认。性能和正式证据汇总因精度门禁尚未执行，不宣称整项适配完成。远端工作根 `/mnt/nfs/users/jinghao/minimaxM3.1`；用户参考补丁保持原样，未提交、推送或创建 PR。

用户要求的服务脚本位于 Host/容器同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh`，2026-10-01 验证 SHA-256 `c03db886fc93600b0ab1202bc70629ec3d66476f4382cdccb2996cbe264d3bdc`、mode `0755`、同 inode `29236341840`、容器语法和端口占用拒绝退出码 1。它独立启动 BF16/TP16、`max_model_len=204800`、`max_num_seqs=64`、prefix cache enabled、`FULL_DECODE_ONLY` 服务，自动加载唯一外部平台插件 `fl`；完成完整多模态预热和 6/6 decode 图捕获，`/health` 200、`/v1/models` 报 204800。两道短题正确，报告 `04-runs/service-smoke-204800-full-mm-root-20261001.json` SHA-256 `2dc9bb269817475c90e2b7ac9c59512e811050fcf525ba2732b936af179efbdc`；约 201652 prompt tokens 的长请求正确，报告 `04-runs/context-natural-202k-full-mm-root-20261001.json` SHA-256 `64333785c9348705e26ba74cc117c64185279bc18d52f1e58ca8c04d650cbbe6`。验证后服务与容器持续运行。

204800 的默认多模态预热在 FlagGems `conv3d_forward_kernel` 报 PPU 非法内存访问。仅排除 `conv3d` 后，T-Head FlagGems 的 `cudnn_convolution` 又把 5D 输入转回同一 kernel；同时排除 `conv3d,cudnn_convolution` 后，完整预热与图捕获通过。根脚本采用这个经过单变量验证的运行配置，不再带 `--skip-mm-profiling`。这是当前 PPU/软件版本的 workaround，确切的内核越界条件尚未定位，见[问题 009](adaptation/009-context-204800-mm-profile.md)。脚本与实际 API 进程均无 `VLLM_PLUGINS`、`TMPDIR`、XDG、FlagGems、Triton 或 Torch 显式缓存环境；容器默认缓存首次编译较慢，见[问题 008](adaptation/008-default-cache-cold-start.md)。此前 100k 失败记录保留在[问题 007](adaptation/007-context-100k-capacity.md)，不能再当作当前容量结论。

同一组 5 个多模态请求在最终根服务上均 HTTP 200：蓝图、数字 OCR、双图顺序和八帧视频答对，纯红图仍误答“绿色”，因此为 **4/5 答案正确**，不是多模态精度通过；报告 `04-runs/mm-requests-204800-full-mm-root-20261001.json` SHA-256 `e3951305365ca93bee3ac1770c6d12255b1c9df2d232198e3135dcec2d70a2a7`，具体缺陷见[问题 010](adaptation/010-red-image-color-error.md)。`FULL_AND_PIECEWISE` 当前未作为通过图级别：MiniMax 自动启用 breakable graph，使编译模式为 `NONE`、`splitting_ops=[]`，只改图模式不能形成 prefill piecewise 图，详见[问题 004](adaptation/004-full-graph-backend-coverage.md)。既有 `framework.yml` 原生回执绑定此前 65k 配置；204800 尚未重跑正式 GPQA，先前最好成绩 167/198＜0.88，性能和整体验收未完成。
