# 007：启用已安装FlagGems-vllm的现有运行时接入

基线 `model-eager-mamba-fixed-20261024` 仍使用Plugin默认 `VLLM_FL_USE_FLAGGEMS_VLLM=0`。
日志显示 `silu_and_mul_with_clamp=reference.torch`。已核实Plugin注册将此算子的FlagGems实现
限制在该开关开启时；真实实现存在于已安装 `/opt/FlagGems-vllm`，无需产品代码修改。
PR455的QSA/PLE直接调用FlagGems-vllm，与该通用dispatch开关相互独立。

拟改仅新实例的运行配置 `VLLM_FL_USE_FLAGGEMS_VLLM=1`。该开关也切换现有通用算子接入，
因此先执行Plugin activation控制/选择测试与FlagGems-vllm现有clamp测试，再验证整模真实
日志命中及输出。保留当前默认实例结果作为基线；不更改Plugin公共默认值、不扩大源码范围。
若新配置出现错误，保留失败、定位对应算子而非静默回落到reference。原clone排除仍有独立
CPU RNG负对照依据，不因开启此开关擅自撤销。

Plugin activation及clamp controls已有测试21 passed in20.18s，原生记录
`04-runs/flaggems-vllm-binding/plugin-activation.log`。整模新开关尚未验证。

FlagGems-vllm现有clamp完整设备测试 **72 passed in129.47s**，无skip；原生记录
`04-runs/flaggems-vllm-binding/clamp-device.log`。在GPU释放的间隙执行，随后启动的
6400预算实例仍保持原开关0，以先单独验证缓存配置；开关1整模验证另行进行。

## 整模正对照与等待诊断

FGV开关1的 `model-eager-fgv-enabled-20261024` 已通过3条短问及8730-token五请求；
三次命中各6400，冷/热token/logprob完全相同（delta0）。但短问约62/32/44s，前缀命中约48/47/50s，
暖态重复仍有长等待，不能归因于一次初编译。已保留warm三问及3次非暂停Python栈转储。
栈2明确进入FGV `moe_align_block_size._run_tle_atomic_fused` →LibTuner default_policy
→SQLPersistantModel.get_benchmark→SQLAlchemy automap反射，底层NFS rpc等待；另两次在
FlagGems MetaX index_put/nonzero路径。只作单次状态诊断，不进行性能采样或正式性能运行。

代码已有 `FLAGGEMS_DB_URL`，FGV与FlagGems均消费；先验证 `sqlite:///:memory:` 的config与
benchmark读写契约，再仅增加这一运行时配置比较相同请求。保留NFS数据库；不清空缓存、
不修改LibTuner或全局派发、不改变数值kernel。内存SQL为进程级临时缓存，无额外离根文件。
若此对照不能消除等待，再定位剩余原因；不能把本轮观察宣称正式性能达标。

已检查主FlagGems clamp实现：创建limit设备标量且NaN语义需另证，不立即把它视作与现有
FGV实现完全兼容；未进行任何clamp绑定源码修改。本节整模对照时点的实际源码为after-mamba-compat快照；后续graph修复身份见008/009。

内存SQL契约probe已通过FGV和FlagGems两者：缺项→写config→三次读回、写benchmark→读回
完全一致，engine_database均为:memory:；原生 `04-runs/flaggems-vllm-binding/db-memory-probe.json`。
原实例完全暖态三问仍25.637/25.614/25.013s，均答案正确。新实例
`model-eager-fgv-memorydb-20261024` 仅增加FLAGGEMS_DB_URL=sqlite:///:memory:，
真实服务效果待检验；不把probe通过当作模型性能通过。

内存SQL整模实例已完成三类真实回归：短问3/3正确（首条31.247s，其后3.258/2.760s）；
8730-token前缀五请求全部正确，命中增量0/6400/6400/0/6400，重复回答token相同、
logprob最大差0；流式1至30输出与中途插入7×8请求实际重叠，结果逐行1..30和56均正确。
证据均在04-runs/model-eager-fgv-memorydb-20261024/{smoke,prefix-state,mixed-state}.json。
这些是bring-up诊断时延，不是冻结目标下的正式吞吐测试。内存SQL不保留跨进程调优数据库，
Triton文件缓存仍保留在批准根目录；后续graph沿用该配置，未修改库代码或删除NFS数据库。
