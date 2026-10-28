# 002：单机通信图回放后退出停滞与 RDMA 告警

## 范围与证据

- 状态：`verified`（单机生命周期问题）；日期：2026-10-27。
- mx-101 / 当前 glm5.3-flash；Torch `2.10.0+metax3.8.2.2`，原生nccl进程组，8卡。
- 工作根 `04-runs/comm-single-20261027/`；每rank原始测量在 `ranks/rank-*.json`，
  驱动命令/进程状态/stdout在 `mx-101/`。
- `test/nccl_test/` 现场无可执行测试工具，因此此处为原生Torch环境探针，
  不能冒充正式模型执行模式、通信性能或完整适配验收。

## 已验证事实与假设

所有8个rank均核对：8192元素all-reduce结果36、all-gather中每个rank的值正确；
一次通信图capture及两次变输入replay结果均正确。随后驱动进程仍未结束，
首版代码在graph对象仍存活时执行最终barrier及destroy_process_group。

日志同时反复出现bnxt_re provider仅支持kernel ABI1、宿主机ABI8的告警。
这证明镜像RDMA provider存在兼容性风险，但尚不能据此认定它是当前单机退出停滞的根因。
未修改宿主机网络、驱动、系统RDMA配置或任何产品源码。

受控假设：先释放通信图，再销毁通信组；第二版只改变graph/communicator生命周期顺序，
增加阶段记录，以区分最终barrier与销毁的停滞位置。跨机传输能力需后续独立验证。

## 生命周期操作

探针运行超过360秒且所有rank均完成数值/图回放后，已准备核对torchrun PID、父进程、
完整命令及rank记录，再仅对该任务启动器发送SIGTERM。停止请求和原因存为
`mx-101/stop-request.json`；必须继续核实真实退出结果，不能把发出信号当作已停止。
适配容器保持运行，不操作其他容器或进程。

## 当前结论

首版自有torchrun启动器2120已收到SIGTERM并通知8个worker退出，驱动退出码1，保留失败。
第二版仅将图对象释放提前到最终barrier前，并新增阶段记录；所有8个rank均完成
`eager_all_reduce`、`eager_all_gather`、`graph_all_reduce`（1capture/2次变输入replay）、
`release_graph`、`post_graph_barrier`，最终state=passed。驱动退出码0，耗时约50.7秒；
证据为 `04-runs/comm-single-v2-20261027/`。该受控对照验证了本探针的图对象/进程组
生命周期顺序是退出问题的原因；未修改任何通信库或框架产品代码。

双机16卡已使用同一第二版探针开始独立验证，结果在 `04-runs/comm-dual-20261027/`。
RDMA告警的跨机影响尚未判定。该环境探针不选择最终模型图模式；
服务仍须按FULL到PIECEWISE逐级验证。
