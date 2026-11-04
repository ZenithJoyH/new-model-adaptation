# 002：容器 bnxt RDMA provider 与主机 ABI 不匹配

状态：最小provider兼容处理与双机通信前置已验证，2026-11-03。两端实际适配容器和映射见环境分析。

容器libibverbs报provider仅支持kernel ABI1、现场uverbs为ABI8。
102容器 `ibv_get_device_list` 返回0，同主机返回5，四个bnxt_roce端口ACTIVE。
容器原ibverbs-providers/libibverbs1为39.0-1；主机为OFED2407mlnx52。
单机MCCL通过不能满足双机RDMA前置。

主机实际加载库：

- `/usr/lib/x86_64-linux-gnu/libibverbs.so.1.14.52.0`，SHA-256 `2029445c13d0d9dd4c585e74eedd57665f5afa4f7d6071c3ace59f5921cce6ac`。
- `/usr/local/lib/libbnxt_re-rdmav34.so`，SHA-256 `e2694779e895e2682e113dea8d8d5a50b92af7bad4ec617216541cf87ef9fae1`。

用户已明确授权最小provider兼容处理。每机复制上述主机provider至
`01-environment/<Host>/rdma-provider/libbnxt_re-rdmav34.so`，内容哈希一致。
`ldd -r` 未发现缺失符号；仅在任务进程设置 `RDMAV_DRIVERS` 为该目录的 `libbnxt_re` 前缀，
两机均枚举并打开5个HCA。容器原libibverbs39及系统provider均未替换，主机配置和容器生命周期未更改。
证据 `04-runs/<Host>/rdma-provider-probe-20261103.json`；102/103 SHA-256分别为
`53b0e9257f2732f64dfcbee7f7aac2199eab771c909ea7d6216d60dfa365ad22`、
`571ae89295051b552ab41138d569bbad8967770ff9300093c89d75b2d24f6edf`。

官方mccl_tests固定为 `1e44d4af1b177f2ab9e23bdd0b393ad757d08f4e`；两机各8-rank本地三项通过。
双机16-rank、BF16、8B–256MiB、factor4、每rank一卡、检查开启、warmup5/20次，
AllReduce/AllGather/ReduceScatter均退出0、Out of bounds0。
全尺寸平均busbw为15.8679/10.5754/10.0172 GB/s，不是模型吞吐或大包峰值。
所有rank的PID namespace对应实际适配容器；16/16实际加载库观察齐全，使用镜像MCCL3.8.2和选定provider，
日志确认NET/IB、RoCEv2 GID3。MPI控制daemon位于主机，计算rank均由docker exec进入对应容器。

原生结果 `04-runs/mccl-cross-sixteen-rank-host-orchestration-v3-freegpus-20261103/result.json`，
SHA-256 `bd024e0d23a7965ac1032c4dbf6214d4e5c0daa20fba231b16dd78e0ee8577f4`。
此前错误的MPI rank编排和GPU占用时的两rank超时记录保留；释放资源后同配置两rank及16rank通过，见003。
本结论仅覆盖通信前置；模型、量化、缓存与服务验收仍未完成。
provider当前在bind mount内，未做镜像打包；交付时仍需容器内部副本及实际交付验证。
