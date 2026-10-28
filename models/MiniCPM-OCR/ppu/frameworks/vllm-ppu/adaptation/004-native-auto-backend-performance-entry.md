# 004：使用原生默认视觉后端与人工性能入口

2026-10-27，用户指出无需强制TORCH_SDPA。现场发现根脚本已经被人工改成默认 `--no-enable-prefix-caching`，缓存分支已移除，运行中的旧服务则仍开启缓存。经询问，用户明确选择“保留脚本默认关闭，用作性能启动入口”。本轮按该选择保留人工缓存设置，覆盖仓库普通启动默认开启的约定，不擅自恢复旧分支。

变更仅限当前任务启动配置：删除 `--mm-encoder-attn-backend TORCH_SDPA`，由指定厂商镜像内vLLM默认选择；同时去掉已没有定义的cache_args空展开。262144上下文、64序列、0.55显存、图像4/视频1、FULL_AND_PIECEWISE、PPU4/TP1、8014和原生模型名保留。没有产品源码、SDK、依赖或权重变更。

人工入口原SHA为bd02fa79d2621336355b84d62e5e489c9fa0c7888e73b5ea07eba958a9dd2f82，保存在批准根 `01-environment/native-auto-backend-perf-20261027/start-before-manual-perf.sh`；容器内部旧交付材料也备份于该目录。新脚本与 `/opt/minicpm-ocr-ppu-native/start-model.sh` 同步。只停止按命令行核实的本任务旧API66163，容器保持运行，其他服务不受影响。

当前性能配置仅核实实际后端、缓存关闭、图启动和HTTP健康就绪；不在关闭缓存的配置上重跑非性能精度验收，不运行正式性能测量。旧缓存开启的执行模式/精度小集合回执已转入control.history，不充当新性能配置的通过证据。正式performance接口和整体验收仍不可用。
