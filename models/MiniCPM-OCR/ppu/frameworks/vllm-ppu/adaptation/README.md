# 适配问题索引

- [004：原生默认视觉后端与人工性能入口](004-native-auto-backend-performance-entry.md)：自动FLASH_ATTN，按用户明确选择保留默认关闭前缀缓存；只核验启动就绪。
- [003：与父目录启动参数对齐](003-align-parent-launcher.md)：262144/64/TORCH_SDPA，保留原生设备端口与历史证据。
- [001：OCR注册、处理器接口和源码审查](001-ocr-native-support.md)。11个Python文件，16项定向回归通过，真实权重与独立参考验证。
- [002：FULL图限制与前缀缓存](002-graph-and-prefix-cache.md)。保留FULL失败；选定FULL_AND_PIECEWISE，正常启动显式开启缓存。

原始产物均在PPU-01批准根 `/mnt/nfs/users/jinghao/MiniCPM-OCR/ppu-native`。不修改外部权重、参考checkout、Torch、Transformers或原生库，不提交或推送。
