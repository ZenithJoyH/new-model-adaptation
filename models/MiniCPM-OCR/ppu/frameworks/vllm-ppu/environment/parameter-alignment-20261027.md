# 参数对齐后的部署环境

2026-10-27，PPU-01 / minicpm-ocr-ppu-native。主机、镜像、容器ID、已验证的工作根映射及实际安装包均沿用[初始环境](README.md)，没有容器重启或产品源码改动。只更新当前任务启动配置，外部父脚本保持只读。

与父脚本对齐：max-model-len=262144、max-num-seqs=64、mm-encoder-attn-backend=TORCH_SDPA、显存0.55、图像4/视频1、前缀缓存开启及FULL_AND_PIECEWISE。删除显式max-num-batched-tokens；API实际默认8192。原生设备PPU4/TP1、端口8014、模型名MiniCPM-OCR-PPU-native保留，避免影响FlagOS的PPU2/9999；不加载Plugin专用环境变量。后台和日志操作在调用侧，脚本不混入安装、检查、清理或评测命令。

新启动脚本SHA-256 `36f58ad7e43b820318be57a9975a5eadbd2915b35a33f91b32bb6ca3f4c78e1f`。新部署指纹 `035672fd74d7a9a7d9a52188a0443e1ab8244c52260a99dcb1f86c75896720e0`，精确身份保存在批准根 `01-environment/parameter-alignment-20261027/deployment-aligned.json`。全部权重文件SHA及已安装11个改动文件重新校验，与原身份一致。源码、Torch、Transformers、SDK和原生库没有更新。

旧启动脚本、部署及交付材料保留在同目录备份中，旧回执保留在framework.yml的control.history；不作为新配置通过证据。当前持久交付位于该目录的delivery-aligned，容器内部 `/opt/minicpm-ocr-ppu-native` 已同步相同新文件；新镜像验证仍pending。
