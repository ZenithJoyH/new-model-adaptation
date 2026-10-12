# 014：锁定版 vLLM dummy batch 要求多模态处理器返回 input_ids

## 元数据

- 状态：`open`（两项处理器契约已由带缓存独立回归验证；整模复试待验证）
- 首次出现及最后验证：2026-09-23
- Host / 容器：`H100-149` / `deepseek-v41-plugin-adapt-20260923`
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、eager、前缀缓存启用、`max_model_len=2048`

## 现象和根因

第八轮完成全部权重加载（vLLM 记录 `1662.42 seconds`）后，在
`model_runner.profile_run()` 的多模态 dummy batch 阶段，8 个 worker
均于锁定版 vLLM `BaseMultiModalProcessor._apply_hf_processor_text_mm()`
的 `processed_data.pop("input_ids")` 报 `KeyError: 'input_ids'`。
原始日志：
`H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`
21:02:03 的 traceback。

Plugin 的 `DeepseekV4VLProcessor` 之前只生成图片 patch/grid/types，
文本或无图片时返回空 `BatchFeature`。这不满足该 vLLM 版本的处理器接口；
而图片占位符扩展原本就由 Plugin 的 `_apply_prompt_updates` 负责，
不能把未扩展文本误标为已在 HF processor 中扩展。

## 处理与验证

本次在 Plugin 的 `common/mm_preprocess.py` 让 stand-in HF processor
复用框架提供的模型 tokenizer，对所有文本路径返回 `input_ids`；图片路径
继续返回 patch/grid/types。`_hf_processor_applies_updates` 明确返回
`False`，保留既有的 prompt-update 扩展职责。没有修改 vLLM、权重或其他
依赖。变更前文件 SHA-256：
`dfd88d6c986c18dd45ec3559a3e148ad0c6ea247fe8363d4ea62ef15028cce34`。
补丁位置：
`/public/flagos/jinghao/deepseekV4.1/02-issues/h100145-ring-20260923/v41-mm-input-ids-h100149.patch`。
Ansible `--check --diff`、`git apply --check`、应用和语法检查均通过。

独立测试使用模型配置和 DSML tokenizer：纯文本 `Hello` 返回
`input_ids=[[19923]]`；单张 32×32 图片路径返回
`input_ids=[[129264]]`、`patches.shape=[1521,3,14,14]`、
`vit_grid=[[39,39]]`、`types.shape=[184]`。这只覆盖处理器直接输出。

第九轮整模越过 `input_ids` 错误，但在带 processor cache 的图片-only
分支报 `AttributeError: 'DeepseekV4VLProcessor' object has no attribute
'_merge_kwargs'`。锁定版 vLLM 在该分支调用 HF `ProcessorMixin` 的
私有方法；Plugin 的 stand-in 不是该类。原始日志为同一 `service.log`
21:45:38 的 traceback。独立诊断开始未传 cache，因而误走另一分支；
补上 `processor_only_cache_from_config` 后复现了完全相同的错误。Plugin
现在重用基类的文本加图片处理分支，并以 dummy placeholder 提供图片-only
路径所需的 prompt，避免复制 HF 私有 `_merge_kwargs`。第二补丁在
`02-issues/h100145-ring-20260923/v41-mm-only-h100149.patch`。

带 cache 的诊断再次执行，`MULTIMODAL_REGISTRY.get_dummy_mm_inputs`
成功返回 2048 个 profile prompt token 与 `image` 多模态数据。诊断脚本为
`02-issues/h100145-ring-20260923/mm-registry-diagnostic-h100149.py`。
这验证了原始失败的 registry/处理器路径，但不证明整模 profile、实际图像
推理、eager 或 graph 数值。

待在下一轮 TP8 整模启动验证 dummy batch，然后对最小文本请求验证。
知识库处理状态：`needs-validation`。
