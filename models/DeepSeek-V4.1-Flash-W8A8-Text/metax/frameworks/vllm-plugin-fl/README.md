# DeepSeek-V4.1-Flash-W8A8-Text / MetaX / vllm-plugin-fl

2026-11-04，目标 `mx-102`、`mx-103`，指定0.28镜像。整模尚未加载，适配与正式验收未完成。
两机适配容器 `deepseek-v41-text-plugin028-20261103` 保持运行，批准根均为
`/public-flash/jinghao/deepseekV4.1`。镜像digest、源码和映射见环境分析。

- [环境分析](environment/environment-analysis.md)：实际安装身份；双机16卡MCCL三项0错误。
- [配置接入](adaptation/001-v41-registration-and-contracts.md)：两机各20项单测通过；完整模型/量化/cache仍缺失。
- [W8A8接入](adaptation/005-w8a8-checkpoint-format.md)：已注册格式并定位修复真实量化/矩阵乘边界问题，未将局部通过作为整模结论。
- [RDMA兼容](adaptation/002-rdma-provider-abi.md)：用户授权的最小provider处理及通信证据。
- [资源竞争](adaptation/003-gpu-resource-contention.md)：已授权终止竞争worker，保留容器，推理PID1暂停。
- [验收状态](acceptance/README.md)：模型eager/graph、sanity、正式精度/性能和交付均未通过。

不要在这里保存脚本、源码、补丁、JSON 结果、原始日志、缓存或临时文件。
