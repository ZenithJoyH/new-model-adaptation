# 015：锁定版 O 投影 FP8 helper 不适配 V4.1 W8A8

## 元数据

- 状态：`open`（H100 小张量数值验证通过；整模 eager/graph 待验证）
- 首次出现及最后验证：2026-09-23
- Host / 容器：`H100-149` / `deepseek-v41-plugin-adapt-20260923`
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- Plugin / vLLM / FlagGems-vllm HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `ee0da84ab9e04ac7610e28580af62c365e898389` /
  `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`

## 问题及受控复现

模型 `quantization_config` 明确将全部 `attn.wo_a` 设为对称、按通道的
INT8 权重和按 token 动态量化激活。Plugin 现有 W8A8 线性内核加载后把
`wo_a.weight` 整理为 `[K,N]` 行主序，规模 `[K, groups*R]`，并保存
`weight_scale`。原 O 投影仍调用锁定版 V4 的 FP8 helper，它把输出量化为
FP8，并访问 `wo_a.weight_scale_inv`，不符合此模型权重布局及缩放接口。

在 H100 上以 INT8 `wo_a` 合成输入调用原 helper 的单独复现还发现更早的
阻断：锁定版 vLLM 逆 RoPE Triton kernel 报
`TypeError: dynamic_func() missing 1 required positional argument: 'launch_pdl'`。
复现脚本为远端
`/public/flagos/jinghao/deepseekV4.1/02-issues/h100145-ring-20260923/o-proj-repro-h100149.py`。
这是独立于大模型权重加载的接口问题；尚未通过整模执行到该算子。

## Plugin 方案与范围

已检索当前 FlagGems-vllm 与 FlagGems：已有 INT8 动态量化与 scaled matmul。
FlagGems-vllm 的 Cutlass 入口要求列主序 B，不适合当前 Plugin post-load
行主序权重；其 `triton_scaled_mm` 支持当前布局，因此优先使用后者。
两库的逆 RoPE 融合算子只输出 FP8，没有 W8A8 所需的未量化输出。
Plugin 在 `vllm_fl/models/deepseek_v4_1/nvidia/o_proj.py` 增加只处理
逆 RoPE 和 group 排列的 Triton kernel，然后调用 FlagGems-vllm
`scaled_int8_quant`、`triton_scaled_mm`。FlashMLA 与 FlashInfer 两个
V4.1 NVIDIA 后端经同一 helper 接入；非 INT8 路径仍调用原 FP8 helper，
在当前锁定栈未验证。vLLM、FlagGems 和权重均未修改。

补丁：
`/public/flagos/jinghao/deepseekV4.1/02-issues/h100145-ring-20260923/v41-o-proj-h100149.patch`。
应用前 `flashmla.py` / `flashinfer_sparse.py` SHA-256 分别为
`481bb7ef6a47981ec07cfb9005b7d9fcea7bd16389c3404441d3c7af2779e8ff` /
`288405b9d0e73333f7c35485600dbb6b897beada65650349f72b356125eef7b0`。
Ansible `--check --diff`、`git apply --check` 和实际应用通过。

## 验证与限制

H100 两组、每组一头的 BF16 合成测试，分别比对 PyTorch 逆 RoPE 和
逐组 INT8 缩放矩阵乘：逆 RoPE 最大绝对误差 `0.0`，最终输出最大绝对
误差 `0.0`，形状 `[3,256]`。测试脚本为远端
`02-issues/h100145-ring-20260923/o-proj-test-h100149.py`。
该结果不等于整模推理、真实 checkpoint 数值、图捕获或精度通过。
后续需验证实际 `wo_a` 加载布局、eager/graph，并清理或限定未验证的
FP8 fallback。知识库处理状态：`needs-validation`。
