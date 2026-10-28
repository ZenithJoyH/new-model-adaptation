# 006：异构 GDN/PLE 的 align 前缀状态复制

## 基线与证据

mx-101 / qwen3.8-flash，Plugin实际安装 `/opt/vllm-plugin-FL@f41b7de8`，当前只有请求的PR455
差异（53文件，patch SHA256 ad9fab5e...）。vLLM只读ee0da84a，原完整diff保持。
`model-eager-prefix-align-20261023`已就绪，但首条真实请求4.74s后HTTP500，服务自行退出。
`smoke.json`保留请求/失败，不当作生成通过；该实例实际cache=True、mode=align、TP8、max_len50000。

根因：Plugin runner的_get_mamba_bufs直接调用vLLM0.24 MambaBuffers.create，原生
get_mamba_groups要求所有MambaSpec完全相等。模型GDN有(conv,temporal)两个状态，PLE只有conv，
shape/dtype不同但block_size和num_speculative_blocks一致。该断言在真正forward之前触发。
既有PPU问题011也曾记录同一独立缺口；它当时没有给出已验证修复，不借用其测试结论。

## 改前范围与设计

已读原生MambaBuffers、preprocess_mamba、collect_mamba_copy_meta、conv/temporal copy callbacks
和Plugin所有调用点。原生preprocess只从代表spec读取block_size/num_speculative_blocks；
真实复制逐层读取kv_cache、按copy callbacks与每层状态zip，已有byte-copy kernel支持实际dtype/stride。
因此不需要复制调度算法、改vLLM、伪造spec或按group重复更新请求状态。

| 文件/符号 | 改动与必要性 | 验证 |
| --- | --- | --- |
| compat/mamba_cache.py（新增） | 兼容缓冲工厂：同质直接委托原生；异构non-spec要求相同block与spec block计数、模型声明的copy callbacks为全局callbacks前缀，按真实各层state数量分配copy条目并保留原group IDs；复用原生MambaBuffers/CopyBuffers和preprocess/kernel | 原生断言负对照、同质透传、元数据容量/非连续group IDs、守卫 |
| worker/model_runner.py::_get_mamba_bufs | 只替换工厂入口并传现有get_mamba_state_copy_funcs getter，按真实MambaSpec.mamba_type核对callbacks；保留原native preprocess、请求更新、spec分支、注册及其它模型路径 | 原worker回归、真实GDN+PLE prefix复制及服务 |
| tests/unit_tests/worker/test_mamba_cache_compat.py（新增） | CPU契约与设备精确copy/graph回归 | 源/目的块不同且每group独立block表，padding/未选块不变，至少两次变输入replay |

同质路径包括原spec postprocess完整保留。异构spec postprocess目前仍不支持，明确失败而非套用
错误的固定state数量；本模型原配置已拒绝MTP/spec，此修复不缩小任何先前能工作的异构范围。
如果模型没有声明每类型callbacks、callback顺序不兼容、block_size或spec block计数不同，提前
报明确错误，不猜测状态布局。新工厂仅一次性元数据/缓冲分配，热路径复用原native函数，
不新增计算fallback或调优参数。

异构扩展明确限定num_speculative_blocks=0；任何非零spec扩展计数也拒绝，而同质原生路径
不变。Factory不需要模型名或forward_context，不引入跨模型依赖，只消费已有callbacks声明。

改后先跑最小纯metadata负/正对照、CPU守卫、真实MetaX三state精确复制与graph、Plugin受影响
worker/model测试，再启动新的eager实例；不能靠关闭prefix缓存消除失败。源码/部署与环境回执
重新绑定。完整模型请求、graph、最终交付均尚未通过；下文记录实际实施与结果。

已实施上述三文件范围。07-bugs独立metadata复现原生失败(rc2)、Plugin工厂通过，保留原
group IDs[1,3]；2请求×(GDN两state+PLE一state)=6条指针/大小缓冲，未改任何spec或调度规则。
新测试 **13 passed in 20.81s**，含BF16/FP16 conv + FP32 temporal、两种group顺序、
带page padding的真实MetaX byte-copy与每组两次变输入graph replay，状态及padding精确比较。
同质委托、非零spec计数/错block/callback/missing声明拒绝均通过；原生函数与kernel只读。
复现导入保留既有MetaX patch循环导入警告；未声称消除此环境告警。格式检查通过；较宽回归（Qwen3.8模型、worker、KV绑定与公共注意力metadata）**108 passed in 23.43s**，原始记录 `04-runs/heterogeneous-mamba-copy/regression.log`。

新实例 `model-eager-mamba-fixed-20261024` 使用相同TP8/max_len50000、prefix=True/align和clone排除，
config SHA256 `42e3abfa2d084b07a1815aae315d0ee110d8eb36c0cf76194c255d523e39a193`。
API PID305026、PGID305026、start_ticks1107992713；实际就绪后3条greedy请求均正确输出2/56/5。首请求286.523s（首次编译及NFS metadata锁等待），后两条2.183s/1.569s；无异构spec断言。证据 `04-runs/model-eager-mamba-fixed-20261024/smoke.json`。长前缀复制与graph仍待验证。

8730-token真实prefix回归已通过，三次各命中6400，独立salt零命中，冷/热相同问题token与
logprob完全一致；见005及其原生记录。vLLM完整diff SHA保持原基线，无任务修改。
当前实际安装快照 `01-environment/installed-identity-after-mamba-compat.json` SHA256
`f465566e0f73c176c2e4459e488e32ce9801c1db57b8dc0a491ca7f5d450b513`；
含新增文件的Plugin完整补丁 `02-issues/plugin-after-mamba-compat.patch` SHA256
`cff41e9139f1efb1abd22b95796bd081105a9881d8d03269aab480ca95f8cdb6`。
