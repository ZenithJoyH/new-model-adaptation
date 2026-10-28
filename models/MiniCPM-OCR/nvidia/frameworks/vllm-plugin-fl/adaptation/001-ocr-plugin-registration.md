# 001：OCR 模型语义接入 Plugin

2026-10-20，H100-149，初始安装容器 `minicpm-ocr-flagos`，最终运行容器 `minicpm-ocr-flagos-runtime`。范围为 Plugin `main@a696859b9aa528dfd5b21f5da3403fdc16bac4cd` 加本轮未提交差异；empty vLLM、Transformers 和权重均不接收产品修改。

## 差距、职责及方案

上游缺少 `MiniCPMOcrForConditionalGeneration`、`minicpm_ocr` 及 OCR 处理器注册。模型结构复用 vLLM MiniCPMV4_6/Qwen3.5；OCR 特有4x默认、16x选项、像素决定的小图缩放、占位符计数和视觉层/merger权重映射归属于模型专用模块。通过现有 general_plugin 入口加载幂等注册，接入 AutoConfig/AutoProcessor 和 ModelRegistry，不改写 vLLM 安装文件、不使用路径覆盖。

代码在真实 editable 安装 `/opt/vllm-plugin-FL/vllm_fl/models/minicpm_ocr/`。模型、配置和图像/视频处理器来自同机原生适配中已验证的用户提供实现，迁移只调整模块归属和导入，并通过子类复用已安装 backbone；没有复制语言模型、视觉编码器或公共 worker。图像/视频处理兼容代码用于补齐该镜像 Transformers5.12 与用户5.19开发版OCR接口差距，不能直接引用另一个容器的可变代码作为部署依赖。来源及逐文件哈希见工作根 `02-issues/plugin-copy-provenance.json`。

涉及接口：逐图 target_sizes 对齐4x/16x token数、图像专用缩放与视频选项隔离、混合请求按merger标记分组、window attention独立QKV加载到fused参数。所有运行算子仍经Plugin既有OOT/dispatch与backbone路径。配置最大长度262144，初始服务按profile采用50000，TP1、64序列、图像4/视频1、GPU1显存比例0.55。

## 初期验证记录（历史）

`04-runs/install-20261020/plugin-tests.log`：新增OCR7项与实际FlagGems-vllm接口17项共24项通过；模型及处理器文件AST语法、git diff --check通过。实际导入无PYTHONPATH，Plugin来自/opt，FlagGems与FlagGems-vllm来自容器site-packages。

eager服务已解析正确OCR架构，但设备UUID转换阻塞发生在模型加载前，另见002；因此这里尚不宣称推理或graph通过。后续需完成实际文本/图像/多图/混合4x16x及视频回归，检查最终diff并保留未测平台限制。

PR base 尚未由用户指定，本轮不提交/推送/创建PR。任务开始时Plugin源码干净；构建后新增本轮原生扩展.so。产品修改前检查曾因这个生成项中止，未写源码；核实其来源后才允许继续。最终设计审查待实际推理和graph验证后刷新。

## 最终接口与 eager 实测补充

2026-10-20，在同一运行容器补齐AutoVideoProcessor的OCR标准映射：独立CPU接口先复现Unrecognized video processor，再注册并验证实际从权重元数据加载MiniCPMOcrVideoProcessor、默认4x。最终`plugin-tests-final.log`共25项通过。该变化只属于OCR注册，不修改公共视频解析器。

`04-runs/eager-reference-v2-20261020/`保存最终eager-v5配置下15项真实请求与输出：文本、小图、普通图、4x/16x、禁用小图上采样、自适应缩放、多图，以及4路混合4x/16x。15/15文本、输入token数、completion数及实际生成token ID完全匹配同权重的独立HF参考，无错误。引用参考SHA-256 `ed317a7e717c72d48987e5f7d6e555259b4d28609860c584260788e7240db360`。没有将仅字符串对比包装为logit精度测量。

首个文本196.82秒，首次小图80.53秒、普通图114.97秒、16x76.35秒；这些冷启动形状引发大量新内核编译。tokenize独立4.6ms，短文本12秒诊断超时保留于`02-issues/api-probe-20261020.json`，不可删除或当成通过。预热后的自适应小图1.68秒，但混合批次仍存在5–62秒冷形状开销；graph及预热后重复验证尚待完成，不声称性能已优化。

服务生命周期：eager-v4在SIGTERM后仍残留启动worker，核实process.json启动时间、模型/端口和子进程后仅终止旧任务树；stop-escalation.json保留证据。eager-v5转图前先验证15项全部token一致，再按所记录父子树有界停止，graph-transition-stop.json确认所有旧任务进程退出，容器持续运行；没有停止原生OCR或其他GPU服务。

最终graph和启动器复验已完成，见004及acceptance/README.md；前文待验证文字只描述当时进度，不是最终状态。产品源码身份与最终source.patch绑定，25项接口和独立算子回归均保留。
