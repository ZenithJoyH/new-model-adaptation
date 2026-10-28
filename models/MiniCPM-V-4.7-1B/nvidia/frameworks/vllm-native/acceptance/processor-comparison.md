# 4.7 单图 canvas 处理器对照

2026-09-28 在 `H100-149` 的 `MinicpmV4.7-1B-native` 中，使用
`/data/models/MiniCPM-V-4.7/weights/1b` 随附的
`MiniCPMV4_7Processor` 对一张 128×128 红图进行处理，并将其
`target_sizes_mrope`、图像边界、三通道位置和 decode delta 与已安装
vLLM 4.7 adapter 的 `MultiModalFeatureSpec` 路径比较。

结果：75 个输入 token；图像边界 `[4, 68]`；网格 `[32, 32]`；
视觉网格与参考处理器一致，位置及 delta 完全相同，两个空间通道确实不同。
远端结果为批准根中的 `04-runs/processor-compare-20260928.json`，SHA-256
`52d8d51c41092d1136bc441d2f7ee65a91bc0be611e93141c8f22c07f9bb95b2`；
诊断代码在 `02-issues/minicpmv47-processor-compare.py`。

此对照使用 checkpoint 同一个 canvas helper，证明 vLLM 取得的图像网格、
占位边界及 helper 调用契约相符；它并不构成独立实现的逐 token logits
数值等价证明，也不覆盖复杂多切片或视频帧的参考位置逐项对照。
