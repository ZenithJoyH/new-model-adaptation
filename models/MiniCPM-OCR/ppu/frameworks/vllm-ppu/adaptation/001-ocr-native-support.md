# 001：OCR 标准注册与原生接口兼容

2026-10-27，PPU-01 / `minicpm-ocr-ppu-native` / vLLM `0.23.0+v0.2.0.ppu2.1.0`。模型注册和处理器接口问题已解决；验证边界如下。

## 基线与经验匹配

未修改基线 get_config 对 `minicpm_ocr` 抛 ValueError，无法加载用户指定 checkpoint。参考本模型 NVIDIA 原生问题001和现有 PPU Plugin OCR 模块：同为 MiniCPMV4_6/Qwen3.5、4x/16x 几何和像素相关 resize；差异是原生 PPU vLLM 0.23、Transformers 5.8.1。历史通过不能证明当前兼容或数值正确。

## 修改前限定计划

仅修改实际安装 vLLM Python 组件：新增 `model_executor/models/minicpm_ocr.py`，新增 OCR config、几何、图像、视频与组合处理器模块；修改配置、处理器及 ModelRegistry 的标准惰性注册入口和必要导出。复用 MiniCPMV4_6/Qwen3.5，保留视觉 QKV loader 和逐项 4x/16x 语义。根据实测差异调整 OCR 子类接口。现有 MiniCPMV4_6、公共调度热路径及其他模型不改，不删除文件。

以已有 PPU Plugin OCR 模块为参考，在当前接口下重新审阅；不加载 Plugin、不复制源码 checkout，不使用 PYTHONPATH。保存原始安装文件、新增文件清单和 SHA，最终逐 hunk 审查。权重、外部参考源码、Transformers、Torch、驱动和原生库只读。

## 回归计划

验证配置、标准 registry、处理器几何和请求选项隔离、4x/16x、视频；真实权重 eager 文本/图像/批处理；按 full → full-and-piecewise → decode-full → piecewise 验证 graph，降级前保留原因与修复尝试。正常前缀缓存开启，代表请求对照已核实参考。检查原 MiniCPMV4_6/Qwen3.5 注册和导入。experimental profile 无正式精度/性能接口，不声明 optimized。

过程代码与原始证据仅留批准根 `01-environment/`、`02-issues/`、`03-acceptance/`、`04-runs/`。实际修改、测试结果与限制待实测补充。

## 当前实测与接口修复

配置、标准 ModelRegistry、组合处理器及原 MiniCPMV4_6/Qwen3.5 导入成功；16 项几何、4x/16x、混合标记、像素与并发隔离回归通过。4 项 Plugin 注册专用测试未选择，不能算作原生回归通过。证据：`04-runs/import-cpu-tests.log`、`04-runs/cpu-regression.txt`。

首次 eager 在 dummy 输入阶段失败：0.23 的 MiniCPMV 父类将现代 OCR 处理器包装为旧 MiniCPMVProcessor，访问不存在的 `image_processor.version`。限定修复为 OCR ProcessingInfo 的 `get_hf_processor` 直接使用 ctx 标准加载的 OCR processor；不修改父类或共享路径。失败日志 `04-runs/eager-001/service.log`，修改前 OCR 文件保存在 `02-issues/ocr-model-before-processor-fix.py`。修复后的 eager-002 成功，见下。

## 真实权重与独立参考

eager-002 完整加载779个张量，模型占用2.47GiB，HTTP健康检查通过。文本、4x/16x、切片、自适应小图、多图及4路混合请求均HTTP200；两帧MP4也正确识别已知文字。原始结果 `04-runs/functional-eager/`、`04-runs/video-eager/`。

同权重已安装 Transformers MiniCPMV4_6 模型作为独立参考；处理器使用当前 OCR 几何，但语言和视觉网络走 Transformers 实现。参考脚本首次遗漏16x的模型侧 downsample_mode，保留失败并在002中修正，只改测试程序。关闭思考、固定转录提示词后的6类图像（含故意保留的退化小图）prompt token IDs、生成 token IDs 和文本全部与 eager 一致；首轮图模式也6/6一致。证据 `04-runs/hf-reference-closed/`、`04-runs/execution-eager/`、`04-runs/execution-graph/`；最终重验另存 final run。

极小168×84图像关闭放大时，原模型参考和vLLM均输出错误重复字符；该情况不是通过的OCR正确性案例。默认放大或自适应放大可识别。开放式文本/Markdown生成在两种实现间出现措辞或标点差异，因此不声称任意生成逐token一致，也不把这些案例放入严格文本 sanity。选定5例闭集转录均由独立参考与已知图像内容交叉核验，失败和限制保留。

## 最终源码审查

修改共11个Python文件：7个新增OCR专用文件，4个现有配置/处理器/模型registry文件仅增添惰性注册和导出。实际增量在 `02-issues/final-source.patch`、`final-source-manifest.json`、`existing-registration.diff`；逐hunk与限定计划一致，没有删除、共享运行热路径改动或其他模型实现修改。新增OCR模型保留按项merger标记、fused视觉QKV加载和旧processor包装隔离。原 MiniCPMV4_6/Qwen3.5 注册和导入仍正常。

普通wheel安装无Git checkout，不伪造PR base或HEAD；基线以镜像ID、包版本及完整修改前文件哈希为准。当前未提交、推送或创建PR。未验证其他平台、TP/PP、量化、完整上下文容量和正式精度/性能；本条经验保持local-only。

最终冻结配置后的 `04-runs/execution-eager-final/`、`04-runs/execution-graph-final/` 再次各6/6对照通过；图进程直接实测6次capture_end和48次replay。误差0仅指选定生成token IDs，不指logits。最终源码哈希重验仍仅11个计划内文件发生变化，审查材料在 `04-runs/source-review.json`。
