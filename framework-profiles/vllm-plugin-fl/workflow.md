# vLLM + vllm-plugin-FL 适配工作流

本 profile 继承仓库通用五阶段、安全、远端目录和证据规则，并补充以下强制要求：

实施前必读 [详细流程](detailed-workflow.md)（[中文](detailed-workflow.zh-CN.md)）。

1. 在适配容器内核实 vLLM、editable-installed `vllm-plugin-FL` 与 FlagGems 的实际导入路径、
   revision、工作树归属和版本关系。vLLM 源码及安装目录全程只读。
2. 开始 FlagGems 接入判断前，在用户授权的现有 FlagGems checkout 中同步最新代码并记录
   revision；不得在远端工作根目录复制第二份源码仓库。
3. 模型语义和平台能力通过 Plugin 现有模型注册、OOT、dispatch、backend、量化、attention、
   worker 或 compilation 扩展点接入，不得临时直接调用绕过 Plugin 架构。
4. FlagGems 已有兼容算子时补齐 Plugin dispatch/backend/注册或平台绑定。FlagGems 缺失兼容
   实现时，在 Plugin 内新增 Triton 实现并通过相同 dispatch 接入，记录检索 revision 和缺失证据。
5. Triton 实现必须兼容 graph capture/replay，避免 capture 阶段主机同步、不支持的动态分配、
   依赖数据的主机控制流以及不稳定 shape 或地址，并单独覆盖 eager 与 graph 测试。
6. 一次性诊断脚本留在远端 `02-issues/` 或 `05-tmp/`；Plugin 只接收必要产品代码和可维护测试。
7. graph 配置必须按 `full` → `decode-full` 的顺序适配：先尝试覆盖 prefill 与 decode 的全量图；
   只有核实并记录全量图阻塞后才允许降级到 decode 阶段全图。`decode-full` 是最低验收要求，
   不能作为默认起点；更低覆盖级别只能用于诊断，不能通过执行模式验收。

具体 Plugin 设计与交付标准见
[Plugin 修改与 PR 交付标准](../../docs/plugin-contribution-policy.md)；当前源码结构参考见
[vllm-plugin-FL 项目分析](../../docs/vllm-plugin-FL-analysis.md)。
