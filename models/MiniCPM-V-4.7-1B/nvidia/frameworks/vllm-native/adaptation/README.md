# 适配问题索引

用户明确允许直接修改容器已安装的 vLLM wheel。4.7 模型专属适配已完成基本功能验证；
正式数值对照、准确率、性能与完整原生回执尚未完成。产品改动仅在目标容器的
`site-packages/vllm/model_executor/models/`，过程代码及结果保存在批准的远端工作根。

- [001：4.7 注册与 canvas M-RoPE 接口差距](001-minicpmv47-registration-canvas-mrope.md)：
  功能修复与 eager/decode-full 变输入推理已验证。
- [002：Triton 无法发现 libcuda](002-triton-libcuda-path.md)：
  使用明确驱动目录变量恢复导入，未改镜像或系统库。
- [003：GDN 限制 mixed 全图](003-gdn-fullgraph-limit.md)：
  full 请求被 vLLM 自动降为 piecewise；显式 decode-full 通过基本推理验证。
- [004：前缀缓存默认值在本模型上未生效](004-prefix-cache-default.md)：
  精简脚本的受控对照确认必须显式保留启用参数。
- [005：MMLU-Pro biology 子集分数与答案提取诊断](005-mmlu-pro-subset-score.md)：
  原始严格分数两边均为 31/50；确认答案格式提取损失，未证实 NV 独有的模型精度回退。

- [006：MMLU-Pro math / other 配对低分分析](006-mmlu-math-other-score-analysis.md)：
  原分数 FlagOS 63/100、NV 52/100；最终答案核对为 60/100、52/100，确认首次匹配高估
  FlagOS、具体推理错误与数据疑点；NV 适配根因仍待受控验证。

按发生顺序维护 `NNN-short-title.md`。每条记录只描述一个问题的现象、诊断、受控对照、根因、
解决方法、验证结果和限制，不保存过程脚本或原始日志。
