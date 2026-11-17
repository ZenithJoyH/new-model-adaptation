# LightX2V Plugin-FL 实验适配工作流

继承仓库通用五阶段、委派、远端执行、人工控制及v2证据要求。当前只覆盖MetaX eager图像/音视频生成Python API与异步HTTP任务，不提供完整正式验收或optimized资格，不套用vLLM/OpenAI聊天服务或PPU Torch-FL的要求。

1. **结构与推理链路**：中文说明模型输入输出、dtype/layout、文本/主模型/VAE链路、算子策略作用域、实际HTTP请求线程与多rank调用链。所有模型/Host/容器/版本/绝对路径放模型工作区，不写入可复用profile。
2. **环境**：核实际解释器、正常import路径、源码revision或固定归档及hash、厂商栈、模型资产、容器映射、进程/GPU资源、HTTP/媒体/队列依赖及监听端口。缺失依赖先核授权，不默认安装或启动外部服务。多机必须先按通用MetaX通信前置验证，本profile不自动授权其他Host。
3. **实现**：仅允许在已核实的容器安装版Plugin中按有界文件/符号实现接入和可维护测试；LightX2V基架、FlagGems/FlagOmni、厂商组件及模型/权重均只读。不用PYTHONPATH、替代checkout或过程目录放产品实现。先检查已有模型专用policy在每rank真实请求线程的进入/退出、异常恢复与重复请求隔离；不得把context只包在不执行推理的线程。复用已安装框架公共server/worker和串行任务生命周期，不平行重造HTTP框架或队列。无合适公共接入点或需要写只读组件时，停止受影响改动并交主Agent重新定界。
4. **功能验证**：按acceptance.md的functional→evidence→summary执行。所选工作只允许声明实验功能结果，不能以checks回执冒充正式视频sanity/精度/性能。启动前冻结模型参数/算子策略/精度/并行/输入及HTTP生命周期、队列容量、输出判据和资源保护；部署指纹绑定真实代码/配置/启动命令。GPU验证须独立预算、主Agent新鲜资源确认和唯一受控启动，禁止试OOM代替容量分析。服务采用已审最小容器内start-model.sh，不放诊断、安装、缓存目录堆叠或自动kill。只能管理当前任务进程，保留容器/其他服务；用户要求常驻时验证后保留该服务。
5. **复盘**：记录实际失败、未验证能力和可复用限制。历史API/离线结果只能作为已绑定输入和基线，不自动提升新profile阶段状态。

本profile的prefix_caching为not_applicable，限定为本实验图像/音视频生成任务的非自回归KV-prefix缓存；不等同于框架的模型专用feature cache/请求reuse。后者必须在模型运行计划明确冻结，任何改变独立验证。Graph/compile/量化/可选融合/跨机及并发复制模型均不因profile存在而获授权。

升级active前必须为此执行栈实现独立数值/正式精度与可重复性能的原生runner、adapter和证据validator，并做真实端到端验证；本次不发明validator、不改通用工具以放宽契约。
