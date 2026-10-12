# Hy4-preview 固定版本与参考资料分析

## 范围

- 官方来源：`Tencent-Hunyuan/Hy4-preview`
- 固定 revision：`ada7b1faf9b70585edc90a9ef552d0059fb246e7`
- 核对日期：2026-08-28
- 用途：为模型结构、Tokenizer、权重布局和量化参考提供跨平台事实，不作为任何平台的
  运行配置或验收结果。

原始配置、聊天模板、文件清单、权重分片头摘要和一次性检查脚本曾保存在本地 `_shared/`。
按照当前目录标准，这些过程文件已删除；下文保留经核实的必要结论。没有把它们复制到
其他本地目录。

## 官方配置结论

| 项目 | 核实值 |
|---|---|
| 架构类 | `HYV4ForCausalLM` |
| 主干 | 78 层，hidden size 6,144；首层 dense，后续 77 层 sparse MoE |
| Attention | gated MLA；64 attention heads；QK 256，V 256；KV latent 512 |
| Indexer | 32 heads × 128 dim，top-2,048；21 个 full、57 个 shared 层 |
| MoE | 256 routed experts、top-8、1 shared expert；expert intermediate 2,048 |
| MTP | 1 个 next-token prediction layer |
| 位置编码 | 最大位置 1,048,576；RoPE default，theta 10,000,000 |
| 词表 | 120,832 |
| 源权重 dtype | BF16 为主，部分控制与归一化相关张量为 F32 |

与旧 W8A8 配置去掉量化字段后逐项比较，确认的配置差异只有：

- `transformers_version`：`5.10.2` → `5.16.2`
- 新增 `bitwise_backward_align=false`
- 新增 `use_dsa=true`
- 新增 `use_mla=true`

结构相同不能证明新旧权重数值相同，也不能直接继承旧 W8A8 的精度结论。

## 权重布局结论

通过 131 个 safetensors 分片头核实：

- 共 2,006 个张量、779,960,992,733 个参数元素。
- 1,380 个 BF16 张量包含 779,930,197,312 个元素。
- 626 个 F32 张量包含 30,795,421 个元素。
- 参数 payload 合计 1,559,983,576,308 bytes；分片文件合计
  1,559,983,809,380 bytes。
- 专家权重采用 packed 布局：gate/up 为 `[256,4096,6144]`，down 为
  `[256,6144,2048]`；旧 INT8 产物使用逐专家权重和 scale，二者不能按文件布局直接互换。

本次只核对分片头、offset、shape、dtype 和官方文件清单，没有读取约 1.56 TB 权重 payload
重新计算全量哈希。官方清单中的分片 SHA 不是本次独立复算结果。

## Tokenizer 与生成配置

- 新版 `tokenizer.json` 大小为 9,358,955 bytes，基础词表 120,000，added tokens 832。
- 新旧 tokenizer 的规范化顶层组成一致；新版 tokenizer 类为 `TokenizersBackend`。
- BOS、PAD、EOS 分别为 `<｜hy_start:opensource｜>`、`<｜hy_pad:opensource｜>`、
  `<｜hy_end:opensource｜>`，ID 为 120000、120002、120025。
- 思考标记包括 `<think:opensource>` 和 `</think:opensource>`。
- 聊天模板的 `reasoning_effort` 接受 `high` 和 `no_think`，旧的 `low` 路径已移除。
- 默认生成配置为采样模式，`temperature=0.9`、`top_p=1`、`top_k=-1`；正式适配与验收
  仍以实际服务和评测配置为准，不直接继承这些默认值。

当时使用 Transformers 5.8.1 只确认 `TokenizersBackend` 可以解析；没有执行完整
`AutoTokenizer` 加载与聊天模板端到端测试。

## Eco-Tech W8A8 参考结论

曾核对 `Eco-Tech/Hy4-preview-w8a8@9b5eacd62c7306e64513110cf8cca1d283894c43` 的参考
配置和量化建议：

- 模型结构配置与上述官方版本一致，主要差异是其 `transformers_version=5.10.2`。
- 建议对 routed expert 使用 per-token activation INT8 和 per-channel symmetric weight INT8。
- 建议排除 shared experts、router gate 和 MTP。
- 参考文件的 verified tags 指向 `vLLM_Ascend / Atlas_A3_Inference`，且
  `verified_model_types` 为空。

因此该方案只能作为量化思路参考，不能证明 PPU、NVIDIA 或其他平台已经兼容，也不能作为
当前 PPU W8A8 实现的直接运行配置。

## 证据摘要与限制

| 原资料 | SHA-256 | 说明 |
|---|---|---|
| 官方 `config.json` | `a2c0dc5ec7c5b85b83c5514d1f923dcaeb3510ac0aa0816c3c26a2418ee80f8d` | 固定 revision 配置 |
| 官方 `generation_config.json` | `001b5da7349623a53ce45b6d75a9e29e1b7b0a0532b30589b7ca9a480f137546` | 默认生成参数 |
| 官方 `tokenizer_config.json` | `15267c495102b0ce259408a0b3a9dc11a6de74dd7dd8ef5b9757f64252a9b2df` | Tokenizer 元数据 |
| 官方 `chat_template.jinja` | `8a9925228e1c72edc6806b985ba06a4df2cc4ff803b4710a6d6e25d0ac03fae2` | 新聊天模板 |
| 旧聊天模板 | `26a30a9719e57cdd39358c09d5fdd92a9c96be23d313a8c3670356c3920f3307` | 仅用于差异比较 |
| Eco-Tech 配置 | `774dbdef09ae96bf04eb12a823d5db95705e516f6d8356ceac8c95cdf5e0ff95` | W8A8 参考 |
| Eco-Tech 量化建议 | `73e6dd628f541e6e00df1b1885e82ac0778f0255584f16a9ed1eae2a884e5711` | Ascend 标签参考 |

尚未验证新版 BF16 参考 logits、新 INT8 量化误差、1M context 的实际可用性及新版
SwiGLU 截断语义。相关平台结论必须在目标环境重新验证。
