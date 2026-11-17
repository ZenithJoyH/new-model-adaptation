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

102首批七文件已安装，完整39文件上下文通过全部七项项目hooks，40项数值/边界/图回归通过。
日志`04-runs/mx-102/candidates-independent-v1-20261104.log`；FlagGems公开topk实际执行、
NaN选择后写-1、tie允许任意合法顺序及最新块固定保留均已覆盖。
受控原生Benchmark v22完成双模式：mask最小speedup为7.1744/17.2300；
select最小0.01653/0.01480，低于保留的0.9门槛，不能判性能通过。
证据`04-runs/mx-102/candidates-controlled-benchmark-v22-20261104/`，33次资源观察、源码前后一致。
需要继续盘点既有公开选择器与真实大K性能；不删除真实形状或改低门槛。

后续盘点：FlagGems大K路径需排序多chunk再排序8192项；FGV旧bucket选择器仅4096项scratch，
全ties时6250候选可能溢出；persistent_topk相关分支无条件分配TLE共享内存，现场TLE不可用。
因此不把两者接入当前声明范围，不修改旧选择器或FlagGems ATen实现。
下一批限定本模块新增candidate专用packed-key选择kernel：nblocks<=8192、out_k<=8192且k>1024时，
把FP32有序位表示和局部block id打包成UINT64，使用Triton排序，保留NaN最高与原输出-1过滤；
其余参数仍在执行前选择既有FlagGems公开topk。该分支只处理V4.1候选分数，不注册ATen替换。
补NVIDIA/MetaX配置和实际分支命中/大K非有限、ties与完整回归、原生性能；不放宽阈值。

102 packed v2原全部及新增共47项通过，含8192边界、填充、全ties、NaN/Inf、负值和真实大K新输入graph。
日志`04-runs/mx-102/candidates-independent-v2-20261104.log`。v3只修导入/说明，AST核对所有函数不变，
39文件完整上下文七项hooks通过；新路径/边界及graph八项复查通过。
v23双模式原全部形状受控基准通过，保留0.9门槛：select最小0.954455/0.942818，
mask最小7.226191/17.197314；34次资源观察、源码与控制前后一致。
证据`04-runs/mx-102/candidates-controlled-benchmark-v23-20261104/result.json`，SHA-256
`c0e23038d5bfa509b663fa8a95fe8288383191eb28b43b9f244f99fc6bf40860`。
103尚未同步候选算子，整模型长上下文仍未接入；不扩大为双机或整模通过。

103 v26已同步候选增量并保留其注意力修复，完整39文件静态上下文校验后，
候选47项加注意力14项共61项独立复测通过，日志
`04-runs/mx-103/candidates-attention-peer-v26-20261104.log`。两机FGV切片现一致；
候选性能证据仍归102 v23，注意力图模式性能失败仍保留，整模型未接入。
