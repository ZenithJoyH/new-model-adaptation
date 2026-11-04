# 009：比例1/2压缩与开放组状态

状态：2026-11-04契约已核对，尚未修改本切片产品源码。FGV HEAD f108ba81，
安装树`/opt/FlagGems-vllm`，现有mHC/Engram/W8A8/MoE修改须保留。
主线固定参考e77daef89e18的`common/ops/fused_compress_quant_cache.py`：
比例1直接对FP32 KV做RMSNorm；比例2对相邻两行FP32 KV/score按每通道softmax池化，
再FP32 RMSNorm，最终只在闭组行物化BF16。无APE、无重叠组。
开放组FP32环形状态由调用方持有；请求程序先读旧行形成chunk首个闭组，再写当前chunk尾部，
其余闭组只读当前原始行，避免并发写环形状态造成读写竞争。

FGV已有kpool是带APE的FP8 index缓存写入，QSA压缩使用另一种pool规则及128维MRoPE，
普通V4压缩含比例4/128及重叠组；均不满足目标的512维、FP32分数、无APE和BF16边界。
不得把这些接口按名称相似直接用于V4.1，也不复制到Plugin。新增公开
`deepseek_v41_compress_norm`放`ops/deepseek_v41_compress_norm.py`，复用现有libentry/libtuner。
新增只限该实现、同名独立测试/原生Benchmark、ops导出、operators元数据和NVIDIA/MetaX调优配置。
不修改第三方、通用tuner或vLLM源码；RoPE/缓存插入与Plugin状态接线另行限定后实施。

公开契约：raw FP32[N,512*ratio]、INT32/64 positions/slots；ratio为1或2，eps有限正数，
BF16 norm[512]与调用方输出[N,512]。比例2另需FP32[blocks,capacity,1024]环形状态、
请求query边界和token→batch-request映射。caller保证单请求连续位置、独占ring block，
slots编码block*capacity+position%capacity；负slot/padding不读写，非法物理slot防越界。
只更新有效闭组输出及各请求最后capacity行状态，其余输出/状态保持原值。
标量/shape/dtype/device/stride及不支持的alias在计算前拒绝。
autotune必须恢复STATE和OUT，避免重复试跑改写开放组后污染结果；不增加用户开关。
独立CPU FP64池化/归一化参考与精确状态副本，覆盖混合请求、空/奇数chunk、跨chunk闭组、
环绕、重排/padding、非有限值、非法参数前置拒绝、冷调优和新数据graph回放。
新增kernel按每token定位闭组，避免主线pair-grid在奇数尾端先读取positions的越界风险。

Plugin后续候选：现有V2 `RequestState`以free_indices分配槽位，请求存续期间不换槽，
remove_request后可复用，ModelState已有add_request生命周期扩展。可在Plugin拥有的稳定ring中
按真实请求槽位维护少量开放组状态；必须验证请求重用/重置、前缀命中起点、抢占恢复和PP。
目前只完成只读生命周期盘点，未以该候选替代已验证缓存规格，未声称支持整模型。

102实际首轮41 passed、1 failed；失败发生在测试构造alias时误写`torch.bfloat16()`，
尚未进入算子。只纠正该dtype常量调用后42 passed，原断言/容限/数值代码保持。
日志`04-runs/mx-102/compressor-operators-v{1,2}-20261104.log`。
冷热调优的精确状态比对、跨chunk、环绕、strided/offset、NaN/Inf及新数据graph已覆盖。
安装阶段曾丢失SSH回传；复查七文件after hash及安装记录完全一致，再续跑格式与测试，
没有重复安装。静态hooks、103独立验证、受控性能与模型接线仍待完成。

适用七项hooks现已通过。首轮flake8发现独立参考的一个未使用局部变量，仅删除该无副作用
赋值后复核通过，数值实现/断言不变。精确静态快照v15共29个源/配置上下文文件；
42项数值/状态/graph结果仍绑定相同产品算子。已开始103按基线与全静态上下文核验后的独立复测。

103七文件同步及独立复测已完成，42 passed；日志
`04-runs/mx-103/compressor-operators-v15-20261104.log`。
manifest SHA-256 `b513d92ddf38e0ecd459b26063c6afd7581c176466c437f82e571c2e0dd70a43`。
性能测量已开始；Plugin消费与模型缓存生命周期仍未验证。

后续Plugin范围限`models/deepseek_v41/model_state.py`的可选压缩状态准备、
新增同目录`compressor_metadata.py`的请求/slot复制、新增薄dispatch provider与既有registry条目，
以及对应dispatch单元和真实GPU元数据/生命周期测试。保持现有Engram历史和无压缩模型路径。
model须显式声明capacity=8和reset接口才启用；否则不分配新增buffer。
按V2真实idx_mapping生成稳定ring slot和token→batch-request映射，query尾部填相同终点，
使用固定预分配缓冲，不读取CPU token占位符。dummy全为无效slot，不写数值状态。
NewRequestData实际有num_computed_tokens；新请求/抢占重加入必须从偶数位置起算，
奇数起点在重置前明确拒绝，不能读取复用槽位的旧状态。模型接入还须约束实际cache block为偶数，
并验证前缀命中和抢占行为；这不是已完成的服务支持声明。既有请求跨chunk奇数起点继续使用自己的ring。
请求加入时通过model公开reset接口重置该槽位，状态由模型持有；数值池化仍只调用FGV公开API。

103受控原生压缩benchmark完成：每模式8形状，kernel speedup最小2.8333、最大4.9147；
cudagraph最小5.0118、最大13.8179，保持0.9门槛。32次资源观察无外部计算，源码/环境前后一致，
Benchmark/tuner控制文件对固定HEAD一致。结果
`04-runs/mx-103/compressor-controlled-benchmark-v15-20261104/result.json`，SHA-256
`14a2a244d38a3c9f90128d2b79eca4cf70d3e857c3d73577f53b600497d7e955`。
仅为压缩算子结果，不等于模型请求生命周期或PP/async验证。Plugin六文件切片已完成本地静态预检，
102实际安装验证已开始。

102实际Plugin接线已通过：新增dispatch/原Engram单元14 passed；新增请求metadata/生命周期/
真实压缩组合及原历史准备共52 passed，日志`04-runs/mx-102/compressor-plugin-{unit,functional}-v1-20261104.log`。
根公开压缩API实际经统一dispatch消费真实GPU请求映射，重排chunk先读旧ring再更新，CPU FP64
参考及精确状态副本通过。新模型能力需显式声明，已有无压缩路径保留；新请求奇数起点及speculation
明确拒绝，尚未验证真实scheduler抢占/前缀/PP服务。FGV/Plugin v17全适用hooks通过；103复测进行中。

103联合切片复测完成：FGV matmul188 passed、48项原CUDA/vLLM对照deselected；
dispatch单元14 passed；实际元数据/生命周期及原Linear/Engram调用方102 passed。
日志`04-runs/mx-103/compressor-metadata-{library,unit,functional}-v17-20261104.log`。
联合manifest SHA-256 `6256f9e4e346998b3f94f56353ec49b92d4431dd29be5b4094e781a12771ed85`。
双机源码及框架接线已一致，真实整模型与scheduler行为仍未验证。
