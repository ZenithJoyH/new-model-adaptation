# NVIDIA 原生 vLLM 适配工作流

本 profile 继承仓库通用五阶段、远端工作根、源码边界和证据规则。只适用于用户明确指定的
NVIDIA 原生 vLLM 容器，不继承 `vllm-plugin-fl` 的 Plugin 或 FlagGems 写入授权。

1. 写入前核实容器、镜像、权重、处理器、vLLM 包元数据与导入路径、已有 Git 源码根、
   revision、工作树归属和源码如何成为实际导入代码。只有核实后的现有 editable/source
   形式 vLLM 产品树可写；安装 wheel 的 `site-packages` 不是可直接修改的源码 checkout。
   不能在批准的远端工作根下创建源码副本。
2. 以模型配置、参考实现和 vLLM 已有模型/多模态接口建立基线。先沿用正式模型注册、
   多模态处理器、权重加载、位置编码及现有语言模型实现。记录共享接口的调用方与守卫
   未命中行为；模型语义放在模型适配器，不在公共执行热路径按名称分支。
3. 产品树只保留必要实现和可维护回归测试。一次性检查、服务配置和原始结果分别放在
   批准工作根的 `02-issues/`、`01-environment/` 和 `04-runs/`。外部权重及模型仓库只读。
4. 建立相同模型输入的变更前后正确性基线，覆盖文本、图像和模型声明支持的视频路径。
   验证视觉 token 数、M-RoPE、权重映射、prefill/decode、批处理与相关已有模型。
5. graph 按 `full` → `full-and-piecewise` → `decode-full` → `piecewise` 逐级尝试，
   每一级定位和修复后仍有阻塞，记录证据才能继续向下。按通用工作流核实实际生效模式并
   比较性能；后续验收和最终脚本绑定该 Host 最终验证模式，变更时重新验证受影响证据。
6. 每次实质变更后审查真实 vLLM diff、已有改动、PR base、HEAD、影响矩阵与测试结果。
   未经用户明确要求，不提交、推送或创建 PR。

通用细则见 [模型适配流程](../../docs/model-adaptation-workflow.md)、
[证据契约](../../docs/framework-evidence.md) 和 [执行指南](../../docs/workflow-guide.md)。
