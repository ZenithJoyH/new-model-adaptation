# 适配问题索引

- [001：V4.1注册与契约](001-v41-registration-and-contracts.md)：注册、配置、真实16 rank构造/文件头及完整权重加载通过；最终整模服务见015。
- [002：RDMA provider ABI](002-rdma-provider-abi.md)：最小兼容处理和16rank通信前置已验证。
- [003：GPU资源竞争](003-gpu-resource-contention.md)：按授权清理后仍发生外部重建，受干扰性能不可采信，容器保留。
- [004：PP与异步调度](004-pp-async-scheduling.md)：历史通信及初次启动记录；最新同源码ON/OFF对照见015。
- [005：动态W8A8格式](005-w8a8-checkpoint-format.md)：双机量化加载与数值/graph切片、完整权重加载通过；整模质量见015。

- [006：Engram与V2元数据](006-engram-and-v2-metadata.md)：双机CPU布局、GPU算子、V2元数据和模型编排切片通过；整模未验证。

- [007：最终mHC收拢](007-mhc-final-collapse.md)：双机公开接口/RN数值与graph通过，103当前切片受控算子性能通过。
- [008：MoE clamp](008-moe-swiglu-clamp.md)：单token排序优化及量化/通用调用方双机各217项通过；原kernel小控制形状失败保留，v42受控双模式复测通过。
- [009：比例1/2压缩](009-compressor-and-cache.md)：双机数值、状态/图及请求槽位切片通过，103算子性能通过；整模未验证。
- [010：注意力公开API复用](010-attention-public-api-reuse.md)：分区优化39项回归、103原五形状双模式基准及两机模型注意力链通过；整模未通过。
- [011：两级候选](011-two-level-candidates.md)：独立数值/graph、102受控算子性能及模型注意力链通过；整模未通过。

- [012：索引器与位置选择](012-indexer-position-topk.md)：复用已验证MetaX TopK；索引K严格数值/graph、103受控性能和模型注意力链通过，整模待验证。

- [013：clone注册与布局](013-clone-autograd-dispatch.md)：修复及数值、分发、graph证据，详见记录；不能替代整模质量验收。
- [014：运行内存](014-memory-budget-and-startup.md)：完整权重加载及缓存容量诊断，详见记录。
- [015：输出健康与PP异步](015-output-health-and-pp-async.md)：修复多余head Q RMSNorm后长短输入恢复；FULL、TP8/PP2的15组async ON/OFF对照与C8文本sanity均正确，完整GSM8K候选测量正在运行，正式门禁未通过。
- [016：最终源码审查](016-final-source-review.md)：PR整理5文件完成，13项隔离图/集成回归和8项恢复sanity通过，三仓候选补丁/正文/180块索引已交付；原64服务已恢复。公开依赖、高精度比较及最终目标/CI仍未完成，不声明source_review通过。
- [017：评测停止词](017-reasoning-stop-condition.md)：完整v1发现Q:截断思考并产生空最终答案，保留失败后终止；同题对照和1319条输入/评分不变检查通过，新停止配置完整v2已冻结启动，结果待验证。
