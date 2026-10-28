# 适配问题索引

- [001：editable Plugin 导入被镜像内旧 namespace 遮蔽](001-editable-plugin-import-shadowing.md)：
  环境阶段的受控只读对照已确认；TP2 eager 运行时已进入新注册类。
- [002：MiniCPM-V 4.7 MoE 与 canvas MRoPE](002-minicpmv47-moe-canvas-mrope.md)：
  Plugin 新模型适配；TP2 eager 和 decode-full 的最小文本、图像回归已通过。
- [003：Triton 缓存并发](003-triton-cache-concurrency.md)：
  Parastor 共享缓存两次启动遇到 `Errno 16`；容器条件性钩子提供逐进程隔离。当前用户脚本改用默认 `/root` 缓存位置后也完成最小启动，但缓存不在批准目录。
- [004：FlagGems 视觉 SDPA 非法地址](004-vision-sdpa-illegal-address.md)：
  限定服务配置排除两条问题实现后，eager 图像推理通过；算子根因待修。
- [005：GDN backend 阻断 mixed prefill/decode 全图](005-gdn-full-graph-limit.md)：
  TP2 full 请求被 vLLM 自动降为分段图；decode-full 已通过最小回归，用户选定的显式
  `FULL_AND_PIECEWISE` 已捕获分段 prefill 和全图 decode，当前 API 图文与十并发请求均通过。
- [006：默认 thinking 使十并发短题输出截断](006-default-thinking-sanity-truncation.md)：
  关闭模板 thinking 后短答案十题通过；`max_num_seqs=10` 的 TP2 服务已完成
  混合十题和纯文本十题回归。
- [007：用户改写的启动脚本缺少独立运行条件](007-user-edited-launcher-self-containment.md)：
  editable Plugin 已重新安装；当前原文脚本无 `PYTHONPATH` 实际启动并通过 6/6 图文，
  但重新缺少占用保护和日志/缓存目录约束。
- [008：与 1B 共用适配器](008-unified-dense-moe-adapter.md)：
  新容器内共用 dense/MoE 与 canvas；双模型 TP2 eager/graph 共 50/50 API、14 项契约与
  8 项 checkpoint 对照通过，整模不设置旧 attention 黑名单。
- [009：当前 Plugin 0.4 容器支持 35B-A3B DSpark](009-dspark-plugin04-single-gpu.md)：
  授权复制权重至现有容器，修复 vLLM 0.28 MoE padding 兼容；TP1 eager 9/9、graph 19/19，
  新增测试 5/5、共有回归 24/24。当前 1B 服务暂停，未做正式精度/性能。
- [010：DSpark 双卡及默认上下文](010-dspark-tp2-default-context.md)：GPU6/7、TP2、64 序列，
  默认 batch token 8192、长度 262144；两类缓存逐进程隔离后图捕获与 73/73 API 功能通过。

001–007 保留独立容器的历史状态。2026-10-08 新容器的视频帧、大图切片和并发复验见 008；
FlagGems 根因修复继承自 1B 环境，不写成原 35B 容器已更新。

此前图像 prefill 的位置已与 checkpoint 自带算法逐项对照；当时视频、长上下文、
mixed prefill/decode 的 full graph 和正式回归仍未完成。后续问题按 `templates/adaptation/issue-record.md`
建新编号记录，不把运行缓解写成算子根因修复。
