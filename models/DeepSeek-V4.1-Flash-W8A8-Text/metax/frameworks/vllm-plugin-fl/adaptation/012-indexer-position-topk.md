# 索引器位置 TopK 接入

范围限定实际安装FGV的MetaX `persistent_topk` 无TLE后端、新后端导入、厂商tune，以及对应独立测试/原生Benchmark。
沿用已有root公开API、配置和marker，不改Plugin数值实现、不改vLLM或第三方依赖。
已核对实际MetaX目录仅有依赖TLE的persistent_topk.py；无TLE时转发generic，后者仍无条件使用
TLE共享内存分配，不能用于本镜像。旧bucket实现4096项scratch不足以覆盖50000项全ties。
替代限定为每行独立CTA的四字节radix阈值选择，不需TLE或跨CTA barrier。

契约：FP32二维logits内层连续、可有row padding/offset；INT32连续lengths，其numel等于行数；
INT32 caller output形状[rows,k]，k为512/1024/2048，支持row padding；连续同设备UINT8 workspace
保留API但此实现无需scratch、不修改。max_seq_len缺省width，显式非负整数取与width的最小值。
长度按有效域[0,max_seq_len]限定；不足k时输出全部有效位置并以-1补齐；其余输出无序唯一TopK，
ties任意合法顺序，NaN按最高分，Inf/-Inf保留，正负零可任意tie。输入不变，output禁止与输入共享storage。
空行数无launch。参数/布局/设备错误在写入前拒绝；目标device guard沿用runtime。
使用libentry/libtuner、caller output恢复及MetaX配置；先于执行根据TLE能力选择，无执行后重试。

按operator:A2/A3/B1/B3/C1–C7/D1–D5/E1–E6/F1–F4/F6验证公开后端实际命中、CPU独立集合/分数参考、
真实50000长度、全ties/非有限、padding保护、非法输入、另一设备与新输入graph。
原生Benchmark保留0.9门槛及全部失败，数值通过不等于性能或整模型通过。

首轮48项全失败，日志`04-runs/mx-102/position-topk-v1-20261104.log`；实际has_triton_tle为True，
公开入口选择已有MetaX专用后端，未命中新加的无TLE分支。前述“现场TLE不可用”的判断不成立。
限定真实连续input/output重新通过原公开API检查N=1/8/128、width6250/50000、k512及2048全ties，
五组CPU独立分数集合和新输入graph均通过。证据`04-runs/mx-102/existing-position-topk-probe-v1-20261104.json`。
因此最终选择复用原MetaX实现，模型安排连续output；不继续扩张支持范围或实现重复TopK。
按精确前后hash撤回五文件试验（恢复原init/tune，移除本任务新增实现/test/benchmark），保留全部失败证据。
此复用诊断不等于完整indexer、模型或原生性能通过；后续不引用未命中的48项作为新后端精度证据。

后续索引K生产限定FGV新增薄公开`deepseek_v41_indexer_k_store`：复用FlagGems RMSNorm、
FGV公开GPT-J RoPE与indexer_k_quant_and_cache，不复制数值kernel。Plugin已准备group-first positions
及仅闭合组的slot，算子仅消费metadata。BF16[rows,128]经FP32 RMS/BF16、尾64 RoPE/BF16，
UE8M0 FP8缓存按页先128值字节后单FP32 scale；比例1/2均使用既有32/64行页。
原indexer_k_quant_and_cache SHA-256为879294b83221ca00d685fd904984957a3ad8e85f893c8228adc73fb1070dcea4；
其原生autotune会写cache且无恢复，限定迁移decorator为libentry/libtuner、恢复value/scale两view，
补两厂商同原warps配置与device guard/empty处理，保留原数值与旧测试支持范围。
新增薄API导出/配置与独立CPU数值、cache保护、实际公开复用命中、冷调优、新输入graph及原回归。

103首轮indexer-store-v1为2通过、1失败后停止；7行样例15个FP8字节相差1，原严格断言保留。
根因复核：FlagGems RMSNorm在乘weight之前先转回输入BF16；V4.1原生store要求乘weight后才BF16。
不能将同名RMSNorm视为相同契约。改复用FGV已公开`mhc_rms_norm`，其宽度由输入决定，
FP32归一化和weight乘法后才保存BF16，正好满足当前契约；不改FlagGems，不增加数值kernel。
补丁仅替换薄API中的公开调用及实际复用命中测试，完整严格独立参考重新验证。

103 v2完整34项通过（新增29项与原缓存量化5项），包括两种RoPE dtype、空/1/7/33行、32/64行页、
page padding、负slot跳过、输入不变、公开复用实际命中、非法写入前拒绝和新输入graph。
所有cache字节继续与独立CPU FP32→BF16→FP8参考逐位一致，没有放宽阈值。
日志`04-runs/mx-103/indexer-store-v2-20261104.log`；完整43文件静态上下文七项hooks通过且字节不变。
103实际FGV上下文v29；102仍v26，尚未同步该八文件切片。原生双模式性能正在独立测量，整模未接入。

102 v30已同步索引K及薄权重反量化增量，53项全部通过（本切片34项与权重接口19项），
日志`04-runs/mx-102/dequant-indexer-peer-v30-20261104.log`。
103索引K受控原生Benchmark完成：四个形状/模式，kernel最小speedup6.415204，
cudagraph最小4.861454，保留0.9门槛；31次资源观察，源码与测量控制前后一致。
证据`04-runs/mx-103/indexer-store-controlled-benchmark-v30-20261104/result.json`。
控制器结果的scope末句误沿用candidate文案，实际plan、pytest模块与结果op均为indexer K；
该文案错误不作为候选算子证据，原结果保留，不重写历史测量。
