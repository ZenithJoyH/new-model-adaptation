# 012 mHC编译边界

首次真实FULL尝试 `glm-full-graph-diagnostic-v9-20261028` 在任何capture/请求之前失败。
102 worker日志定位 `Glm5NextModel.forward -> MHCPreOp -> CachedOp -> FGV mhc_pre_with_norm
-> mhc_pre -> _get_fn_bf16_cached -> contiguous_copy -> libentry.run`。
Dynamo错误为Unsupported method call，GetAttrVariable(TritonKernelVariable(), params)的切片。
101主节点rc1；102失败后仍有本任务headless存活，先精确记录并停止，容器保持运行。

归属：模型接入缺少opaque编译边界，而非mHC数学错误。既有MHCPreOp/MHCPostOp/
MHCFusedPostPreOp只是nn.Module直接CachedOp，暴露了库内部Python调度；已有indexer和
Plugin ViT attention使用vLLM正式direct_register_custom_op+fake_impl扩展点。
优先复用该边界，仅GLM三处mHC封装保持dispatch真实计算；不改CachedOp公共控制面、
FGV libentry/数学kernel、Torch、SDK或vLLM，不通过全局禁编译规避。

修改前范围：

| 文件/符号 | 改动 | 必要性 | 验证 |
|---|---|---|---|
| Plugin models/glm5next.py三处mHC模块及邻接注册/fake | 新增薄custom-op和元数据实现，三个模块委托torch.ops | 阻止Dynamo追踪运行时调度，数学仍经CachedOp | 修改前真实fullgraph负对照；三op真实数值、schema/fake、动态token fullgraph compile、两次变输入GPU replay |
| Plugin tests/unit_tests/patches/test_glm5next_pipeline.py | 仅追加上述回归 | 保留现有PP/graph断言 | 原完整57项+新增编译回归；四层PP组合不变 |

Plugin HEAD仍4e23ae8f；模型v9基线与完整31文件快照一致，新改前按字节SHA守卫。
目标仍先重试FULL；本次不构成下调graph档位的理由。其他模型不使用GLM专属torch.ops名称。

协议核验：FGV pre返回新post/comb/value；post分配empty_like(residual)返回新张量，
fused返回新residual_cur与三pre结果，均不修改调用者输入或返回输入别名。
fake仅分配正确shape/dtype/device的元数据张量，不能替代真实设备数值测试。


隔离负对照 `mhc-compile-baseline-v10-20261028/mx-102` 确认失败在严格
`torch.compile(fullgraph=True,dynamic=True)`：库缓存分支的tensor.is_inference不支持追踪；
真实服务inference/Parameter分支更早走contiguous_copy后触发libentry.params切片错误。
两者均是Python调度被暴露，不通过修改库的缓存策略来掩盖。

102实现仅新增三个GLM专属torch.ops薄函数及fake，原模块名保留，真实计算仍CachedOp。
Fake按residual元数据返回新post/comb/value，post/fused无输入修改或别名。
测试覆盖128及实际4096宽度、1/3动态token、norm可选、缓存/Parameter分支、
schema/fake与两次变输入replay；原PP三项完整字节前缀保留。
模型增量校验脚本曾误将字符位置用于字节后缀，写入后断言退出且未启动测试；
已只读取回完整文件，核验AST及原文本前后段一致，保留失败记录，修正后恢复67项回归。


本轮两文件每个增量hunk均已审查：只增加三op必要schema/调度/fake，保留模块名和CachedOp
策略控制。没有复制数学实现、改公共CachedOp、禁用编译或改FGV/Torch/vLLM。
两机全部67项通过（10245.88s、10184.89s）。源码仍31文件，其余29个文件及所有tracked
diff和HEAD与v9一致。v10完整整模/FULL尚待；当前只称编译边界局部修复通过。

v10六请求已完成（`glm-eager-model-probe-v10-20261028/mx-101` rc0），短问4/Paris、
3532-token长输入及重复yellow、混合请求和带reasoning的chat最终**4**均正常。
idle对照仍执行，尚不声明v10数值控制或FULL通过。

重试FULL前另核对相邻的模型专属SiluAndMulWithClamp编译边界：只读链路显示其经
CachedOp进入FGV普通Python/Triton入口，与本问题相关。已准备隔离编译探针，必须在
v10 eager/reference通过且其精确任务进程退出后执行；尚未运行或修改该符号。
探针结果才决定是否扩大同文件范围，不能把静态推测当作已确认缺陷。

相邻探针已真实失败：`glm-activation-compile-probe-v10-20261028/mx-102` rc1，
所选实现default.flagos，经FGV的logger.debug触发Dynamo Unsupported。v10源码未改时
在同目录result.json保留完整错误；它发生在请求/捕获前，不是数学失败。不能只全局忽略logger，
因为库还有标量处理、调优和Triton启动Python，边界应封装完整算子。

据此在改产品前扩展同一问题清单：仅模型SiluAndMulWithClamp与邻接薄torch.ops/fake、
同一pipeline测试文件追加clamp的CPU数值、schema/fake、动态shape严格编译与变输入graph。
薄实现用原CachedOp及原生forward_native实际读取的三个标量字段，保留alpha=1/beta=0守卫；
模型调用仍为原类，公共op名称/优先级和FGV/公共activation源码不改。现有类内CachedOp
在opaque实现内统一持有，删除仅属该类的重复实例；没有外部GLM专属导入调用者。
fake按gate视图empty_like分配，匹配原FGV空输入/stride/dtype及新输出协议。

本次权重实际hidden4096、dense intermediate12288、MoE intermediate2048、shared1、
limit10；TP8对应本地激活宽256/1536，新增测试据此固定，不能沿用其他模型维度。
102仅扩大模型同一区域及原pipeline测试末尾；新增四项覆盖BF16/FP32、空/1/3 token、
独立CPU公式、严格Inductor fullgraph、schema/fake与两次变输入replay。原67项断言保留。
本次不更改FGV数值或logger，不改公共activation provider，不降低graph档位。

v11两机全部71项通过（10258.30s、10153.12s），原67项和新四项均成功；四项新用例内
包含0/1/3动态token、CPU独立参考、schema/fake及两次变输入replay。两个增量文件已逐hunk
审查：纯封装和元数据，原alpha/beta错误守卫保留，重复CachedOp实例移入真实opaque实现，
没有新增数学kernel或改公共行为。其余29个任务文件、HEAD和tracked diff与v10一致。
v11的13文件归档SHA07945a99e9fed64f9e8953ec7c7132dbb410f205351655e5071fc048357bab60。
当前重新执行同源整模，完整FULL、GPQA和性能尚未通过。
