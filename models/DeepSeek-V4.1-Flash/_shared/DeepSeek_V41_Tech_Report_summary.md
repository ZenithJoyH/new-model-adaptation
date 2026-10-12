# DeepSeek-V4.1-Flash: Pushing the Limits of KV Cache Compression

## 论文信息

- **作者**：DeepSeek-AI
- **年份**：2026
- **来源**：随模型发布的 Technical Report；远端文件
  `/public/models/DeepSeek-V4.1-Flash/DeepSeek_V41_Tech_Report.pdf`
- **快照标识**：SHA-256
  `ba68e2e40408125ae6d2f63a9a241b61c73910691c74ec1a2a7023c851eac08d`
- **公开页面**：[Hugging Face 模型页](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)、
  [DeepSeek 官方发布说明](https://www.deepseek.com/en/news/deepseek-v4-1-flash/)
- **阅读边界**：远端未安装 PDF 文本提取库，安全策略也不允许把远端 PDF 复制到本地。因此本文
  是基于随报告发布的官方模型卡、公开发布说明、模型配置和参考实现做的受限摘要；没有把未从
  这些材料复核的报告正文细节当作事实。

## 研究背景与动机

长上下文 Agent 工作负载通常具有输入极长、输出持续增长、缓存命中频繁的特点。传统 decoder-only
架构需要在大量层中长期保存 KV cache，HBM 与 SSD 成本随上下文长度和并发迅速增长；与此同时，
大 MoE 虽降低每 token 的激活参数，却没有自动解决 KV 存储和索引成本。

DeepSeek-V4.1-Flash 的目标是把“输入处理成本”“输出生成成本”和“持久 KV 成本”拆开优化，同时
保留 1M token 上下文、原生图像理解、MoE 容量和 Agent 能力。官方把它定位为新架构系列中最小的
模型，但其主干仍有 552B，完整逻辑参数还包含约 196.9B Engram 条件记忆。

## 主要贡献

第一项贡献是 Causal Encoder-Decoder（CED）非对称结构：40 层分为 20 层 causal encoder 和
20 层 decoder，解码器全局 KV 从编码器最终隐状态投影。官方给出的激活量为 prefill 8B/token、
decode 16B/token，使输入占主导的 Agent 请求更便宜。

第二项贡献是 Compressed Sparse Attention 2（CSA2）。各层静态采用 Full、Reindex 或 Reuse，
在层间共享主 KV、index K 和 Top-K indices；解码器再用两级 sparse indexer，把后续重索引限制在
首个 Full 层生成的候选块中。结合 FP4 main KV，官方声明 global KV 降至 890 bytes/token。

第三组贡献包括 Single-Pass mHC、Engram 条件记忆、DSpark speculative decoding 和原生视觉
编码器。它们分别面向 residual mixing、稀疏 n-gram 记忆、草稿生成吞吐和图文联合建模。

## 方法论

文本主干 hidden size 为 5120、40 层、64 attention heads。CSA2 同时使用 128-token sliding
window 和最多 512 个压缩全局位置；压缩比例在 encoder 主体为 2:1，在 decoder 为 1:1。四个
Full 层产生共享 KV/index，四个更深 decoder 层只在候选池中 Reindex，其余层 Reuse。

每层 MoE 有 384 个 routed experts 和 1 个 shared expert，每 token 激活 6 个 routed experts。
router 使用 sqrt-softplus、correction bias 和归一化 Top-K；专家是带 clamp 的 SwiGLU。专家权重
采用 E2M1 FP4 打包、dense projection 多为 E4M3 FP8，embedding/head/vision 多为 BF16。

mHC 把 residual stream 扩展为 4 路，并为 attention/FFN 计算 pre、post 与 Sinkhorn-normalized
comb mixing。Engram 在第 1、14 层注入 hashed n-gram lookup，总逻辑参数约 196.9B。DSpark 使用
3 个 draft 层、5-token block、Markov head 和 confidence head；随附 readable reference 只实现
forward，未把 speculative verification 接入默认生成循环。

视觉侧为 32 层、1024 hidden 的 DeepSeek-ViT，使用 14×14 patch、2D RoPE 和全双向 attention；
3×3 pixel-unshuffle 后经两层 aligner 投影到 5120 维语言空间，从语言主干第一层开始联合处理。

## 实验结果

官方模型卡报告的 base-model 结果包括 MMLU-Pro 74.1、HumanEval Pass@1 79.4、GSM8K 93.0、
LongBench-V2 45.2、MMMU-Pro 56.5、DocVQA 95.6。Instruct 模型在最大 reasoning effort=100、
temperature=1.0、top_p=0.95 下报告 GPQA Diamond 90.9、Codeforces rating 3471、Terminal-Bench
2.1 Pass@1 90.6、DeepSWE v1.1 resolved 74.2、CyberGym 88.1 和 AutomationBench 54.8。

这些数字来自官方内部/指定 harness 设置，并非本仓库在 H100-145 上复跑的结果。模型卡还说明
base 模型分数差 0.3 以内视为等价；Agent benchmark 使用特定 scaffold、最大 reasoning effort
和最长 1M 上下文，不能与不同采样或前端协议的结果直接比较。

## 局限性

- 552B 仅是 backbone；完整权重逻辑参数约 763.2B，部署容量不能按“激活 8B/16B”估算。
- 公开 readable reference 不是生产 serving engine：没有实际启用 DSpark 生成循环，未实现
  CED prefill 计算裁剪和 SWA Bounded Replay，cache 也不是 packed FP4/FP8 驻留。
- 官方结果依赖指定 harness、采样参数、reasoning effort 和长上下文；本机尚无独立复现。
- H100 没有原生 FP4 Tensor Core。参考 kernel 先把 FP4 tile 转为 FP8，再使用 FP8 GEMM，部署
  可行性与吞吐需实测。
- 当前 H100-145 的 8 张卡被其他模型服务占用；本次只做静态分析，没有加载、精度或性能证据。

## 核心要点

- 这是 552B backbone、约 763.2B 完整逻辑参数的多模态 MoE，而不是“小参数 Flash 模型”。
- 真正的效率来源是 CED 的输入/输出非对称和 CSA2 的跨层 KV/index 共享，而不只是 MoE。
- Engram、mHC、DSpark、FP4 KV 与视觉路径都引入普通 vLLM 模型没有的接口和算子约束。
- H100-145 理论上应从 TP8 开始，但每 rank 静态权重约 62.55 GiB，运行时余量紧，1M 上下文
  不能靠静态容量推断为可用。
- 后续适配必须分别验证 text/vision、eager/graph、router/Engram/CSA2 数值和生产级缓存语义。
