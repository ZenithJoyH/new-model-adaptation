# 011：两级候选块评分与掩码

状态：2026-11-04改前计划。目标FGV HEAD f108ba81，安装树`/opt/FlagGems-vllm`。
主线e77daef89e18 `candidate_blocks.py` blob efc7c418cad6afbe330338f26e37daa9a04f8561：
每8个位置的最大logit为块分数，最新块置+Inf，选2048块，NaN/负Inf选中值按原规则写-1；
后续indexer按候选块和因果边界原地mask。logits在packed列空间，block id相对每行start；
保留native对超出width候选块的最后一列clamp行为，不能将其简单当作无效id忽略。

盘点FGV公开persistent_topk/bucket_sort_topk与FlagGems ATen topk：普通选择器不含分块评分、
最新块及后续mask完整契约。新FGV wrapper可复用FlagGems公开topk做中间块选择，
其余新数值kernel放FGV，Plugin只消费公开结果和准备请求/slot metadata。
不新增Plugin ATen adapter；FGV内部明确调用已存在的FlagGems ATen实现，避免依赖外部全局
注册状态而落入原生Torch计算。FlagGems本身保持只读清洁，不在此添加融合算子。

拟新增`ops/deepseek_v41_candidates.py`，公开`deepseek_v41_select_candidate_blocks`与
`deepseek_v41_apply_candidate_mask`；新增同名tests/benchmark，补ops导出、operators元数据和
NVIDIA/MetaX tune配置。当前支持FP32 logits、INT32候选、INT32/64一维bounds、block_size=8，
正row_repeat及连续内维/可padding行stride；所有scalar/dtype/shape/device/alias在计算前检查。
空rows/width明确定义，无隐藏持久状态。候选输出为caller buffer；mask只改logits。
普通评分/输出/flag kernel写完整fresh workspace；原地mask autotune恢复LOGITS。
不改普通topk、router、其他数值内核或第三方。

独立CPU参考覆盖最新块、随机唯一分数、ties、NaN/Inf/-Inf、packed starts、row_repeat、
部分末块、-1填充、边界/超范围候选、empty、padded stride/offset及拒绝前不变；
实际冷autotune和新输入图回放验证。确认FlagGems公开topk实际命中，不能仅验证输出shape。
目标形状包含block_size8、topk_blocks2048、width50000；性能沿用原生Benchmark，
未测/失败不判通过。Plugin接线及长上下文整模型仍待后续验证。
