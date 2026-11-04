# 适配问题索引

- [001：V4.1注册与契约](001-v41-registration-and-contracts.md)：配置切片通过，完整模型接入未完成。
- [002：RDMA provider ABI](002-rdma-provider-abi.md)：最小兼容处理和16rank通信前置已验证。
- [003：GPU资源竞争](003-gpu-resource-contention.md)：按授权清理后仍发生外部重建，受干扰性能不可采信，容器保留。
- [004：PP与异步调度](004-pp-async-scheduling.md)：Send/Recv前置通过，整模PP+async尚未启动；无异常则按用户要求继续常规适配。
- [005：动态W8A8格式](005-w8a8-checkpoint-format.md)：双机量化加载与数值/graph切片通过；完整权重加载未通过。

- [006：Engram与V2元数据](006-engram-and-v2-metadata.md)：双机CPU布局、GPU算子、V2元数据和模型编排切片通过；整模未验证。

- [007：最终mHC收拢](007-mhc-final-collapse.md)：双机公开接口/RN数值与graph通过，103当前切片受控算子性能通过。
- [008：MoE clamp](008-moe-swiglu-clamp.md)：双机公开量化/激活及实际专家dispatch接线通过，算子性能待测。
- [009：比例1/2压缩](009-compressor-and-cache.md)：目标契约与请求槽位生命周期已核对，数值与状态更新验证中。
- [010：注意力公开API复用](010-attention-public-api-reuse.md)：FP8分页布局与双缓存契约已核对，真实复用验证及模型注意力仍待完成。
- [011：两级候选](011-two-level-candidates.md)：分块评分/最新块与mask契约已核对，FGV完整数值接入待验证。
