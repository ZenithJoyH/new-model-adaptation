# 新模型适配测试文件

本目录保存可复用测试工具。先按所选 profile 确定适用入口；模型或平台专用配置、包装脚本
放在已批准远端根目录的 `03-acceptance/`，原始结果放在 `04-runs/<run_id>/`。
本地 framework 工作区的 `acceptance/` 只保存 Markdown 摘要和准确证据引用，不修改公共
测试基线承载单次任务。目录和缓存要求见[远程操作细则](../docs/remote-operations.zh-CN.md)。

## 目录

- `perf_test/`：vLLM、SGLang 的推理性能测试和 Profiling 工具。
- `Accuracy_test/`：服务型精度评测工具。正式入口 `llmrun.py` 在适用的 FlagEval 镜像中
  执行事先冻结的一个或多个 task；GPQA Diamond 只是示例。数据集、完整样本数、指标和阈值
  按[精度工具契约](Accuracy_test/README.md)与 profile 核实。
- `ocr_perf/`：OCR 跨平台性能比较工具，不生成正式框架验收回执。
- `workflow_test/`、`operations_test/`：本地契约与控制工具回归；统一入口
  `./scripts/syntax-check --offline` 同时运行 `ocr_perf/` 的本地测试。
- `nccl_test/`：平台通信测试脚本，仅在对应平台和通信后端适用时使用。

## 数据与结果

`perf_test/ShareGPT_V3_unfiltered_cleaned_split.json` 是约 642 MB 的本地性能测试数据，
已通过仓库 `.gitignore` 排除。测试生成的 `outputs/`、`results/` 和 `logs/` 同样不提交。
仓库只保存可复用测试代码、无敏感信息的配置和适配结果摘要。
