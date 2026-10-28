# 2026-10-08：35B 与 1B 共用 Plugin 验证

用户要求在新容器整合两模型适配代码。本轮目标为 `H100-149` 的
`MinicpmV4.7-unified-20261008`，权重为只读挂载的
`/data/models/MiniCPM-V-4.7/weights/35b-a3b`。
状态：`functional-passed`；35B TP2 eager 6/6、共用启动器的
`FULL_AND_PIECEWISE` 图模式 19/19 通过。mixed PIECEWISE 7/7、decode FULL 5/5
捕获完成；覆盖文本、图像、多图、双帧视频、真实大图切片、变输入重放与十并发。

完整配置、共同代码身份、测试矩阵、缓存隔离、启动方式、过程失败及未测试边界见
[双模型共用 Plugin 功能验证](../../../../../MiniCPM-V-4.7-1B/nvidia/frameworks/vllm-plugin-fl/acceptance/unified-code-validation-2026-10-08.md)，
设计见 [008](../adaptation/008-unified-dense-moe-adapter.md)。

共同安装位于新容器内部 `/vllm-workspace/vllm-plugin-FL`，不设置 `PYTHONPATH`。
新容器 CUDA 0/1 对应宿主机 GPU 6/7；继承 1B 环境的 FlagGems 广播 mask 修复，
不使用旧 attention 黑名单，显式开启 prefix caching。
共用启动器为 `/opt/minicpmv47-unified/start-model.sh 35b`。

原 `MinicpmV4.7-35B` 容器、原 Plugin、原工作根启动脚本与 8021 服务未修改。
最终 `final-validation.json`、`final-host-state.json` 均为 `passed`；新容器保持运行，
验证服务停止、18347 关闭、GPU6/7 释放，原 8001/8021 API 正常。
本轮仅为功能回归，未运行正式精度、性能、长上下文或发布镜像验证；
不修改 `framework.yml` 的历史状态或证据绑定。
