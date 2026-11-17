# LightX2V Plugin-FL 实验功能验证要求

所有步骤仅为experimental的已声明checks，不构成完整正式适配通过。当前没有LightX2V视频正式accuracy/performance adapter；不使用flageval-openai/vllm-bench-serve冒充。profile不声明保留名sanity、execution-mode、model-eager或performance：这些名称关联已有专用原生检查，当前媒体任务没有对应完整契约，不能只填true跳过。functional结果最多支持模型工作区functional，完整acceptance/optimized保持未完成。

## functional

- `policy_binding`：精确记录每rank、请求线程/上下文与模型专用operator policy，硬后端顺序及参数，异常/请求结束后状态恢复；不静默使用全局ATen替换冒充局部policy。
- `native_dispatch`/`no_silent_fallback`：证据来自真实请求的主模型阶段，含native调用/缓存launch及实际device kernel时窗交叉核对。逻辑调用、调优launch、API与kernel数分开，不能旁测独立算子凑命中。变更数值计算时仍须按适用operator标准补独立数值参考，不能以格式健康代替正确性。
- `model_residency`：记录worker/模型加载身份和加载次数，串行第二请求复用同一模型，未重复加载或跨请求串入旧状态。容量冻结并发/队列，不允许未经容量验证复制整模型。
- `request_lifecycle`：绑定本轮服务进程/启动指纹和endpoint，验证真实任务提交、排队/运行/完成、失败传播/非法输入不挂死、多rank协调、状态查询及输出获取；仅GEThealth/HTTP200不算生成成功。
- `media_output`：冻结代表输入与判据，保存原视频/音频或图像及其hash，核原tensor有限/非全零/非恒定、媒体解码的帧/尺寸/fps/音频格式/时长与实际代表帧/输入相关性审阅；无独立听审或数值oracle必须明示。不得把旧shape成功当新shape通过。
- `resource_state`：记录Torchallocated/reserved全程峰值、物理采样口径、host余量、请求前后及服务常驻状态/异常恢复。只管理本任务，不能停止容器或他人服务。实际参数改变后重验对应容量与功能。

## evidence 与 summary

按固定v2 profile snapshot、scope/run/context/deployment及实际Host集合绑定framework_check；producer、逐check measurement/review和原始artifact hash不可缺，true必须有本轮证据。保存源diff/审阅与未修改栈的前后版本/hash；不把source归档冒称gitcheckout。共享最小start-model.sh与配置绑定同服务功能验证和交付，保留命令、PID/startticks/容器/端口/实际模型参数、输入/结果及原生SHA清单。本地模型目录只保存简短中文Markdown及精确远端引用，不复制脚本/原日志/JSON。

当前schema的checks可表达这些实验功能项，但没有视频正式sanity/performance原生runner与测量adapter，不能因此宣称正式服务验收。后续若引入正式sanity、accuracy、performance或改变profile契约，必须实现对应原生能力、提升profile版本、显式workspace-control升级固定snapshot并重验受影响阶段；不得通过改名/文档/刷新hash迁移旧通过结果。任何用户明确性能目标仍须保留，未测不宣称达成。
