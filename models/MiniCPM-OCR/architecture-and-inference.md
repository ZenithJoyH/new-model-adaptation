# MiniCPM-OCR 架构与推理链

2026-10-20，依据用户包内 `MiniCPM-OCR-1.0/config.json`、Transformers OCR 参考实现及 vLLM 参考适配器；本次平台 NVIDIA、Host `H100-149`、profile `vllm-native`。

## 配置与数据流

架构名 `MiniCPMOcrForConditionalGeneration`，`model_type=minicpm_ocr`。BF16 单文件权重 2,600,969,816 字节，SHA-256 `cee5e1ac9c37e0b5794e4ba6754bec75d55a553ac1e1418a41d442f0e733fb3b`。模型由 SigLIP 风格视觉塔、窗口注意力 merger、下采样 MLP 与 Qwen3.5 文本骨干组成。

视觉配置为 27 层、hidden 1152、16 heads、intermediate 4304、patch 14、位置网格 980；第 6 层处可执行 2×2 窗口 merger。OCR 默认 `downsample_mode=4x`，跳过额外的 ViT merger，保留更多视觉 token；16x 模式执行额外合并。图像处理器使用分辨率 448、最多 9 个切片、图像 ID 和均值/标准差 0.5。

输入图像先按实际像素和请求选项决定缩放与切片，转换为拼接像素张量及 `target_sizes`。每片的视觉占位 token 数须从实际 patch 网格面积除以 4 或 16，不能仅按原始图像宽高推算。小图的自适应缩放使用 Otsu 阈值与连通区域统计；其决策依赖图像像素。图像和视频的请求选项须分别处理，避免把图像专用缩放规则施加到视频帧。

视觉塔输出经 merger 投影至文本 hidden 1024，再替换 `<|image_pad|>` 或 `<|video_pad|>` 对应嵌入。图像与视频 token ID 分别为 248056、248057。文本骨干 24 层、intermediate 3584、8 query heads、2 KV heads、head_dim 256；每四层一层 full attention，其余为 gated delta linear attention。线性层有 16 个 key/value heads、维度 128、卷积核 4、FP32 SSM 状态。文本使用配置中的默认 RoPE，partial rotary factor 0.25、theta 10000000；不自行增设 canvas M-RoPE 语义。

prefill 同时处理视觉特征与文本序列并建立 KV/SSM 状态；decode 复用状态逐 token 生成。权重嵌入与输出头共享。最大配置上下文 262144，但实际服务容量另按 GPU 资源验证，不据配置声称已支持全部长度。

## 本次实现边界

容器已有 vLLM 0.24.0 的 MiniCPM-V 4.6 和 Qwen3.5 实现可复用。新增 OCR 注册、配置兼容、视觉处理及权重映射，优先限制在 OCR 适配器；不替换现有框架或通过 PYTHONPATH 选择另一份源码。GPU 0 单卡 TP1 为本次验证范围；其余设备和跨卡并行不据此宣称通过。

原镜像 Transformers 5.12.1 不识别 OCR，而权重声明 5.19.0.dev0。需将必要兼容代码放入已安装的 vLLM 组件；外部权重、原始包及 Transformers 安装保持只读。正式精度、性能及完整上下文验证须分别保留真实证据。
