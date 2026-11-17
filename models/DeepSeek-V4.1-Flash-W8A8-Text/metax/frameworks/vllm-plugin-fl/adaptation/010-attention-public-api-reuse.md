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

102完整回归v1为11通过、1失败，证据`04-runs/mx-102/flashmla-independent-v1-20261104.log`。
失败是首个BK tile全部无效、后续tile仍有效时输出NaN；在线softmax先算了负Inf减负Inf。
修复范围现扩展到MODEL1主/附加缓存两处递推：仅当累计最大值仍为负Inf时，指数平移用0，
累计max继续保留负Inf；这样空tile贡献0且不污染后续有效tile。有限最大值的运算顺序不变。
改前源SHA-256 `4d0e38e3601f73dd7f5a82f3b80b79cf2b8431a93fac842dfef1aa2a400d916f`。
扩展回归覆盖主/附加缓存独立前置32个无效位置和新输入图回放；保持原FP64参考与误差阈值。
适用operator:C4/C5/E4/E5；尚未验证的修复不计通过。

102 v3扩展回归14项全部通过，日志`04-runs/mx-102/flashmla-independent-v3-20261104.log`。
六个最终变更文件逐hunk核对，完整36文件静态上下文的七项项目hooks通过且字节未被修改。
source SHA-256为`2fd3b7bbf8fb6e44002a64a52f2bbc6b46085bf6513a09198b3c164f6755b9c3`。
103 peer六文件manifest SHA-256
`4e372a890079c190f157c17026d6c6f64d6c3537412b96423e50c0e3c88b4304`；
该切片已安装并通过独立回归，受控原生Benchmark进行中，仍不判算子性能或整模通过。

103 v20受控测量完成，35次资源观察、源码/控制前后一致。kernel最小speedup0.935162，
cudagraph最小0.505816（单token、双缓存128+512位置），低于保留的0.9；不判联合性能通过。
证据`04-runs/mx-103/flashmla-controlled-benchmark-v20-20261104/result.json`，SHA-256
`7ca23abf818f4334d83435afaec024655aa600f76974b434425016df90ebfed8`。
编译metadata显示BK16/BH16使用53248B共享内存；正在通过原公开API与标准tuner做进程内
配置诊断，不修改产品源码、不将诊断计时当正式Benchmark验收。后续优化范围待资源证据确定。

103进程内配置诊断v2：BK16/BH16 warps4约0.592ms graph，warps8约0.714ms；
BK32/BH16的两组都因88064B>65536B编译拒绝，证据`04-runs/mx-103/flashmla-tile-probe-v2-20261104/`。
单调tile无法直接解决。下一批限定MODEL1加入MetaX配置控制的COMBINE_ROPE constexpr：
将第二段192维NoPE和64维RoPE复用现有BF16 kv_blk1，以一个256维dot代替分开的256+64 dot，
减少重复共享内存与补零运算；保留原非MetaX分支、量化/缓存寻址、safe_max、sink及LSE语义。
NVIDIA不启用该配置。测试仍用完整CPU FP64参考、14项原回归与新输入graph，性能重新正式测量；
未验证的资源/性能收益不计通过。实际源与MetaX tune及配置测试之外不扩展。

103 combined v4生成控制脚本误改循环缩进，13项数值失败、1项配置通过，原日志保留；
v5按AST定位五处局部改动并校验外围循环结构，原14项全部通过，未变更参考或容限。
证据`04-runs/mx-103/flashmla-independent-combined-v5-20261104.log`。
BK32即使合并第二段仍需81920B，被标准tuner编译拒绝；实际选中BK16/BH16/warps4。
v6移除两个无效BK32配置，保留已验证BK16的warps4/8；完整36文件上下文七项hooks通过。
正式双模式性能仍在进行，不能以数值通过或移除无效候选代替性能门槛。

103 v25正式双模式测量结束：kernel最小1.006058，cudagraph最小0.527195，
图模式单token双缓存仍未达0.9。35次资源观察与源码前后绑定一致；保留
`04-runs/mx-103/flashmla-controlled-benchmark-v25-20261104/`，后续优化仍未完成。
已验证数值切片同步102并复测通过，仍不判注意力联合性能通过。

下一批Plugin编辑限定`models/deepseek_v41/attention_metadata.py`的整数slot/上下文/SWA索引/
按token复制block table及logical→physical转换，和`cache.py`的CacheLayer、Backend、MetadataBuilder；
对应新增functional整数参考/图测试与unit cache-spec/真实allocator布局检查。按plugin:A3归框架，
不读写KV数值，不改vLLM或既有request ring，不提前注册整模型。
原生V4 builder的_layer_type_for仅接受1/4/128，不能直接用于比例2，故新增V4.1专用builder。
原始块64、比例1/2对应物理页64/32，匹配既有paged_mqa公开范围。V2 BlockTables使用原始
逻辑块，而allocator对compressed spec改用storage_block_size；新metadata从positions和block table
明确计算物理slot，只用原始slot的正负判断padding，避免重复或遗漏比例换算。
覆盖混合prefill/decode、多请求重排、块边界、prefix起点、无效/越界物理块、padding、query长度、
页padding/stride、别名拒绝及新输入graph；完整模型/PP/prefix调度仍须服务实证。

102新四文件已安装，37文件完整Plugin上下文的适用hooks通过。新cache-spec/真实allocator
布局、metadata整数/图及原ring/history共97项通过，日志`04-runs/mx-102/cache-metadata-v1-20261104.log`。
原始64-token block table由native prepare_kernel_block_sizes验证；实际allocator将比例2映射为
32行物理页，page padding和content-only view逐位保护区检查通过，不复制或重排KV缓存。
103已同步同一四文件并通过相同97项，日志`04-runs/mx-103/cache-peer-v20-20261104.log`。
模型端仍待接线，以上不证明整模或PP调度通过。

后续性能修复候选限定既有MODEL1 kernel的split-K分区和FP32部分结果归并，不复制kernel。
拟将预留num_splits参数扩展为1/2/4/8，仅MODEL1 sparse FP8可分区，非法值在metadata/输出写入前拒绝。
通用默认保持1；MetaX小批双缓存策略放既有厂商目录并从公开入口注册。临时partial仅单次调用，
sink只在最终归并纳入分母，公开LSE继续排除sink，空行和保护区语义保持。
变更边界为既有FlashMLA源、MetaX薄策略/导出及独立数值/图测试；原五形状双模式benchmark与0.9门槛不变。
需覆盖各分区数、单/双缓存、页padding、空/前置无效块、正负Inf sink、out及新输入graph，
并复跑原14项和注意力链。当前仅记录方案；运行中的整模服务所冻结安装源码不作并行修改。

整模流式加载失败退出后，103先安装四文件分区切片，独立测试39项通过，含原14项、显式1/2/4/8分区、
64/128头、16/64页、单/双cache、保护区/空行/前置无效位置、Inf sink、新输入图、非法参数及实际厂商命中。
日志`04-runs/mx-103/flashmla-split-v1-20261104.log`。MetaX仅小批双cache默认8分区，显式参数保留；
通用默认1，单次FP32 partial/LSE缓冲不保存为跨调用状态，sink在最终归并一次计入。
受控v38五形状双模式全部达到原0.9门槛：kernel最小1.460987、graph最小1.200977，37次资源观察，
源码/控制前后不变，`04-runs/mx-103/flashmla-controlled-benchmark-v38-20261104/result.json`。
参考仍为公开的同GPU非融合组合，不是CUDA原生FlashMLA或整模型加速结论。103 Plugin attention链4项也通过新实现。
v38原生结果SHA-256 `b347e156793699481c38d893eec4303803c5040546cb837e71c3a3ac4015e625`。
