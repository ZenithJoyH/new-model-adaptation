# 001：OCR 注册、处理器与 0.24.0 权重接口兼容

2026-10-20；`H100-149` / `minicpm-ocr-vllm-native` / NVIDIA TP1 / `vllm-native`。

## 问题、实现与影响

原镜像 `get_config` 报 `minicpm_ocr` 未识别，未修改前不能加载模型。用户包内 vLLM 实现基于更新接口：token 编码帮助函数、处理器签名、模态请求选项合并及 QKV 权重映射均与 0.24.0 存在差异；不适合整体覆盖旧版本。

在实际安装的 vLLM 添加 OCR config、图像/视频处理器及模型适配器，并仅改四个标准注册入口。配置复用已安装 `MiniCPMV4_6Config` 的同构文本/视觉结构，保留 OCR 默认 4x、共享 embedding 和全部视觉层。图像/视频处理的几何实现来自用户包，按本机 Transformers 接口调整导入。配置及处理器按标准注册表惰性导入，其他 model_type 未命中时沿用原路径。

模型语义限制在 `model_executor/models/minicpm_ocr.py`：占位符按真实 target_sizes 计算；请求覆盖与不同模态分别解析；4x/16x 混合批次按逐项 merger 标记分组；视觉窗口 Q/K/V 单独加载到 0.24.0 的 fused 参数。无公共运行热路径的模型名称判断。未修改 MiniCPM-V 4.6、Qwen3.5、权重或 Transformers 安装。

## 实测

- 权重完整加载，模型占用约 2.47 GiB。
- 包内测试首次运行 21 passed、1 failed。失败项仅断言 `load_weights is 4.6.load_weights`，该断言依赖新版本 4.6 已具有正确 fused 权重支持；本次兼容实现保留独立 loader，因此不伪报原测试全绿。
- 真实 eager 服务完成文本、两种图像分辨率、4x、16x、原始小图、自适应小图、多图，以及四并发混合模式，共 11 次请求，均 HTTP 200 且输出正确。前缀缓存显式开启后重复通过。
- Transformers 5.12.1 的同构 `MiniCPMV4_6ForConditionalGeneration`，使用同一权重、OCR config 和处理器，对七组代表性请求做独立参考推理；生成文本及 prompt token 数均 7/7 一致。此结论不等同于原包 5.19 开发版整体环境的逐算子或 logits 一致性证明。
- 前缀缓存开启的两帧 MP4 请求返回 `HELLO OCR\nTEST 149`，HTTP 200、prompt 534 token。

## 可复查证据与限制

原始请求/响应：远端 `04-runs/eager-functional-20261020/` 和 `04-runs/eager-prefix-functional-20261020/`；视频 `04-runs/eager-prefix-video-20261020/`；参考 `04-runs/hf-reference-20261020/results.json`；启动与错误日志保留在对应 run 目录。测试程序在 `03-acceptance/`，不进入产品代码。

实际改动以最终安装文件哈希及 source.patch 为准；无 Git HEAD、PR base 或提交，不伪造 revision。源码审查判断：复用现有注册与模型接口，守卫未命中行为不变；主要未验证范围为其他 GPU、TP/PP、量化、完整 262144 上下文及正式数据集精度/性能。
