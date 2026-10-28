# 001：官方 Plugin 主线缺少 GLM-5.3 模型接入

## 元数据与基线

- 状态：`open`；日期：2026-10-27。
- 范围：mx-101、mx-102 / glm5.3-flash，BF16，双机16卡；实际并行布局待通信验证。
- Plugin `/opt/vllm-plugin-FL@4e23ae8f`、FlagGems `/opt/FlagGems@3eab0949`、
  FlagGems-vllm `/opt/FlagGems-vllm@ddce1d66`；三者在修改前工作树干净。
- vLLM `/opt/vllm@ee0da84a` 只读，完整继承 diff 哈希
  `2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`。

## 已核实问题与参考

权重架构为 `Glm5NextForConditionalGeneration`、model_type 为 `glm5_next`。
当前 Plugin 主线仅有 GlmMoeDsa 等其他模型注册；没有对应配置、模型实现、KPool cache
接入或多模态 processor。该缺口不能通过增加 TP 数目解决。

历史公开实现 `ZenithJoyH/vllm-plugin-FL` 的 `support-glm5.3-flash@115ecb8f` 含模型、配置、
cache 接入与 processor，但相对当前官方主线包含122个文件的大范围差异和其他平台改动。
仅作为来源参考，禁止整分支覆盖、删除当前 HY4 或替换当前图编译/dispatch/worker 层。
历史 PPU 中 BF16 indexer provider 使用的部分符号在当前 FlagGems-vllm 已不存在；
不能直接复制其 provider 后宣称 MetaX 可用。

## 初始变更边界（产品代码修改前）

| 所属组件 | 文件/符号 | 动作与必要性 | 验证 |
|---|---|---|---|
| Plugin | `vllm_fl/configs/glm5_next.py` | 新增真实 text/vision/conditional 配置，与本地config保持一致 | AutoConfig加载、字段/架构保持、多次注册 |
| Plugin | `vllm_fl/models/glm5next.py` | 引入来源明确的GLM模型编排，接入当前安装的vLLM层和CachedOp接口 | 模型导入/注册、权重协议、状态/并行接口、eager/graph整模 |
| Plugin | `vllm_fl/patches/glm5next.py` | 新增受模型架构约束的hybrid/KPool注册和cache接入；按当前worker接口适配 | 非GLM守卫未命中、cache布局/地址、前缀状态、重复注册 |
| Plugin | `vllm_fl/transformers_utils/processors/glm5next.py` | 接入真实多模态processor；不将conditional权重静默改名为纯文本架构 | processor加载、图像/视频最小测试与明确限制 |
| Plugin | `vllm_fl/__init__.py:register_model` | 添加惰性且幂等的GLM注册调用 | fresh/spawn/重复注册及已有模型注册回归 |
| Plugin | `dispatch/backends/flaggems/impl/glm5next.py`、现有 `register_ops.py` | 仅新增GLM需要的算子契约/薄适配；复用现有库实现，不复制reference后端的torch计算 | 直接算子数值、dispatch命中、dtype/shape/状态边界及graph回放 |
| Plugin | 对应 `tests/unit_tests/patches/`、`tests/unit_tests/dispatch/` 中GLM回归 | 新增可维护注册/隔离/契约测试 | 现有测试入口运行，数值测试直接调用真实算子 |

该表是有边界的初始计划，不代表全部文件均已修改。实现时核对每一增量diff；需要额外
共享层或新kernel时先补充已复现缺口、调用契约、归属、文件和回归矩阵，再编辑。
FlagGems 本次已完成官方 master 的快进同步，不计划定制修改；FlagGems-vllm 先验证现有实现。
vLLM、其他平台/模型代码和其他任务配置不在修改范围。

## 接入设计与风险

模型语义保持在模型 adapter，算子通过现有 CachedOp/registry。当前主线已有
`prewarm_cached_ops`，优先适配模型调用而不整体替换参考分支的dispatch控制面。
KPool/Indexer 必须明确压缩页宽、scale存储、Hadamard、tail ring和slot地址。
当前库已有FP8缓存的可移植存储/解码路径；选择前必须验证MetaX实际数值和graph行为，
不得以符号存在推断可用。mHC需恰好一次RMSNorm；KDA须覆盖prefill/decode/混合和状态更新。

历史 ContextVar/RLock、small-head、KPool尾部问题仅是候选风险。只有完整错误签名匹配后
才复用相应处理；不默认退图、不增加执行超时掩盖错误。

## 验证与当前结论

原生环境基线在工作根 `01-environment/mx-101/`、`mx-102/`。
当前正在运行库自带8项GLM数值基线；尚无新产品代码修改、模型加载或服务通过结论。
后续先注册/配置、算子、组件，再双机整模；正式精度为用户指定GPQA198题≥88%。
最终逐块审查新增模型来源、必要性、共享调用方、守卫未命中和全部组件diff；
未验证项及失败结果保持原样，不以历史PPU结果补齐MetaX验收。

## 2026-10-27 接入前补充边界

现有 vLLM `FlashMLASparseBackend` 仅声明576维和SM9/10，而实际模型压缩Q/K为512维、
TP8下每rank8个头；FlagGems/FGV现有sparse MLA kernel支持512维，但要求64/128头。
拟先直接验证 FlagGems `constant_pad_nd` 将头补至64、调用既有FGV sparse MLA并裁掉
填充头，CPU参考及变输入graph通过后才接入；不改通用kernel，也不伪造设备capability。

| 组件/文件 | 必要增量 | 守卫/验证 |
|---|---|---|
| Plugin `dispatch/backends/vendor/metax/impl/attention/mla/glm5next.py`（新） | 复用vLLM BF16 sparse metadata/control，512维及实际C550能力声明；cache写入、query拼接、补头和attention通过CachedOp | 仅GLM结构且MetaX被选择；BF16/无sink/512维；head4/8/64直接数值和graph，其他模型仍原selector |
| Plugin `models/glm5next.py:Glm5NextMLAAttention` | 在该模型构造前使用正式attention selector参数/既有backend注册接口选专用backend；新增路径仅该架构 | 默认attention selector未改；正式模型构造确认backend命中 |
| Plugin `patches/glm5next.py` | 移植的config/runtime hook改为当前接口，worker只安装该GLM cache协议；注册幂等 | fresh/spawn/repeat，非GLM配置无变化 |
| Plugin `dispatch/backends/flaggems/impl/glm5next.py`（原计划内） | 当前FGV公共函数薄适配：KDA/conv/mHC，FP8 KPool/query/cache，复用已有量化和Hadamard | CPU与既有FGV算子对照、alias/scale/layout、没有复制kernel或Torch计算回退 |
| Plugin processor新文件 | 修正来源代码video-only token计数的未赋值merge_size，且默认kwargs复制后再更新 | 只视频、图像、不同merge_size的计数，文本加载不加载GPU |

FP8 indexer cache每slot实际132字节（128值+4字节scale），与原参考BF16 cache不同。
移植时使用132的spec、真实scale gather，query先Hadamard再逐头FP8量化，scale恰好折入
weights一次；不沿用BF16 identity-scale假设。KDA变长prefill使用实际metadata的
chunk_indices/chunk_offsets，不能在FGV中临时同步GPU生成。新增主模型四文件来自同一
公开revision，先静态导入/配置验证，再组件/整模；未完成接入前不宣称服务可用。

### MetaX 正式选择接口补充

实际 `MLAAttention` 的 `attn_backend` 参数在DeepSeek包装器内没有暴露给子类；
PlatformFL统一通过CachedOp调用vendor selector，当前MetaX策略明确指定vendor。
因此额外仅修改 `vendor/metax/metax.py:MacaBackend.attention_backend` 的MLA+sparse分支：
在当前config为glm5_next/glm5_next_text时返回新backend，其余保持原有返回值。
测试目标/非目标/无config三种场景，禁止全局替换原生FLASHMLA_SPARSE注册。

构造器无论是否sparse都会实例化dense prefill backend；当前主线FlagGems adapter只对
CUDA available，MetaX不满足，原生FA扩展也不存在。新vendor文件内复用既有
FlagGemsMLAPrefillBackend子类，能力守卫限MetaX、FP16/BF16、QK/V≤256，operator仍通过
CachedOp；在本模型config校验中用正式CUSTOM prefill registry选择，仅未显式选择时生效。
这只是该模型的实际backend集成，不改变当前主线公共prefill selector或其他模型配置。

配置集成负对照 `glm-config-integration-20261027/mx-102` 已实际加载conditional架构、
processor和50K配置；随后CUSTOM prefill slot冲突而明确失败。当前主线已占用该slot，
不能覆盖。撤回本任务新增CUSTOM注册，改为与现有HY4一致的model边界selector包装，
但包装必须检查当前GLM结构+MetaX+未显式指定prefill，其他配置调用原selector；
对三个按值导入别名幂等安装，不改vLLM源码/全局CUSTOM归属。增加非目标/显式选择回归。

### 双机PP的mHC边界协议

逐块检查来源模型时发现其PP只传 `x/residual`，丢弃尚未融合的post/comb；下一stage又从
post=None进入pre，无法还原完整4路残差。这是TP8/PP2必须修正的模型协议缺口，限定在
新 `Glm5NextModel.__init__/forward`：stage边界先用已注册 `mhc_post` 完成融合，传一个
flatten为4D宽的残差张量，下一stage恢复 `[T,4,D]`；IntermediateTensors工厂同步4D。
非mHC保留原两tensor协议；无vLLM/worker/通信算法更改。新增模型维护测试模拟相同层
完整执行与多stage执行，数值及graph比较；真正双机16卡推理仍为后续必须项。

当前FGV只导出已融合的 `expand_pools_and_append_tail(pool_ids,seq_lens,pool_size)`，其
源码明确为GLM原两个identity映射操作的等价合并。模型适配改为一次CachedOp调用该既有
算子，去掉旧分支的两个不存在provider；不复制算子或用Torch重写。prefill使用真实positions
+1，decode padding时与Q相同协议pack实际token序长，避免padded行长度错配；真实KPool
执行要求positions，profiling/fake路径仍可无positions。补充精确索引和变输入graph回归。

### packed KDA模型编排

独立序列对照 `glm-kda-packed-baseline-v3-20261027/mx-102` 中prefill、decode各自通过，
混合(1,1,4)失败：来源编排把decode和prefill一起传chunk，但当前metadata的chunk_indices/
chunk_offsets只覆盖prefill。修复限定新模型 `_forward_reference_safe_gate` 的KDA分派段：
decode按真实decode token/slot切片走recurrent，prefill使用现成prefill_* metadata和64-token
chunk元数据，分别更新同一状态cache；不改GDN builder或FGV数学核。增加多序列/跨64chunk
对照及decode变输入graph；spec metadata在未实现前显式拒绝，不静默用非spec路径。

新测试早期SD/DS conv fixture及NHWC CPU→CUDA传输导致的state ABI失败已保留：诊断测得
新fixture `[5,2,128,128]` stride为 `(32768,1,256,2)`，与vLLM实际as_strided dense-HVK
不同，测试现强制正确物理布局。它与问题005早期已经contiguous的冷路径差异不是同一结论。

## 102 接入验证进展

- `glm-registration-regression-v2-20261027/mx-102`：14项配置、processor计数、幂等、非目标模型、
  不同vendor及显式prefill选择回归通过。原测试对LazyConfigDict读取副作用的假设错误已修正，失败证据保留。
- `glm-config-integration-v5-20261027/mx-102`：真实权重目录配置、conditional架构、tokenizer/
  processor文本加载，50K上下文、TP8/PP2、前缀缓存开启及全部新provider解析通过；确认
  专用sparse和prefill backend命中。此前CUSTOM冲突及旧符号失败均保留，没有vLLM修改。
- `glm-pipeline-mhc-baseline-20261027/mx-102`：PP第二stage实际mHC shape断言失败；
  `glm-pipeline-mhc-fixed-20261027/mx-102`：三种切分、与完整执行相同的mHC math、两次
  变输入graph全部通过（3项）。这不替代真实双机权重加载/推理。
- `glm-cache-adapters-20261027/mx-102`：池ID展开/因果tail精确索引，以及零RoPE BF16主KV
  写入、head8补头sparse MLA的CPU数学对照、变Q/K两次graph，2项通过。
- `glm-kda-packed-fixed-20261027/mx-102`：独立prefill/decode、混合batch、65token跨chunk
  与逐序列执行的输出/conv及recurrent cache对照4项通过；decode model graph另独立验证。

以上是组件和编排验证，正式服务/GPQA198≥88%/性能尚未执行，不能标记adaptation完成。

### 第一次真实双机加载：PP工厂缺口

`glm-eager-bringup-20261027` 两节点已完成模型构造和权重读取；101主进程120/120分片
完成，文本参数audit无missing，但other-PP层名字被原参考audit记作unexpected（待按实际
PP归属审查，不将此警告当作缺权重）。首次profiling在102的
`ModelRunnerFL._dummy_run → model.make_empty_intermediate_tensors → sync_and_gather`
断言失败：返回None。检查新CausalLM继承SupportsPP的空协议方法，却未将内部model已有的
工厂暴露给包装器。限定在新 `Glm5NextForCausalLM` 初始化的工厂委托；核对真实引用的
`glm4_1v` conditional基类后，只补确实缺失层。新增真正调用公共PP工厂的测试，验证返回
IntermediateTensors及4×hidden宽度，再重试相同双机eager配置。不改公共runner来绕过断言。
原运行与失败均保留，仅停止本任务已核实服务进程，容器不停止。

真实引用的 `glm4_1v` 基类原本在构造中设置工厂委托，但新conditional构造绕过了它，
且新CausalLM也遗漏该委托。两层各增加一个实例工厂委托后，
`glm-public-pp-factory-fixed-20261027/mx-102` 两项公共接口回归通过；
原负对照两项均返回None。修复未改公共runner、SupportsPP或vLLM。

### 真实prefill的padded tail布局（2026-10-28）

第三轮 `glm-eager-bringup-v3-20261027` 使用65536/seq8、align和glm45，健康检查200；
缓存约948547 tokens、14.47x。首次真实请求已越过修复后的embedding clone并进入KPool，
但 `persist_prefill_tail → FGV kpool_seed_tail_cache` 报
`Tail seed cache requires packed inner dimensions and non-overlapping blocks`。
当前模型 `_logical_tail_cache_view` 只narrow padded第三维，不能保证score/K两区的内部stride
仍为 `(pool×D,D,1)`。原有小测试使用紧凑分配，没有覆盖真实padding/reshape链，不能支持
现场布局正确的结论。

下一步先用实际 `KpoolTailSpec/KpoolTailBackend`、只读vLLM reshape helper及模型runner
适配器构造带padding的最小复现，记录shape、stride、page bytes和shared storage。修复限定
新模型 `models/glm5next.py:_logical_tail_cache_view` 或模型专属
`patches/glm5next.py:_reshape_kv_cache_tensors` 中确证错误的布局构造；沿同一物理页做
metadata view，不能用contiguous拷贝掩盖in-place缓存地址问题，不改vLLM或放宽FGV检查。
新增维护测试在 `tests/unit_tests/dispatch/test_glm5next_ops.py`，覆盖真实padded页、原紧凑页、
prefill seed→decode压缩、跨请求slot和至少两次变输入graph，检查原storage实际更新及未触碰
padding。先负对照后修复，再两机回归和相同基础配置整模重试。

进一步负对照修正了初始假设：`glm-tail-layout-diagnosis-20261028/mx-102` 中，实际reshape
对紧凑/padded页、FlagGems开关两侧均满足packed stride，单独的padding不是根因。
`glm-tail-core-bootstrap-v2-20261028/mx-102` 在新进程只导入模型spec、不构造模型时，
EngineCore仍走原生分组，将tail block4扩成768，shape为 `[8,2,768,128]`，narrow后的
channel stride98304，复现完全相同错误；手动调用已有 `install_glm5next_kpool` 后，
tail保持4槽、page12672 bytes、stride `(6336,512,128,1)`，真实seed通过。首版fixture
遗漏实际indexer的block-stride能力标记而提前失败，已保留，不作根因证据。

因此不修改narrow view、公共runner或FGV检查。必要增量限定为新模型模块加载完成后安装
已有幂等cache hooks：EngineCore反序列化custom spec会导入该模块，但不执行模型构造或
API侧config.verify；bootstrap必须覆盖这个生命周期。新增fresh subprocess/pickle测试调用
真实分组，校验4槽与页大小；不分配GPU、不修改非GLM组。另用真实分组得到的padded spec
测试seed的共享storage、跨请求slot、padding完整性和变输入graph。此前表中的候选布局修改
因被负对照排除而不实施。末端decode数学继续由现有KPool回归及真实整模请求共同覆盖。

bootstrap首轮32项组合中25项通过，fresh分组/4槽/非GLM组断言已通过，但测试新增的
“CUDA完全未初始化”假设失败。`glm-tail-import-initialization-20261028/mx-102` 分阶段实测
确认在导入原生core utils时，既有FlagGems DeviceDetector已调用get_device_properties并初始化
runtime；发生在GLM spec/bootstrap导入之前。测试改为记录这个真实前态，要求新增bootstrap
不改变初始化状态且不增加tensor显存分配，不据此修改无关设备发现逻辑或宣称CPU-only导入。
独立 `glm-tail-padding-storage-20261028/mx-102` 已通过真实分组/padded页alias、跨请求seed、
全页padding完整性与两次变输入graph；完整组合仍需重跑并核验101。

`glm-tail-bootstrap-fixed-v2-20261028/<host>` 两机各32项完整组合回归通过，包含fresh pickle
分组及不新增初始化/显存、非GLM组、真实padded storage与graph、原有KDA/PP/配置/Qwen。
产品增量仅为模型模块末尾安装已有幂等cache hook；没有改tail布局、FGV断言或公共runner。
13文件第三版归档SHA `3c3c6e622e3afed299e9595767fd35843c225955fab1195e8bab2783c9257a72`。
101逐项验证旧manifest后只同步模型和cache测试两文件，未覆盖其他改动。

之后两机仅对16个本任务新建Python文件执行Black及逐文件AST等价核对；实际格式变化只有
Plugin新cache测试和FlagGems新clone测试，产品代码AST均未变化，已有上游文件未格式化。
前后哈希记录为 `01-environment/source-format-<host>-20261028.json`，13文件最终格式版
为 `01-environment/glm-model-integration-source-manifest-v4.json`。第四轮整模
`glm-eager-bringup-v4-20261028` 重用65536/seq8/align/glm45基础配置；真实请求与图模式仍待通过。

第四轮真实启动在scheduler构造时失败：`HybridKVCacheCoordinator.__init__` 的
`block_size must be divisible by hash_block_size`。只读调用链确认EngineCore完成聚合后将
`cache_config.block_size` 设为所有组的最小值4，而KDA的物理块仍384；原生resolver因此触发
Mamba不对齐回退并返回hash384，tail4无法整除。配置hash覆盖也处于该提前返回之后，不能
解决问题。进一步确认当前vLLM不读取新spec的`participates_in_prefix_caching`；即使仅修复
hash，tail manager的空hit也会把所有prefix命中压成0。

本次必要增量限定Plugin新模型shim `patches/glm5next.py:install_glm5next_kpool`：仅对含
KpoolTailSpec的组，以物理组LCM计算scheduler粒度、以GCD/显式有效override计算hash粒度，
保留原有context-parallel限制；同时让原生Hybrid coordinator的prefix匹配组排除storage-only
KPool tail，分配与manager列表仍保留tail。通过现有符号兼容hook同时覆盖EngineCore已绑定
的resolver引用，保持幂等和非GLM原调用。禁止改vLLM、关闭prefix或将所有KV物理块缩为4。
测试增加在原有新建cache测试内，先验证旧实现的负对照，再覆盖真实分组→scheduler聚合→
resolver→KVCacheManager构造、prefix开关、tail固定页、有效/无效hash override、非GLM路径、
真实缓存写入后的重复prefix命中及不同prefix miss。两机通过后才重新加载整模。

`glm-cache-coordinator-baseline-20261028/mx-102` 旧实现负对照8失败1通过，精确复现
resolver返回384/384、重复prefix命中0及显式hash override被提前返回忽略。限定修复后，
新增原生coordinator/BlockPool用例通过；首轮驱动漏设实际worker的FGV启用环境变量，导致
3个原有设备dispatch测试无可用实现，10项缓存/初始化测试通过，失败原样保留。使用实际
`current_platform.import_kernels()` 和 `VLLM_FL_USE_FLAGGEMS_VLLM=1` 后，
`glm-cache-coordinator-worker-20261028/<host>` 两机均43项通过，包含原有配置16、KDA4、PP3、
适配器15及Qwen5。额外覆盖fresh EngineCore导入别名、重复安装、两个context parallel拒绝分支。
产品新增61行均在新GLM shim内，未修改vLLM及FG/FGV，也未关闭prefix。

13文件第五版归档SHA `d0c9de833296c4557bd6e2d3e43196d1a6db1fe144fab85a992aefd90c98be5e`；
shim SHA `9cf598d9af3dae9610fe3e3344bca85cc0648b260efceaf860c95b4b5aeedf34`，
cache测试SHA `24f8fea10c139efdf27a330a173fe5ece0c1c2f653a1a483b449e0c4edc2e3ce`。
两机 `source-snapshot-v5-<host>.json` 核验全部25份任务源码及只读vLLM原差异。
快照生成器两次仍引用旧manifest/格式记录而拒绝写入，纠正绑定优先级后通过，没有改写旧快照。
第五轮 `glm-eager-bringup-v5-20261028` 已启动，相同65536/seq8/align/glm45配置，
真实整模与正式验收结果仍待核实。

第五轮通过scheduler并启动API，但实际请求先在sparse MLA的默认TLE选择失败（008新增
触发域），随后decode的 `paged_mqa.py:200` 拒绝页表容量。调用链确认模型已将KV cache、
metadata.seq_lens及页表转换为pool单位，却仍在 `sparse_attn_indexer_kpool` 给库传原始
`max_model_len=65536`。库的页表范围检查合理，不能放宽。修复限定同一模型函数对该实参
按 `cdiv(max_model_len,index_kpool)` 转换；index_kpool=1保持原值，spec支持范围不扩大。
在新建 `test_glm5next_ops.py` 增加完整decode adapter集成：实际FP8 quant/cache、原生
metadata形状、真实paged-MQA/topk/池展开；覆盖pool4、非压缩1、不整除context上限、不同
query/跨页context以及至少两次变输入graph，对照CPU oracle的选池与尾token。库只读此
问题，不改其校验/计算。先负对照后实施，一机验证再同步另一机；其余源码保持v5。

decode集成首版fixture错误地给raw cache多加一维，提前触发rank校验，已保留为无效根因证据；
按模型真实三维raw cache纠正后，pool4复现同一长度错误，pool1进一步暴露薄provider直接
别名无法适配当前FGV八参数 `top_k_per_row_decode`，报next_n重复。静态核对当前公开入口
确认prefill同样要求显式num_rows/strides/top_k。同步扩展必要清单：Plugin新
`flaggems/impl/glm5next.py` 仅新增两个topk参数适配函数，按logits/目标indices真实shape/stride
补齐八参数，不复制数学、不改FGV公共接口；把两名由_DIRECT移动至_ADAPTERS（避免重复
注册），环境预检仍显式核对两个库算子存在。新增真实prefill topk CPU对照和变输入graph，
decode原集成用例覆盖其另一适配器。以完整模型默认dispatch执行，不mock数学或放宽断言。

102上修正后decode pool1已通过eager及两次变输入graph；pool4首次CPU oracle仅因arange
默认int64与目标int32不同而失败，修正oracle dtype后数值及graph通过。完整组合40项通过后，
额外prefill stride1=2测试失败。独立 `glm-prefill-topk-units-20261028/mx-102` 确认连续列
输出正确相对索引，stride2且row_start>0则现有FGV kernel把row_start当元素偏移而非列索引。
实际模型MQA logits为列连续（stride1=1），此既有库问题不是当前模型触发条件，因此不扩大
到无关topk kernel重写。新prefill adapter限定经验证的单位列stride，其他输入在算子写入前
明确ValueError；测试保留该负分支，同时用行padding、列stride1的真实支持布局验证数值与graph。
本任务没有删除库接口或既有测试，未声称stride2库缺陷已修复。进一步补齐真实top-k512规模
（模型选择2048 token对应512 pool）及非整除max_model_len、跨页metadata回归，防止小k替代
真实服务触发域。

`glm-indexer-production-shapes-20261028/mx-102` 最终49项完整组合通过：配置16、KDA4、PP3、
indexer/cache adapter21及Qwen5；真实512-pool选择、跨页、非整除上限、非压缩路径、
prefill相对索引及行padding均覆盖实际算子、CPU oracle和两次变输入graph。未支持列stride2
在metadata预检直接拒绝，不修改公共库/模型正常列连续路径。实质产品增量仅为pool长度
换算、两个topk参数适配及受证据限制的stride守卫，没有Torch数学回退。完整源集检查确认
只有本轮5个已有任务文件变化，FG/只读vLLM及其他20个任务文件保持前态（完整总数仍25）。
13文件v6模型归档SHA `1824eb2cb56919b8a7f29ddec0e01bb8b0753ea6845530e4a7661bd0b8a390ae`。
101已按v5完整快照核验后仅同步这5文件，正在重复49项模型组合与28项sparse矩阵。

101组合驱动的第一组49项已通过（最终flush的原生pytest摘要73.98s）；随后在尚持有GPU
上下文的父进程中启动FGV pytest子进程，子进程停在futex且无编译进度数分钟。按精确
PID/PPid/start_ticks/cmdline哈希发送SIGTERM后，两父子均退出，驱动rc241，失败保留；
不能把该驱动视作两组整体通过。现拆为独立进程运行，避免嵌套GPU测试生命周期干扰。

101拆为独立进程后，`sparse-mla-tle-isolated-20261028/mx-101` 28项通过（18.74s），
`glm-indexer-production-isolated-20261028/mx-101` 49项通过（37.05s），均有rc0终态。
102对应49项（51.33s）和28项（18.57s）已通过。两机 `source-snapshot-v6-<host>.json`
核验全部25个任务文件和vLLM原diff，第六轮整模 `glm-eager-bringup-v6-20261028` 启动中。

第六轮真实整模首次完成短答案：`2+2→4`（含冷编译181.65s）、`France capital→Paris`
（10.81s）。随后>2048 token混合长prefill在 `cp_gather_indexer_k_quant_cache:128` 报
`head_dim must be divisible by quant_block_size`。单rank首异常显示库按scale第二维的
**byte数**计算量化块（`128*4/size(1)`）；模型workspace按当前数学契约分配FP32 `[N,1]`，
直接别名被当成1 byte，得到错误quant_block_size512。库最终本就view回FP32，错误属于薄
provider的存储适配，而非head_dim/库校验。服务与probe按登记PID停止；短请求证据保留，
长请求/整轮未通过，不复用其为完整eager验收。

下一步只改Plugin新 `flaggems/impl/glm5next.py`：将gather从_DIRECT移至_ADAPTERS，
提供同storage的 `scales.view(torch.uint8)`，使FP32[N,1]按4 byte宽度传入库，保留库读取
真实FP32scale；预检仍核对实际公共算子。只做metadata view，不拷贝/转换/伪造scale，不改
FGV、FG或vLLM。新增原 `test_glm5next_ops.py`：FP32及原byte buffer守卫两侧真实gather
原storage更新与跨页两请求CPU对照、两次变输入graph；并增加**完整长prefill indexer**
（native workspace + metadata → gather → FP8 MQA → prefill topk512 → pool/tail展开）
的eager CPU对照与变输入执行，覆盖不同request累计offset与未完成pool边界。图回放覆盖
实际可capture的组成算子；完整prefill函数当前含host分支，不用mock或伪造CPU读数宣称其
整体capture通过，完整模型graph仍单独按优先级验证。先负对照、102验证，再同步101。

`glm-gather-scale-baseline-20261028/mx-102` 原byte-buffer数值/两次变输入graph通过，实际
FP32[N,1]精确复现quant_block_size512错误。薄provider新增8行metadata view及注册/预检
调整后 `glm-long-prefill-fixed-20261028/mx-102` 52项完整组合通过。再将长prefill调用链
扩展至每请求128 query、两请求共256 query，`glm-long-prefill-batch-fixed-20261028/<host>`
两机各53项通过、rc0（102 39.78s、101 40.38s），含FP8 MQA、topk512、真实workspace锁定、
不同request累计offset、尾pool和CPU oracle。全prefill变query做eager对照，组成算子保持
capture/两次变输入graph，未用CPU读数替换GPU路径来声称全prefill capture。

全部25个任务文件两机v7快照一致；只有provider与原有新测试两文件更新，FG/FGV/vLLM均
保持v6身份。13文件v7归档SHA `b26c0345200e471ce5bc90d0ef283ca6987db645c693d661076664ad4756e9b3`。
第七轮 `glm-eager-bringup-v7-20261028` 与六请求probe已登记启动，同65536/seq8/align/glm45
和prefix开启配置，等待真实长混合/prefix/chat完成；graph及正式GPQA/性能仍未验收。

第七轮六个真实请求全部完成：短问4/Paris、混合3532-token长输入yellow及短问Paris、
相同长输入单独重用yellow、chat有效reasoning与正文4。原生metrics记录prefix命中2304
token；这是功能证据，未当作正式验收。混合长请求与缓存重用chosen-token logprob最大差
0.093409。随后 `glm-prefix-single-20261028/mx-101` 两组独立salt顺序冷/热各四请求，
答案均yellow，但冷/冷差0.070313、热/热差0.127043，数值重复性尚未成立。驱动rc0只表示
完成测量，result.status=measured。执行模式预定0.05阈值保持不变。

原生indexer builder只读核查确认MLAAttentionSpec.compress_ratio=4已用于prefill总长度、
causal边界和decode context，没有证据支持“漏除4”的假设，不为此新增补丁。
`glm-prefix-idle-20261028/mx-101` 每次请求前两次间隔11秒idle metrics屏障后，四个答案均
yellow；冷/冷最大差0.010586、热/热0.011097，冷/热仍为0.077147和0.076636。异步重叠
不能单独解释前缀复用差异。继续用实际KDA前向检查不同旧state（零/有限值/NaN）在新请求
初始化后的独立性；不修改产品源、只读vLLM或验收阈值。

`glm-kda-fresh-state-20261028/mx-102` 诊断rc0：实际8-head、D128的模型KDA前向，
130/2048/3532 token，旧conv/recurrent state分别为0、0.5、NaN且初始标记False，
与零状态且标记True、重复零状态均逐元素相等，输出及最终两类state有限、最大差0。
此证据排除所测条件下的新请求旧状态污染，不证明prefix复制正确。随后按登记PID、
PPid、start_ticks、命令哈希记录停止v7任务推理进程，容器保持运行；准备原生LLM同配置
一次性RPC追踪冷/热分块及复制前后状态，不修改安装源码，不作为正式性能测量。
两节点退出码0；102原生关闭曾等待8 worker后自行SIGKILL并报告semaphore清理告警，
保留原始日志，不将退出码视为正常请求或资源清理无告警的证明。

首轮 `glm-eager-state-trace-20261028` 完成加载后，native MsgpackEncoder拒绝函数RPC：
`Object of type function is not serializable`，尚未安装追踪或发送模型请求。调用者退出码1，
其finally调用原生shutdown；随后精确停止102遗留headless进程并验证登记后代均不再活跃。
这属于诊断配置遗漏，不据此修改数值代码。v2诊断仅对无HTTP API的原生LLM/同任务headless
进程启用native `VLLM_ALLOW_INSECURE_SERIALIZATION=1`，先实际Msgpack函数编码/解码往返
通过才加载权重；不进入正式启动脚本、精度/性能配置或交付。失败日志另有原生MCCL退出时
缺少ncclCommAbort告警，保持只读组件边界，不扩大为SDK修改。

新增待证假设与改前边界：原生EngineCore初始化cache时把cache_config.block_size写为所有
group最小值4；GLM现有resolve wrapper虽然返回scheduler LCM384/hash GCD4，却未修正该
配置字段。原生Scheduler._mamba_block_aligned_split读取cache_config.block_size而非其
constructor收到的scheduler block_size，可能按4而非真实KDA384对齐，从而复用错位状态。
先保留v2整模冷/热分块与初始状态追踪；再调用真实原生Scheduler方法做受控负对照。

若证实，仅修改Plugin既有 `patches/glm5next.py::resolve_block_sizes`，在GLM KPool group
且现有合法hash/非CP守卫通过后，将cache_config.block_size同步为已计算的LCM，保持返回
hash GCD/override及所有group Spec、page、索引、原生调度算法不变。现有
`tests/unit_tests/dispatch/test_glm5next_ops.py` 追加真实native align分块契约：冷prefill
3532/step2048应为1920+1536+76，所有可缓存端点整除384；前缀恢复、decode、显式hash、
非法hash无配置副作用、非GLM/CP守卫均覆盖。不改FG/FGV/vLLM，不新增全局调度补丁或
关闭prefix，不放宽0.05。先102负对照与完整组合，再精确同步101及同配置整模复验。

`glm-align-baseline-20261028/mx-102` 真实原生Scheduler负对照失败(rc1)：resolver返回
384/4但cfg.block_size仍4，3532-token输入实际得到2048+1484，未出现384对齐检查点。
限定修复后 `glm-align-fixed-v8-20261028/mx-102` 完整55项通过(38.62s)，含prefix开关两侧
真实Scheduler冷分块1920+1536+76、3456恢复、common prefix和decode；合法hash同步与
非法hash无副作用断言通过，原非GLM/CP守卫及其余53项保持。增量仅resolver5增/1删及
原新测试53行，无公共调度器、group Spec或数学kernel变化，全部增量hunk已审。
当前shim SHA `9bf63067b3cfc8d752a778d21fe53534453d921e84a27be4759427bf14eadde2`，
test SHA `476ae762c62afe9f3a6054e7813465ce362e3a1ab81b8e515265299d0557cc2c`。

v2整模追踪虽已通过16-rank RPC，却因诊断包装参数未保留原生KDA关键字名称而失败，
没有可用冷/热状态结论。已修正一次性包装并增加实际关键字ABI绑定预检；不混入产品修复。
该次异常后101的MCCL等待无法自动结束，登记caller/EngineCore先SIGTERM、等待超过60秒，
再对同一登记8 worker先SIGTERM并等待15秒，仅强制退出仍存活worker；确认GPU worker
退出后对仍等待的同一EngineCore强制结束，全部按start_ticks和命令hash核验、记录原始原因。
102原生executor自行终止其任务workers。容器未停止；不将此故障恢复当作正常关闭无告警。

v8两机55项及原生环境gate通过。第八轮六请求均完成，短问4/Paris、混合长输入yellow、
cache重用yellow、chat正文**4**。真实prefix命中3456，混合长请求/重用最大logprob差
0.008382；修复确实改变检查点边界，但该单组结果不能证明全部重复性。
`glm-prefix-idle-v8-20261028/mx-101` 四请求答案均yellow，冷/热差0.043855和0.040999、
冷/冷0.014162、热/热0.070691；预先固定0.05整体检查失败(rc1)。下游chat参考驱动按守卫
停止、尚未发送其三个请求。保留失败并继续诊断，不调整阈值，不开始graph/正式精度。

下一轮一次性原生LLM诊断核对全部16 rank的实际冷分块和hot初始conv/recurrent state，
对照冷请求真实保存的对应位置检查点，并记录KDA输入/输出摘要；在真实prefill top-k输入上
额外执行一次同算子到独立scratch，检查选择集合/顺序及差异处score，不改变模型使用的首份
结果。诊断含同步/额外计算，结果不作为性能证据，观测可能影响竞争行为。暂不修改新的
产品代码；若发现新根因，先限定所属组件/符号及独立负对照和回归再实施。
