# Qwen-Image-2.1 模型结构与推理链路分析

## 分析对象与证据

- 模型：`Qwen/Qwen-Image-2.1`，远端权重路径 `/mnt/cpfs/models/Qwen-Image-2.1`。
- 模型快照：ModelScope `master`；快照元数据未暴露不可变仓库提交，因此后续复现还需保留逐文件校验。
- 参考实现：`/mnt/nfs/users/jinghao/qwen-image/Qwen-Image-2.1-ref-qwen-image-2.1.zip`，SHA-256 `0f788ee6b453d223903d1bd88bac0a7108d71bf627f2453b44c0409c75ad62f3`，ZIP comment 固定源码提交 `9511e982f22ea8fcc64faf277d90b3a21f8a83f6`，包版本 `diffusers 0.41.0.dev0`。
- 分析日期：2026-09-17。
- 参数量：依据 safetensors 文件头统计共 `16,219,988,836`；其中 DiT `7,115,124,736`、Qwen3-VL `8,767,123,696`、VAE `337,740,404`。权重目录约 31 GiB。
- 已验证事实来自模型配置和上述固定参考实现；PPU 算子可运行性、数值精度和图模式兼容性属于后续适配验证，不在本文中预判。

## 模型整体结构

### Qwen3-VL 条件编码器

- `Qwen3VLForConditionalGeneration`，BF16；文本塔 36 层，hidden size 4096，32 个 query heads、8 个 KV heads，head dim 128，MLP intermediate size 12288。
- 文本侧使用 `RMSNorm`、GQA、SiLU MLP 与三轴 M-RoPE；最大位置长度 262144。
- 视觉塔 27 层，hidden size 1152、16 heads、MLP 4304，patch size 16，spatial merge size 2，并向 DiT 输出 4096 维条件表示。
- 纯 text-to-image 时不提供条件图像，视觉塔不会参与实际前向；image-conditioned editing 时视觉塔和 VAE encoder 均参与。

### 单流 block-causal DiT

- `QwenImage21Transformer2DModel`：32 个 `QwenImage21TransformerBlock`，hidden size `32 × 128 = 4096`，MLP expansion ratio 3，输入/输出 latent channels 均为 64，patch size 1。
- 文本、条件图像 latent 和目标图像 latent 组成一个 joint sequence。条件图像 token 被放回 Qwen3-VL 预留的 image slots，目标图像 token 追加在序列末尾。
- 每层包含无 affine 的 LayerNorm、Q/K/V/out 线性投影、per-head Q/K RMSNorm、三轴 RoPE、attention、门控残差和 SwiGLU FFN。调制投影在所有 block 间共享，不在每层重复持参。
- `axes_dims_rope=[16,56,56]`，分别表示 frame、height、width，合计 128，与 attention head dim 一致。
- block-causal 规则为序列因果，同时每个图像 block 内部双向。默认 `QwenImage21AttnProcessor` 将 prefill 分解为逐段 SDPA；可选 `QwenImage21FlexAttnProcessor` 以 `BlockMask` 执行单次 flex attention，但必须编译，否则会物化 fp32 score matrix 并带来显存风险。
- `causal_condition=true` 时文本和条件图像 token 始终按 `t=0` 调制，因此其 K/V 在首步提取后可跨去噪步复用；默认 `use_kv_cache=true`。

### Causal 3D VAE

- `AutoencoderKLQwenImage21`，64 维 latent，图像输入/输出 4 channels，spatial scale factor 8，temporal scale factor 8。
- Encoder base dim 96，decoder base dim 144，层级倍率 `[1,2,4,8,8]`，每级 2 个 residual blocks。
- 核心为 causal 3D convolution、RMS norm、SiLU、上下采样、mid-block SDPA、quant/post-quant convolution。单图仍以 temporal length 1 的五维张量处理。
- latent 使用模型配置中的 64 维 mean/std 做反标准化后再解码。

## 端到端推理链路

1. `DiffusionPipeline.from_pretrained` 根据 `model_index.json` 加载 `QwenImage21Pipeline`、Qwen3-VL、DiT、VAE 和 `FlowMatchEulerDiscreteScheduler`，随后整体搬运到目标设备。
2. 可选条件图像先按目标分辨率调整尺寸；一份送 Qwen3-VL processor/encoder，另一份由 VAE encoder 转成 latent。
3. Prompt 经 Qwen3-VL 编码为 4096 维上下文；仅当同时提供 negative prompt 且 `true_cfg_scale>1` 时编码负向 Prompt。
4. 随机初始化 64-channel 目标 latent，按 spatial factor 8 打包为序列；条件图像 latent 位于目标 latent 前。
5. 默认 40 个 Flow-Matching 去噪步。首步对完整 joint sequence 做 block-causal prefill 并提取每层前缀 K/V；后续步只重算目标图像 queries，并关注缓存前缀与目标 block。启用 CFG 时每步执行正、负两次 DiT，因此计算量约翻倍。
6. Scheduler 更新 latent；完成后按 mean/std 反标准化并 reshape 回五维 latent。
7. VAE decoder 输出图像，image processor 转为 PIL/NumPy/Tensor，最终保存文件。

当前 `inference_with_gems.py` 使用 50 steps、negative prompt 和 `true_cfg_scale=4.0`，与参考实现推荐的 40 steps、无 guidance 不同；适配 bring-up 应先使用参考默认值，确认正确性后再验证原脚本参数。

## 关键算子清单

| 阶段/组件 | 算子或符号 | dtype/shape/layout | 并行或 graph 影响 | 证据状态 |
|---|---|---|---|---|
| Qwen3-VL 文本编码 | embedding、RMSNorm、linear/mm、GQA SDPA、RoPE、SiLU、逐元素乘加 | BF16，hidden 4096，32Q/8KV heads | 长 prompt 和 M-RoPE；纯文本不走视觉塔 | 配置已验证，PPU 待跑 |
| Qwen3-VL 视觉编码 | Conv/patchify、LayerNorm、attention、GELU、merge/projection | BF16，hidden 1152 → 4096 | 仅 image-conditioned 路径 | 配置已验证，PPU 待跑 |
| Prompt/latent 拼接 | repeat_interleave、nonzero、cat、slice、index assignment、zeros/ones | joint sequence；image slot 每项展开成 2×2 latent tokens | `tolist()`/`int()` 会同步；动态 token 布局影响 graph | 代码已验证，PPU 待跑 |
| 时间与共享调制 | sin/cos timestep embedding、SiLU、linear、chunk、where | BF16/部分 fp32 | 调制在 32 层共享 | 代码已验证 |
| DiT 投影与归一化 | linear/mm、LayerNorm、RMSNorm、cast | hidden 4096，head dim 128 | 每步每层高频 | 代码已验证，FlagGems 路由待测 |
| 三轴 RoPE | complex view/mul 或等价实数旋转、cat/slice | axes 16/56/56，head dim 128 | `complex64` slice 是既有 Torch-FL/FlagGems 风险 | 代码与既有失败已验证 |
| Block-causal attention | SDPA 或可选 flex_attention、bool mask、tril、cat | prefill 多 segment；decode 为 cached prefix + target | 默认实现无需 compile；flex 路径必须 compile | 代码已验证，PPU backend 待测 |
| KV cache | clone、slice、cat、per-layer Python cache | 32 层 K/V；首步 extract，后续 cached | cache on/off 会因 BF16 tiling 产生可见但合理的样本差异 | 代码已验证 |
| SwiGLU FFN | two linear projections、SiLU、mul、output linear | 4096 → 12288 → 4096 | 每层高频 | 代码已验证，PPU 待测 |
| Flow scheduler | sub/add/mul/div 与 timestep/sigma 操作 | latent sequence，BF16/标量混合 | 每步一次；无采样 token 或通信 collective | 代码已验证 |
| VAE decode | causal Conv3D/Conv2D、RMS norm、SiLU、upsample、SDPA | 5D latent，z_dim 64，单帧输出 | 卷积覆盖与临时显存是主要风险 | 代码已验证，PPU 待测 |
| 后处理 | clamp/normalize、permute、CPU copy、PIL conversion | 输出图像 | 设备同步与保存 I/O 不应计入 kernel 性能 | 代码已验证 |

模型为 dense 架构，不含 MoE/router/expert dispatch，不含量化/反量化，也不需要 TP/collective 才能完成单卡推理。

## Plugin、FlagGems 与运行时依赖

- 加载入口：`DiffusionPipeline.from_pretrained('/mnt/cpfs/models/Qwen-Image-2.1')`，要求参考 fork 提供三个 `QwenImage21*` 类。
- 运行框架是 Diffusers，而非 vLLM；本轮不需要修改 vLLM，也不应把模型语义放入 Torch-FL 公共 dispatch。
- Torch-FL 负责 `flagos:0` 设备与 ATen dispatch；FlagGems 可通过 Torch-FL `flagos_python` 路径接管兼容算子。
- 已知风险：FlagGems `slice.Tensor` 不支持 `complex64`，Qwen-Image-2512 的 RoPE 已复现该错误；在根因修复前只能使用精确到单算子的 CUDA/native 回退，并记录退出条件。
- `eager` 风险集中在新模型类缺失、attention backend、complex RoPE、动态 block metadata、Conv3D 和 dtype 支持；graph 风险还包括 Python KV cache、`tolist()`/`int()` 同步与动态序列布局。本轮用户要求的是脚本推理支持，不据此宣称 graph 已通过。

## 适配风险与最小验证

| 项目 | 风险 | 最小验证 |
|---|---|---|
| Qwen-Image-2.1 实现移植 | 整套开发版覆盖 stable 0.40.0 可能引入无关 API 代差 | 固定 ZIP/commit；以官方 0.40.0 wheel 为基线只移植专用实现；导入新旧 Pipeline；保留回滚包与 wheel SHA |
| QwenImage21 类注册 | Lazy import 或 optional dependency 失败 | fresh Python 导入三个类并读取配置，不分配设备 |
| 权重兼容 | key、shape、dtype 不匹配 | CPU/meta 配置加载后单卡完整 `from_pretrained` |
| Block-causal attention | 默认 SDPA 在 PPU 的 bool mask/segment 路径失败 | 参考默认 processor，低分辨率 1-step text-to-image |
| complex RoPE slice | FlagGems 不支持 complex64 | 无回退负对照；单算子 native 回退对照；后续 dtype-aware dispatch 根因修复 |
| KV cache | extract/cached shape 或精度问题 | 2-step，`use_kv_cache=true/false` 分别完成并检查有限值 |
| VAE | causal Conv3D/upsample/SDPA 覆盖不足 | latent 输出先过，再启用 VAE decode 和 PIL 保存 |
| 原脚本参数 | 50-step CFG 双倍 DiT 调用，放大运行时间和显存 | 参考默认 40-step no-CFG 成功后再跑现有脚本 |

## 结论

参考 ZIP 与权重配置构成一致的 Qwen-Image-2.1 实现，当前容器失败的首要原因是公开 Diffusers 0.40.0 缺少专用 Pipeline、DiT 和 VAE 类。最小正确适配是保留 stable 0.40.0 基线并移植固定参考提交中的专用实现，而不是安装整套开发分支或篡改 `model_index.json` 映射到旧类。安装后仍需逐级验证 PPU attention、complex RoPE、KV cache 与 VAE；在这些验证完成前，状态保持“适配中”，不宣称精度或 graph 验收通过。
