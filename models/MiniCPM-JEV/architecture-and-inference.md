# MiniCPM-JEV 架构与推理链

本记录针对用户提供的 `qwen35_2b_l2_triple_value_checkpoint-3000`，属于 OCR 一致性 reward model 的 **value head** 分支。模型不是 MiniCPM-OCR 生成模型；`minicpm-ocr` 仅作为本轮容器环境来源。

## 已核实的模型语义

基座为 Qwen3.5 2B 多模态模型，文本隐藏维度 2048、24 层，每四层一个 full attention，其余为 GatedDeltaNet linear attention。视觉塔为 24 层、patch size 16、spatial merge size 2，输出维度 2048。checkpoint 的 `score.weight` 为 `[2, 2048]`；没有语言生成所需的 `lm_head` 权重。配置文件仍声明 `Qwen3_5ForConditionalGeneration`，不能仅根据该字段选择生成任务。

输入固定为原图、原样 OCR 文本和渲染图。value head 使用无 system、无 assistant 前缀的 prompt，以 `<|im_end|>\n` 结束；图像占位符后不额外添加换行。图像使用 checkpoint 原生 64 token 下限，不能套用 vocab head 的 4 token 下限。原图与渲染图顺序不可交换。

视觉编码结果替换相应图像 token 的文本 embedding，经混合 GDN/attention 文本主干计算后，在最后一个非 padding token 上池化，执行无 bias 的二分类线性头。分数为 `softmax(logits.float())[1]`，表示一致的概率，不生成 token。在产参考阈值为 `0.5606135129928589`。

## 本轮已验证的 vLLM 接入

复用 vLLM 0.24 的多模态 Qwen3.5 实现和原生 `--runner pooling --convert classify`，使用 LAST pooling 与分类激活。已有转换加载完整视觉/文本权重和 `score` 线性头。Plugin 的正式模型注册替换视觉组件，使学习位置表的双线性插值以 FP32 计算后恢复 BF16；其余视觉、语言模型、权重映射和 processor 沿用原生实现。主体为 BF16，分类头保留 vLLM 原生 FP32 默认值，响应为两类 FP32 概率。客户端也可取原始 logits 后 softmax。

PPU 适配使用新容器中实际安装的 `vllm-plugin-FL` 和 FlagGems/FlagGems-vllm；没有导入路径覆盖。eager 和显式 PIECEWISE 均完成严格参考对照。当前 vLLM 的 pooling 配置将三档含 FULL 的模式改为 PIECEWISE；已按序检查，未将自动降级视为 FULL 通过。最终使用原生 EagerAdaptor 保留 PIECEWISE CUDA Graph，避免 Inductor 路径的额外 BF16 数值偏差。运行日志核实真实请求命中 PIECEWISE。

文本位置配置上限为 262144，按当前 profile 使用 50000；训练记录的 12000 与位置配置上限含义不同。本轮样例长 222–782 token；4/8 并发均验证。图捕获覆盖至 1024 batch token，更大 batch 允许原生 eager fallback；没有声称所有 50000 长度输入或所有 batch 都已图捕获。

## 参考与验证边界

现有 HF Transformers 5.10.4 / PPU BF16、SDPA 路径在 2026-10-21 完成 12 样本对照，最大参考分偏差约 0.003685。原始证据位于 `PPU-01:/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt/04-runs/`。本轮必须独立核验新服务；历史 HF 结果不等于 vLLM 已通过。

当前仅提供 value head 权重及 12 个随包样例。vocab head、完整数据集指标和正式生成式 FlagEval 任务不在这些样例的证明范围内。

完整 safetensors：4426567144 字节，618 个 tensor、2213245760 个参数，SHA-256 `6e8e43049340a9d18f711634dcc88eb5880a3cd69c852815e76d5de3aea28dcc`。冻结部署指纹为 `8ce80f553f0ab4dfbfe91bfb097c68c0bb995b3594fa60ce2930c4da73c8ed10`。
