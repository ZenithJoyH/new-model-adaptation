# 启动参数对齐完成

2026-10-27，PPU-01 / minicpm-ocr-ppu-native，根级启动脚本与父脚本对齐核心推理设置：262144上下文、64序列、TORCH_SDPA视觉注意力、显存0.55、图像4/视频1、FULL_AND_PIECEWISE和前缀缓存开启。去掉额外固定的批次预算，原生API实际默认8192。保留独立PPU4、8014、MiniCPM-OCR-PPU-native及原生环境；父脚本和FlagOS服务未修改。

新脚本Host/容器路径均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR/ppu-native/start-model.sh`，SHA-256 `36f58ad7e43b820318be57a9975a5eadbd2915b35a33f91b32bb6ca3f4c78e1f`；已经默认调用实际启动并核验。启动器保持最小命令，不混入安装、评测、缓存目录覆盖或后台管理；未知参数退出2，性能分支只切换前缀缓存。本轮没有性能测试。

真实权重eager及graph各6类输入均与独立参考的prompt及生成token IDs一致；图测得538次capture_end、98次replay。新API文本和两帧视频通过，原生5例4并发service-sanity全部通过。额外64客户端并发、128项短OCR请求128/128匹配、0错误，服务运行请求采样峰值64。结果在 `04-runs/aligned-capacity-20261027/`；这不是正式性能测量，也不表示64路满262144上下文或长上下文质量通过。

新部署指纹 `035672fd74d7a9a7d9a52188a0443e1ab8244c52260a99dcb1f86c75896720e0`。源码仍是初始适配的11个Python文件，全部哈希及权重身份已重验，无产品代码、SDK或依赖变更。原图模式限制继续成立；当前GDN能力仍为UNIFORM_BATCH，不声称FULL通过。极小图关闭放大和自由生成一致性限制保留。

新的持久交付材料为 `01-environment/parameter-alignment-20261027/delivery-aligned/`，容器内部 `/opt/minicpm-ocr-ppu-native/` 已同步相同文件。原始配置、交付副本和验收记录保留为历史，旧32768/8回执不用于本轮。容器未停止、重启或删除；仅重启本任务API，最终服务保持运行。

状态functional，experimental声明的基础检查已复验，完整正式验收、正式精度/性能和新镜像验证仍未完成；不标optimized。没有提交、推送或创建PR。
