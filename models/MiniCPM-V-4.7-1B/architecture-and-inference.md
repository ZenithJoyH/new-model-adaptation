# MiniCPM-V-4.7-1B 结构与推理链路

## 证据与范围

2026-09-28 在 `H100-149` 的 `MinicpmV4.7-1B-native` 容器只读检查
`/data/models/MiniCPM-V-4.7/weights/1b/`。`config.json` SHA-256 为
`0d2f763cf97a0a5beec8f52b13b4cbf7262680df6fd35e1f0e48c09288c4bb12`，
`modeling_minicpmv4_7.py` SHA-256 为
`398ec5cf6a8b31d136fbcaf3671c1be2bc25d3ffc77aa457feec185d26999bd2`。
权重 `model.safetensors` SHA-256 为
`3b801e149bc6dab4bb8c4cf61bed4197cce810f6c2f523f60b266459f809251c`，
`tokenizer.json` SHA-256 为
`33861e37bb955af1e3f3061182b820f347eba2b9c2c1011c82794bf0d6e77b54`。
下述结构基于该配置、参考实现和 safetensors 的 tensor 形状/名称；尚未证明 vLLM
执行路径和输出正确性。checkpoint 上游 revision 未随本地文件提供，不能以目录时间代替。

2026-09-28 在 `PPU-13` 的 `minicpmV4.7-1B` 容器再次只读核实用户指定的
`/mnt/cpfs/models/MiniCPM-V-4.7/weights/1b`：`config.json`、
`modeling_minicpmv4_7.py` 和 `model.safetensors` 的 SHA-256 均与上面列出的
H100-149 文件一致，`mrope_minicpmv4_7.py` SHA-256 为
`cf6d70719e9e58bbab40612e56efeb6fb5cb7019b0aa780e1536aedb5023b1c3`。
因此文件级架构分析适用于这份 PPU 权重；PPU 执行路径仍需独立验证。

## 总体结构

- 顶层 `MiniCPMV4_7ForConditionalGeneration` 由视觉塔、视觉特征 merger、
  Qwen3.5 文本骨干和独立 `lm_head` 组成，支持 text、image、video。
- checkpoint 共 780 个 tensor、1,554,476,272 个参数。按 tensor 名前缀：
  语言骨干 752,161,600，视觉塔 522,299,312，视觉 merger 25,967,104，
  `lm_head` 254,048,256。此为文件参数计数，不等于运行时显存或实际计算量。
- 文本配置为 BF16、hidden size 1024、24 层、8 个 attention heads、2 个 KV heads、
  head dim 256，词表 248,094；每四层中的前三层为线性注意力，第 4 层为全注意力，
  合计 18 个线性注意力层和 6 个全注意力层。线性层使用 gated delta/conv 状态，
  与全注意力 KV cache 并存；最大位置配置为 262,144，尚未做长上下文实测。
- 视觉塔为 27 层、hidden size 1152、16 heads、patch size 14 的 ViT。
  默认在第 6 层后进行窗口注意力 merger；`downsample_mode=16x` 在中间和最终
  merger 中压缩视觉 token。配置允许 `4x` 分支，但这份 checkpoint 的默认值为 `16x`。

## 输入、位置编码与输出

1. 图像处理器把图片切成可变网格 patch；视频处理器逐帧处理后按 NaViT 形式打包。
   processor 按每个 patch 的目标网格展开 image/video 占位符，并保证视觉 token 数
   与视觉特征数一致。image/video token id 分别为 248056/248057。
2. 视觉 patch 进入 ViT，在配置的插入层后可进入窗口注意力 merger，再经 MLP merger
   投影到文本 hidden size。参考模型把这些特征填入文本 embedding 中对应占位符。
3. 本 checkpoint 的 `mrope_mode=canvas`。processor 输出 `image_bounds`、
   `target_sizes_mrope` 和特殊 token id；参考模型在 prefill 计算空间位置，保留
   `rope_deltas` 用于后续 decode。这与顺序文本位置复制到三个 M-RoPE 通道不同。
4. 融合 embedding 经过 24 层 Qwen3.5 文本骨干、独立 LM head 产生 logits；
   生成时复用全注意力 KV 与线性注意力状态。视频帧走同一视觉编码与融合路径。

## 并行与关键算子

参考配置提供文本骨干的 TP 计划，但当前权重为单文件 BF16 checkpoint；实际 vLLM
TP 拆分、视觉塔并行、cache 分配及 graph capture 均未实测。关键路径包括 patch
embedding、视觉自注意力和窗口 merger、MLP merger、gated delta/卷积线性注意力、
全注意力、RoPE/M-RoPE、权重映射和混合 cache 管理。

## 待验证问题

- vLLM 0.24.0 只注册 `MiniCPMV4_6ForConditionalGeneration`；4.7 缺少注册。
  4.6 adapter 已包含 Qwen3.5 骨干、视觉塔与权重前缀映射，可作为设计参考；
  不能直接复用其顺序 M-RoPE，因为本 checkpoint 要求 canvas 位置。
- 图像/视频占位符、视觉特征数量和 canvas M-RoPE 在 vLLM 的多模态接口、
  chunked prefill、decode、批处理及 graph replay 中尚未验证。
- 1B 名称为模型变体标签，checkpoint 实际总参数约 1.55B；权重来源 revision、
  基线准确率与性能目标仍须冻结。
