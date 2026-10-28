# 适配问题索引

- [008：迁移 FlagGems-vllm paged Flash 优化](008-flaggems-vllm-flash-attention.md)：2026-10-12 已支持实际 H8/HKV2/D256、block288；66 项回归及 12 项实际模型检查通过，8000 服务启用优化。算子 prefill/mixed 加速约1.85–2.20倍；正式精度和整模优化后性能未重测。

- [001：MiniCPM-V 4.7 注册与 canvas M-RoPE 差距](001-model-registration-canvas-mrope.md)：2026-10-08 已将实际安装 Plugin 切换为 `support-minicpmV4.7@aa4228e`，工作树干净；14 项单测、4 项 checkpoint canvas 对照、5 项 BF16 离线视觉及 35 项图模式服务请求通过。正式验收另行执行。
- [002：图片请求颜色错误及重复标点](002-visual-output-corruption.md)：2026-10-08 已修复实际安装的 FlagGems split-KV 合并布局错误，34 项回归及真实 Q/K/V 三次对照通过；已提交 [Issue #6872](https://github.com/flagos-ai/FlagGems/issues/6872) 和 [PR #6873](https://github.com/flagos-ai/FlagGems/pull/6873)。已移除 Plugin FP32 实现及 OOT 注册，BF16 离线 7/7 与原脚本 FULL_AND_PIECEWISE 服务 25/25 请求通过；正式精度/性能未执行。
- [003：GDN backend 使完整 graph 请求降为混合 PIECEWISE](003-gdn-full-graph.md)：FULL 阻断已复现；新源码下 decode-full 捕获 7/7，图像基本检查通过，正式执行模式验收待证据绑定。

## 当前 Host 的适配结论

2026-10-08 更新：FlagGems attention 修复后已撤除专用 FP32 缓解，实际安装 Plugin 已切换为统一分支 `support-minicpmV4.7@aa4228e`，包含模型注册与 canvas 桥接；当前 PPU2 服务按用户原脚本运行 `FULL_AND_PIECEWISE`，混合 PIECEWISE 与 decode FULL 各捕获 51/51，35/35 文本/单图/双图/切片/视频及并发回归通过。服务 API PID `445525`，端口 8000，健康检查 200。正式验收状态未更新；以下 2026-09-29 结论属于历史配置，不能替代当前验收证据。

2026-09-29，当前 Plugin 未提交差异已逐文件审查：4.7 模型注册与 canvas 位置桥接在模型 adapter，T-Head BF16 视觉 attention 的 FP32 分块缓解在既有 OOT 扩展路径。PPU-13 的聚焦单元测试 7/7、eager 离线红蓝图和当前 decode-full 服务文本及 224/448 红蓝图均通过；当前部署身份探针 27/27。vLLM wheel/source 与 FlagGems wheel/source 未被修改。基础实现和受限硬件的最小推理已完成；GDN 导致 `FULL` 降为混合图，故正式验收需绑定最高可用 `decode-full`。正式十并发科学题、精度和性能单列于 `acceptance/`，不由本结论代替。
