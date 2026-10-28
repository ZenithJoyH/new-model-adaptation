# 原生 PPU 与 FlagOS 的应用性能差距分析

2026-10-27，只读复核 PPU-01 上既有三份 portable v1.1 测量、逐请求记录、服务配置、安装源码和启动日志。未追加推理、启动新实例、修改源码或改变运行中服务。分析及源码身份清单保存在原生工作根下。

结论：本批测量中，原生环境的整页吞吐约为稳定 FlagOS 基线的 3.80–4.48 倍，差距主要体现在 HTTP 包围的服务处理时间。两套栈的视觉注意力、语言注意力路由以及 FlagGems/编译运行路径不同；现有证据不能将总差距按百分比分配给视觉编码、prefill、decode 或单个算子。优先检查注意力路由和持续生成期间的实际热点，不能把全部差距直接归给 TORCH_SDPA 或某个 GDN 算子。

后续纠正：在 [FlagOS Flash Attention 启用验证](../../vllm-plugin-fl/adaptation/002-ppu-flash-attention.md) 中已复现“选择 FLASH_ATTN，但 OOT 默认路由走 forward_native/SDPA”。因此本文涉及原生视觉 FLASH_ATTN 的历史日志只证明所选标签，尚无该轮独立 FA2 调用记录，不能仅凭标签作视觉 kernel 性能归因。MMEncoderAttention.enabled() 固定为 True，曾提出的全局 custom_ops none 禁用解释不成立。原始测量数字不变。

后续实测：[FlagOS 同时使用实际视觉 FA2 与语言 vendor.thead FA3 的完整重测](../../vllm-plugin-fl/acceptance/005-portable-v11-ppu-flash-performance.md)得到 7.13/9.86/10.72 页每分钟，未消除 gap，原生/本次为 3.84/4.73/5.21 倍。固定 32 页综合分与原生相同，输出无明显缩短。不同物理卡、测量时间和框架版本的限制仍在；该观察不能替代同卡控制或算子 profiling。

## 可比性与限制

- 同一 Host、同型号 PPU-ZW810E 96 GiB、单卡 BF16、相同 checkpoint 身份 `7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`。
- 相同 bench.py SHA `2ce4b471d80cd44c484bef52ac8902874ed4b39205612ee3c72d5e532433ec12`。旧包与 report-2 的差异仅为汇总工具和说明；混包比较由原版 compare.py 的严格兼容检查核对。
- 并发、输入图片/提示词/生成参数、完整场景预热和补轮规则相同；两类缓存均关闭；上下文 262144、max_num_seqs 64、批次 token 预算 8192、显存比例 0.55，图模式均为 FULL_AND_PIECEWISE。
- FlagOS 在物理 PPU3，原生在 PPU5，测量时间分别为 10 月 26 日、27 日。尚未做同卡、交替运行的控制实验，倍率是本批应用测量的观察值。
- FlagOS vLLM 为 0.24.0+empty，原生为 0.23.0+v0.2.0.ppu2.1.0；不是仅切换 Plugin 的单变量比较。两边 Torch 均为 2.10.0，元数据指向相同 Torch wheel SHA；编译器分别为 FlagTree 0.7.0+ppu3.6 与 Triton 3.5.0+gitcc5446cf。

## 差距规模

主表使用最后两轮稳定的 FlagOS 完整三场景记录，避免把最新 batch 的不稳定结果当作稳定排名。

| 场景 | FlagOS 吞吐中位数（页/分钟） | 原生吞吐中位数（页/分钟） | 原生/FlagOS |
|---|---:|---:|---:|
| interactive | 7.2062 | 27.4192 | 3.805 倍 |
| batch | 10.4183 | 46.6740 | 4.480 倍 |
| loaded | 13.3627 | 55.8900 | 4.183 倍 |

FlagOS 后一次 report-2 测量为 interactive 7.2872、batch 11.5866 页/分钟，相应倍率为 3.763、4.028；其中 batch 最后两轮波动 11.49%，不满足包内稳定性规则。latest loaded 已按用户指令中止，不使用其部分输出。

| 场景 | FlagOS 区域 HTTP 平均耗时（秒） | 原生区域 HTTP 平均耗时（秒） | HTTP 耗时比 |
|---|---:|---:|---:|
| interactive | 1.3320 | 0.3682 | 3.617 |
| batch | 2.9045 | 0.6601 | 4.400 |
| loaded | 4.5683 | 1.0668 | 4.282 |

上表来自完整基线与原生全部计时轮，交互各 429 请求、批量/加压各 1018 请求，不含预热。HTTP 包含传输、服务端 CPU 前处理/调度、GPU 执行和响应处理，不能直接等同于 GPU kernel 时间。

区域请求在 HTTP 和区域 semaphore 排队之外的平均开销约 0.27–0.71 毫秒，semaphore 排队平均约 3–4 微秒。该分解覆盖客户端读图/编码等请求准备，不独立测量整页后处理；它说明优先优化客户端准备难以解释秒级 HTTP 差距。

## 输入、输出和负载类型

完整基线与原生的 r1 请求按 `(page_id, block_id)` 一一配对：interactive 143/143、batch 509/509、loaded 509/509 的 prompt token 数相同。不能把性能差异解释为视觉 token 数大幅减少。token 数一致不等价于证明所有中间张量或处理实现一致。

最新 FlagOS 与原生的固定 32 页 r1 合计输出分别为 34395、34370 token，相差约 0.073%；Markdown 字符数分别为 88112、88090。质量子集综合分分别为 97.5245、97.5632，均未设置质量通过阈值。没有明显以减少输出换取约 4 倍吞吐的迹象。

| r1 配对区域，最新 FlagOS vs 原生 | 数量 | FlagOS HTTP 均值（秒） | 原生 HTTP 均值（秒） | 两组累计 HTTP 时间比 |
|---|---:|---:|---:|---:|
| batch 正文 text | 286 | 3.086 | 0.665 | 4.64 |
| batch 公式 display_formula | 52 | 3.737 | 0.899 | 4.16 |
| batch 表格 table | 19 | 12.516 | 2.455 | 5.10 |

这些请求并行执行，累计 HTTP 差不能相加为整轮墙钟节省或某算子的贡献比例。

代表性长输出：`page-5d58cdf7-6d00-4ea5-97b2-358cbc0cab21` 的 block 7，两边输入均为 2591 token、输出均为 2431 token，最新 FlagOS HTTP 25.9546 秒，原生 5.6368 秒，差 20.3178 秒。差距并不限于短标题或某类图片；持续生成链路值得优先分析。但非流式数据没有首 token/逐 token 时间，不能据此直接宣称 decode 占差距的某一比例。

## 源码与日志确认的实现差别

1. **视觉注意力选择标签不同，实际调用还需绑定执行路由。** FlagOS 历史启动日志记录 TORCH_SDPA；原生日志记录 ViT 与 MMEncoderAttention 选择 FLASH_ATTN。对应源码分支分别调用 `vit_torch_sdpa_wrapper` 和 `vit_flash_attn_wrapper`，但 OOT 与平台路由会影响实际进入哪条路径。FlagGems 还注册了 ATen SDPA 相关算子，当前共享 oplist 可看到其注意力调用；该 oplist 不绑定历史计时 run，因此不能当作历史热点统计。须先取得实际调用证据，再做视觉后端单变量对照；当前没有它独立贡献的数值。
2. **语言 full-attention 的选择策略不同。** FlagOS 的 `vllm_fl/dispatch/config/thead.yaml` 为 `prefer: flagos`，attention_backend 的顺序是 flagos → vendor → reference。两次历史日志确认实际选择 `default.flagos`。`FlagGemsBackend.attention_backend()` 默认返回 TRITON_ATTN；只有 `VLLM_FL_USE_FLAGGEMS_ATTN` 开启才返回 AttentionFLBackend。PPU vendor.thead 的 FA3 路径存在，但没有被优先选中。历史冻结环境没有保存该 attention 子开关，故不把两种 FlagOS 子实现中的一种写成已取证的最终类；原生则有 FLASH_ATTN 的明确运行日志。
3. **算子接管与编译栈不同。** WorkerFL 可通过 `flag_gems.enable()` 接管 ATen 算子；注册表包含 linear/mm/addmm/bmm 和 SDPA。两边未量化投影入口都调用 `torch.nn.functional.linear`，因此仅凭 Python 函数名不能断言底层执行一样，也不能断言所有 GEMM 都走 FlagGems。尤其 compiled graph 可能改变 lowering 路径，需 trace 确认实际 kernel。small-M 投影、输出头、norm/activation、GDN 状态读写都是待测候选，当前不作性能排序或耗时占比结论。
4. **存在 FlagTune 资源兼容告警。** 两次 FlagOS 启动日志都出现 AUTO preload fallback：平台包内 `flaggems/mm/gemv_ppu/bf16-bf16-bf16/model.tar.gz` 的配置有未知 `configs` 字段，导致报错的 mul/scalar、mul/broadcast_2d 变体在该进程关闭 AUTO，回到 default。它证明这些调优资源没有按预期加载；不证明 GEMV 是实测最大热点，也不证明全部算子都退回默认。告警发生在启动期，启动和完整预热已排除在计时外，不能将其加载耗时直接计入稳态差距。

上述 FlagOS Plugin、FlagGems、FlagGems-vllm 和 vLLM checkout 的 HEAD、diff SHA、status 均与最新测量记录一致；8 个抽取的原生安装文件 SHA 与该轮 component-after.json 一致。没有为分析修改或替换安装组件。

## 已缩小的方向与后续验证顺序

两边均有图模式及捕获证据，FlagOS 日志有 mixed prefill/decode PIECEWISE 和 decode FULL 捕获，不能解释为“一边开图、一边全 eager”。图模式名称相同也不能证明融合和实际回放覆盖完全相同。GDN 源码中两边都存在 packed non-spec decode 快路径，prefill 日志为 Triton/FLA；当前证据不能把 FlagOS 单独判成缺少这条快路径。

最新 FlagOS 服务日志的 131 个周期观察中 Waiting 最大值为 0、GPU KV 使用率最大值为 1.3%；前次完整记录有等待样本（最大 12），KV 最大值同为 1.3%。这是有限频率采样，不覆盖所有瞬时状态，但不支持优先把约 4 倍差距归因于 KV 容量不足。直接增加上下文、显存比例或 max_num_seqs 不是本轮证据指向的首项改动。

建议下一步按以下顺序取得可归因的证据；本次未执行这些新增实验：

1. 在同一物理卡、同一原生栈中仅切换 FLASH_ATTN / TORCH_SDPA，固定短输出与长输出案例，分别测 TTFT 和 decode 时间，估计视觉后端差异的实际影响。
2. 在隔离诊断实例为两套栈采集同一请求的 CPU/GPU trace，标注图像处理、ViT、文本 prefill、decode；观察 device kernel 时间、调用数及 CPU/设备空隙，区分内核慢与提交/调度间隙。
3. 保持版本和输入固定，针对 trace 排名前列的真实 kernel/shape 做单项对照，重点确认语言 attention 路由、GEMM/输出头实际 lowering、GDN/conv/state 操作及融合覆盖。先有热点，再决定是否修改对应组件。
4. 单独修复/验证 FlagTune 配置兼容后做等价 A/B，不把启动告警消失当作性能收益。复核完整输出质量，再用同包工作负载验证收益。

## 证据索引

- [FlagOS 完整三场景](../../vllm-plugin-fl/acceptance/002-portable-v11-performance.md)、[FlagOS 最新两场景](../../vllm-plugin-fl/acceptance/003-portable-v11-interactive-batch-latest.md)、[原生三场景](portable-v11-native-20261027.md)。
- 远端分析脚本：PPU-01 `/mnt/nfs/users/jinghao/MiniCPM-OCR/ppu-native/03-acceptance/gap-analysis-20261027.py`。
- 远端分析根：`/mnt/nfs/users/jinghao/MiniCPM-OCR/ppu-native/04-runs/gap-analysis-20261027/`；`analysis.json` SHA-256 `8b2bdbae6619732d074d05720e6482355bd6b0e37b33493f31a013c662027ba9`；`source-review.json` SHA-256 `139506538afcc03c51f613268b20f7a9d377d42a3e39afcb1290c9a9e275d74d`。
- 原始报告 SHA-256：FlagOS full `d129f68f06ed1d58a838f91350af1246d15a4ac955b1bfa92fc5d2ec066a1c98`；FlagOS latest selected `2c8f4d039083df957754b8b48f1499249d2794f9d1d83433797af2ca636fae3f`；native `1e926ab53f4c3ba4dc11c49cfeff9b1a8678c552076fc917d8ee86c2abd6af48`。
- FlagOS 关键源码：`/workspace/vllm-plugin-FL/vllm_fl/dispatch/config/thead.yaml`、`dispatch/backends/flaggems/flaggems.py`、`worker/worker.py`、`attention/utils.py`；原生及 FlagOS 的实际 vLLM 安装均在各自容器 `/usr/local/lib/python3.12/site-packages/vllm/`。具体文件 SHA 见 source-review.json。

此分析不改变正式框架验收状态，不提供单算子优化已验证或新镜像验证的结论。
