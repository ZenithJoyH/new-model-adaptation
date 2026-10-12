# 012：M3.1 参考图像预处理补丁审查

## 元数据与边界

- 状态：`hypothesis`（图像几何和 token 差异已验证；精度收益、像素数值及服务资源尚未验证）；首次与最后验证：2026-10-03。
- Host `PPU-07`，容器 `minimaxM3.1`，镜像 `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`；Host/容器工作根同为 `/mnt/nfs/users/jinghao/minimaxM3.1`，根与补丁的设备号/inode 在两侧一致。
- 目标模型 `/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`；Plugin editable tree `/workspace/vllm-plugin-FL` HEAD `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加既有任务 diff，vLLM `/workspace/vllm` HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`，FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`。
- 待审补丁 `minimax-m31-reference-image-preprocessing.patch` SHA-256 `f616d87129005ce1ed4a7c17720678022f0665c66808b614573fde2feafc2715`。`git apply --check` 通过，但新模块不存在、Plugin 入口没有安装调用；用户启动的 TP16、204800、64 sequences、`FULL_DECODE_ONLY` 服务仍为未打补丁版本，`/health` 200。本轮没有应用补丁、停启服务或修改产品源码。

## 问题签名与原始证据

目标 checkpoint `preprocessor_config.json` SHA-256 `41fa5397ebd57aeb7bf2f1fff9b1cbf98839678bf6b7193efac1035933bea0ec` 声明 `max_pixels=451584`、`size=672×672`；`vision_config.image_size=672`。当前 vLLM `MiniMaxM3VLImageProcessor` 默认按 451584 面积上限做 `smart_resize`，且 `max_long_side_pixel=None`。同 400 道题干在用户原始 NVIDIA、PPU 文件中逐项一致；前者 `max3.1_erqa_nv.json` SHA-256 `f48c9df64e3a0434d437a265098f907603bce73b36b07b58e6d6d332a14e4`，后者 `max3.1_erqa_ptg.json` SHA-256 `b93ea0b82b463554f301127d46b296970a6cf94f6733012d0fdb9c167df67a91`。NVIDIA 的 `usage.prompt_tokens_details.image_tokens` 在 400 题都有值；PPU 文件没有该细项。

基于 [FlagEval/ERQA](https://huggingface.co/datasets/FlagEval/ERQA) 固定 revision `6bf393250b0981c3f6dd77eb58b6d6879038633f` 的 630 张图片尺寸清单 `03-acceptance/erqa-full-temp1-p95-k20-c32-20261002/manifest.json`（SHA-256 `224cfd3a6a0181d4a468a48cdc02b74b3993635ba1034c7f1f278260dc657817`），独立计算现有 `smart_resize` 与补丁 `aligned_size`：

| 指标 | 现有路径 | 补丁公式 |
|---|---:|---:|
| 630 张图片中改变尺寸 | — | 587 |
| 全部图片视觉 token 估算合计 | 237820 | 433645 |
| 单张最多视觉 token | 576 | 3960 |
| 400 题中与 NVIDIA `image_tokens` 完全一致 | 15 | **400** |
| 400 题中预测的 `NV.prompt_tokens - PPU.prompt_tokens` 完全一致 | — | **400** |

例如 `ERQA_1` 原图 320×256：当前路径 308×252、99 视觉 token、PPU prompt 364；补丁路径 336×280、120 视觉 token、NVIDIA prompt 385。二者差 21 token，恰好吻合。仅启用 vLLM 已有 `max_long_side_pixel=2016` 路径、保留其 112 像素短边下限和四舍五入规则时，仅 **118/400** 题与 NVIDIA 图像 token 数一致，不能替代此补丁的对齐公式。原 NVIDIA 服务的具体预处理源码不可见，因此 400/400 的 token 对齐证明几何与计数一致，尚不证明插值后的像素值逐位一致。

## 补丁接口、受控检查和影响范围

补丁在 Plugin `register_model()` 中调用新模块安装函数，改写共享 `MiniMaxM3VLImageProcessor.preprocess/get_number_of_image_patches` 和 `MiniMaxM3VLProcessingInfo._get_vision_info/get_image_size_with_most_features`。实际扩展点是 Plugin 模型注册时的兼容 hook；vLLM 保持只读。独立 `python3 -B` CPU 子进程仅从补丁文本载入函数并临时 monkey patch 自己的进程，未修改运行中服务：

- 320×256 PIL、NumPy HWC 和 Torch CHW 三种输入均能预处理，`image_grid_thw` 从 `[1,18,22]` 变为 `[1,20,24]`，原始 patch 数从 396 变为 480；`_get_vision_info` 的 image token 由 99 变为 120，三处计数一致。重复安装返回 `False`，具备此进程内幂等性。
- 同一子进程的视频处理器 320×256、8 帧 `_get_vision_info` 前后均为 396 token，证实这个实例的 video 分支保持旧路径；未运行视频请求或不同尺寸回归。
- 最大图片 dummy 尺寸由 672×672 提高到 2016×2016，单图最大视觉 token 上界由 576 提高到 5184，**9 倍**。当前服务 PPU 显存约 85,000/98,304 MiB（`./scripts/accelerator-check --limit PPU-07` 2026-10-03 输出前四卡），新预热、encoder cache、KV 容量和 TP16 图捕获能否通过尚未实测。

## 诊断、方案判断与限制

- 已确认：补丁在现有 Plugin 工作树上可干净应用；其公式能对齐这 400 题的 NVIDIA 图像 token/总 prompt token 差；常见 CPU 输入的尺寸、预处理和 token 计数相互一致。它**目前对运行中的服务无效**，因为源码未应用，且运行中进程不会动态载入新文件。
- 未确认：私有 M3.1 官方参考实现是否确实采用 2016 长边、168 短边和该 PIL BICUBIC 像素语义；原 NVIDIA 服务代码、原始评测采样参数也未知。目标 checkpoint 自带配置仍是 672 面积上限；不能只用另一服务的 token 数宣布模型精度会提高。已有相同解析口径的 NVIDIA 239/400 与当前 PPU 采样复测 230/400 也不是受控单变量对照。
- 设计风险：安装入口没有 M3.1 或 checkpoint 守卫，会改变共享 MiniMax M3 图像处理器在所有使用该 Plugin 的模型/平台上的默认行为，且绕过现有 `max_pixels` 约束。2016 dummy 使资源预算显著上升。要作为生产适配，应把规则限定在已证实采用该参考语义的模型配置，核查 PIL/数组/张量、`do_resize=False`、短边/长边边界、多图和视频守卫，并完成实际 TP16 启动、多模态请求、同题精度与内存比较。
- 本次属于**诊断性补丁审查**；尚未选择作为 root-cause fix 或生产 workaround。与[问题 011](011-erqa-garbled-generation.md)的乱码签名不同：已验证的采样配置让 400 题没有替换字符，图片几何差异在此之前就存在；不能把乱码归因于缩放。与[问题 010](010-red-image-color-error.md)的纯色误判也没有已证实因果关系。无 FlagGems 算子变更；知识库状态 `needs-validation`，不更新 `framework.yml` 正式验收状态。
