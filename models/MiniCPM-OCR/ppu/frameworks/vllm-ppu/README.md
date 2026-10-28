# MiniCPM-OCR / PPU / 原生 vLLM

当前按用户选择使用性能启动入口：去掉强制视觉后端参数，原生实际选择FLASH_ATTN；默认关闭前缀缓存。262144/64、PPU4/8014等参数保留，已重启并核验HTTP就绪，未运行正式性能评测或新的精度小集合。新脚本SHA-256 `b47da23bf9cb8eff46aaf927a577a86ebd5228ce9a5e0973bae9d256b51bd5ae`，容器内交付同步。见[原生默认后端与性能入口](environment/native-auto-backend-performance-20261027.md)。以下缓存开启的适配和验收均为历史结果。

最新参数已按父目录脚本对齐：262144上下文、64序列、TORCH_SDPA、0.55显存、FULL_AND_PIECEWISE及前缀缓存开启；批次预算使用实际默认8192。保留PPU4、8014端口和原生模型名。新脚本SHA-256 `36f58ad7e43b820318be57a9975a5eadbd2915b35a33f91b32bb6ca3f4c78e1f`，根路径不变，容器内部副本已同步。

新配置eager/graph、原生5例sanity及64客户端并发128项短OCR全部通过；服务采样running峰值64。详见[本轮对齐总结](acceptance/parameter-alignment-summary.md)。完整正式验收及新镜像验证仍未完成。以下为首次32768/8配置的历史记录，不充当当前配置证据。

2026-10-27，PPU-01，新容器 `minicpm-ocr-ppu-native` 基于用户指定原生0.23镜像，适配checkpoint `merge_rl_mergedp1_7140_hf5_4x`。当前状态functional，容器和最终服务保持运行。

API为PPU-01的 `8014/v1`，模型名 `MiniCPM-OCR-PPU-native`。使用PPU4/TP1、32768上下文、8序列、16384批次token和显存比例0.55。最终图档位FULL_AND_PIECEWISE，前缀缓存开启；FULL受原生GDN后端能力限制，保留失败与诊断。未停止其他服务。

16项CPU回归通过；真实权重eager/graph各6类图像与独立Transformers参考的prompt和生成token IDs一致，图直接统计6次捕获、48次回放；最终文本/视频路径通过，绑定当前实例的原生5例4并发sanity全部通过。关闭放大的极小图在参考中也识别退化，自由生成未承诺跨实现逐token一致。

Host/容器根均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR/ppu-native`。根级可执行 `start-model.sh` 已实际启动并验证，SHA-256 `fb250cb53139ef7cdc80f3310520ed0217463447ab853e5e222e000084572c2c`。持久恢复材料在 `01-environment/delivery/`，相同容器内部副本为 `/opt/minicpm-ocr-ppu-native/`；权重为声明的只读外部输入。无PYTHONPATH或外部开发源码依赖。

本profile为experimental，仅声明的基础验证通过；完整正式验收未完成，不标optimized。未进行正式精度、性能、满长容量或其他平台/并行验证；镜像未打包，image validation=pending。未提交、推送或创建PR。

- [环境与精确身份](environment/README.md)
- [问题、实现与源码审查](adaptation/README.md)
- [执行模式证据](acceptance/execution-mode.md)
- [原生小集合结果](acceptance/sanity.md)
- [交付、限制与总结](acceptance/summary.md)
