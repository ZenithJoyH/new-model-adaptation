# 源码设计审查

## 收尾变更边界（2026-10-28）

G1检查发现Plugin支持表尚无本模型及可运行示例。下一次仅在实际安装的
`README.md`增加一行真实状态与一节双机使用说明，并新增
`examples/glm5_3_flash_chat.py`，向已启动的服务发送确定性算术请求、检查最终答案。
示例使用命令行endpoint/model参数，不写私有地址、密钥或个人权重路径；说明列出已验证
依赖基线及本任务补丁要求，不声称未发布补丁已在上游发布。验证范围是语法、CLI help、
README链接及当前graph服务真实响应。此增量不修改运行时代码、依赖安装或最终启动脚本。
完成后需重新冻结包含这两个文件的源集合；原33个运行/测试文件的同源证据保持可核对。

首个真实示例请求回答`2 + 2 = 4`，数学正确，但新示例对不同提示词错误地要求冻结参考的
`**4**`格式而失败（232.10s，含首次通信/JIT）。只将新示例的提示词和生成参数对齐既有
eager参考（briefly、max_tokens512、top_p1、seed0），保留精确答案断言；不改产品或原测试。
v13-final身份/原始失败保持不变，后续需新快照与身份，不能覆盖失败或仅更新旧回执哈希。

用户于2026-10-28明确批准本次D3例外：以公开基线SHA、完整冻结补丁及文件哈希、验证后的
镜像锁定交付，公开发布留待后续。未授权提交或推送。最终规范判断仅在该例外范围内有效，
不能表述为三个适配补丁已有公开提交。

审查对象是两机容器实际安装目录，不是远端工作根中的第二份源码。
以下v1～v13记录保留历史判断；以末尾最终v14范围、证据与逐组件结论为准。
阶段状态须在对应原生回执通过后更新，本文本身不是运行成功证明。

本记录原名source-review.md，现按本地编号布局更名为010-source-review.md；历史已冻结环境
记录中的原名指向同一审查记录，不改写历史环境证据。

## 基线与来源

| 组件 | 实际安装HEAD/分支 | 任务前状态 | 当前范围 |
|---|---|---|---|
| Plugin | `4e23ae8f24b380ee845f6ab3f5c8c136151d4959` / main | 按用户要求回到主线后干净 | 4个已有文件、11个新文件 |
| FlagGems | `3eab0949b9beea777e910ff8666b9ef53081d35c` / master | 官方主线快进同步后干净 | clone注册一块、1个新测试 |
| FlagGems-vllm | `ddce1d66c98cfdbdcfff36364f3d10e3af9d499c` / main | 干净 | 4个算子文件、4个新测试 |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389` / detached | 继承87个mode-only差异 | 只读，未新增内容差异 |

上述分支是实际安装分支，用户未请求PR，目标PR分支尚未另外确认。比较基线是这些明确的
上游HEAD，不把本地分支名视作维护者已接受的PR目标。没有暂存、提交或推送本任务代码。

Plugin四个主模型文件的来源为公开 `support-glm5.3-flash@115ecb8f`，保留Apache-2.0声明。
仅引入GLM结构、配置、cache和processor；没有复制其122文件整分支、公共worker或图编译层。
现有vLLM不含该模型，且不能表达KPool/tail与bounded KDA组合，故需要模型专属接入。
当前安装改动与来源的差异另按下表审查；新文件的整体新增也计入审查，不能只看git diff。

## 逐文件/块审查

| 文件/符号 | 必要性、兼容性与判断 |
|---|---|
| Plugin `__init__.py:register_model`（4行） | 在原Qwen注册后惰性注册GLM；不移动原注册，不在导入时分配GPU。重复调用由新注册函数守卫。 |
| `flaggems/register_ops.py`（4行） | 沿当前registry/allow加入薄provider；不替换原控制面或优先级。 |
| `vendor/metax/metax.py:attention_backend`（10行） | 仅MLA+sparse且真实text model_type匹配时选512维MetaX backend；无config/其他模型返回原路径。 |
| `vendor/metax/patches/chunk_delta_h.py` | 问题005；6处累积gate指数使用调用方声明的exp/exp2，不再忽略USE_EXP2。False保留原结果，True与CPU隔离对照一致；不改其他厂商kernel。 |
| 新 `configs/glm5_next.py` | 保留conditional/text/vision真实嵌套字段及vLLM消费的别名；校验层类型，不把权重改为纯文本模型。 |
| 新 `models/glm5next.py`：Indexer | FP8值与scale的132-byte协议、同基底Hadamard、一次Q scale、真实prefill scale gather；移除错误BF16 identity scale假设。旧两个不存在provider由当前库等价融合池展开/tail算子替代，未删库接口。 |
| 同文件：KDA | 有界gate走既有dispatch；修复混合decode/prefill的metadata归属；spec未实现时在cache修改前明确拒绝。保留原状态dtype/布局，未据新fixture错误改生产ABI。 |
| 同文件：mHC/PP | 恰好一次norm；PP出站完成post mix并传4路残差，入站恢复；两层包装器委托公共工厂，非mHC保持原两tensor协议。SwiGLU按当前CachedOp对象接口传入swiglu_limit，非默认alpha/beta明确拒绝。 |
| 同文件末尾：EngineCore bootstrap | 反序列化custom spec后立即安装已有幂等cache hooks；真实negative证明未安装时tail块被原生分组从4扩为768，stride协议失效。没有修改tail view或FGV检查；fresh pickle与原生core导入/重复安装覆盖。 |
| 同文件：cache/conditional | KPool tail固定每请求一页且不参与prefix命中；conditional保留视觉塔及真实processor。未实现spec/其他vendor实际执行不作支持声明。 |
| 新 `patches/glm5next.py`：注册/prefill | 惰性幂等；撤回冲突CUSTOM slot试验，采用模型+MetaX+无显式选择的边界selector；已有三个按值导入别名各包装一次，非目标调用原函数。 |
| 同文件：KPool/cache hook | 分组、压缩表、页对齐、tail manager/zeroer和reshape均由模型type/spec守卫；使用当前vLLM公开/现有扩展点而不写vLLM。持久形状buffer保持graph地址；完整模型cache读写和prefix复用仍须实测。 |
| 同shim：scheduler hash / prefix组 | 仅含KpoolTailSpec时覆盖原生Mamba不对齐hash回退，LCM384/GCD4保持物理块与请求hash协议；EngineCore按值导入别名同时绑定。原生Hybrid分组后仅从prefix匹配组排除tail，完整manager仍分配固定新页。负对照命中0，修复后真实BlockPool写入命中768，变前缀miss；prefix开关、override、context parallel与非GLM均覆盖。 |
| 新 `flaggems/impl/glm5next.py` | 只做现有公共算子别名/参数适配；topk显式补齐八参数，prefill限定实际unit-column-stride并在写入前拒绝库已知不支持布局，环境预检保留真实topk符号。按MetaX与FGV启用条件可用；无复制数学kernel或Torch计算回退。补头复用FlagGems constant_pad_nd。 |
| 新 `vendor/metax/impl/attention/mla/glm5next.py` | 正式声明C550/512维BF16能力；复用原metadata/control，KV写入/Q拼接/sparse通过CachedOp，8头补64后裁回。未伪造SM90能力。 |
| 新 `processors/glm5next.py` | 来源processor整体必要；保留其资源上限，额外只修正video-only merge_size与默认kwargs被原地污染。计数测试覆盖image/video/both；真实图像/视频服务尚待验证。 |
| 5个Plugin新测试文件 | 两机43项模型/cache组合通过；注册/隔离、processor计数、公共PP工厂、packed KDA、实际mHC分段、KV/sparse adapter、gate底数。mock仅用于选择/构造隔离；数学与图测试调用真实组件。 |
| FGV `causal_conv1d.py` | 问题003；MetaX静态寄存器tap替代SDK无法翻译的indexed shuffle；其他平台仍原gather，状态/空slot/激活协议保留。 |
| FGV `mhc_with_norm.py` | 问题006；BLOCK是语义reduction extent，固定在kernel内，避免AABS重复注入；没有放宽数值或改norm次数。 |
| FGV `fp8_fp4_mqa_logits.py` | 问题007；MetaX等字节view后软件解码E4M3/BF16 dot；原生FP8、FP4和其他平台TLE选择不变。 |
| FGV `flashmla_sparse.py` | 问题008；只改MetaX候选为16×16/stage1满足64KiB共享内存；新增3行仅在MetaX拒绝NVIDIA MMA TLE；其他平台原64×64候选与数学/TLE选择不变。TOPK80/128/2048各触发域均验证。 |
| 4个FGV新测试文件 | 覆盖守卫两侧、实际dtype/stride/边界和CPU oracle，graph均含capture与至少两次不同输入回放。旧DeepGEMM依赖测试collection失败保留，不通过删除原测试规避。 |
| FlagGems `__init__.py` clone项（+3/-1） | 问题009；修复pair嵌套并使用设备专属Autograd key。保留GPU clone自定义反向节点与CPU原生Autograd，不改公共registrar或新增计算fallback。 |
| FlagGems新 `test_clone_registration.py` | CPU RNG与梯度负对照先失败；修复后CPU/GPU值、layout、梯度、变输入graph及原有clone回归两机各31项通过。 |

## 当前增量身份与限制

已有文件binary diff SHA：Plugin
`13c38a61a37698362380830b702221021831125286fc176ca2380f41eaaa8588`；FlagGems
`13b702c4d5e85aec3ef33f95218e2cbdf6f9b37eb957b9d9fe65b21d9dfe5e24`；FGV
`16e4ef6d5d3fa2ebde6d9578403e1be477eca04be0e3c565a7b0dfe3de0f65f4`。
vLLM继承diff仍为 `2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`。
以上diff hash不包含新文件；模型13文件v8 manifest、各新增算子测试与clone修复记录共同覆盖。

当前判断：修改均能对应问题001、003、005～009，未发现跨组件重复workaround、吞异常、
删测试或无关重构。Plugin、FGV、FlagGems仍待完整整模与图模式验证后给出最终PR候选结论；
vLLM为无本任务组件变更。其他平台实际设备、RDMA、MTP与完整视觉/视频仍未验证，不将
MetaX文本局部测试扩展为这些场景通过。

第五版模型集成归档SHA `d0c9de833296c4557bd6e2d3e43196d1a6db1fe144fab85a992aefd90c98be5e`。
新GLM shim本次61行增量和cache测试逐块核对均对应001，没有删除/替换已有公共接口。
整模eager v5、完整graph及实际prefix复用仍在验证；局部43项不能替代这些结果。

第六版新增逐块审查覆盖模型pool长度1处、provider的两参数适配（从_DIRECT移至_ADAPTERS
等价注册以避免重复，预检补回真实符号）、prefill列stride守卫及FGV TLE vendor守卫。
3个Plugin/2个FGV已有任务文件更新，无新增任务文件、无库公共API删除。模型真实512池
规模49项在102通过，101独立28项sparse通过；完整整模及graph验证仍待完成。FGV既有
非单位列stride topk缺陷不在本模型实际契约内，未改该库kernel，不作支持声明。

第七版仅provider和原新测试更新：gather由直接别名移至薄适配器，FP32 workspace使用等字节
uint8 view满足库byte-width ABI并保持同storage写回；真实库符号仍列入环境预检。不存在
数值转换、scale替换或Torch计算回退。两机53项包含原byte/实际FP32、capture/两次变输入、
native workspace锁定的完整长prefill链路及256-query/512-pool CPU对照。增量已逐块审查，
其他组件保持v6。完整v7模型服务/graph及source_review阶段最终结论仍待验收。
模型v7归档SHA `b26c0345200e471ce5bc90d0ef283ca6987db645c693d661076664ad4756e9b3`。

第八版增量逐块审查：仅已有GLM shim的resolver及原新测试变化。真实负对照证实，
返回scheduler LCM384仍不足以使原生Mamba align生效，因其另读cache_config.block_size=4。
在原GLM KPool、非CP、合法hash守卫后同步这一字段，保持tail Spec4/hash4、page与数学
kernel不变；非法hash在字段修改前抛错。没有复制或修改公共Scheduler，未增加调优开关。
新测试实际调用原生align方法，覆盖prefix开关、3532长输入、检查点恢复、common prefix、
decode和EngineCore别名；原hash守卫补配置副作用断言。全部增量hunk对应001，未删除测试。
两机各55项通过（102 38.62s、101 38.96s），其余23个任务文件及三个组件tracked diff不变。
v8归档SHA `f54e78bda153f682e17ab812bf94e8b538c2921c23f6847c076012b179a63acd`。
v7整模六请求功能已完成，但发现的冷/热数值差异须由v8同配置请求重新验证；最终组件
PR候选判断仍待整模/graph和全部变更收尾，不能从55项局部回归直接提升阶段状态。


## 第九版增量审查（当前，替代上述旧版身份）

问题011真实负对照定位同分Top-K选择/输出顺序在相同输入下变化。逐块审查九个文件：
两个FGV generic host入口仅新增keyword-only canonical_output=False、使用既有canonical
分支及对应语义tuner key；两个MetaX wrapper只透传并在True时跳过TLE安装，不改数学kernel、
调优候选或默认分支。两个FGV原测试文件只在末尾追加测试，原字节前缀和断言保留。
Plugin provider默认False仅透传，GLM模型仅两处自身调用显式True；原GLM测试文件末追加两项，
未重命名registry、改变优先级、触及其他模型。guard默认两侧以及CPU oracle/重复/两次变输入
graph均覆盖。全部hunk对应011，无删除、全文件格式化、重复kernel或Torch计算回退。

两机各57项Plugin（原55+2）和38项FGV新增测试通过。FGV旧默认TLE稳定性测试的修改前
失败保留，不作修复或通过声明；72项未选FGV测试及其他平台实机未执行。可选确定路径相对
非确定默认路径更慢；同语义Torch稳定参考微测SpeedUp1.72～2.71，不等于整模服务性能。
新路径整模数值、graph档位及正式验收仍待验证，组件最终PR候选结论仍进行中。

源集合31文件（原25加六个FGV原文件），两机source-snapshot-v9完整绑定。Plugin和FG
tracked diff与前述相同；FGV当前tracked diff SHA为 `b1f2105670f693aa0c9b20e604357003aa590517a189dd45fc5449f726149c99`。
新文件身份还须结合完整快照，不能只看tracked diff。13个GLM接入文件v9归档SHA
`1ef0e9b26ae57b8ca99b3721e74964c345d05b6f5b19045c08a5e5036486fb27`。
vLLM只读身份未变；本轮没有新增FlagGems或vLLM改动。环境绑定见environment-identity-v9.md。


## 第十版增量审查（当前）

问题012仅两个已有任务文件变化。模型hunk替换三个直接CachedOp模块的forward边界，
增加GLM专属torch.ops schema、纯元数据fake和正常CachedOp实现；原模块名、数值实现、
可选norm及n_splits/tile_n协议保留。无输入修改或输出别名，opcheck已检查schema/fake。
没有修改公共dispatch、Triton库调度、FGV数学、Torch或vLLM，也没有全局禁编译。
测试hunk只追加十项；原PP三项前缀及断言原样保留。所有hunk均对应012必要性清单。

两机各67项通过，新增项含真实4096维和128维、1/3动态token、可选norm与Parameter/缓存
分支、严格fullgraph Inductor编译、schema/fake及两次变输入graph replay。相同计算的FGV
源码与v9相同，旧mHC CPU数值回归和38项Top-K证据按完整源SHA复用，未声称重新执行。
总任务源仍31文件，只有模型和原PP测试变，其他29文件/所有HEAD及tracked diff不变。
GLM13文件v10归档SHA 792724554f54e09dbd332da19364b2b7cf0f3e0c570110f64fc0199720c051ee。
完整整模及FULL仍待同源复验，组件最终PR候选判断继续待定。

## 第十一版增量审查（当前）

相邻SwiGLU真实严格编译负对照失败后，只扩大同一模型/PP测试两文件。新增GLM专属
opaque schema/fake，真实函数仍通过原CachedOp，以原生forward_native实际读取的三个
标量字段传递参数。原alpha=1/beta=0错误守卫不变；类内重复CachedOp由opaque实现统一
持有，没有外部GLM专属导入调用者。fake从gate视图empty_like分配，保留singleton/stride
与新输出协议。没有改公共activation、logger、FGV数值、Torch或vLLM，不降graph档位。

四个新增用例使用权重实际TP8本地宽256/1536，覆盖BF16/FP32、空/1/3 token、独立CPU
公式及极值、schema/fake、严格Inductor fullgraph和两次变输入replay；原67项前缀/断言
保留。两机全部71项通过（10258.30s、10153.12s），全部增量hunk已逐块审查并对应012。
其余29任务文件、所有HEAD/tracked diff与v10不变，源集合仍31文件。GLM13文件v11归档SHA
07945a99e9fed64f9e8953ec7c7132dbb410f205351655e5071fc048357bab60。
完整v11模型与FULL仍待复验，最终组件PR候选判断继续待定。

## 第十二版增量审查

v11整模六请求、idle冷/热及四chat参考随后实际通过，见013的复用边界。
问题013只新增一个测试文件、修改MetaX原standalone补丁的两个hunk：按原生模块是否提供
CacheCompiledArtifact选择具体类；返回行保持原构造参数。旧版本缺类时保留原类型，未改变
其他平台入口、缓存算法、TF32设置、FX输出遍历或任何数值代码。新增测试四组合实际调用、
保存、原生加载并验证两次变输入；独立进程恢复在进程退出后另跑，避免GPU上下文争用。
没有删除既有实现/测试、吞异常、修改Torch/vLLM、放宽断言或保留已证伪的缓存模式修改。

完整33文件中原31个SHA与v11完全一致。Plugin当前tracked diff SHA为
6774165427ec0822ec9fe0718eb53f899ba68833ca9a12ca190e88ee5d14b7c5；
FG、FGV及只读vLLM身份保持v11不变。新文件必须结合33文件快照审查，不能仅依赖tracked diff。
两机各四项和独立恢复均已通过，其他Torch版本与其他平台实机未验证。
此增量职责与设计符合013清单，最终组件结论继续等待双机与整模型graph验证。

## 第十三版增量审查

014的FULL及两个隔离负对照确认indexer旋转/量化的Python追踪边界。逐块审查模型两段
新增注册及SparseIndexerOps的两个替换：注册名均为GLM私有，真实实现仍调用原CachedOp，
保留group/dtype/两种scale布局/UE8参数。fake只分配新输出元数据；旋转按原库返回连续布局，
量化按原empty_like和scale的permute布局。原class接口和调用链保留，原两CachedOp实例移至
同模块全局并由既有prewarm机制发现，没有重复数值实现、绕过dispatch、公共禁编译或
修改FGV libentry/logger。其他indexer及KDA调用已处于既有opaque算子内，不扩大包装。

测试只在原PP文件追加十例，原71项字节前缀及断言完整保留。修正新增无效shape断言
的错误层级已在014记录，未改原测试或产品错误行为。两机均81项通过；
覆盖独立CPU Hadamard、FP8 scale与误差界、原FP8字节对照、schema/fake、动态编译和
每例两次变输入图重放。没有全文件格式化、删除数学路径或保留过程诊断hook。

当前33文件中模型和PP测试SHA见014，其余31个精确SHA保持v12。Plugin tracked diff
SHA仍6774165427ec0822ec9fe0718eb53f899ba68833ca9a12ca190e88ee5d14b7c5；两个
模型新增文件尚未tracked，完整33文件快照才覆盖本轮变化。FG/FGV/vLLM无新增修改。
本增量满足已声明职责边界；最终组件PR候选结论仍待双机回归、受影响eager与FULL复验。

## 最终范围与逐组件结论（v14，2026-10-28）

两机`source-snapshot-final-v14-<host>.json`逐项核实35文件：Plugin19、FlagGems2、FGV14；
原33个推理/测试文件保持已验证v13的精确SHA，最后增量仅README和chat示例。Plugin tracked
diff SHA为adb86acb793922e094956211567397c978470c6375ccbc7d50b594cbf94957ea；FG/FGV/vLLM
diff保持前述值。完整补丁、原文件与新增文件清单、numstat和基线见
`03-acceptance/delivery-v14/source-manifest.json`。所有新增文件均纳入快照，未操作Git index。

最后两个文件逐块审查：README仅支持表、适用的双机设置和固定依赖/本地补丁要求；不把
未发布补丁冒充公开版本。示例只使用stdlib和显式endpoint/model参数，调用现有API并校验
已有eager确定性答案，使用英文logging和Apache SPDX。真实v14例运行通过，39.037s；
v13不同提示词的格式断言失败与随后Black检查失败保留。只格式化该新文件且证明AST不变，
没有放宽数学或原有测试断言。进程工件均在批准根，没有进入组件源码。

受影响整模证据是同源v13：eager六请求、四chat参考及冷/热prefix四比较通过（最大差
0.02571076155）；显式FULL_AND_PIECEWISE四请求输出一致，误差最大0.03231409937，
16rank每请求均新增2次replay，capture119～124、累计replay8。FULL在修复真实编译边界后，
仍因原生MLA/indexer只有UNIFORM_BATCH能力而自动切档；保留失败和逐级回退原因，不宣称
纯FULL通过。最终API从根脚本a9ccaa41...启动，默认prefix开启、无诊断反序列化开关。
完整数值/算子/graph独立参考测试及失败边界见003、005～009、011～014；不把哈希本身当作
数学验证，不声称未选的72项FGV旧测试通过。

| 规范 | 适用证据及判断 |
|---|---|
| A1～A4、B1～B3 | 模型/processor/cache元数据在Plugin；数值修复在FG/FGV。provider沿既有dispatch，公开API先在库内补齐及验证，再由GLM显式选择。没有第二源码树或私有文件加载。 |
| B4、C1～C4 | 执行错误向上抛出，不在副作用后换实现；模型/MetaX能力守卫、别名/幂等/原子安装测试保持。MetaX编译类按实际存在能力选择，旧版分支未实测并披露。 |
| D1～D2、D4～D5 | canonical_output默认False保持原路径，仅GLM两处True；无全局禁编译或新增诊断开关。退出条件见各问题；不把默认TLE原有不稳定包装成已修复。 |
| D3 | 按用户明确批准的本次例外交付：公开基线SHA＋三组件完整冻结补丁/文件哈希＋待验证镜像。公开发布延后，未提交推送；例外不扩展到其他任务。 |
| E1～E3、F1～F3 | mHC/KDA/cache/量化协议、独立CPU oracle、真实dispatch与capture/两次变输入replay，完整16rank及prefix复用证据均保留；opaque fake仅元数据，真实数学仍走原CachedOp。 |
| E4 | 复用原生资源管理；诊断原生退出仍出现semaphore/shm追踪警告，已披露，按精确任务PID清理102。未擅改只读引擎生命周期；这是SHOULD的已知限制，不隐瞒为无警告退出。 |
| F4、F7 | 实际MetaX两机回归、格式与diff检查已执行；新增源码英文日志/版权头。当前无提交或PR；PR前完整pre-commit/目标CI尚待执行，不声称其他硬件和Torch版本通过。 |
| B5、F6 | 未新增芯片厂商或修改CI路由，相关新增平台/流水线条款不适用；实际16rank Socket通信已验证，RDMA未验证。 |
| G1～G2 | 支持表链接指向随补丁交付的真实示例，CLI help及API真实响应已验证；仅保留长期设置/限制，无过程日志或性能数字进入产品README。 |

逐组件设计判断：Plugin、FlagGems、FlagGems-vllm均可作为所声明MetaX BF16文本范围的
PR候选；vLLM没有本任务组件变更，继承87项mode-only差异保持原样。该判断包含上述D3
用户例外，不代表已公开发布或上游接受，也不代替接下来的GPQA198/88%、性能及镜像验证。
其余平台、MTP、实际图像/视频质量未验证，不扩大支持声明。未发现无法对应问题的增删、
重复跨组件workaround、删除原测试或无关重构。管理工具的双机取证改动另见015，不在三个
产品补丁内，不改变模型数学或profile要求。
