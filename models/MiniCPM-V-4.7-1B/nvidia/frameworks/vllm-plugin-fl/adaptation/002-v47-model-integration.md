# 002：MiniCPM-V 4.7 模型注册与 canvas M-RoPE

## 元数据

- 状态：`hypothesis`（文本、图片、短视频和 decode-full 功能已验证；复杂输入的位置数值等价性与正式精度仍待验证）
- 首次出现/最后验证：2026-09-28
- 模型/Host/容器：`/data/models/MiniCPM-V-4.7/weights/1b` / `H100-149` / `MinicpmV4.7-1B`
- Plugin / FlagGems / vLLM：`3a27a6fb2d514cdf55c00481bf813225dac63319` / `da6727e38f6f8eedef6cba43695a87b4996f9eca` / wheel `0.24.0+cu129`
- 执行模式：单卡 eager 文本与 224×224 单图、decode-full 文本/多图/短视频已跑通；full graph 受 GDN backend 限制

## 事实与完整签名

目标配置架构为 `MiniCPMV4_7ForConditionalGeneration`、`model_type=minicpmv4_7`、
`mrope_mode=canvas`；`ModelRegistry.get_supported_archs()` 中不存在 4.7，
vLLM 仅注册 `MiniCPMV4_6ForConditionalGeneration`。4.6 模型的
`get_mrope_input_positions` 明确复制三个顺序通道；目标 `mrope_minicpmv4_7.py`
按 image/slice bounds、目标 patch 网格、视频帧及结构 token 计算空间位置和 decode delta。
目标模型参考源码 SHA-256 `398ec5cf6a8b31d136fbcaf3671c1be2bc25d3ffc77aa457feec185d26999bd2`；
vLLM 4.6 文件 SHA-256 `fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`。
这项静态差距由后续运行、位置数值检查和模型专用实现验证；不能用来解释
FlagGems attention 的 CUDA 失败。

在已核实的 editable Plugin 源码中新增模型专用
`/vllm-workspace/vllm-plugin-FL/vllm_fl/models/minicpmv4_7.py`，并通过
`vllm_fl:register_model` 懒注册 4.7 架构。配置构建解析为多模态 4.7，
整模权重加载成功。1B `text_config.model_type=qwen3_5_text`，shim 复用 vLLM 4.6
视觉路径和 Qwen3.5 dense 文本骨干，
将目标 checkpoint 的 `mrope_minicpmv4_7.compute_canvas_rope_index` 接到 vLLM
`get_mrope_input_positions`。vLLM 接口的 decode delta 与目标源码差一个基准：
vLLM 按 `max(position)+1-len(input_tokens)` 消费，和已支持的 Qwen2-VL 一致；
目标参考函数返回 `max(position)-len(input_tokens)`。首次 shim 直接返回参考 delta，
代码审查后发现这一处 off-by-one，已将返回值加 1。vLLM
`MRotaryEmbedding.get_next_input_positions_tensor` 明确按 `delta+context_len`
计算下一 token。容器内 CPU 数值对照脚本
`02-issues/minicpm_check_delta.py` 使用四个图像占位 token，得到 prefill
最大位置 4、参考 delta -4、修正后 vLLM delta -3、下一位置 5；断言通过。
修正后源码 SHA-256
`38cbc45fa9bd97a198a382a4b984cbb73eba28795978837807df720f70fa1c93`。

文本 eager 原始记录为 Host/容器同路径
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/04-runs/eager-text-cudnn-filter-v8-20260928/run.log`，
SHA-256 `1b95f296504fd43822c6f7d521c4582c2ca15ff95baf13e43862387683e2cd55`。
224×224 纯红图片通过模型 tokenizer chat template、vLLM 多模态预处理与模型生成，
输出明确识别红色；原始记录 `04-runs/eager-image-v1-20260928/run.log`，
SHA-256 `63d1856d2897e7d4efccae9d0fa058ec55ff081b6ea75c35c75ff7e648ef2d17`。
两次均 TP1、物理 GPU1、BF16、max model len 50000、正常前缀缓存，且都使用
[003](003-flaggems-cudnn-attention.md) 中的进程级算子过滤。这些结果证明最低限度
模型可用，不构成 canvas 位置数值等价或图片理解精度证明。
修正 decode delta 后，在相同 `FULL_DECODE_ONLY` 配置下再次通过文本与单图
推理，且日志记录 decode FULL 捕获 2/2；原始记录
`04-runs/decode-full-v2-delta-fix-20260928/run.log`，SHA-256
`de2430de7b9def2938388a3cc5ed859d929112077360615d0e9a9cad33277a94`。

## 职责、候选扩展点和影响面

Plugin 的 `vllm.general_plugins: fl = vllm_fl:register_model` 是正式注册入口，
`vllm_fl/models/` 是模型专用 shim；vLLM wheel 不可写。
优先复用 vLLM 4.6 的视觉塔、merger、Qwen3.5 dense 文本骨干与权重映射，在 Plugin 注册
独立的 4.7 架构，而不是给 4.6 添加别名。模型专用处理器需要让 vLLM M-RoPE 接口拿到
每个图像/视频特征的网格数据，按目标 processor 的结构 token 计算 canvas 位置。
须核实权重 shape、image/video 占位符、chunked prefill、decode delta、batch/cache
以及 graph replay；已有 4.6 和 Qwen3.5 注册是守卫未命中代表路径。

已有原生容器问题记录与本次权重和架构相同，但执行框架、Plugin revision、导入路径不同，
只提供假设。知识库 TP timeout 与 full graph 条目未出现相同签名，不复用其 workaround。

## 下一步验证

继续检查更复杂的 processor/token 数与 canvas 位置数值等价性，
chunked prefill、长上下文、高分辨率及 batch/cache 组合；
full graph 已优先尝试并由 GDN backend 明确降级，见
[004](004-gdn-full-graph.md)。后续实质改动须重查真实 diff、
PR base、HEAD/dirty、vLLM 未变化及 4.6/Qwen3.5 守卫路径。
任何算子缺口先以已同步 FlagGems revision 检索；不根据相似关键字先行修改共享 backend。

## 2026-09-28 实际差异设计审查

目标源码 checkout 为 `/vllm-workspace/vllm-plugin-FL`，确认的 PR base
`origin/main` 与当前 `HEAD` 均为
`3a27a6fb2d514cdf55c00481bf813225dac63319`；开始前工作树干净，
没有继承差异。当前未暂存差异仅 `vllm_fl/__init__.py` 的 4.7 懒注册，
并有两个本任务未跟踪文件：`vllm_fl/models/minicpmv4_7.py`、
`tests/unit_tests/test_minicpmv47_canvas.py`。前者 SHA-256
`38cbc45fa9bd97a198a382a4b984cbb73eba28795978837807df720f70fa1c93`，
测试 SHA-256 `e167cd0bc70d75e06ee0676ad2c50c0d9a5cfbe995b4aa5e351a9281b6129383`，
注册 diff SHA-256 `94348fa8abe3406545fcfe154bf56612e871347f68f6b6f73042990726946f59`。
无暂存、提交或推送；`git diff --check` 通过。实际文件已逐一审阅。

| 路径或调用方 | 设计影响与验证 |
|---|---|
| 4.7 架构 | 用现有 general plugin registry 懒注册独立架构；模型专用 shim 复用 vLLM 4.6 视觉/权重/1B dense 文本实现，只桥接 canvas M-RoPE；文本、单图、多图、视频 eager/graph 功能实测。 |
| 4.6 与未知 4.8 | `ModelRegistry.get_supported_archs()` 实测 4.6 仍命中、4.7 新命中、4.8 未命中；不改变 4.6 源码或公共 worker。 |
| Qwen3.5 文本骨干与其他模型 | 只沿用 vLLM 既有实例，不改其源码、默认值和 dispatch；本轮没有对其他模型整模推理。 |
| 非 NVIDIA 平台 | 新注册和模型文件没有主动引入厂商 SDK 或平台分支；本轮未在其他硬件实测，不能宣称跨平台适配完成。 |

模型结构与 canvas 位置属于专用 adapter 职责，现有 vLLM 4.6 扩展点足以
复用视觉和权重路径，另起 worker/dispatch 或修改只读 vLLM wheel 都没有必要。
没有吞异常、全局 FlagGems 策略变更或模型名热路径判断。回归测试 2/2 通过，
修正后的 decode-full 文本/单图、多图和视频结果见本记录及
[功能报告](../acceptance/functional-validation.md)。

结论：此模型专用差异可作为 **PR 候选**，不等同完整适配验收；
FlagGems attention 仍需独立复现和有界修复/规避验证，长上下文、TP>1、
高分辨率及正式精度/性能未覆盖。任何实质改动后须重新审查、更新哈希。
未按本次请求提交、推送或创建 PR。
