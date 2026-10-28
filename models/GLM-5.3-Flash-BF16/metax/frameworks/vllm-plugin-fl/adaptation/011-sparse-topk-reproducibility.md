# 011：稀疏索引选择的重复性（诊断/方案验证中）

## 已验证基线

v8源码与身份见environment-identity-v8.md。`glm-eager-state-topk-v3-20261028/mx-101`
四个原生LLM请求均返回yellow及相同token IDs，rc0、result.status=measured。
两组cold/hot均实际命中3456；16 rank共544条热KDA记录的conv/recurrent初始状态，
与对应冷检查点逐元素相等（1088项state比较），未发现本轮状态复制偏差。

同一真实prefill logits重复执行公共算子至独立scratch，输入不变，输出顺序会变化；
例如rank3/4/5/7的1536×864输入第765行在pool342与397间选择不同，两score完全相同，
均为-141.28079223632812。原有top-k文档只保证集合数值，不保证同分稳定，不能把合法
同分选择直接认定为算子数学错误。需要验证GLM选择确定的集合/顺序是否消除已知整模波动。
这次诊断有同步与额外计算，不用作性能或正式验收。关闭时仍有已记录MCCL告警。

## 改前项目真相表

| 字段 | 冻结范围 |
| --- | --- |
| Current op | FGV row-wise prefill/decode top-k；GLM压缩pool选择，参照Torch2.10 topk |
| Editable | FGV两处`ops/top_k_per_row_{prefill,decode}.py`的公共host入口及现有tuner语义key；对应既有测试追加；Plugin薄provider与原GLM测试的必要接入 |
| Read-only | vLLM、FlagTree/SDK、FG；原测试/参考断言及既有benchmark不改，保留原默认行为 |
| Identity | FGV `/opt/FlagGems-vllm@ddce1d66`；prefill SHA a5065ab1a58a3bd803c3129d6a79d4ee7b8743f6d8b738ae32064d077dc17a03；decode SHA a6f7666758a90a71c2109223826e7580555680d8123e76fbff3ab685516b932f |
| Build | Python/Triton直接生效；新进程，不用PYTHONPATH或另建源码树 |
| Validation | 先独立重复/同分负对照及强制现有canonical路径正对照，再正式可选接口、原调用方守卫、CPU oracle、capture和两次变输入replay；102后101 |
| Benchmark | GPU event中位µs，越小越好；原默认路径保持，确定路径对齐Torch stable argsort取K再按索引排序；逐shape报告，不用总均值隐藏回归 |
| Active set | F32，K512，prefill(N864, rows1/76/1536)，decode(N16384, rows1/8)；功能另含非整除、非零row_start、行padding、空有效范围、少于K、next_n1/2 |
| Timeout/profiler | 功能/微测各600s；MetaX profiler尚未核实，用真实dispatch、launch/路径参数及GPU event作替代证据；不声称服务性能通过 |
| Autotune | 不新写kernel/候选配置；复用既有标准路径和NVIDIA top_k_per_row_standard配置。若显式语义flag影响同shape工作量，tuner key加入CANONICAL_OUTPUT；MetaX原固定launch保留 |
| Fallback | NO_TORCH_COMPUTE_FALLBACK；生产只用既有Triton路径，无Torch计算/排序/复制回退 |

已读实际FGV AGENTS.md和workflow.md；optimization.md/deep_opt.md在root及docs均不存在，
不声称读过缺失文件。新增能力必须通过现有导出入口，非另注册一套算子。

## 对齐契约表

| 字段 | 契约 |
| --- | --- |
| Torch | [Torch2.10 topk](https://docs.pytorch.org/docs/2.10/generated/torch.topk.html)本身不保证同分索引稳定；本轮确定性作为显式可选能力，不改变旧默认契约 |
| Device/input | 实际C550；logits F32二维，column stride1/行padding，prefill有效区间与decode seq_lens遵循原ABI；indices预分配int32 |
| Output/alias | 原地写同一indices，pool ID仍相对有效起点，未选位置按原协议-1；不修改logits、range或cache |
| Deterministic | 拟复用原CANONICAL_OUTPUT分支的稳定收集/同分索引规则和确定输出顺序；先独立验证其小列数语义，不凭名称宣称通过 |
| Dtype/bounds | 不扩展FP16/BF16/int/complex输入；有限F32、合法range为本次覆盖；NaN/Inf/signed-zero沿原实现，非新支持声明 |
| Autograd | 推理indices接口，无训练/反向新增承诺；Torch只用于测试/微测参考 |

## 路径与变更清单

| 路径 | 方案与验证 |
| --- | --- |
| 原默认 | 不指定新参数时保持原TLE选择及65536列canonical阈值，验证旧八参数调用与守卫两侧 |
| 显式确定路径 | 先用诊断进程强制既有标准CANONICAL_OUTPUT路径，验证小pool稳定性及成本；成功后才考虑keyword-only可选flag复用该分支 |
| Plugin接入 | 仅MetaX GLM薄provider按需请求该可选能力，prefill/decode统一，保留公共dispatch与真实符号预检；不在模型层复制top-k |
| unsupported/其他平台 | 不扩展原无效dtype/layout；其他平台默认入口保持；缺少硬件时只报告选择隔离测试，不声称设备通过 |

目前尚未实施上述FGV/Plugin API增量。先验证既有canonical路径，若不能稳定或性能不合理，
重新审查方案，不降低数值门槛、不删除失败记录、不通过Torch fallback消除故障。

`glm-topk-canonical-path-20261028/mx-102` 既有generic标准路径正对照通过：prefill/decode
各20次重复精确相同、CPU稳定同分参考及两次变输入graph通过。小型8-row默认负对照未
复现波动，保留该结果；实际整模输入的重复差异仍由上述16-rank记录证明。五个generic
组件场景canonical为86/108/338/104/99µs，Torch稳定排序参考160/189/588/199/268µs，
SpeedUp1.74～2.71。原生CUDA sort dispatch已确认；mcprof/nsys/ncu均不存在。

进一步核对公共导出发现MetaX实际通过`runtime/backend/_metax/fused/top_k_per_row_*.py`
覆盖generic入口，并惰性安装TLE shim。因此前述generic默认耗时不能当作实际服务默认耗时；
增补真实公共入口的负/正对照和组件微测。若实施可选参数，范围必须包含这两个vendor wrapper
的必要透传/选择守卫。拟定keyword-only `canonical_output=False`：默认旧路由不变；显式True
复用既有标准canonical分支、保留旧大列数自动canonical；MetaX wrapper无需为该调用安装TLE。
不以环境变量全局关闭TLE，不新增数学kernel。此范围调整发生在任何新产品代码编辑之前。

真实公共入口独立负对照已复现：`glm-topk-canonical-public-20261028/mx-102` 的20次调用，
prefill产生17种顺序/6种集合，decode为18种顺序/3种集合；两者6行不同于确定同分参考。
诊断进程调用既有标准canonical分支后，均20次精确重复、CPU oracle及两次变输入graph通过。
拟实施变更清单：两个generic入口加keyword-only canonical_output=False及既有tuner key，
两个MetaX fused wrapper作必要透传/避免该调用安装TLE，两个原FGV测试文件末追加能力回归；
Plugin provider的两处八参数适配显式请求True，原GLM集成测试补真实路径重复/graph覆盖。
未指定参数的全部默认入口、导出名称、数学kernel与配置候选保持；旧测试函数和断言字节
前缀保留。先FGV102验证，再Plugin集成、逐块审查和101同步，最后整模复验。

真实公共入口微测完成：五场景默认TLE约49/50/136/65/65µs，确定路径86/111/340/105/99µs，
相同确定语义的Torch参考158/192/584/201/268µs，SpeedUp1.72～2.71。可选能力有明确成本，
不能将它称为比不确定默认路由更快；默认路由保持不变，整模收益/成本尚未测量。
MetaX wrapper基线SHA：prefill为30cdc996e51cf97fa90cbce3065a15435b574bb06c6e6b3134c8d5128ce0ad91，
decode为5b6521a6a0e13cd9620e0d9125b83ab51d1a4dec0ec14862ac2c9635cd675179。

原测试负对照 `topk-existing-stability-baseline-20261028/mx-102` 在未改源码时已失败：
prefill repeated_inputs_stable_selection[False-continuous-253-703-512]重复输出有76.6%位置
不同，rc1。该默认TLE基线失败完整保留，不修改/删除其断言或把新增可选测试当作旧测试通过。

102新增FGV能力38项通过（238.92s），两处host入口、两处vendor透传及tuner语义key增量
均已逐块审查，没有数学kernel改动，两个原测试文件字节前缀保持。
Plugin接入前进一步限定调用面：CachedOp的top_k_per_row名字是共享名字，不能令provider
无条件True而影响其他模型。改为provider可选参数默认False、纯透传；仅GLM模型自身
`sparse_attn_indexer_kpool`两个调用点显式请求True。新增集成测试也显式请求该能力；
其他模型/旧四参数调用保持False。新增涉及的model文件属原001已验证模型专属边界，
不改registry名字、选择优先级或其他模型代码。


102接入验证：修改前不传参数的公共CachedOp测试真实失败（56.6%位置不一致），
显式True的接口负对照因旧provider缺失keyword失败。接入后 `glm-canonical-fixed-v9-20261028/mx-102`
57项全通过（116.59s）；包含原55项和新增prefill/decode确定性重复、CPU oracle、两次变输入graph。
原测试完整字节前缀未变。两处模型调用仅增加显式True，provider默认False只透传，逐块审查
未见绕过dispatch、重复kernel或其他模型行为修改。FGV六文件和Plugin三文件增量已核对，
其余原25文件中未涉及者的SHA、各组件HEAD以及vLLM只读diff均保持。101同步验证中，
跨平台实机未测；MetaX可选确定路径已验证，不宣称默认TLE旧稳定性测试通过。


101同步后完整57项通过（131.95s），FGV可选能力38项通过（222.98s，72项未选择）；
两机测试集合相同。未测的72项不列入通过数，原默认不稳定负对照保持。
当前GLM13文件归档SHA为1ef0e9b26ae57b8ca99b3721e74964c345d05b6f5b19045c08a5e5036486fb27。
全组件任务源集合31文件（原25加六个原FGV文件），九文件增量已审查；
整模冷/热控制、graph级别、正式GPQA与服务性能尚待，不能以局部测试替代。


v9双机 eager `glm-eager-bringup-v9-20261028` 的六请求探针
`glm-eager-model-probe-v9-20261028/mx-101` 已完成（rc0）：短问4/Paris，
混合Paris和3532-token长输入yellow，重复长输入yellow，chat含reasoning及最终**4**。
chat59个生成token、23.83s，仅记录本次诊断耗时，不作为服务性能或跨版加速结论。
独立idle冷/热控制尚在执行，六请求不能替代数值一致性、graph或正式精度。


v9独立idle控制 `glm-prefix-idle-v9-20261028/mx-101` 全部四请求完成，原0.05门槛通过：
两组各自cold/hot logprob差均0，cold/cold与hot/hot均0.0393586233；输出均yellow、
2个token，两次hot均真实prefix命中3456。保留跨salt重复差异，不宣称整模完全bitwise确定；
此次四对照满足冻结阈值，v8热/热0.070691的失败仍保留。接下来生成固定chat参考、
首次FULL graph实际尝试；正式执行模式、精度和性能尚未通过。


v9固定chat参考 `glm-eager-chat-references-v9-20261028/mx-101` 已通过，冻结
reference-manifest.json（4/5/56/Paris），后续sanity使用该真实参考。切换FULL前，仅对
本任务API/headless根PID发送SIGTERM，stop-request.json保留PID/start ticks/父子树/cmd SHA；
逐机/proc核验所有记录后代已退出，两个run均rc0，容器保持运行。共享NFS状态可短暂延迟，
因此额外按各机真实/proc核验，没有只依据另一机读到的state判断清理完成。
