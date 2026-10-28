# 004：双机 MCCL 网卡选择

## 基线与问题

2026-10-27，mx-101、mx-102 的 `glm5.3-flash`，各8张C550；PyTorch
`2.10.0+metax3.8.2.2`，实际通信库 `/opt/maca/lib/libmccl.so`。
两机首测在首个 all-reduce 失败：102的rank11先报 `ncclSystemError`，连接到了
不属于本次共同网段的地址，101同组等待。原始结果位于批准根
`04-runs/comm-dual-20261027/`，失败日志原样保留。

## 根因与修复

运行环境设置了 `NCCL_SOCKET_IFNAME`，但实际 MCCL 库读取 `MCCL_SOCKET_IFNAME`。
二进制和日志只读核对后，以两机均存在的 `inbond1` 设置正确变量；Gloo 同样使用该接口。
没有改驱动、网络配置、通信库或产品源码。旧组的101 launcher PID4151经cmdline、PPID
核对后发送SIGTERM，driver记录rc1退出；102原组自动退出。容器始终运行。

## 受控验证

- 新配置：批准根 `01-environment/comm-dual-mccl-mx-101.json` 和 `...mx-102.json`。
- 原生证据：批准根 `04-runs/comm-dual-mccl-ifname-20261027/`。
- 101 driver4275 / torchrun4281，102 driver1675 / torchrun1681，均rc0正常退出。
- 16 ranks 的 eager all-reduce、all-gather；一次capture和两次变输入replay；释放graph后
  barrier及通信组销毁均通过。单机图生命周期处理见问题002。
- 实际跨机路径为 `NET/Socket`；`bnxt_re` 用户态库与内核 ABI 不匹配的警告仍存在，
  不宣称RDMA/RoCE已验证，也不据此报告性能通过。

## 后续与边界

后续模型双机启动保留必要的 MCCL/Gloo 接口选择；诊断 `MCCL_DEBUG=INFO` 不进入最终启动器。
该探针不替代vLLM实际并行、整模图执行或精度/性能验收。未变更任何组件源码。
知识库状态：`local-only`。
