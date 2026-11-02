# vLLM + vllm-plugin-FL 适配工作流

本 profile 继承仓库通用五阶段、安全、远端目录和证据规则，并补充以下强制要求：

实施前必读 [详细流程](detailed-workflow.md)（[中文](detailed-workflow.zh-CN.md)）。
全程遵循[推理框架插件开发规范 v1](../../docs/inference-plugin-development-v1.md)，
按任务索引检查适用条款，并在已有计划和最终审查中记录条款与验证证据。
涉及 FlagGems / FlagGems-vllm 时同时阅读[算子层开发规范](../../docs/operator-development-standard.md)
的综述和任务索引，适用【必须】均进入既有计划、测试和最终 `source_review`；条款注明规范来源。
任何产品代码增改删前，按[贡献标准](../../docs/plugin-contribution-policy.md#0-改前限定范围改中控制增删)
在已有计划/问题中列明各组件的必要文件/符号、变更理由和测试，实施中核对增量 diff。
不能因允许修改三个组件而同时修改三个组件；最终逐块审查所有被改组件的 diff。

1. 在适配容器内核实服务解释器、vLLM、已安装 `vllm-plugin-FL`、FlagGems 及可选
   FlagGems-vllm 的包元数据与实际导入路径。有 Git 时记录 revision/diff，否则记录安装版本
   和文件哈希。直接修改已安装组件，普通 site-packages 和 editable 源码均可；禁止通过
   `PYTHONPATH` 或其他导入覆盖选择另一个版本。vLLM 源码及安装目录全程只读。
2. 开始 FlagGems 接入判断前，在用户授权的现有 FlagGems checkout 中同步最新代码并记录
   revision；不得在远端工作根目录复制第二份源码仓库。
   普通安装没有 Git checkout 时，直接修复已安装组件不要求另建 checkout；需要同步升级
   时先确认兼容版本和现有改动的保留方式，再更新同一安装环境，不得用路径覆盖切换版本。
   允许对已核实的 Plugin、FlagGems、FlagGems-vllm 进行必要产品修复与聚焦测试，
   不扩大到 vLLM 或未声明组件。
3. 模型语义和平台能力通过 Plugin 现有模型注册、OOT、dispatch、backend、量化、attention、
   worker 或 compilation 扩展点接入，不得临时直接调用绕过 Plugin 架构。
4. FlagGems 承载 ATen 算子，通过自动替换机制生效；验证替换启用、实际命中、数值及图模式，
   不为每个 ATen 算子补 Plugin 接线；数值单测显式调用 `flag_gems.<op>`，自动替换命中另测。
   按用户澄清 FlagGems 仅提供 ATen 算子；vLLM 算子（含非 ATen 融合计算）检索
   FlagGems-vllm 的实际版本与公开 API，不因“通用融合”而放入 FlagGems 或冒充 ATen overload，
   对齐参数、dtype、layout、状态写入及 graph 契约；已有兼容实现按 Plugin 现有架构补齐
   dispatch/backend/注册或平台绑定。缺失实现时，ATen 算子归 FlagGems，vLLM 专用算子归
   FlagGems-vllm；先交付公开 API 和测试，再按各自路径接入。记录对应算子库的检索 revision、
   缺失证据和公开依赖固定版本/SHA，不能仅凭 FlagGems 没有实现就认定 vLLM 算子缺失。
   仅修改已声明且核实可写的组件；不得将数值 kernel 临时放入 Plugin。A3 所述框架 metadata
   处理仍归框架侧，不因采用 Triton 就迁入算子库。
5. Triton 实现必须兼容 graph capture/replay，避免 capture 阶段主机同步、不支持的动态分配、
   依赖数据的主机控制流以及不稳定 shape 或地址，并单独覆盖 eager 与 graph 测试。
   按算子规范验证独立参考、真实后端命中、变体/布局/状态契约、graph 新输入新结果及
   autotune 状态恢复；实现/优化按同条件 baseline 做组件 benchmark，满足目标仓库准入，
   缺少硬件如实记录未验证项。此为阶段 3 局部验证，不替代阶段 4 精度和正式性能。
6. 一次性诊断脚本留在远端 `02-issues/` 或 `05-tmp/`；Plugin 只接收必要产品代码和可维护测试。
7. graph 按 `full` → `full-and-piecewise` → `decode-full` → `piecewise` 逐级尝试。
   每级定位/修复后仍有无法解决的阻塞才回退一级，并保留逐级证据；不得跳级或默认仅开
   decode 图。按[通用工作流](../../docs/model-adaptation-workflow.zh-CN.md)核实实际模式并
   比较性能，保持精度、稳定性和原生验收要求。全部图模式失败时，eager 不能代替 graph 通过。

具体 Plugin 设计与交付标准见
[Plugin 修改与 PR 交付标准](../../docs/plugin-contribution-policy.md)；当前源码结构参考见
[vllm-plugin-FL 项目分析](../../docs/vllm-plugin-FL-analysis.md)。
