# Qwen3.8-Flash-Next / metax

mx-101 / qwen3.8-flash 的本次适配与测量交付已完成，采用
[vllm-plugin-fl工作区](frameworks/vllm-plugin-fl/README.md)。
远端工作根 `/public-flash/jinghao/qwen3.8-flash`；已完成指定PR和FlagTree源码部署，
RoPE修复与显式FULL_AND_PIECEWISE整模对照通过，最终脚本10例105token一致；
GPQA全198题183/198（92.42%）通过。仅graph性能九场景27轮完成，756请求成功、0失败，
长输入高并发的12次抢占重算保留；不判断业务性能达标，不声明optimized。

2026-10-27精简并验证的host/容器脚本均为`/public-flash/jinghao/qwen3.8-flash/start-model.sh`；
容器内部副本为`/opt/qwen3.8-flash-delivery/start-model.sh`，SHA256均为
`c207cc11bfba76819ec04510cd34c8647ecc5fec92492dd48e8ba1eff6e3eda3`。
实际normal启动、两组24请求的默认本地DB精度/延迟对照、105token回归及内部文件一致性通过，服务保持运行，镜像验证pending。
全量精度与九场景性能仍为2026-10-25原脚本/实例的结果，本次未重跑。
[当前启动脚本记录](frameworks/vllm-plugin-fl/acceptance/launcher-default-db-20261027.md) ·
[2026-10-25适配与交付记录](frameworks/vllm-plugin-fl/acceptance/adaptation-summary.md)。

[返回模型概览](../README.md)。
