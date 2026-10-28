# 004：FlagGems clone 接管 CPU RNG 保存

mx-101 / qwen3.8-flash 首轮eager服务 `model-eager-20261023` 已退出，容器保持running，
8卡进程均释放。131/131权重加载完成，耗时363.65s；NFS自动预取完成后加载明显加快，
不据初始估计添加load-strategy参数。

profile_run实际首个失败链：VocabParallelEmbedding -> get_masked_input_and_mask的内部
torch.compile -> AOT preserve_rng_state -> torch.clone(torch.random.get_rng_state()) ->
FlagGems clone -> CUDA-shaped device context接收CPU设备，报Expected a cuda device, got cpu。
因此不是模型权重缺失、CUDA graph失败或CPU模型执行；全模型enforce_eager不会关闭所有内部
torch.compile。MCCLLibrary缺少ncclCommAbort发生在失败后的清理线程，另保留不当作初因。

FlagGems当前安装e510c6bb的clone使用Autograd包装，内部GPU copy没有CPU守卫。
先在 `07-bugs/clone-cpu-rng/reproduce.py` 独立复现，配置对照结果待验证。
不修改FlagGems/vLLM产品代码；复用Plugin已有 `VLLM_FL_FLAGOS_BLACKLIST_APPEND=clone`，
只作用本任务服务进程，保留平台默认blacklist和其他FlagGems算子。GPU clone也会使用原生
PyTorch路径，需在整模正确性/性能中如实验证影响；这不是FlagGems根因已修复。
退出条件：上游clone/注册器具备正确设备守卫，CPU RNG与GPU clone及整模回归通过后移除此项。

后续使用新run id、独立配置/日志重启本任务服务；不覆盖首轮失败，不重启容器或其他服务。
基础运行语义改变，之前环境身份/回执候选不得直接提升为新配置完成证据，需重新绑定。

独立结果：`04-runs/clone-cpu-rng/before.json`按预期失败(rc2)，CPU uint8 RNG clone报相同异常；
`excluded.json`排除clone后精确相等通过。正对照保留现有注册器的一条“function拼接str”跳过警告，
不将其隐去；该警告不是clone数值失败。
新配置 `01-environment/eager-clone-excluded-20261023.json`，新run
`model-eager-clone-excluded-20261023`；TP8、上下文50000、batch4096/sequences32、文本、
eager及前缀缓存策略均不改，唯一推理环境差异为追加clone排除项。启动前核实旧PID76405已消失、
mx-smi无设备进程；未对容器或其他进程发停止信号。

前缀缓存实际默认值与其独立配置纠正、进程停止记录见[005](005-prefix-cache-align.md)。

## FULL第三轮：编译期CPU randn候选缺口

model-graph-full-artifact-fixed-20261024已越过旧产物构造错误，Inductor编译期设备trap
明确指向randn_kernel；异步异常在preserve_rng_state恢复处报告。所有worker退出，8卡无进程。
安装FlagGems randn实现对device=cpu仍无设备守卫，分配CPU out后直接启动Triton；
Torch原生rand_strided用于编译随机测试输入，可能请求CPU存储。先用独立进程最小复现确认，
不能仅凭异步栈判定此候选为根因。

本轮先不改FlagGems源码；若CPU负对照成立，仅在现有进程级追加排除中增加randn，
继续同一FULL配置。验证CPU三dtype的原生固定种子精确对照、GPU原生路径，以及整模。
该排除也影响GPU randn；属于已披露的临时设备边界workaround，待上游提供设备守卫后撤销，
撤销须重新验证编译和真实模型。未观察到模型推理数学路径需要随机正态采样，不据此作性能结论。

候选未证实：Torch+use_gems的CPU 8192元素FP32/FP16/BF16三项均通过，故没有加入randn排除。
GPU0/7三dtype、1/17/8192/104857600/209715200元素共30项通过，原生对照也30项通过；
注册表确认randn/randn_like在Gems上下文已注册。完整日志/JSON位于04-runs/randn-cpu-compile。
这不是整模非法地址的负对照复现，不能宣称问题修复。保留首轮驱动对“应失败”断言失败的
事实及未执行after.json；改为开启CUDA_LAUNCH_BLOCKING=1与原生Inductor日志，在同一FULL
整模路径获取准确同步异常和实际编译输入，再决定是否需要任何配置/源码改动。

## 首次异常已确认及最小算子排除

model-graph-full-first-exception-20261024通过原生worker临时扩展捕获恢复RNG前的异常链：
Inductor wrapper.generate_and_run_autotune_block →select_algorithm.generate_example_value
→rand_strided→torch.randn→FlagGems ops/randn.py145→Triton MetaX driver.launch非法地址。
这确认真实整模编译期Gems randn调用失败，先前的小规模CPU候选仍不成立；两卡30尺寸
独立测试未复现的限制保留。当前尚未提取原始故障输入形状，不宣称底层randn已修复。

配置处置改为仅进程级追加randn：VLLM_FL_FLAGOS_BLACKLIST_APPEND=clone,randn，
仍保留平台原黑名单、FGV开关1和全部其他模型kernel。与原生固定seed比较CPU/GPU三dtype，
再跑原参数FULL；撤销失败的benchmark_combo_kernel试验，去掉临时worker扩展、同步与大日志。
该排除也影响GPU randn，作为临时workaround披露；移除须同一整模编译场景不再非法地址且
数值/graph回归通过。不是永久改变平台默认值，也未修改FlagGems源码。

randn单项排除预检未通过GPU精确种子比较（CPU三项通过），保留excluded-exact-seed.json/log。
注册表确认randn已排除，但normal_仍注册；RNG状态在注册前后相同，重置seed到context内
仍不同。现场ops/normal.py62–107确认normal_经normal_distribution复用同一randn_kernel。
故完整最小原生入口排除需clone,randn,normal_；不扩展到未调用的randn_like或全部随机算子。
新增native-normal-reproduce.py验证项目原配置解析、保留平台黑名单、实际注册表两个入口
均不在场，再做CPU/GPU三dtype精确种子对照；该结果通过前不将配置标记有效。

完整最小排除预检已通过：项目真实配置解析得到masked_fill,masked_fill_,clone,randn,normal_，
平台两项原排除保留；Gems真实注册表randn与normal_均不在场，CPU/GPU三dtype共6项
8192元素与原生固定seed逐元素完全一致。见excluded-native-normal.json/log。
后续整模恢复原FULL/mode3/custom_ops all、原生默认组合测速；只有此追加黑名单变更，
去掉worker诊断扩展、MACA同步、TORCH_LOGS和debug_dump_path，仍开启原生graph统计。
