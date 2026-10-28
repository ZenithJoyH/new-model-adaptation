# 原生默认后端的性能启动环境

2026-10-27，PPU-01 / minicpm-ocr-ppu-native。用户明确保留人工修改后的默认关闭前缀缓存性能入口，并允许原生vLLM自动选择视觉注意力后端。已删除强制TORCH_SDPA及未定义cache_args引用，未恢复旧的默认开启缓存分支。

指定厂商镜像中的平台选择器实际选择FLASH_ATTN；启动日志同时记录vit attention和MMEncoderAttention使用AttentionBackendEnum.FLASH_ATTN，未将其称为已经比较过性能的最优后端。当前进程配置enable_prefix_caching=False，262144上下文、64序列、PPU4/TP1、8014、显存0.55、图像4/视频1和FULL_AND_PIECEWISE；有效批次预算仍为8192。

新启动脚本SHA-256 `b47da23bf9cb8eff46aaf927a577a86ebd5228ce9a5e0973bae9d256b51bd5ae`；新部署指纹 `f944121baff4e4df521b3c12a948e0d57264037c181ed407ef7df06f62021148`。部署、人工脚本备份、配置审查和交付材料在批准根 `01-environment/native-auto-backend-perf-20261027/`。当前delivery-current与容器内 `/opt/minicpm-ocr-ppu-native/` 同步，旧内部材料保留备份。该脚本默认性能配置，不含性能开关分支。

容器ID仍为c7761d51cd375b946bdad104c97ea8c80837e282f86edf1099e713e75b27de82，Host/容器根与41:15135181180映射已重新核验，容器保持运行。只停止经命令行核实的本任务旧API；源包版本、11个已安装Python文件差异集合和各文件SHA复核不变，没有产品、SDK、依赖或权重变更，也没有PYTHONPATH覆盖。

本轮只做启动配置、实际后端、图初始化和HTTP健康核验；关闭缓存时不签发新的功能精度小集合或正式性能回执。旧缓存开启的验收状态已归档，不为新性能配置背书。现场结果见 `04-runs/native-auto-perf-20261027/startup-verification.json`；正式accuracy/performance和fresh-image验证仍未执行。
