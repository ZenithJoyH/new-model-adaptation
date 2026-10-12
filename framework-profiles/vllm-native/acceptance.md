# NVIDIA 原生 vLLM 验收要求

- `execution-mode`：真实权重在 eager 与 graph 均可推理；多模态模型还须验证其声明的
  图像与视频路径。graph 按 `full` → `full-and-piecewise` → `decode-full` → `piecewise`
  逐级尝试；每个更高档位都必须有定位、修复尝试和未解决阻塞证据。记录准确配置、服务
  身份、实际 graph 模式和变输入回放结果；全部图模式失败时不能以 eager 代替 graph。
- `sanity`：使用已验收主模式做冻结并发的小批量正确性、输出健康和性能预检；覆盖代表性的
  文本及图像请求，并检查 token 数、位置编码和输出语义。视频路径按模型能力另行记录。
- `accuracy`：冻结数据集、样本数、指标键和阈值，通过项目 `adaptation/accuracy` 原生入口
  完成正式评测。保留全部样本和原生回执；错误样本和最终超时按项目契约计入。
- `performance`：准确性通过后，使用 `adaptation/performance` 原生入口。仅针对准确服务
  实例的性能配置显式加入 `--no-enable-prefix-caching` 并核实生效；记录同条件基线。
- `evidence`：核对当前 vLLM 源码 Git 身份、原有与本轮 diff、真实运行修订及产物完整性。
- `summary`：恢复正常前缀缓存配置，验证根级 `start-model.sh` 的语法、容器映射、实际
  就绪、最小必要参数、SHA-256 与已验收 graph 级别。脚本不得停启适配容器。

正式验收沿用仓库的完整原生证据要求；缺少数据集、运行回执或资源时保持未完成状态。
