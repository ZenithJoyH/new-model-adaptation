# 002：图片请求颜色错误及重复标点

## 元数据和完整签名

- 状态：`operator fix verified / PR open / mitigation retained`；2026-10-08 已将 split-KV 合并布局修复应用到实际安装的 FlagGems，34 项聚焦回归及真实 Q/K/V 三次对照通过，已提交关联 issue/PR。Plugin FP32 缓解保留，整模型回归和正式验收未完成。
- 首次出现：2026-09-28；最后核对：2026-10-08。Host `PPU-13`，容器 `minicpmV4.7-1B`，镜像 `sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f`。
- 模型 `/mnt/cpfs/models/MiniCPM-V-4.7/weights/1b`；PPU-ZW810E 物理卡 2，TP1，BF16，eager，最大上下文 50,000，正常开启前缀缓存。
- Plugin 基准 `3a27a6fb2d514cdf55c00481bf813225dac63319` 加本任务 4.7 adapter；vLLM wheel `0.24.0+empty`；FlagGems wheel 5.3.5，源码 checkout `80d0000d93dad55320df06687eb088a5b6dad07d`。
- 服务脚本 `01-environment/eager-start.sh`，日志 `04-runs/eager-v1-20260928/server.log`；启动日志选择 `FLASH_ATTN` 作为 `MMEncoderAttention` backend。

## 对照及原始证据

同一 API 进程 PID 2612（boot ID `e0f88877-608c-4443-a22d-2d773ff175f1`，启动 tick `330252502`）的 `/health` 前后均为 200。文本 `1+1` 请求输出最终答案 `2`，正常停止；224×224 纯红 PNG 请求返回 200，却将图片回答为白色，64 token 长度截止。原始结果为远端工作根下 `04-runs/eager-smoke-v1-20260928/result.json`，SHA-256 `c101f378a687140b6efda1d80c3bbaed30185068033a40bfd0b4e4e895f743ee`。

保持同一服务配置、固定温度与文字选项，改用 448×448 纯红及纯蓝 PNG 各一次，`max_tokens=256`；两次均返回 200，但输出均为连续 256 个 `!` 且长度截止。原始结果 `04-runs/color-v1-20260928/result.json`，SHA-256 `50903c3da46062a537e912d5a200f07d1efe510ae1a2c1e33aacd57e72a3cb38`。两次请求的输入颜色不同，异常输出相同；暂不能判定是非有限 logits、视觉权重、视觉算子、位置、视觉嵌入注入或模型其他路径。

对相同 448×448 红图只采首 token 并请求 top-5 logprobs，得到 `!`，它和另一候选的 API logprob 都为 `-9999.0`。原始结果 `04-runs/logprob-v1-20260928/result.json`，SHA-256 `3274e51bd427bd5c0bc634a28444f1e11547317475a363c50b5cee7d91ef41a0`。此 API 哨兵值支持非有限 logits 假设，但不是对模型张量 NaN 的直接观测。

请求 FULL graph 被 GDN backend 降为 mixed PIECEWISE 后，服务的文本请求仍最终答 `2`，224×224 红图输出 64 个 `!`；原始结果 `04-runs/fullgraph-smoke-v1-20260928/result.json`，SHA-256 `6e9a5e6230d20c2926262bc2f269f27d8f6bc1f3a8e21e20a71ccc12e11f4d60`。graph 降级详见 [003](003-gdn-full-graph.md)，这不是正式 graph 验收。

在空闲物理 PPU3、TP1、BF16、与服务相同的 `FLASH_ATTN` 视觉 backend，单独按 vLLM 4.6 adapter 映射加载本权重的 351 个视觉参数，以 448×448 红图运行视觉 embedding、各层、窗口 merger 和最终 MLP merger，31 个阶段均无非有限值；最终视觉张量为 `[64,1024]`，目标网格 `[16,16]`。记录 `04-runs/vision-finite-v1-20260928/result.json`，SHA-256 `3d9a8a0b7b1ad19ae92ba75705e4099487795498e5328ec465a4a7c39fcf16fa`。这只排除该隔离 TP1 输入下视觉塔的直接非有限值，不证明服务内视觉嵌入、prefill 及 logits 正确。

同一 224×224 红图的 API render 与 checkpoint `AutoProcessor` prompt token 逐个一致，共 91 个；HF 图像 bounds `[[19,83]]`、目标网格 `[[32,32]]`；render 多模态占位 offset 15、长度 69。记录 `04-runs/render-compare-v1-20260928/result.json`，SHA-256 `7b8aadd531cb1245a7551bd434e5aa2200e0eb25d03c12eeeaabee87f34eb069`。它排除 token 序列差异，但尚未逐张量比较实际视觉 embedding。

用同一 91-token 图像的 checkpoint canvas 位置，在物理 PPU3 对照 vLLM `MRotaryEmbedding.forward_cuda` 与 `forward_native`：218/273 个位置元素不同于顺序基线，但 Q/K 最大绝对差均为 `0.015625`，无差值大于 `0.1`、无非有限值；顺序基线同样通过。记录 `04-runs/mrope-compare-v3-20260928/result.json`，SHA-256 `0564060049119d724bb5d1fcf38334ecf345f978c5f3f03753a7259ae5693c6d`。v1/v2 因诊断脚本未设 vLLM config / 未注册架构而停在构造前，失败结果单独保留，不代表算子失败。该孤立 RoPE 对照不覆盖运行中 GDN attention 及其上下文。

显式 decode-full 实例保持相同模型、PPU2、TP1、BF16、缓存和端口；图捕获仅 decode FULL 7/7。健康/文本请求通过，文本最终答 `2`，红图仍输出 64 个 `!`。原始 `04-runs/decodefull-smoke-v1-20260928/result.json` SHA-256 `b7de2ee721a2984ed301a8c5b3d21896cb5788acfd870ba7884dd53c717a2580`。同实例只在请求加入 `chat_template_kwargs.enable_thinking=false` 后红图仍输出 64 个 `!`，`04-runs/no-think-image-v1-20260928/result.json` SHA-256 `4b963c0fa2942abd3608941c8d606dc4ba04ce89438d0e1861fc4bae8c79f9ed`；thinking 模式不能解释异常。

checkpoint 原生 `AutoModelForCausalLM` 在物理 PPU3 BF16 对 21-token 文本和相同 91-token 红图分别完整前向，末 token 的整个 logits 向量均为有限值。原生模型在容器的 Transformers 版本下未实现 `MiniCPMV4_7Model.get_input_embeddings()`，诊断 v1 在此处停止；v2 用该模型已有的 `language_model.embed_tokens` 显式提供 `inputs_embeds` 后通过，没有改动权重/源码。记录 `04-runs/hf-forward-v2-20260928/result.json`，SHA-256 `5b5967577064bc731bdd347090cba876dddc162bd24889ad301adf3d95d64913`。其 GDN 因缺少可选 FLA 库使用 torch 路径，此结果只能支持 vLLM 执行路径差异假设。

同 224×224 红图、相同物理 PPU3、BF16，按 Plugin 映射加载的 vLLM 视觉末端 embedding 与 checkpoint 原生 `get_image_features` 的 `[64,1024]` 张量逐元素对照：平均绝对差 `0.00204`、最大差 `0.0625`、无差值超过 `0.1`、两边无非有限值。记录 `04-runs/vision-compare-v2-20260928/result.json`，SHA-256 `c265f8dabdb6d6c9e520ef6cbf356a1413beef83f4f1e70f2bf5eaa2cfd614c9`；v1 因独立诊断沿用已存在的分布式初始化文件而在计算前停下，失败证据保留。该结果将怀疑集中到视觉 embedding 注入之后，但仍需观察实际服务或等价离线引擎。

显式 decode-full 服务中一个无图片的 168-token 文本请求继续产生连贯的算术推理，未出现重复标点；`04-runs/long-text-v1-20260928/result.json` SHA-256 `c2b9db6e7435728623fcb0c39a38b9246d305f79d036af69e2c3162331834edb`。它排除普通的 prompt 长度阈值，但不证明同长度带视觉嵌入时的 GDN/attention 数值正确。

在空闲 PPU3 上以 `VLLM_ENABLE_V1_MULTIPROCESSING=0` 启动独立 vLLM eager 引擎，对同一 224×224 红图仅取首 token，并以一时诊断 hook 检查视觉 embedding、注入后的 91-token embedding、24 层语言模型和最终 logits。返回首 token `So`；53 个阶段记录均无非有限值，logits `[1,248094]` 全部有限。`04-runs/offline-hook-v1-20260928/result.json` SHA-256 `3a07c0e50d4a5328634a667ebcc21f878702925666d5aa5ce8ef918f2cb7f98e`。该离线测试与 PPU2 API 服务同时改变了物理设备、单进程形式、并发容量和显存比例，尚不能确定哪一项造成差异。诊断过程代码保留在本工作根 `02-issues/`，没有进入 Plugin 产品源码。

在相同 PPU3 离线 eager 实例连续送入红图、蓝图、红图，每次只取首 token，`04-runs/offline-hook-v2-20260928/result.json` SHA-256 `823d3e3303501c952692d31b19f993d15048143760b6dd324db2b24beacd0c23`。第一张红图返回 `So`，视觉 embedding、24 层和 logits 全部有限；蓝图返回 `!`，`embed_multimodal.0` 的 `[64,1024]` 元素全部非有限，`compute_logits` 的 `[1,248094]` 元素也全部非有限；重复红图恢复 `So` 且全部有限。这在同一设备和模式下复现图片错误，并将最早已观测异常推进到视觉 embedding 输出；蓝图与红图同时改变了颜色和请求顺序，尚需分离。红图重复可能命中已有视觉缓存，不能证明重复计算稳定。

保持设备/请求序列/离线 eager 配置，在同样的过程诊断中只增加视觉 embedding、27 层 encoder、窗口 merger、最终 merger 的逐层 hook。`04-runs/offline-hook-v3-20260928/result.json` SHA-256 `c066056b77ef23c4b5da5a7e7615fffa9b76b43816f8536c264bf0be42d28b47`：默认 `FLASH_ATTN` 视觉 backend 下，本次首张红图已在 encoder 第 9 层首次出现非有限值，蓝图在第 7 层首次出现，两个请求的 logits 都全部非有限，重复红图的已缓存视觉结果同样非有限。和 v2 相比，失败首次出现的图片/层次变化，暂不能归咎于固定颜色或仅第二次请求；逐层同步和 backend kernel/调优状态都可能影响复现。无需将“!”解释为采样器本身的根因。

只把离线引擎的 `MMEncoderAttention` backend 改为 `TORCH_SDPA`，保持 PPU3、TP1、BF16、eager、同序列及同 hook。日志核实有效 backend 为 `AttentionBackendEnum.TORCH_SDPA`，但红图仍在视觉第 9 层、蓝图在第 7 层首次出现非有限值，输出均为 `!`；数值和非有限计数与默认 FLASH 对照相同。原始 `04-runs/offline-sdpa-v1-20260928/result.json` SHA-256 `b4e9a371f1d566666a090725ba72a3dab61781b90f48f7277db8a15ffde461ad`。因此切换该后端没有修复本签名，不能将其保留为 workaround；与 35B 历史记录的 SDPA 失败相符，但此结论由本 1B 独立实测建立。

再只增加出错层附近子模块 hook，保持默认 FLASH 与相同红/蓝/红序列。`04-runs/offline-deep-hook-v1-20260928/result.json` SHA-256 `7a9574c220460575aed81168fd8f01de7d6ef26644334aaed19613e70ac90829`：红图第 9 层的 `layer_norm1` 和 `qkv_proj` 全部有限，`self_attn.attn` 首次出现 246 个非有限元素，随后 `out_proj` 扩散；蓝图第 7 层的 `layer_norm1` 和 `qkv_proj` 全部有限，`self_attn.attn` 首次出现 258,048 个非有限元素。相同根因边界指向 `MMEncoderAttention` 实际计算，而非视觉权重加载或后续 MLP。它尚不区分该调用内 backend kernel 与其输入布局/步幅契约问题。

保持 PPU3、BF16、离线 eager、红/蓝/红顺序及同一 hook，只在一时诊断脚本 `02-issues/offline-reference-attn.py` 中把视觉塔每层 `MMEncoderAttention.forward` 替成显式 FP32 QK 矩阵乘、缩放、softmax、PV 矩阵乘，再将输出转回 BF16。共 54 次参考调用均有限；红、蓝两张未缓存图片的视觉阶段与 `[1,248094]` 最终 logits 均无非有限元素，首 token 都为 `So`，重复红图同样有限。原始结果 `04-runs/offline-reference-attn-v1-20260928/result.json` SHA-256 `d0ca874ec3393c1c19efebe3caec5905c4a057333e068ebcfc5b16dfff61c0dd`。这是受控诊断，支持 attention 数值/实现路径为故障边界；只取首 token，尚未证明答案正确，也没有验证服务或 graph。

将上面的同一路径仅延长为 64-token 生成，红图推理和最终回答均判为红色、蓝图均判为蓝色；两图视觉阶段及 logits 仍全有限。`04-runs/offline-reference-answer-v1-20260928/result.json` SHA-256 `d154549b03df1a974ede137950c3acf3817f9cd88cae0505375e74159520a015`。因此 FP32 参考路径提供了本颜色样本的有效修复证据，但仍属一时诊断而非产品实现或正式准确率。

再只将 Q/K/V 按 head 转置后 `.contiguous()`，保留 BF16 `torch.nn.functional.scaled_dot_product_attention` 和同一 prompt、hook、生成长度：首张红图虽有限，但回答白色；蓝图仍在第 7 层 attention 首次产生 77 个非有限元素，最终 logits 全部非有限，输出 64 个 `!`。原始 `04-runs/offline-contiguous-v1-20260928/result.json` SHA-256 `fe6bc59d4a019b84cf130d6b60790a9e974893cecd6a8d359a84a72461184072`。输入步幅记录为 `[[3538944,3456,72,1]]` 三组；单独连续化不足以修复，不能保留为 workaround。

在同一连续化 SDPA 对照上只将 Q/K/V 转成 FP32，SDPA 输出再转回 BF16：红/蓝/红的 54 次 attention 调用、视觉层及最终 logits 全有限，回答分别判为红/蓝/红。原始 `04-runs/offline-fp32-sdpa-v1-20260928/result.json` SHA-256 `af61af801d5453e7325355a7f11cdc6697829065a70569f3e3a04f28c30979ac`。首次红图用时 337.717 秒（含路径首次编译/预热），蓝图 13.516 秒、重复红图 8.044 秒；显式 FP32 matmul 参考对应为 51.303、13.462、8.004 秒。两次独立离线运行不能视为正式性能比较，但 FP32 精度而非单独连续化是当前故障的关键对照变量。

将显式 FP32 参考路径的 Q 分成最多 256 token 的块，仅收紧中间 score 矩阵大小；保持其余模型、设备、顺序、hook 和生成参数，红/蓝/红结果仍分别判为红/蓝/红，54 次 attention 调用、视觉输出与 logits 全有限。用时 50.241、13.538、8.051 秒。`04-runs/offline-chunked-v1-20260928/result.json` SHA-256 `d982d3f8eef59b0c6e5acc20facf20245ec7787e4fa76a35e8ad9fb47d3d4187`。这一受控结果支持将分块 FP32 attention 作为 T-Head 专用产品实现候选，还需按 vLLM OOT 扩展契约验证 packed segment、GQA、eager 与 graph。

2026-09-29 在已核实的 editable Plugin `/workspace/vllm-plugin-FL` 添加 T-Head 专用 `vllm_fl/dispatch/backends/vendor/thead/mm_encoder_attention.py`，从 `vllm_fl/ops/custom_ops.py` 的现有 OOT 注册时机注册 `MMEncoderAttention`，没有修改 vLLM 或 FlagGems 源码。该实现将 Q/K/V 转 FP32、按最多 256 个 query token 分块计算非因果 attention、输出转回原 dtype，并处理 packed segment 和 GQA；这是平台数值缓解而非模型名判断或 PPU 内核根因修复。最初放在厂商 `impl/` 包下时，包初始化会导入当前 vLLM 版本缺少的 `flash_attn_supports_fp8`，测试收集失败，原始 `04-runs/plugin-thead-tests-v1-20260929/result.json` SHA-256 `d38ec532ac7a99a007629a3ab465d4d70fda7a0e43bac33691d1e334a75c8fe5`。将本任务新文件移至厂商包上一级并更正两处导入后，5 项聚焦测试通过（含 canvas 3 项与 attention packed/GQA 2 项），`04-runs/plugin-thead-tests-v2-20260929/result.json` SHA-256 `f4efbaeb0ce97bdaaf8bad92043442d79258bd8cd1dd38a61b5213788afd43c7`。

不再注入诊断替代，离线 vLLM eager 实例实际创建 `TheadMMEncoderAttention`。相同红/蓝/红 224 图像给出正确颜色，逐层 hook 和最终 logits 均无非有限值；`04-runs/offline-product-attn-v1-20260929/result.json` SHA-256 `1ce0de03f83e4c20167d2f766e6f0f289e6446e56cfe3a5fe8002fea1b0b2baf`。停止本任务旧 decode-full API 前核实 PID 65592、启动 tick `330787672`、命令哈希、子进程和在途请求为零；SIGTERM 后 PID/子进程消失、端口健康不可用，容器仍运行。原因、命令、结果保存在 `04-runs/decodefull-v1-20260928/stop-result.json`，SHA-256 `5fc3c3bf6fc7abb38c42a834046f0ee1e9772f24e4a4fb0e370fe000bef2ea23`。

新 Plugin 源码下的 PPU2 decode-full 服务脚本 `01-environment/decodefull-product-start.sh` SHA-256 `e36428e175e98a2bb424e1bc1e6b8a7dc2c07efdc0aa93915ed48ce035013923`，日志 `04-runs/decodefull-product-v1-20260929/server.log` 显示 decode FULL 图捕获 7/7、正常启动，前缀缓存开启。API PID 108085、启动 tick `337095994`、命令哈希 `de005c1cebe1acd8a90935259fddd9078fcf8e6e04e260c09ebe1d61c16abd59` 前后不变；文字 `1+1` 最终答 `2`，224 和 448 红/蓝图均正确区分颜色，全部 HTTP 200、正常结束。原始 `04-runs/decodefull-product-smoke-v1-20260929/result.json` SHA-256 `70bddc4172c7d3c53c0a18e1eb1b2a54ff59b47516896e3c809529e9bc9a2a8a`。这是基本功能和图模式回归；十并发固定题、正式准确率和性能仍需按 profile 原生流程验收。

源码审查后将新 `forward_native` 缓解限定为 BF16 输入，其他 dtype 委托上游 vLLM 原实现，避免扩散到未验证的 FP16/FP32 视觉模型；保留 T-Head 厂商身份守卫和已有 OOT 注册。新增 FP16、FP32 守卫未命中测试后，聚焦测试 7/7 通过；`04-runs/plugin-thead-tests-v3-20260929/result.json` SHA-256 `332ef7dfffa6b491aaf31206a604eab746d8798a29ce982faa549fd854c07b38`。只停止本任务 PPU2 旧服务 PID 108085，事先核实命令、启动 tick、子进程和零在途请求，停止后进程/端口不可用且容器运行；`04-runs/decodefull-product-v1-20260929/stop-result.json` SHA-256 `47b212b6ca8d12c850f1f7acfb8ce2929611253a4f1a2cf9aa594638ecd6c2f6`。

最终当前源码对应 `01-environment/decodefull-product-v2-start.sh` SHA-256 `49e44f4ae09f1337b42cc25a899ab93eae2c0c43038ee4b141468d0199198f62` 和服务 API PID 109945、启动 tick `337210114`。`04-runs/decodefull-product-v2-20260929/server.log` 显示 decode FULL 捕获 7/7；`04-runs/decodefull-product-smoke-v2-20260929/result.json` SHA-256 `93d564ca9ebd1c0844cd68b06822e1db6b096dd5a6d1a9fa0830b74b60caec6d` 中，文本最终答 `2`，224/448 红蓝图均答对，全部 HTTP 200 且 `finish_reason=stop`，请求前后服务身份和健康稳定。后续验收须绑定此新服务和最终 Plugin diff，不能复用前一服务的原生回执。

同 Host 的 [MiniCPM-V-4.7-35B-A3B 图片故障](../../../../../MiniCPM-V-4.7-35B-A3B/ppu/frameworks/vllm-plugin-fl/adaptation/002-visual-garbage.md)是候选经验：同架构、PPU、eager、PPU 服务在文本可用后发生红图答白、重复 `!` 和首 token logprob `-9999.0`。差别是 35B 为 MoE/TP2、另一容器与镜像、不同 Plugin adapter 和模型权重；其 SDPA 对照仍失败、TP1 视觉子路径有限值，不构成本 1B 的根因证明。本任务需重新验证。

## 下一步受控诊断

继续审查 T-Head OOT 扩展对其他视觉模型、非 BF16 dtype、较大 packed 序列和高分辨率图像的影响；区分当前缓解与底层 BF16 SDPA 的真正算子根因。后续按 profile 完成 execution-mode、十并发 sanity、正式精度和性能；当前颜色基本检查及 HTTP 200 不能替代正式准确率或性能回执。

## 2026-09-29 最终差异审查和十并发诊断

确认的 Plugin 基点为 `3a27a6fb2d514cdf55c00481bf813225dac63319`，当前 HEAD 未变；两处跟踪文件和四个未跟踪文件均为本任务差异，`git diff --check` 无误，未发现继承修改。T-Head OOT 文件 SHA-256 `0f3ab3d2e9141aa2295d73cf40b9a3f06245bae6f68ef7e29ab7f42c334fe885`，注册调用文件 SHA-256 `4dc6ce00467c00958bd66eb7e4d14f334712496c8451b10e7dc67725d364c4eb`。影响矩阵：T-Head BF16 `MMEncoderAttention.forward_native` 使用显式 FP32 分块路径；T-Head FP16/FP32 委托 vLLM 原实现；非 T-Head 不注册该 OOT；vLLM 和 FlagGems 均未编辑。测试覆盖 dense/GQA、packed 分段、FP16/FP32 未命中和当前 PPU 图像 API；其他视觉模型、TP>1、更大网格和视频仍待验证。当前方案属于 mitigation，若上游 BF16 注意力路径经数值回归证明稳定且性能更好，可移除该显式 FP32 分支；底层算子根因仍未证明。

固定十请求多模态诊断 `03-acceptance/multimodal-concurrent-10-v1.json` 含文本、224/448 红蓝绿黄单图和双图，SHA-256 `81ad89a36ca0e391fd0d1891f2f6ccd842819a3da82c8b3184bd7f60951d9b16`。当前服务同配置第一次 10/10 正确、峰值运行 10、76.414 秒（含首次预热）；第二次 10/10 正确、峰值运行 10、14.884 秒，原始回执分别为 `04-runs/multimodal-concurrent-10-v1-20260929/result.json` SHA-256 `e549968ce7659dba49ba5d95db9441797b5b710776327c5626b149c6df2779de` 和 `04-runs/multimodal-concurrent-10-v2-20260929/result.json` SHA-256 `eb3796fd555355258299e9f32a36d176d3afbf5830256bf59854d44b7626903d`。十请求纯文本对照 10/10、峰值运行 10、8.072 秒，回执 `04-runs/text-concurrent-10-v1-20260929/result.json` SHA-256 `21fc522d4a5eee188ed31904f241e56588bffcfdf7d23bfa1ffd358e4577132c`，该组输出约 500 token。预热和负载差异提示不能把首轮耗时当稳态性能，也不能用两组不同输入的耗时直接计算视觉算子开销；正式性能仍需独立运行。

## 2026-10-08：定位到 FlagGems split-KV 合并输出布局

### 范围与环境

本次继续定位 `mm_encoder_attention.py` 所缓解的视觉问题，选用当前 active `vllm-plugin-fl` profile v6 的适配阶段诊断。Host、容器、镜像和 `/mnt` 绑定映射重新核实，与本记录一致。使用空闲物理 PPU3；PPU2 服务及产品文件未更改，未重跑正式精度。torch 2.10.0、vLLM 0.24.0+empty、Plugin 0.3.0rc2.post1+g3a27a6fb2、FlagGems 5.3.5，实际 FlagGems 为普通安装 `/usr/local/lib/python3.12/site-packages/flag_gems`。没有通过 `PYTHONPATH` 选取其他源码。

独立 eager 引擎沿用 TP1/BF16、上下文 50,000、max_num_seqs=4、前缀缓存开启、显存比例 0.4。本次显式排除 `nonzero_numpy,index,_index_put_impl_`，隔离其他已知缺陷；其余算子正常注册。仅在诊断进程内恢复上游 `MMEncoderAttention.forward_native`，捕获首个非有限 attention 输出后主动停止。

### 实际调用链与真实失败输入

确认调用链：`CustomOp.forward_oot → forward_native → _forward_sdpa → vllm.torch_sdpa_wrapper → F.scaled_dot_product_attention → aten::_scaled_dot_product_flash_attention → FlagGems flash_attention_forward → mha_fwd → split-KV → flash_fwd_splitkv_combine_kernel`。

日志中的 `AttentionBackendEnum.FLASH_ATTN` 只是配置值；本次通过 Python 调用记录和 CPU profiler 确认了实际进入的 FlagGems 函数。历史切换视觉 backend 仍失败，与 OOT 的 native 分发一致，不能据 backend 名称推断真正执行路径。

**启用入口补充（2026-10-08）：** `VLLM_FL_USE_FLAGGEMS_ATTN=1` 控制 Plugin `dispatch/backends/flaggems/flaggems.py:179–187` 是否选择 `AttentionFLBackend`；未开启时该选择器返回 vLLM `TRITON_ATTN`。本次视觉故障经 PyTorch SDPA 的 ATen 注册进入 FlagGems，与该 backend 开关分别控制。

`utils.py:136–145` 的全局 `use_flaggems()` 默认返回 True（受 `USE_FLAGGEMS`、`VLLM_FL_PREFER_ENABLED`、`VLLM_FL_PREFER` 的显式配置约束）；`worker/worker.py:258–288` 据此调用 `flag_gems.enable()` 或 `only_enable()`。已安装 FlagGems 注册表包含 `aten::_scaled_dot_product_flash_attention`，因此 PyTorch SDPA 选到该 ATen op 时可以执行 FlagGems 实现，无需设置 attention backend 专用环境变量。

本次捕获脚本在**独立诊断进程**中移除算子白名单，设置 `VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy,index,_index_put_impl_`；其余注册包含该 flash ATen op。单算子对照使用 `flag_gems.use_gems(include=['_scaled_dot_product_flash_attention'])` 显式注册。实际调用日志 `04-runs/vision-capture-20261008-v1/enabled-ops.txt` 同时记录 `GEMS _SCALED_DOT_PRODUCT_FLASH_ATTENTION` 和 `GEMS FLASH_ATTENTION_FORWARD`。本轮没有改动服务启动脚本或其白名单；恢复原 BF16 attention 以复现的结果，不表示保留 FP32 缓解的现有服务仍执行该故障分支。

红图 27 层输出均有限；随后蓝图在第 7 层首次产生 **542 个非有限元素**。原始 Q/K/V 均为 BF16 `[1,256,1152]`，stride `[884736,3456,1]`，storage offset 分别为 `0/1152/2304`；全部有限，最大绝对值分别为 `9.5/6.125/3.578125`。按 16 heads、head_dim=72 还原为 `[1,16,256,72]`，保存真实激活用于同输入对照。

### 同一 Q/K/V 的算子对照

以 CPU FP32 显式 QK/softmax/PV 为参考；每条路径运行三次。误差为整张输出的最大绝对差。

| 路径 | 观测 |
| --- | --- |
| 原生 BF16 SDPA 默认 / 强制 FLASH | 三次有限且一致，最大误差 `0.008285` |
| 原生 BF16 MATH / EFFICIENT | 三次有限且一致，最大误差分别 `0.007821 / 0.008706` |
| 只注册 FlagGems `_scaled_dot_product_flash_attention` | 明显错误，有限输出最大误差约 `3.38–3.46`；一次产生 26 个非有限元素 |
| 完整 FlagGems 注册配置 | 重现相同错误；单独 contiguous 仍明显错误 |
| FlagGems FP32 SDPA | 命中 efficient 路径，三次有限，最大误差 `4.53e-6` |
| 直接 FlagGems `scaled_dot_product_attention_forward` | 三次有限，最大误差 `0.008706`，与出错 flash/split-KV 分支不同 |

只启用 math/efficient/overrideable 注册的那些 default 对照仍实际命中原生 FLASH，**不能据此宣称对应 FlagGems 算子已通过**。强制 CUDNN 返回无可用 kernel，作为不支持保留。首次编译/调优耗时不是性能基准。

### 根因与排除的假设

`flash_attention_forward` 将 head_dim=72 补到 96。实测复制区逐元素正确，补齐区全零；补齐产生 `[B,S,H,96]` 连续布局，stride 为 `[393216,1536,96,1]`。本形状实际触发 **n_splits=2**。

`flash_kernel.py:1111` 的合并内核读取的 partial output 是 `[split,B,H,S,D]`。但输出写回使用：

```python
out_ptr += pid * BLOCK_M * head_size
out_offset = row * out_s_stride + dim
```

第一行按 `[B,H,S,D]` 展平定位，第二行混入实际 `[B,S,H,D]` 的 sequence stride；没有从 flattened row 解出 batch/head/sequence，也没有正确使用其 stride。因此连续 BSHD 输出出现重叠写、漏写和超出逻辑输出末端的写回。API 的 `flash_api.py:1172` 同时把 `out_h_stride` 传成 `out.stride(-1)`，修复时应传 head 轴 stride；原合并内核此前未使用该参数。

受控验证：

- 显式先在 BHSD 输入上补到 96，再转置，保留 head-major storage：10 次均正常。该对照同时改变了布局，不能将结果归因于仅改变 head_dim。
- 仅给 masked load 添加 `other=0`：72 维自动补齐入口仍最大误差约 `3.38`，未解决问题；此假设不作为根因结论。
- 保留原始 BF16/自动补齐路径，禁用 split-KV：3/3 有限，最大误差 `0.008706`。
- 保留 split-KV，仅在诊断进程中修正 combine 输出地址并传入正确的 head stride：3/3 有限，最大误差 `0.008706`；完整 FlagGems 注册配置另测 3/3，数值相同。没有加入 FP32 attention 或 masked-load 修改。

修正地址需从 `r=pid*BLOCK_M+row` 解出 `batch=r//(H*S)`、`head=(r//S)%H`、`sequence=r%S`，按 `batch*out_b_stride + head*out_h_stride + sequence*out_s_stride + dim` 写回。该进程内候选已验证当前真实输入；产品化还需覆盖其他 batch、长度、布局及 graph。

这解释了历史现象：输出可能有限但颜色错误，也可能 NaN 后扩散成重复 `!`；错误随分配/请求顺序变化；contiguous 不能避开自动补齐产生的输出布局；FP32 路径避开该 flash/split-KV 分支。原 `mm_encoder_attention.py` 提供的 FP32 分块实现因此保留为已验证缓解。

### 远端证据与恢复入口

以下路径均相对已批准的 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B`，原始日志/脚本留在远端，不复制进本地模型目录。

| 产物 | SHA-256 |
| --- | --- |
| `04-runs/vision-capture-20261008-v1/result.json` | `ef3abfbeb9246aa48832623c4f1706154c76d37e5eb6c36a2dd568f80374011f` |
| 同目录 `first-bad-qkv.pt`（激活，约 1.77 MB） | `7621e06cb96849c515e91984bd0629e67b42d9084cd2afcdbc3d9993e1eba4c7` |
| `04-runs/vision-fixture-20261008-v1/result.json` | `95b5269b0114cbf44a4f8845349cc81feec30b9a3ec9c7ed94856372050294b8` |
| `04-runs/vision-masked-load-20261008-v1/result.json`（假设排除） | `7a6afbb33cd0075878260556855509215f50d0068c9b3c23d8463dabb22f0eb2` |
| `04-runs/vision-boundary-20261008-v1/result.json`（布局定位和进程内修正） | `6db90707e737b34b27c1dadd947268df17fc18ce5272431a65970e9b5a545b8a` |

对应过程脚本为 `02-issues/vision-{capture,sdpa-fixture,masked-load,boundary}-20261008-v1.py`。
实际安装文件哈希：`ops/flash_kernel.py` 为 `eef0202e6c0ed08bef8098adede1a603c63354c54b54a19414e210b675157265`；`ops/flash_api.py` 为 `9d6f1e1ec802d132b074a618c173a9ea424f4d5793fd0cbcead687796155a70f`；两者本次未修改。

### 无权重最小复现

已保存并实际运行 `07-bugs/splitkv-combine-stride-20261008/repro.py`，SHA-256 `b32ee83c9f271fd2e7279b4b765f415cf2d6fdbb5de5990ac38b8c40e4062e81`。它直接调用已安装的原合并内核，构造两个 partial output 和零 LSE，预期结果为两份 partial 的均值，无需读取模型权重或启动服务。输出逻辑张量外另分配足够的 backing storage 并填入哨兵，确保错误写入仍落在本测试实际分配的存储内。

| 输出布局 `[1,256,16,96]` | 错误元素 | 未写元素 | 逻辑输出外哨兵被改写 | 最大误差 |
| --- | ---: | ---: | ---: | ---: |
| BSHD 连续，stride `[393216,1536,96,1]` | 392561 | 344064 | 1344 | 126.234375 |
| head-major storage，stride `[393216,96,24576,1]` | 0 | 0 | 0 | 0 |

结果 `04-runs/splitkv-combine-repro-20261008-v1/result.jsonl`，SHA-256 `e0efdc46bb32cdff5107d23ba6576bd3d4c89d76914760f3ef03e2efedae7556`；执行 rc=0，内置断言确认坏布局失败、对照布局完全正确。真实模型激活对照与此独立复现共同证明合并输出布局错误。

在已核实的 `minicpmV4.7-1B` 容器、物理 PPU3 空闲时复现：

```bash
cd /mnt/nfs/users/jinghao/MiniCPMV4.7-1B
CUDA_VISIBLE_DEVICES=3 python3 /mnt/nfs/users/jinghao/MiniCPMV4.7-1B/07-bugs/splitkv-combine-stride-20261008/repro.py
```

本次五个实际诊断任务均已结束、rc=0；capture 阶段在保存失败输入后主动捕获异常退出，属于预设诊断停止。2026-10-08 11:12 的 `accelerator-check --limit PPU-13` 核实 PPU3 恢复为 1 MiB/98304 MiB；容器保持运行。全程保留现有 Plugin 缓解和 PPU2 服务，没有修改安装包。

本地 `syntax-check --offline` 的 252 项 workflow 测试和 6 项 operations 测试通过；后续 workspace audit 未通过，当前 PPU `framework.yml` 明确提示 profile revision 已变化、须复核证据。此项未通过保留，不为通过审计改写历史验收绑定；本次只新增诊断结论，未更新正式适配/验收状态。

### PR #6871 与本问题的对应关系

2026-10-08 只读审查用户提供的 [FlagGems PR #6871](https://github.com/flagos-ai/FlagGems/pull/6871)，核对 head `ef76e47de58e2a20b8d8e06d1132ff2357b07981`、base `0dddb4628ae215931171a7f6e04a1183777dcd8a` 的完整两文件 diff，并读取 head 对应源文件。

该 PR 在 `src/flag_gems/ops/attention.py` 的 `scaled_dot_product_attention_forward` 中用 `broadcasted_stride` 修正非空 attention mask 的广播寻址，并增加 `tests/test_attention_mask_broadcast.py`。本问题在无 mask 的 flash/split-KV 分支复现，不进入被修改的 mask 分支。

进一步核对 PR head，而非只看 diff：[flash_kernel.py:1132](https://github.com/ZenithJoyH/FlagGems/blob/ef76e47de58e2a20b8d8e06d1132ff2357b07981/src/flag_gems/ops/flash_kernel.py#L1132) 和第 1174 行仍保留原 combine 基址/写回计算；[flash_api.py:1172](https://github.com/ZenithJoyH/FlagGems/blob/ef76e47de58e2a20b8d8e06d1132ff2357b07981/src/flag_gems/ops/flash_api.py#L1172) 仍将 head stride 传为 `out.stride(-1)`。`flash_attention_forward` 仍通过 `mha_fwd` 使用该合并路径。因此，仅合入 #6871 当前变更不能修复本记录已定位的 split-KV 输出布局问题，需要独立修正 combine 寻址及其 API 参数并增加对应回归。

上述判断来自 PR 源码/差异与本地既有复现的对应审查；本轮未应用该 PR、升级远端包、执行 PR 分支测试或改动现有服务。不据此声称已在 PPU 上验证该 PR 的 mask 修复效果。

### 2026-10-08：已安装组件修复与上游提交

用户明确要求提交 issue 和关联 PR，已发布 [Issue #6872](https://github.com/flagos-ai/FlagGems/issues/6872) 与 [PR #6873](https://github.com/flagos-ai/FlagGems/pull/6873)。PR 正文使用 `Fixes #6872`，GitHub issue timeline 已核对关联成功；PR 尚未合并，上游 CI 和维护者审查待完成。提交 `b0009abd20531db1a4dd1d1ee60dc9f28055713c`，fork 分支 `ZenithJoyH:fix/splitkv-combine-output-strides`。

沿用此前用户对干净 checkout 快进同步的明确授权，先核实 `/workspace/FlagGems` 的 `master → origin/master` 跟踪关系与干净状态，再快进到 `0958d2da98055f1e2198a56201e3eea6f7591981`。该基点的两个公共源文件与容器普通安装的 5.3.5 对应文件逐字节一致。没有重装整个包、切换导入版本或修改 vLLM。

最终修复将 flattened row 解为 batch/head/query，使用真实输出 stride 寻址；公共 API 的 head stride 改为 `out.stride(-2)`，同时传入 head 数和 query 长度。源码检查发现 Enflame GCU400 API 导入同一公共 combine 内核，故同步更新其调用参数；其他厂商独立实现保持原样。完整 PR 只有以下四个文件，基于上述 upstream master 单独提交，没有继承 #6871 的 mask 改动或诊断脚本。

| PR 文件（相对 FlagGems） | 已验证 SHA-256 |
|---|---|
| `src/flag_gems/ops/flash_kernel.py` | `19940f11b4a3de9b77399166fd595498ae6d22da8aa6ef2ff4eb1ddf62f7a3aa` |
| `src/flag_gems/ops/flash_api.py` | `ffbe6e6aa05940c5586d3fee08644c4eec86044cf220db856d913fcaa6630b15` |
| `src/flag_gems/runtime/backend/_enflame/gcu400/ops/flash_api.py` | `6aac1054d300d23d4fcbf7574ba6950056407901358662e06efb34e5fb6fef44` |
| `tests/test_flash_attention_splitkv_combine.py` | `ccbec4ea20ccea0280afd64bf41af375efc32df9b448037cf7a3c31e490270aa` |

前两个修复直接应用到 `/usr/local/lib/python3.12/site-packages/flag_gems/ops/`，并同步到既有 `/workspace/FlagGems`。安装包没有 GCU400 对应文件，该项只修改源码并静态检查，未声称硬件验证。原文件和应用哈希保存在远端 `07-bugs/splitkv-combine-stride-20261008/pr-candidate/before/` 与 `applied.json`。发布后四个 Git blob SHA 与本地候选一致，两个安装文件与实际测试记录一致。

#### 修复前后测试

测试在空闲 PPU3、原安装包导入路径执行。首轮正常源码 pytest 入口因当前 conftest 引入而旧 wheel 缺少 `flag_gems.cli_override` 停在收集前；第二轮测试夹具只替换 SM 数的对象没有保留设备属性，触发 `major` 属性缺失。两轮失败均保留在 `04-runs/splitkv-pr-before-20261008-v1/`、`v2/`；不作为算子失败证据。最终夹具委托原设备属性，只覆盖 SM 数，使 split 选择稳定，真实内核计算不被替换。

最终使用与 PR 逐字节一致的自包含测试文件，路径为 `07-bugs/splitkv-combine-stride-20261008/pr-candidate/test_flash_attention_splitkv_combine.py`，命令为 `python3 -m pytest <该文件> --confcutdir=<pr-candidate目录> -q --tb=short --disable-warnings`，修复前另加 `-k test_splitkv_mha_output_layout -x`。没有通过 PYTHONPATH 或 sys.path 选择源码包。原生源码 conftest 入口在该旧安装包上仍未执行，限制已写入 PR。

| 验证 | 结果 | 证据（相对远端工作根） |
|---|---|---|
| 修复前公共 `mha_fwd` 真实 split/combine | 7943/9792 元素不匹配（81.1%），最大误差 123.3125；rc=1 | `04-runs/splitkv-pr-before-20261008-v3/pytest.log` |
| 修复后 24 项直接合并、6 项公共入口、4 项 graph | **34 passed**；图用例各更换 partial/LSE 输入后重放两次，保护区不变 | `04-runs/splitkv-pr-after-20261008-v1/pytest.log`、`pytest-result.xml` |
| 真实第 7 层 Q/K/V，ATen flash 单算子注册，自动补齐 72→96 | 3/3 无非有限值；均实际命中两路 split-KV、连续 BSHD；最大误差均为 0.0087063313 | `04-runs/splitkv-pr-after-20261008-v1/fixture.json` |

回归包含 FP16/BF16、连续 BSHD/head-major/gapped storage、多 batch/head、query 尾块、维度 32/64/96/128、2/3/5 splits、独立 CPU 加权输出和 LSE、空 KV 分片、输出 alias、逻辑输出孔洞及末尾哨兵。保护存储足以容纳旧错误写入，避免测试本身跨出设备分配。graph 结果仅证明 combine 算子捕获/重放，不代表整模型 FULL_AND_PIECEWISE 验收。

关键证据 SHA-256：修复前日志 `158502641dfe5db8bb0af5aa3519ce33a13b46e18b4ea7e3a83798206093489c`；修复后日志 `e151aeecea44c60b60db37937241ef8b5485152a7b4ae25e16d671a355e607cb`；修复后 JUnit `78c9fe06f4454acf67c3e64d6cf97418ea314d17b89fa89fb74ecfaecef012b2`；真实输入回执 `880f0d2753c3a007fcf5e53874740de4ecdedc27a12c4021a72967811111b6c4`。实际异步任务 `j838967577070.3663912`（修复前 rc=1）与 `j835916196010.3687924`（修复后两步 rc=0）均结束，原生回执位于 `05-tmp/ansible-async/`。

Python 语法、Black、isort、flake8、远端 `git diff --check` 通过。项目 `syntax-check --offline` 的 252 项 workflow 测试（1 skipped）、6 项 operations 测试及本地语法检查通过；workspace audit 仍有原来的 12 项 profile revision 错误，未修改历史验收绑定。硬件数值只验证 PPU，未运行 NVIDIA/Enflame、正式精度或性能。设计与影响审查见 [FlagGems 修改审查](../environment/flaggems-splitkv-pr-review.md)。

最后核实容器仍在运行，当前 8000 端口 `/health=200`；本轮没有启动/停止服务、修改启动脚本或 Plugin 缓解。根脚本当次 SHA-256 为 `0c9f9441a02125426ebc799d5eba81d37919db950ed83fa3345a0be985c27a45`，仅为只读现场快照，不重用历史启动验证；FP32 OOT 文件仍为 `0f3ab3d2e9141aa2295d73cf40b9a3f06245bae6f68ef7e29ab7f42c334fe885`。未构建镜像或验证新安装文件在完整服务重启后的效果。

### 2026-10-08 PR CI 失败与修复

用户要求修复 PR #6873 的 CI。检查初始提交 `b0009abd20531db1a4dd1d1ee60dc9f28055713c` 的原生 Actions 日志后，确认失败分为两类：

- `code-style`（run `37723489100`）和 `rule-check-required`（run `37723489147`）均在 checkout 中连续 `git fetch` 超时；格式/规则检查尚未执行，不能归因于代码格式。
- 单测 run `37723489252` 的 NVIDIA job `113136420063` 已完成新增测试 **34 passed**，随后 `tools/test-op.sh` 把辅助模块名转换成 `flash_api or flash_kernel` marker，98759 项全部 deselect，pytest 非零退出。
- 同 run 的 Enflame job `113136420477` 已完成新增测试 **30 passed、4 skipped**（CUDA graph 条件不成立）；随后相同 marker 筛选收集整个 tests 目录，在无关 `test_conj_physical.py` 导入时，GCU FP8 转换因 `TOPSATEN_STATUS_NOT_SUPPORT` 直接 abort。这不是本次 combine 回归的数值失败。

修复提交 `27f8001e54f5e6474c54566e07776f7f87ef723a` 已快进推送到原 PR 分支，仅调整测试组织：原自包含文件拆为 `tests/test_flash_kernel.py`（24 项布局 + 4 项 graph）与 `tests/test_flash_api.py`（6 项公共入口），后者相对导入前者的非测试辅助函数。现有 CI 按 `tests/test_<module>.py` 识别直接覆盖，从而不再对这两个模块做全目录 marker 收集。没有修改 CI 工作流、生产内核、容差、skip 或无关 FP8 测试。

本地使用未修改的上游 `test-op.sh`、`derive_changed_operators.py`，以 stub coverage 验证命令选择（不冒充硬件数值验证）：旧文件名复现 marker 失败；新文件名各运行一次正常模式和一次 quick CPU 参考模式；故意失败时立即非零退出。AST 对照确认原有 9 个辅助/测试函数及 decorators 完全保留，34 项参数化用例未减少。Black/isort/flake8 通过。发布文件逐字节回读匹配；测试 SHA-256：API `32e4ee976bc8eb77e2f82e793c39733996ad4fbfd2a4ac26c8c7be769e0a9a62`，kernel `bf7a5fd204d5730ab8173eb68ace8d0926a12958e1151f3883dbe0e85d1762f1`。

新 HEAD 的 Enflame job [113141028335](https://github.com/flagos-ai/FlagGems/actions/runs/37724939724/job/113141028335) 已 **success**：API 常规/quick CPU 各 6 passed，kernel 常规/quick CPU 各 24 passed、4 skipped；无 marker 全目录收集或 FP8 abort。NVIDIA job [113141027931](https://github.com/flagos-ai/FlagGems/actions/runs/37724939724/job/113141027931) 同样 **success**：API 常规/quick CPU 各 6 passed，kernel 常规/quick CPU 各 28 passed，合计每种模式 34 passed。两个 job 都直接运行两份测试，无 marker fallback。

新 HEAD 的 [code-style](https://github.com/flagos-ai/FlagGems/actions/runs/37724977477/job/113140978075) 与 [rule-check-required](https://github.com/flagos-ai/FlagGems/actions/runs/37724939406/job/113140852651) 仍各连续五次 checkout 超时，检查步骤未执行。两份工作流都将 `secrets.CI_HTTP_PROXY` 写入 lowercase proxy 环境变量，实际 job 日志展开为空；这提示 fork PR 的 secret 不可用可能覆盖了 runner 的既有代理，但未验证 runner 网络，不能把提示当作已证实的唯一原因。尝试 GitHub job rerun 返回 403 `Resource not accessible by integration`；当前连接没有上游 Actions 重跑权限。需要维护者处理 runner 网络/代理及重跑；未改动工作流或降低 CI gate。

此前“未验证 NVIDIA/Enflame”描述仅指初始提交前的人工验证；本节补充上游 CI 的实际硬件结果，不据此声明完整 CI 已通过。本轮仅 GitHub PR 与本地记录操作，没有远程连接、生产环境修改或正式精度评测。

### 2026-10-08 isort CI 补充修复

用户再次反馈 CI 失败。最新 [code-style job 113143976550](https://github.com/flagos-ai/FlagGems/actions/runs/37725936503/job/113143976550) 这次 checkout 成功，实际 pre-commit 检查仅 `isort` 失败；YAML、EOF、空白、Flake8、clang-format、Black、导出排序等均通过。日志给出的差异只有两份新增测试的 import 分组：`flag_gems` 是仓库第一方包，应放在 pytest/torch/triton 等第三方导入之后并空行分组。此前在临时目录进行的 isort 检查未还原项目包识别上下文，因而漏检；不能将这次失败继续解释成网络错误。

已按 CI 的精确差异发布提交 `c13d2aba866e46b235a7bcae88a68e7ec2090e04`，parent `27f8001e54f5e6474c54566e07776f7f87ef723a`，仅两项 import 排序与空行变化；全部测试函数和生产源码不变。使用 `isort --check-only --diff --profile black -o packaging -p flag_gems` 明确第一方分类后通过，Black/Flake8 同样通过。GitHub 回读测试 blob 分别为 API `185c1a1278bc8cf3b89c8eaffdc2c9849c11c249`、kernel `719f38d587169d3090ce392ba23327f7e586285b`，与 CI 先前给出的修正 blob 完全一致。

最新 HEAD 的 [code-style 113149536017](https://github.com/flagos-ai/FlagGems/actions/runs/37727702443/job/113149536017) 与 [rule-check-required 113149535630](https://github.com/flagos-ai/FlagGems/actions/runs/37727702586/job/113149535630) 均 **success**；本轮 checkout 正常且检查实际执行。[Enflame 113149708565](https://github.com/flagos-ai/FlagGems/actions/runs/37727702877/job/113149708565) 同样 **success**，常规/quick CPU 各 30 passed、4 skipped；[NVIDIA 113149708372](https://github.com/flagos-ai/FlagGems/actions/runs/37727702877/job/113149708372) **success**，常规/quick CPU 各 34 passed；[unittest-required 113152395205](https://github.com/flagos-ai/FlagGems/actions/runs/37727702877/job/113152395205) 汇总 **success**，CLA success。最终回读 PR HEAD 仍为 `c13d2aba`，全部已启用检查通过，其余平台按原工作流 skipped；不把 skipped 视作平台硬件验证。PR 未合并。

前一 HEAD `27f8001e` 的 NVIDIA、Enflame 与 `unittest-required` 均已 success（汇总 job `113143606427`）；旧 rule-check 的 checkout 超时失败仍保留。旧提交的通过不直接替代新 HEAD 的 CI 结果。本轮只调整 GitHub PR 测试格式和本地 Markdown 记录，没有远程连接或模型服务操作。

### 下一步与结论边界

该阶段已完成安装组件修复、算子布局/边界/graph 回归及 issue/PR 交付；当时尚待验证无 FP32 替代的完整视觉链和服务图。下节补充实际撤除与回归结果，仍不能声称整模型精度已通过。此视觉问题与 [007 的 GDN int32 索引偏移问题](007-long-accuracy-output-corruption.md) 分别成立；不能用当前结果解释所有纯文本 MMLU 长负载乱码，也未证明与公开 issue #6846 的非法页崩溃属于同一根因。

## 2026-10-08：按用户要求撤除 FP32 mm encoder 缓解

### 实施范围与设计审查

用户明确要求尝试移除 FP32 mm encoder 实现及 OOT 注册，恢复修复后的原生 BF16 路径。本轮是 `vllm-plugin-fl` profile v6 的适配诊断，不执行正式精度/性能。仍为 `PPU-13` / 容器 `minicpmV4.7-1B`（ID `a8861de7fe73...`），已核实 `/mnt` RW bind、宿主/容器工作根 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B` device:inode `41:12343819932`。实际 Plugin 为 editable `/workspace/vllm-plugin-FL`、HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`；FlagGems 5.3.5 从 `/usr/local/lib/python3.12/site-packages/flag_gems` 导入，flash API/kernel 哈希仍为本记录的已修复版本。没有升级包或导入覆盖。

已阅读当前 Plugin README、对应 HEAD 的 dispatch README、实际 OOT 注册及上游 CustomOp/attention 分发契约。修改仅撤除先前的 T-Head BF16 特例，正常默认分发接回上游 `MMEncoderAttention`；不新增替代实现、模型名条件或 dispatch 体系。其他平台原先不注册该特例，本次不改变其策略；非 BF16 回到原实现，与旧缓解委托路径一致。跨平台硬件未重测，不能外推整模型通过。

实施前 Plugin 的继承改动是 `vllm_fl/__init__.py`、`vllm_fl/ops/custom_ops.py` 两个跟踪文件，以及模型 adapter、canvas 测试、FP32 实现和其测试四个未跟踪文件。只撤除本次明确要求的部分，保留模型注册、canvas 桥接与其测试；没有提交或推送 Plugin PR，未假定新的 PR base。

- 删除 `vllm_fl/dispatch/backends/vendor/thead/mm_encoder_attention.py`：旧 SHA-256 `0f3ab3d2e9141aa2295d73cf40b9a3f06245bae6f68ef7e29ab7f42c334fe885`。
- 删除专用于旧 FP32 实现的 `tests/unit_tests/test_thead_mm_encoder_attention.py`：旧 SHA-256 `7a7e2a734fed2380b00ced8c66a304278a253e9014f832a6769b369980154721`。
- 从 `vllm_fl/ops/custom_ops.py` 仅移除 T-Head 注册块，原哈希 `4dc6ce00467c00958bd66eb7e4d14f334712496c8451b10e7dc67725d364c4eb`；修改后逐字节等于 Git HEAD 原文件，哈希 `68406a5fbb37f91ffe1fb7ccaa77eff0bcb75246ca25d8b1852ca55869be28b8`。

三份原文件在写入前均校验完整哈希，备份到远端 `05-tmp/mmencoder-remove-20261008/before/`。执行清单为 `04-runs/mmencoder-remove-20261008/applied.json`，一次性过程代码在 `02-issues/mmencoder-*.py`。vLLM source HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`，实施前工作树干净，全程只读。

### 渐进验证

移除后 canvas 单元测试 **3/3 passed**，证据 `04-runs/mmencoder-remove-20261008/canvas.log`。独立 PPU3 eager 引擎使用 BF16/TP1、50,000 诊断上下文、4 个序列、前缀缓存开启、显存比例 0.4；没有改服务端上下文。模型通过正常安装和 Plugin 注册加载，未用 monkey patch 选择 attention 实现；仅用观察 hook 校验 dtype、输出有限性和实际 Python 调用链。

离线视觉及 PPU2 当前脚本服务验证的最终结果见本节后续记录。本次重启控制只有在 7 项离线用例全部正确且有限、原生类与 FlagGems flash 调用链确认后才执行，并在停止前精确核对旧 API PID `367144` / start tick `387843698`、物理 PPU2 和两次零在途指标。原 `start-model.sh` SHA-256 `0c9f9441a02125426ebc799d5eba81d37919db950ed83fa3345a0be985c27a45`，沿用用户当前参数，包括 `FULL_AND_PIECEWISE`、默认 262144 上下文及当前关闭前缀缓存的设置；该诊断不重标 profile 正式验收通过，也不把该性能参数认作新验收的最终配置。

### 离线 BF16 完整视觉链结果

最初 `offline-result.json` 的前六项单图/重复图检查均有限，224 红/蓝/绿、448 红/蓝最终答案正确。重复红图命中 encoder cache，attention 调用为 0，不计作新的视觉计算。其余五项各执行 27 层 attention，共 135 次，均无非有限值。

首轮双图也命中 encoder cache，64 个生成 token 在最终答案中途截断。初版诊断只判断全文包含颜色，打印了 `OFFLINE PASSED 7`；该宽松条件不代表完整双图答案通过。重启控制进一步检查 `</think>` 后的最终答案，因缺少 red/blue 退出 1，**没有停止旧服务**；证据在 `restart.log`。保留原始 `offline-result.json` 和 `offline.log`，不改写为成功。

随后只补测失败的双图：新进程、225 像素红/蓝图，确保 encoder cache 未命中，客户端 `max_tokens=192`；服务上下文未改变。真实执行 27 次 attention，全部有限，完整最终回答为 `red, blue`。证据 `offline-two.log`、`offline-two-result.json`。与前六个完整用例合并后，在 `offline-validated.json` 逐项严格检查最终答案及顺序，共 **7/7 正确、0 非有限值，162 次实际 attention 调用**。这是一组小范围视觉诊断，不是模型精度评测。

离线全部条件通过后，`restart-v2.log` 记录精确 TERM 旧 API、确认旧服务树退出，使用原脚本启动新 API PID `425141` / start tick `415865981`，命令 SHA-256 `5ae8f440558e94c9ac47e3288804c0b01df0de0cb4cb7e798681ffe389d2db49`。旧日志和进程/零在途快照保存在同目录 `old-service.log`、`old-service.json`。

### 原脚本服务验证与最终状态

同一启动脚本重启后，实际配置为 BF16、TP1、默认 `max_seq_len=262144`、`FULL_AND_PIECEWISE`；混合 prefill/decode PIECEWISE 捕获 **51/51**，decode FULL 捕获 **51/51**。15:06:32（Asia/Shanghai）API 启动完成。当前配置 `compile_mm_encoder=False`、`cudagraph_mm_encoder=False`，上述捕获证明 LLM 服务图路径，不声称视觉 encoder 自身被图捕获。

HTTP 回归共 **25/25 正确且 HTTP 200**：先顺序执行 5 项文本/单图，再对文本、红蓝绿黄 224/448 单图、红蓝双图共 10 项执行两轮 10 并发。逐项检查 `</think>` 后最终答案和双图颜色顺序，全部 `finish_reason=stop`，客户端 `max_tokens=96`；没有更改服务上下文。前后 API PID/start tick/命令哈希一致，结束后 `/health=200`。这是合成颜色小样本回归，不是正式精度、长负载稳定性或性能评测。

离线模型的 27 个 attention 模块实际类型均为上游 `vllm.model_executor.layers.attention.mm_encoder_attention.MMEncoderAttention`，无该类的 Plugin OOT 注册；Q/K/V hook 确认 BF16，调用记录确认实际进入安装包的 `_scaled_dot_product_flash_attention → flash_attention_forward → mha_fwd`。记录中的 `_forward_method` 为共享的 `CustomOp.forward_oot`，不据此声称调用某个特定 `forward_cuda` 方法；原生类、无专用注册、BF16 输入和实际 FlagGems 调用共同确认本次路径。

15:10:15 最终核对：容器保持原 ID 并运行，工作根映射一致；Plugin 仅剩既有模型注册、adapter 和 canvas 测试改动，`custom_ops.py` 等于 Git HEAD，无 FP32 文件/测试或残留 Python 引用；vLLM HEAD 不变且工作树干净，已修复 Flash API/kernel 与 index_put 安装文件哈希不变，启动脚本哈希不变。PPU0/1 原 Worker PID `2208060`、`2208061` 保持，PPU2 新 EngineCore 宿主 PID `3666437`（容器 PID `425621`）；PPU3 诊断进程已释放，显存恢复 1 MiB。

**结论：保留本次移除，当前服务已使用无 FP32 专用缓解的 BF16 路径正常运行。** 原脚本中的 `nonzero_numpy,index,index_put_,_index_put_impl_` 黑名单保持，故不代表 index 修复启用后长负载已验证。未执行正式精度/性能、镜像构建或打包验证；未提交 Plugin PR、未更新 `framework.yml` 的验收状态。

原生证据均在远端 `04-runs/mmencoder-remove-20261008/`，最终核对为 `final-verification.json`。关键 SHA-256：

| 证据 | SHA-256 |
|---|---|
| `offline-validated.json` | `c9739e89cbe4a89ae8dc0ff6f4ce4d0447f13f24afe43da65cc18bd481d37b14` |
| `offline-two-result.json` | `5c67d6d7064f0b4819c31d566a45b975d43d5e34808f7fe9a1a4e7a4a6f0c532` |
| `new-startup.log` | `17c8dbc16ae51e56993a7daf12eb9420490dbde73702f6adf1ad01fdf1ae96d6` |
| `service-smoke.json` | `ab61395eea0b9bff99a2e9b2af24dce1e7eaff4ed1425116dd230e4441ff99b5` |
| `restart-v2.log` | `22d3bbef972475abb5118fc0b6c19f2d87a997d3cb2ff24b1a93961b97bae522` |

异步任务 `j409200206804.3457191`（应用/初轮诊断）rc=0、`j832161447180.3548892`（严格检查拒绝首轮截断双图）rc=1、`j266326213521.3607707`（补测/重启/服务回归）rc=0，均已结束；失败证据保留。监控中一次提前读取尚未生成的日志、一次 ad-hoc raw Python 缩进丢失，仅导致只读快照失败，后续已修正，不归因于模型。本地 `git diff --check` 通过；workspace audit 仍报告已有 profile revision 变化（本 profile 也在其中），不以此修订历史验收绑定。
