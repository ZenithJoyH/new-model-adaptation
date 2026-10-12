# 008：MetaX W8A8 scaled-mm 与整模 eager 闭环

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-21
- 最后验证时间：2026-09-22
- 模型：DeepSeek-V4-Flash INT8
- 平台与 Host 别名：MetaX C550 x8，`mx-59`
- 容器：`deepseek`
- Plugin / FlagGems / FlagGems-vllm / vLLM revision：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `711cf839c4ee5557776c626e1f8b20cc4007fa63` / `c0ffa628e945dc6b51af466d4f1a9b81df9ac4b8` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：eager，TP8+EP，OpenAI chat completion

## 问题现象与根因

- sparse MLA 和 PDL 问题解决后，整模继续暴露 W8A8 linear/MoE 的 vendor dispatch、`out_dtype` 和 DSV4 compressor 路径不完整。
- 根因是 PR 427 的 DeepSeek-V4 通用实现仍依赖 CUDA scaled-mm 语义，而 MetaX 需要从 Plugin 的 vendor 后端进入已支持的量化 GEMM；这不是 glibc 问题，也不能通过改只读 vLLM 隐藏。

## 解决方法

- 在 Plugin 的 MetaX vendor 路径补齐 DeepSeek-V4 scaled-mm、W8A8 linear/MoE 和 compressor 接线；保留 reference/CUDA 原行为与 miss path。
- FlagGems-vllm 仅包含用户已授权的 sparse MLA 聚焦修改；vLLM 始终只读且工作树干净。
- 未增加 CPU fallback，未以模型名散落修改公共执行代码。

## 验证结果

- 聚焦设备算子：sparse MLA prefill/decode、hash top-k、W8A8 路径均通过对应远端设备回归。
- eager 整模：`04-runs/pr427-eager-tp8-20260921-26-*` 完成 109/109 权重加载、TP8+EP 启动和真实 OpenAI 请求，内容精确为 `OK`。
- 相关单测最终汇总：`72 passed, 3 skipped`，位于 `04-runs/pr427-related-unit-after-graph-correctness-20260922/pytest-output.txt`。
- 结论：eager 功能链路通过；正式 accuracy/performance 未执行。

## 限制与下一步

- 当前证据只覆盖 MetaX C550、该 INT8 权重和 TP8+EP，不外推到其他平台或量化格式。
- 图模式的独立编译/捕获问题见 009。

## 经验沉淀

- 知识库处理状态：`local-only`
- 可复用原则：量化语义归模型/Plugin 适配，硬件实现归 vendor dispatch；不要修改只读引擎或引入静默 CPU fallback。
