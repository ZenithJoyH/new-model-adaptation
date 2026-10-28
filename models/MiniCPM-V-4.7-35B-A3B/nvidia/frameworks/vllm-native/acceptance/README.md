# 验证索引

[功能验证](functional-validation.md)记录 2026-09-28 的 TP2 eager/graph
执行模式、文本/图像/视频请求和诊断性十并发测试，以及最终启动脚本。
[混合图根级脚本验证](full-and-piecewise-launcher.md)记录后续按用户要求切换至
`FULL_AND_PIECEWISE` 的启动脚本与重启复测。
[精简脚本验证](minimal-launcher.md)记录 2026-09-30 首轮参数、缓存变量精简、
新服务的请求复测、日志与精确 SHA-256。
[最终脚本验证](lean-launcher.md)记录二次精简后的根级脚本、逐项保留理由和复测。
[8020 恢复验证](recovered-8020-launcher.md)记录用户新脚本失败后恢复必要参数、
启动就绪、图捕获及请求回归；该过度恢复版已被下一次更新替代。
[仅 Triton 隔离验证](triton-only-8020-launcher.md)记录按用户纠正后
恢复原有 vLLM 参数、只增加 Triton 进程缓存隔离的根级脚本与实测结果。
[命令级 PYTHONPATH 验证](command-scoped-pythonpath.md)记录当前脚本移除
全局 export、重启验证和 Triton 隔离仍生效的证据。
[当前多模态请求检查](multimodal-8020-20261001.md)记录同一 8020 服务的
单图和两帧视频请求结果。
[ERQA 8020 诊断](erqa-8020-diagnostics-20261003.md)记录与 PPU-13 同图同题、
同采样参数的 400 题复测及固定 45 题/单题对照；这是诊断，不是正式精度回执。
固定 GPQA sanity、正式精度、性能、证据汇总和完整验收尚未执行。
