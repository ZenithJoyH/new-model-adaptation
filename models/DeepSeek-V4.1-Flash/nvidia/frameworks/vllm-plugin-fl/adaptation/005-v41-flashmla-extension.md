# 005：锁定版 FlashMLA 扩展不可用

## 元数据

- 状态：`open`（Plugin 已接入 FlagGems-vllm；整模 eager/graph 数值未验证）
- 首次出现及最后验证：2026-09-23
- 模型/Host/容器：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`，`H100-145`，`xingchen4-flagos`
- Plugin / FlagGems-vllm / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式：元数据局部构造、整模 eager 诊断启动中

## 签名与已有实现

锁定版 `vllm.v1.attention.ops.flashmla.get_mla_metadata()` 在 SWA builder
分配 decode 计划时抛 `RuntimeError: vllm._flashmla_C is not available`；
同一环境也没有 `vllm._C`。已核对 FlagGems 和 FlagGems-vllm，均有
`get_mla_metadata`、`flash_mla_with_kvcache`、`flash_mla_sparse_fwd` 的
Triton 实现。按用户指定优先使用 FlagGems-vllm：其 decode 接口支持 V4.1
的 512 维查询、584 字节 FP8 cache、附加压缩缓存和 top-k 长度；prefill
接口支持 512 维 BF16 输入，但返回新张量、不接受 vLLM 的 `out=`。
这属于已存在算子的接口差异，不新写 Triton 算子。

## 受控修复与证据

Plugin 的 `sparse_mla.py` 仅对 V4.1 用 FlagGems-vllm 的
`get_mla_metadata` 创建 scheduler；`nvidia/flashmla.py` 的 decode 直接调用
FlagGems-vllm，prefill 把返回结果复制到原有输出切片。旧 vLLM 和其他模型
路径不变。补丁保存在
`H100-145:/public/flagos/jinghao/deepseekV4.1/02-issues/h100145-ring-20260923/flash-fallback.patch`。
同一 H100 的 SWA 局部测试在修改前因缺扩展失败，修改后通过，原始回执为
`04-runs/h100145-swa-20260923/adapter-test.json`。该结果只验证 scheduler
对象和 V4.1 prefill 规划；FlagGems-vllm 内核的完整 FP8/BF16 数值、
TP8 推理和 CUDA graph 尚待完成，不把接口相符当作正确性证明。

本次未修改 vLLM 或 FlagGems-vllm 源码，容器保持运行。整模诊断日志写在
`04-runs/h100145-eager-20260923/service.log`，缓存及临时文件分别在
`06-cache/h100145-eager-20260923`、`05-tmp/h100145-eager-20260923`。
知识库处理状态：`local-only`。
