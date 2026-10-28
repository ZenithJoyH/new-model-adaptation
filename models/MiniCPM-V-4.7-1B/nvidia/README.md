# MiniCPM-V-4.7-1B / nvidia

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)

当前 framework 记录：
- [vllm-native](frameworks/vllm-native/README.md)（v2；历史结论不自动成为新门禁通过）。
- [vllm-plugin-fl](frameworks/vllm-plugin-fl/README.md)（v2；历史结论不自动成为新门禁通过）。

## 整理前平台说明（历史原文）

- Inventory group: `nvidia`
- Hardware query: `nvidia-smi`

当前目标是 `MinicpmV4.7-1B-native` 容器中的
`/data/models/MiniCPM-V-4.7/weights/1b`，使用
[`vllm-native` 框架记录](frameworks/vllm-native/README.md)。
2026-09-28 已验证 Host/容器工作根映射、权重、镜像和 GPU 状态。用户明确授权
修改该容器已安装的 vLLM wheel；`vllm-native` 工作区已实现 4.7 注册与
canvas M-RoPE，完成单卡 eager/decode-full 的文本、图片及视频基本推理。
当前为 `functional`，正式精度、性能和完整原生验收尚未完成。详见
[`vllm-native` 工作区](frameworks/vllm-native/README.md)。

另在同一 Host 的 `MinicpmV4.7-1B` FlagOS 容器中建立独立的
[`vllm-plugin-fl` 框架工作区](frameworks/vllm-plugin-fl/README.md)。该框架已完成
文本、图片、多图、双帧视频和 OpenAI API 十并发功能检查，根级启动脚本在
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/start-model.sh`，当前服务为
`127.0.0.1:8308`、decode-full。Plugin 工作区的正式精度/性能与原生回执仍待执行；
上述 `vllm-native` 状态和证据不由这次 Plugin 工作继承。
