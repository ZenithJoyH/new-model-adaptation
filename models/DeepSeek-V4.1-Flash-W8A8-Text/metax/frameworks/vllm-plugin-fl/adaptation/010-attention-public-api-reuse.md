# 010：注意力、FP8缓存与RoPE公开API复用

状态：2026-11-04只读契约核对与复用测试准备，尚未接入模型注意力。
安装FGV HEAD f108ba81，主线模型参考e77daef89e18；不修改vLLM。
已确认公开`flash_mla_with_kvcache`支持512维稀疏注意力、sink、动态长度及两个独立FP8缓存，
要求Q头数64/128，可按主线方式将TP8的8个真实头填充到64，并只保留真实输出头。
缓存表面每行584字节，实际每页先存576*B字节值区、再8*B字节UE8M0 scale区；
不是逐行交错布局。现有Qnorm/RoPE/KV写入和FlashMLA解码具有相同实际寻址，
与主线V4.1的448维FP8 NoPE、64维BF16 RoPE及7个真实scale一致。

先验证既有公开缓存插入API的Q头数0路径：只写已经归一化的压缩latent，不发射Q数值工作。
非闭组slot设-1，ratio2的RoPE位置按组起点取整；这部分整数位置/slot构造归Plugin metadata。
若现有路径可用就复用，不增加等价kernel。覆盖小/大token数、不同物理块、负slot、
完整CPU编码/解码参考、KV输入不变和图回放；随后测试实际双缓存FlashMLA与sink/长度。
仅新增必要独立复用测试，若发现契约或设备编译问题，先限定修复符号与影响面再改实现。

逆RoPE优先核对公开`apply_rotary_pos_emb`：尾64维view、GPT-J interleaved、逆sin缓存、
原地模式及不同q/k头数。逆sin是初始化时的ATen neg，应验证FlagGems自动替换与数值，
不在Plugin新增数值kernel。零K头在其view(-1,0,D)处可能不可用，不能未经验证依赖。
WO_A目标TP8每rank仅一组，可用BF16普通ColumnParallelLinear；INT8行scale到BF16加载变换
及FP32投影边界仍需核对公开API并单独限定，不能偷换FP8激活或把INT8权重直接当BF16数值。

两级候选算法也已核对主线`candidate_blocks.py`：按8列最大分数排名，最新块置+Inf固定保留，
输出-1填充；后续indexer按候选块及因果边界原地mask，再选512位置。现有FGV的普通topk/
router topk并不包含完整契约。数值评分/选择/mask归FGV，请求与物理slot映射归Plugin。
该缺口仍待实现，不能把短上下文“全部候选”分支当作完整长上下文支持。

最终模型端尚待验证实际KV规格/分组、PP20/20共享源、prefix缓存、抢占恢复、全图及async。
任何上述API复用通过都不构成整模型或服务验收。

102首轮公开API诊断已证明零Q头写入可用：T1/B16、T7/B16 graph、T129/B64 graph，
FP8值/scale、未写字节、KV输入保持逐位检查，RoPE尾部以独立BF16数值参考检查。
随后双缓存FlashMLA在计算前编译资源检查失败：Required 143360B、C550 limit 65536B；
原generic MODEL1只给BK32/BH64。证据`04-runs/mx-102/fp8-public-reuse-v1-20261104/{reuse.json,probe.log}`。
逆RoPE检查尚未执行；不把前面的缓存写入通过扩大为注意力通过。

下一批数值源修改限`ops/flash_mla_with_kvcache.py`中的MODEL1 kernel装饰器和对应launch grid，
以及NVIDIA/MetaX tune配置。kernel数学/输入输出/掩码及V32、dense、TLE分支不改。
原NVIDIA两组BK32/BH64、warps4/8、stage1保持；MetaX先验证BK16/BH16、warps4/8、stage1，
沿用libentry/libtuner。MODEL1 grid必须按候选BH计算，覆盖全部64/128头，不能只改tile导致漏头。
数值源改前SHA-256 `71473c8006e4248f365be41f0099ba25ca739ddb3b1af6dddbb08207d29dd342`。
新独立CPU编码/FP64注意力测试和原生Benchmark按同名源选择机制接入；原CUDA参考测试保留，
无法运行的原生CUDA对照单独记为未覆盖。源码改前已核对目标FGV指导，缺失指南仍沿用既有记录，
不修改第三方、不临时切换其他实现，若仍资源不足就继续诊断而非放宽数值断言。

102 v2独立复用探针通过，`04-runs/mx-102/fp8-public-reuse-v2-20261104/`：
相同三个零Q头缓存场景保持通过；64头双FP8缓存、sink、长度、无效id及新输入graph，
完整CPU FP64注意力输出和不含sink的LSE参考通过；尾64维逆RoPE view通过，
FlagGems neg直调数值与独立自动替换实际命中也通过。前后源码/环境绑定一致。
改动仅decorator与MODEL1 grid，AST核对kernel body保持不变；不能据此跳过完整回归和性能。

完整回归新增`tests/test_flash_mla_with_kvcache_independent.py`，保留原CUDA参考模块的全部门控。
补头数64/128、分页16/64与stride padding、单/双缓存、长度0、前置无效块、out及图回放。
新增独立原生`benchmark/test_flash_mla_with_kvcache_independent.py`；
`tools/select_tests.py`仅补该源的test/benchmark显式映射。原因：当前选择器遇到同名exact测试后
不会选前缀独立模块，而原模块级门控依赖不可用的CUDA FlashMLA参考；不改通用选择逻辑或原门控。
用既有selector函数验证两条映射。矩阵tile/NoPE与RoPE其他实现均不扩展。
