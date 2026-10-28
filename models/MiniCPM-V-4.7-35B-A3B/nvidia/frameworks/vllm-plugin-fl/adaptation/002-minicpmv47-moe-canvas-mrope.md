# 002：MiniCPM-V 4.7 MoE 与 canvas MRoPE 适配

## 元数据

- 状态：`mitigated`（TP2 eager、decode-full 和用户选定分段图的文本/图像功能回归通过；完整正式验收未通过）
- 日期：首次 2026-09-28，最后复核 2026-09-30
- Host / 容器 / 权重：`H100-149` / `MinicpmV4.7-35B` / `/data/models/MiniCPM-V-4.7/weights/35b-a3b`
- 组件：可编辑 Plugin `/vllm-workspace/vllm-plugin-FL`，基础 revision `3a27a6fb2d514cdf55c00481bf813225dac63319`；vLLM wheel `0.24.0+cu129` 只读。

## 签名和根因假设

权重声明 `MiniCPMV4_7ForConditionalGeneration`，其语言子配置为 `qwen3_5_moe_text`，包含 256 个专家、每 token 8 个路由专家；`mrope_mode=canvas`。已安装的 vLLM 只有 MiniCPM-V 4.6 适配，使用稠密 Qwen3.5 并把三个 MRoPE 通道全设为一维顺序位置。直接复用会导致权重结构和图像位置语义不匹配。4.7 的 Transformers 自定义源码提供 `build_image_bounds` 与 `compute_canvas_rope_index`，是数值对照的来源。

## 扩展点、接口和影响范围

Plugin `register_model()` 通过 vLLM `ModelRegistry.register_model()` 注册新架构；`vllm_fl.models.minicpmv4_7` 复用 vLLM 4.6 的视觉编码、merger、embedding 注入和权重映射，语言模块改为现有的 Qwen3.5 MoE 实现。`SupportsMRoPE.get_mrope_input_positions()` 从本次多模态特征的 `tgt_sizes` 与权重自带的 canvas 算法生成位置，缓存缺失尺寸时显式报错。运行配置须关闭多模态处理器缓存，避免缓存命中后丢失尺寸。该接口影响 MiniCPM-V 4.7 的图像/视频、eager 和 graph；现有 4.6 和 Qwen3.5 注册名不应改变。其他平台未验证。

替代方案是修改只读 vLLM wheel 或把 4.7 假装成 4.6，前者越过组件边界，后者语义错误。当前方案仍需验证处理器 prompt 展开、视觉维度、权重键、MRoPE 相等性和多模态缓存行为。

## 受控比较与证据

| 步骤 | 唯一变量 | 观察 | 结论 |
| --- | --- | --- | --- |
| 基线 | 未注册 4.7 | vLLM 无 4.7 模型实现；4.6 使用稠密主干和顺序 MRoPE | 不能直接加载 35B-A3B |
| 插件注册 | 增加独立 4.7 类和注册入口 | `ModelConfig` 识别 4.7 配置及 `Qwen3_5MoeTextConfig`；`ModelRegistry` 解析到新 Plugin 类，声明 multimodal/hybrid/inner state | 仅静态入口通过，仍未证明推理正确 |
| TP2 eager 权重与文本 | GPU 4、5，BF16，50,000 上下文，前缀缓存开启，`--mm-processor-cache-gb 0` | 17/17 shard 加载；`/v1/models` 返回 200；文本聊天返回 200、16 token，首请求 98.32 秒 | 最小文本生成通过；输出因 16 token 上限截断，不能作为回答质量验收 |
| TP2 eager 图像 | 同一服务，64×48 纯红 PNG 与颜色问题 | 首请求 210.11 秒，重复同一请求 13.55 秒；两次均返回 200 和“红色”，30 completion tokens | 最小多模态路径通过；首轮含编译/预热开销，不作为稳态性能结论 |
| canvas 位置 CPU 对照 | 64×48 图像，权重自带 processor 与新适配算法 | `input_ids` 长度 72、`target_sizes=[[28,36]]`；三通道 3×72 位置逐项相等 | 已验证单图 prefill 位置；decode 偏移、批量与视频仍待测 |
| decode-full 图 | 仅更换服务图模式 | `decode, FULL` 捕获；六项文本、红蓝图和 replay 均正确 | 达到该模式的最小功能回归；见问题 005 |
| 用户选定分段图历史脚本 | 显式 `FULL_AND_PIECEWISE`，TP2、GPU 4/5、前缀缓存开启 | 当时脚本启动后，mixed prefill/decode 分段图 5/5、decode 全图 4/4；六项图文和十并发十题均正确 | H100 配置可提供文本和图片服务；分段 prefill 不满足 profile 正式 graph 验收，详见[历史服务验证](../acceptance/service-validation-2026-09-30.md) |
| 2026-09-30 已安装 Plugin 的脚本 | 同一 Host/GPU/TP/图模式，端口 8021、100,000 token，`--mm-processor-cache-gb 0`，不设置 `PYTHONPATH` | mixed prefill/decode 分段图 51/51、decode 全图 51/51；图文 6/6、十并发 10/10，`/health` 200 | 当时运行环境功能通过；极限上下文、视频、正式精度/性能仍未测，见[历史服务验证](../acceptance/service-validation-installed-plugin-2026-09-30.md) |
| 2026-10-01 前一版精简脚本 | 去掉冗余分支和显式 dtype，其余服务参数不变 | mixed prefill/decode 分段图 51/51、decode 全图 51/51；有效 BF16、图文 6/6、`/health` 200；本轮未重复十并发 | 当时短图文功能通过，见[精简验证](../acceptance/launcher-simplification-2026-10-01.md) |
| 2026-10-01 用户再改的当前脚本 | 删除 100,000 token 上限及保护/缓存变量，保留 GPU 4/5、TP2 和图模式 | 实际上限 262,144；两类图各 51/51，`/health` 200，图文 6/6；本轮未重复十并发 | 短图文功能通过，但脚本缺占用保护与目录约束，见[新脚本验证](../acceptance/user-revised-launcher-validation-2026-10-01.md) |

2026-09-28 启动前 GPU 查询显示设备 0、2、3 已有其他 vLLM 进程，4–7 空闲。按用户指定，本任务仅使用 `CUDA_VISIBLE_DEVICES=4,5`、TP=2 的候选启动；不触碰已有进程。先执行 eager 最小推理，再按 profile 做 full graph，不能用静态注册充当完成证据。

## 验证和退出条件

实际差异范围已审查：Plugin 注册入口增加 9 行，新模型适配 129 行；`git diff --check` 和新文件 AST 解析通过，vLLM 与 FlagGems 未改动。仍待验证：视频推理、decode 位置数值对照、更广的变输入批量、full mixed 图，以及正式精度与性能。eager 原始日志位于 `H100-149:/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/eager-tp2-native-cudnn-20260928/server.log`；当前服务运行目录与脚本见上面的新脚本验证记录。若尺寸或位置不能保持正确，应定位最早不匹配项，不以顺序 MRoPE 回退。当前不具备 PR 或完整适配结论。

2026-09-30 安装与最终脚本验证后重新审查实际源码：Plugin HEAD 仍为 `3a27a6fb2d514cdf55c00481bf813225dac63319`，工作树只含 `M vllm_fl/__init__.py`（注册入口 9 行）和 `?? vllm_fl/models/minicpmv4_7.py`（129 行，SHA-256 `2e96de24dc2aa003ed21b146e602102bf9ee30ca075dfe6a8986cb45b006213e`）；后者 AST 解析通过。安装没有向 Plugin 源码添加其他改动，FlagGems 工作树干净、HEAD `da6727e38f6f8eedef6cba43695a87b4996f9eca`，vLLM 保持只读。影响矩阵：新注册名仅命中 MiniCPM-V 4.7，4.6 和其他模型沿原有注册路径；canvas M-RoPE 影响 4.7 图像/视频的 eager 与 graph，多模态缓存缺尺寸时显式报错；本次只覆盖 H100 文本/单图和 TP2 graph，其他平台与视频未验证。正式验收与设计审查仍分开，未提交、推送或创建 PR。
