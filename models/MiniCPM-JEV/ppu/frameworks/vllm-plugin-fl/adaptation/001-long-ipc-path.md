# 001：长工作根导致 ZeroMQ IPC 地址超限

2026-10-23，MiniCPM-JEV / PPU-01 / `minicpm-jev-vllm`，Plugin `06014201f8ea8cd7092a56a945d8fc7998c5a46c`、vLLM `0.24.0+empty`，eager pooling/classify，物理 PPU1、8330。状态：诊断修复验证中。

首次进程 PID297 使用批准工作根的 `05-tmp`，在模型初始化之前由 ZeroMQ 报 `ipc path ... is longer than 107 characters (sizeof(sockaddr_un.sun_path))`。这不是 checkpoint、算子或模型图失败。原始日志和完整参数在远端工作根 `04-runs/eager-baseline-20261023/`。

上游 `vllm.utils.network_utils.get_open_zmq_ipc_path` 使用 `VLLM_RPC_BASE_PATH` 拼接 UUID，不需要修改 vLLM 源码。已在新容器用 pyzmq PAIR 实测 `ipc://@minicpm-jev-vllm-<uuid>` 绑定、收发成功，没有在批准根以外创建文件。

第二轮仅设置 `VLLM_RPC_BASE_PATH=@minicpm-jev-vllm`，其余模型参数不变，日志和进程身份在 `04-runs/eager-abstract-ipc-20261023/`。这是 Linux 抽象 socket 的运行配置修复；后续仍需验证实际 vLLM 多进程握手和模型加载。没有 Plugin/FlagGems 产品修改，也没有修改 vLLM。若最终保留该设置，须在启动参数审查中说明其路径长度原因和 Linux 适用范围。
