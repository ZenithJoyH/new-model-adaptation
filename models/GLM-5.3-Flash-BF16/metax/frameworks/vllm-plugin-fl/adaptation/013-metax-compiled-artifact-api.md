# 013 MetaX编译产物接口

Qwen既有经验只用作线索。当前安装Plugin HEAD4e23ae8f的MetaX
`dispatch/backends/vendor/metax/patches/fix_standalone_compile.py` 原SHA为
e3f5f15b365079177c2a0eb73f1369c6f6752f5c10b95bebb35231434aa7e5cf，未有本任务改动。
Torch实际2.10.0+metax3.8.2.2的CompiledArtifact是抽象基类；原生API返回具体CacheCompiledArtifact，
两者构造参数均为compiled_fn/artifacts。当前旧MetaX补丁仍直接实例化抽象类。

真实CPU小图 `metax-artifact-cpu-flat-baseline-v12-20261028/mx-102` rc1，已完成实际
compile_fx后在旧构造行抛TypeError（缺少__call__/save实现），result.json保留版本/原SHA。
没有把它描述成已发生的GLM FULL错误；GLM此前FULL停在mHC追踪，未到此阶段。
第一CPU诊断样例使用nested输出，不符合该接口的flat FX输出契约，在更早AOT阶段失败；
保留其失败并改用有效flat图，不为不合约的样例扩大产品代码。导入平台会初始化CUDA元数据，
实际图输入/计算为CPU，不声称整个进程没有CUDA初始化。

修改前限定范围：

| 文件/符号 | 变更 | 必要性 | 验证 |
|---|---|---|---|
| Plugin MetaX fix_standalone_compile.py构造类型选择/返回行 | 可选导入原生具体类，缺失时保留原旧类；替换构造类型 | 与当前Torch原生API一致 | 当前负对照；CPU/CUDA实际编译数值、binary/unpacked保存及原生加载；独立进程恢复 |
| tests/unit_tests/compilation/test_metax_standalone_artifact.py | 新增四个设备/格式组合回归 | 保证调用和持久化，而非只检查类名 | 变输入输出、完整数值及原生load；不使用mock替代计算 |

只修改已核实安装Plugin。保留嵌套FX节点遍历、autograd cache key、TF32旧hotfix及旧版
构造路径；不复制Torch序列化算法，不改Torch/vLLM/SDK，不改图档位或采样参数。
未有旧版Torch实机，legacy分支保持原行为但不能宣称旧版本验证通过。
此兼容修改只作用standalone编译返回；v11的31个数学/模型任务文件不变。

首轮构造修复后，CPU编译及调用通过，但保存因AOT cache为空失败，尚未运行其余三例。
只读核对默认bundled_autograd_cache=False；外部再次设False的对照仍失败，排除该假设，
没有修改产品缓存模式。原生check_node_safe要求call_method的目标含example_value元数据，
首版测试用普通symbolic_trace的x.sin/x.sum缺此元数据，AOT cache被跳过。
现将测试改为同数学的公开torch.sin/torch.sum函数节点，并在编译前显式调用原生
check_cacheable；不放宽保存、加载或数值断言，不为不满足缓存前提的样例扩展产品修复。
同步移除本次新测试的未使用Path导入。所有失败日志保留。

102修正后的四例全部通过（105.06s），原生check_cacheable先验证输入FX图可持久化。
随后 `metax-artifact-independent-load-v12-20261028/mx-102` 在独立新进程、全新
Inductor/Triton缓存目录恢复全部四份产物，每份执行两次变输入数值对照，state/result均通过。
实际产品diff只有导入具体类的兼容块和返回构造行；新增测试不替换已有测试。
当前源码SHA为f500ec3311cd38b79e4fdcf749d9cf36e9732d02a9e2be0d0d03a894e092e9ee，
测试SHA为9665f1cfb8e7b1c673cdd674b0e9cdd9fe507e4371dc8607d9b999e1fc7322d1。
原31文件逐一保持v11 SHA，新增后共33文件；101同样四例通过（124.92s），独立新进程
恢复四份产物、每份两次变输入也通过。首次独立启动等待守卫提前退出，未写任务文件；
父测试完成后才实际启动恢复，保留该失败，不重跑或替换四例原结果。

v11 eager六请求、idle和四chat参考已通过；原生日志明确enforce_eager禁用torch.compile和
CUDAGraph。本次新增构造只在standalone_compile_impl返回时执行，不改变导入时的原有hook，
不改变数学实现、调度、采样、权重或拓扑。因此复用未受影响的v11 eager参考并明确其历史
run ID；不将其改称v12实跑。新增编译路径必须由新四例、独立恢复及实际FULL重试验证。
若后续变更涉及数学/执行配置，则重新评估并重跑受影响项。正式graph/精度仍未通过。
