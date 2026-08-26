# 新模型适配测试文件

本目录保存每次新模型适配完成前使用的公共测试工具。模型或平台专用的配置、包装脚本和
简要结果应放回对应的 `models/<model-name>/<platform>/`，避免直接修改公共测试基线。

## 目录

- `perf_test/`：vLLM、SGLang 的推理性能测试和 Profiling 工具。
- `Accuracy_test/`：精度评测工具；正式流程必须在目标机器上进入基于
  `harbor.baai.ac.cn/flageval/flageval-llmeval:v1` 镜像的容器，使用 `llmrun.py`
  执行 GPQA Diamond 评测。
- `nccl_test/`：平台通信测试脚本，仅在对应平台和通信后端适用时使用。

## 数据与结果

`perf_test/ShareGPT_V3_unfiltered_cleaned_split.json` 是约 642 MB 的本地性能测试数据，
已通过仓库 `.gitignore` 排除。测试生成的 `outputs/`、`results/` 和 `logs/` 同样不提交。
仓库只保存可复用测试代码、无敏感信息的配置和适配结果摘要。
