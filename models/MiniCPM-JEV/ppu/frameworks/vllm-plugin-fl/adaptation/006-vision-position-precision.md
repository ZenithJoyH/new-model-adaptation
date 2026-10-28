# 006：视觉位置插值的 BF16 提前取整

2026-10-23，状态：根因单变量、Plugin eager/最终 graph 整模型回归通过。

## 证据与根因

004 的两容器处理器对照对 12 个样例逐项比较 input_ids、attention_mask、pixel_values、image_grid_thw、mm_token_type_ids 的 shape/dtype/SHA-256，全部相同，见工作根 `04-runs/processor-comparison-20261023.json`。因此不能将数值差异归为图像预算或 tokenizer 版本。

同一新容器、同一 BF16 权重、同一 SDPA、同一完整 HF 多模态基座，仅将视觉学习位置表的双线性插值由 BF16 中间权重/乘积改为 FP32，最大概率误差由 0.009766340 降至 0.003685066，末例由 0.922202528 降至 0.915808916，后者与此前 HF 5.10.4 环境完全相同。原始容差仍为 0.005。证据为 `04-runs/hf-base-numerical-v2-20261023/` 与 `04-runs/hf-fp32-pos-20261023/`；缺失/错形权重为空，只有单独使用的 score.weight 出现在 unexpected。

HF 5.10.4 视觉位置插值使用 FP32 bilinear_weights；HF 5.8.1 把权重转换为位置表的 BF16。只读 vLLM `qwen3_vl.py` 的原生及 Triton 插值也把权重转换为 output dtype，存在相同提前取整。差异比较在 `04-runs/transformers-vision-comparison-20261023.diff`。Torch 版本也不同，但上述同容器单变量实验已直接定位此精度影响。

## 所选层级与实现

此变更属于 Qwen3.5 dense 多模态模型的视觉位置编码，不放在 worker、服务名称或 checkpoint 路径分支中。通过 Plugin 正式 ModelRegistry 将 `Qwen3_5ForConditionalGeneration` 接到继承原生模型的 shim；文本模型、MoE 和其他 VL 架构的注册保持原状。

原生模型构造器直接构造视觉组件，没有可覆盖的工厂方法。因此只适配其约 30 行组件构造，换用视觉组件子类；forward、语言模型、混合 cache、权重加载和 processor 均沿用原生实现。显式复用相同 multimodal processor 注册。没有复制完整上游模型、临时改写上游模块符号或修改 vLLM 文件。

位置表转为 FP32，调用 `F.interpolate(..., mode="bilinear", align_corners=True)`，保留原有空间 merge 和时间重复次序，最后转换回模型 dtype。正常 PyTorch dispatch 在 FlagGems 上使用已存在的 `upsample_bilinear2d`；已核查该算子支持 align_corners 和 FP32，不另写 Triton kernel，也不绕过现有注册选择。其余视觉计算及输出仍为 BF16。

产品文件：`vllm_fl/ops/vision_position.py`、`vllm_fl/models/qwen3_5_vl.py`、`vllm_fl/__init__.py` 的模型注册。维护测试为 `tests/unit_tests/worker/test_vision_position.py`。

## 验证与边界

- CPU/PPU、FP32/BF16，独立四角插值 oracle，验证 spatial merge 与多帧重复。
- PPU 使用真实 FlagGems 双线性算子，覆盖 warmup/capture/两次改变位置表的 replay。
- 非法 merge 网格拒绝；worker 原有输出协议四项复测。
- 当前 9 passed，JUnit XML 为 `04-runs/vision-position-tests-v2.xml`。
- 初稿单测用独立 FP32 坐标公式与一 ULP 直接比较，在近零消减处出现 1.624e-6 的 FP32 舍入差异。现将 16 个 FP32 epsilon 的浮点运算误差界与 BF16 存储 ULP 分开；整模型 0.005 容差未改变。旧实现负例仍需在相同界限下失败，不能以调整 oracle 掩盖 BF16 权重取整。
- 旧实现负例 `04-runs/vision-position-before-v2.log` 在同一误差界下失败，确认不是通过放宽界限掩盖 BF16 权重问题。首轮负例脚本导入失败单独保留，未用作数值负例。
- 真实整模型最终配置 eager/PIECEWISE 原生概率两轮 12 样例均通过，最大误差 0.004417300；4/8 并发也通过。最终使用原生 FP32 分类头，避免 BF16 概率输出取整；图编译差异处理见 007。
- 最终源码 Plugin 9 passed、FlagGems 3 passed；其他实际硬件、量化、TP/PP 多卡和 generation 未执行，不宣称通过。完整差异设计审查见 008。

知识库状态 local-only。退出条件：原生 Qwen3.5 视觉插值采用等价 FP32 中间计算，并通过此独立 oracle、变输入图重放及同一整模型样例。
