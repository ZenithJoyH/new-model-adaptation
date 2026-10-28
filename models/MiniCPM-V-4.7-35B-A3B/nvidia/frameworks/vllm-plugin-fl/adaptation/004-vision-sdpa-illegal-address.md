# 004：视觉假输入运行时 FlagGems SDPA 非法显存访问

## 元数据

- 状态：`hypothesis`；2026-09-28
- Host / 容器 / GPU：`H100-149` / `MinicpmV4.7-35B` / 4、5，TP=2
- 运行证据：`04-runs/eager-tp2-cacheiso-20260928/server.log`
- Plugin 基础 revision `3a27a6fb2d514cdf55c00481bf813225dac63319`，FlagGems `da6727e38f6f8eedef6cba43695a87b4996f9eca`，vLLM `0.24.0+cu129`

## 完整失败签名

第二轮服务显式开启 prefix caching，并用逐进程 Triton 缓存。两名 worker 均进入模型加载，TP0 加载完 17/17 safetensors 后在 `determine_available_memory` 的 `profile_run()` 执行视觉假输入。首个 CUDA 错误位于视觉层 `Idefics2VisionAttention.forward()` → `torch.nn.functional.scaled_dot_product_attention` → FlagGems `_scaled_dot_product_cudnn_attention` → `flag_gems.ops.attention._attn_fwd`，报 `CUDA illegal memory access`，多个 autotune 配置随后连续失败。后续 EngineCore/API 失败是传播症状。TP1 尚未报告相同首错；此签名只覆盖 BF16、该视觉假输入和 eager 初始化，不推断真实图像或 graph。

## 归属、假设与受控实验

视觉层源自只读 vLLM 4.6 实现，新 4.7 适配复用它；FlagGems CUDA 注册由 editable Plugin `worker.py` 调用。该调用使用插件已有的 `VLLM_FL_FLAGOS_BLACKLIST_APPEND` 扩展点，因此可在本任务服务配置中仅排除 `_scaled_dot_product_cudnn_attention`，使 Torch 原生 SDPA 处理此形状，而其他 FlagGems 算子保持既有分发。此举是针对首错的**运行缓解**，不是已证明的算子根因修复。下一轮保留 TP2、权重、dtype、设备、prefix caching、逐进程缓存和 eager，其语义变量仅为该算子排除。若启动成功，还需用数值对照验证视觉输出；若仍失败，记录新的首错并停止扩大排除范围。

已核实该轮服务自动退出、GPU 4、5 回到零占用；未触碰其他 Host、容器、服务或只读源码。首次缓存失败见 issue 003，两者签名不同。

第三轮只排除 `_scaled_dot_product_cudnn_attention` 后，Torch 转入另一条 FlagGems `cudnn_attention_forward`。第四轮把第二项误写为 ATen 算子名 `_cudnn_attention_forward`，没有改变实际分发，故重复相同首错；此轮不算有效对照。FlagGems `GeneralOpRegistrar.config_filter()` 按实现函数 `__name__` 过滤。改为 `cudnn_attention_forward` 后，在不加载模型的 fresh process 中，两条 ATen CUDA dispatch 均指向 PyTorch `RegisterCUDA_0.cpp`，不再指向 FlagGems。此静态分发验证只证明排除生效，尚未证明模型运行或数值正确。

第五轮保留其余配置、使用准确的两项实现函数名排除后，TP2 eager 服务完成 17/17 shard 加载和视觉假输入 profiling，API 就绪；纯红图像在首轮和重复轮均正确回答“红色”。证据位于 `04-runs/eager-tp2-native-cudnn-20260928/server.log`，启动配置位于 `01-environment/start-eager-tp2-native-cudnn.sh`。这验证了当前形状下运行缓解的有效性；没有证明 FlagGems 两个算子的通用数值正确性或根因。

## 退出条件

在可复现最小形状上定位 FlagGems attention 的非法访问并完成算子修复、eager/graph 数值与性能回归后，移除黑名单并重跑正式验收。知识库状态 `needs-validation`，不据此推广。
