# PPU-07 诊断环境快照

日期：2026-09-24。仅为本轮验证的身份与边界记录，尚不是完整环境阶段回执。

| 项目 | 核实值 |
|---|---|
| SSH Host | `PPU-07`，hostname `bm-aliyun-wlcb-zonea3-c-810e-96g-10-7` |
| 源容器 | `minimaxM3`，保持运行；另有使用 TP16/8013 的 `minimaxM3-opt-20260921` |
| 新验证容器 | `minimaxM3-latest-20260924`，ID `274609df1ca78264c1af0327ef1aa255f4e7be1ae164dd5d963fbd73a517f116`，运行中 |
| 镜像 | `harbor.baai.ac.cn/flagos-inner-models-release/minimaxm3-pp001-gems5.4.0-tree0.6.2-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-2.1.1-rbd225:202609211044`，ID `sha256:41d96df0b7b416e1e887fe1c4dab21dfc12819875524993f90213fe29214f541` |
| 工作根 | host/container `/mnt/nfs/users/jinghao/minimaxM3-new`；现有 `/mnt:/mnt` bind，双方 `stat` 均为 `41:12343954721` |
| 权重 | `/mnt/cpfs/models/MiniMax-M3`，只读引用 |
| Plugin | editable `/workspace/vllm-plugin-FL`，detached `cafe6363c8c3de5ba4693b91643089c17b3ab87c`；继承镜像的四个 `.orig` 未跟踪文件未修改 |
| FlagGems-vllm | editable `/workspace/FlagGems-vllm`，detached `1f9ac0e0caf3c32111f6be44c8e4d2fef2359546`，tracked clean |
| FlagGems | editable `/workspace/FlagGems`，`3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85`，未修改 |
| vLLM | 安装导入位于 site-packages，源码 `/workspace/vllm` 为 `ee0da84ab9e04ac7610e28580af62c365e898389`，未修改 |

镜像、挂载、入口和代码修订在变更前分别核对；新容器从与原容器相同的镜像创建，原容器及其源码未改动。容器内 `vllm_fl`、`flag_gems`、`flaggems_vllm` 导入路径分别指向上述 editable checkout。新容器使用 host network/IPC，但尚未启动模型服务，预留的验证端口为 8024。
