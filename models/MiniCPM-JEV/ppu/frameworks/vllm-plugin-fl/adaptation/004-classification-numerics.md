# 004：分类服务与原始 BF16 参考的概率差异

2026-10-23，状态：定位中。范围为新容器、单 PPU、双图 Qwen3.5 value head。保持原 demo 的 BF16 容差 0.005，不以分类阈值一致代替概率通过。

## 已验证对照

工作根为 framework.yml 中的 `vllm-plugin-fl`，下列均为其 `04-runs/` 子目录。

| 配置 / run | 请求数 | 最大概率误差 | token / 阈值侧 | 判定 |
| --- | ---: | ---: | --- | --- |
| eager，默认 FP32 head；`eager-worker-fixed-samples-20261023` | 24 | 0.008402884 | 全部一致 | 超容差 |
| eager，BF16 head；`eager-bf16-head-samples-20261023` | 24 | 0.009438813 | 全部一致 | 超容差 |
| BF16 head，原生 logits 接口 + 客户端高精度 softmax；`eager-bf16-raw-samples-20261023` | 12 | 0.008353489 | 全部一致 | 超容差 |
| 上一配置仅改视觉 TORCH_SDPA；`eager-sdpa-raw-samples-20261023` | 24 | 0.008353489 | 全部一致 | 无改善，超容差 |
| 实际 PIECEWISE，BF16 head / raw logits；`graph-auto-piecewise-samples-20261023` | 24 | 0.008637927 | 全部一致 | 超容差 |

两轮重复输出一致。主要异常为末例 `olm_arxiv_math__2503.08272_pg14_10`，原始在产参考 0.912436187。已有 HF/PPU 的独立历史实测为 0.915808916（`../04-runs/transformers-5.10.4-20261021-1437/value-12.json`），也存在 BF16 跨后端差异，但该历史结果不能替当前 vLLM 通过。

vLLM 原生 pooling 默认 FP32 分类头，由 `model_config.head_dtype` 控制；原 demo 模型及 score 为 BF16。使用官方 `--hf-overrides '{"head_dtype":"model"}'` 可对齐分类头 dtype。原生 classifier activation 直接对 logits 执行 softmax，BF16 head 会返回 BF16 概率；原 demo 先 `logits.float()` 再 softmax。逐请求 `use_activation:false` 返回原始 logits，客户端计算 softmax 证实响应取整不是剩余误差的主因。

原配置多模态 encoder 使用 FLASH_ATTN，HF demo 使用 SDPA。受控对照仅切换原生 `--mm-encoder-attn-backend TORCH_SDPA`，对误差无改善，故退出此实验设置。没有修改视觉权重、图像预算、prompt、参考值或容差。

下一项使用同容器 Transformers 5.8.1 的完整 `Qwen3_5Model` 加原始 `score.weight` 构建诊断参考，绕开该版本现成 sequence-classification 类仅加载文本的已知问题。必须验证视觉权重完整加载以及所有 missing/mismatched keys 为空；仅允许 unexpected `score.weight`，该权重另行读取并用于 LAST pooling。脚本留在远端 `02-issues/hf-base-numerical.py`，不修改模型或 HF 产品代码，不作为交付推理路径。

不宣称正式精度通过，也不将此 12 样例集视为完整评测集。无模型代码改动、参考值覆盖或按样例校准。
