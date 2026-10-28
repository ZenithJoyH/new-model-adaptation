# 适配问题索引

当前进度：已完成功能适配。eager/显式 PIECEWISE 均通过 12 样例两轮；4/8 并发及图像消融通过，最终最小启动器已实测就绪。正式全量精度与性能未执行。

- [001：IPC 路径长度](001-long-ipc-path.md)
- [002：FlagGems clone 注册](002-clone-autograd-registration.md)
- [003：worker 异步池化返回值](003-async-pooling-output.md)
- [004：分类概率数值对照](004-classification-numerics.md)
- [005：pooling 图模式](005-pooling-graph-modes.md)
- [006：视觉位置插值精度](006-vision-position-precision.md)
- [007：图编译数值与 EagerAdaptor](007-graph-compiler-numerics.md)
- [008：最终源码设计审查](008-source-review.md)
- [009：满上下文 pooling 调度边界](009-pooling-context-boundary.md)
- [010：适配收敛与最新 PR 审查](010-adaptation-consolidation.md)
