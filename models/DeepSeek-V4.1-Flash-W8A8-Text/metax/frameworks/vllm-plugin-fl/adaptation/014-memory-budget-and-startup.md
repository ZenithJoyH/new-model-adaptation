# 014：整模显存预算与初始化耗时

状态：open。eager v6 两机各8个rank均完成真实权重加载：102每rank 57.52 GiB，103每rank 33.67 GiB。初始 profile 已越过修复后的 CPU clone 路径，但引擎在 cache 分配时报 `No available memory for the cache blocks`，未就绪、未发送模型请求。原始证据为远端 `04-runs/eager-service-v6-20261104/<Host>.log`。

该轮配置为 TP8/PP2、20/20层、50000上下文、2048批token、16序列、显存利用率0.92、async on、prefix on。不能把内存预算错误归因于 PP 异步调度，也没有理由据此下降 graph 等级。失败进程已按精确模型、端口29593、PID namespace和启动时间清理，适配容器保持运行；回执为 `02-issues/<Host>/eager-service-v6-cleanup-20261104/result.json`。

核对实际 Plugin `WorkerFL.determine_available_memory`：cache 预算由 requested memory 减非KV内存及适用的图估算量得到。沿用真实 profile，不改第三方实现、不跳过预算检查。下一受控候选将显存利用率改为0.97，保留其他容量参数并收集 DEBUG 剖析数据；这只是候选，需以实际分配和请求检验，不提前声称50000上下文可用。

初始化耗时还有独立来源：固定 FG revision 的已接入 Cost Model 算子为 mul 与 MetaX mm。日志显示 AUTO preload 多次等待后因缺少可选 xgboost 而转为 DEFAULT。已核对 `runtime/flagtune.py:resolve_tuning_mode` 和 `utils/libentry.py`：`USE_FLAGTUNE=0` 直接选择既有 DEFAULT 配置空间，正是此次 AUTO 失败后使用的路径，不是禁用 FlagGems 或换成 Torch 计算。后续启动使用这一显式设置避免重复的失败探测；不安装可选依赖，不修改 Torch/Triton源码。最终精度与性能必须绑定同一设置并重新验证。

eager v7 使用该候选与新的唯一端口29595；Plugin v32、FGV v41保持，FG为clone最终v3清单。若仍失败，按实际峰值及cache最低需求调整；在请求与图执行得到证据前，正式验收保持未通过。

## 0.97 的初始内存检查与显式 cache 候选

v7 在加载权重前被原生 `request_memory` 拒绝：通信初始化后每卡可用59.43/63.59 GiB，0.97要求61.69 GiB。该候选未验证模型前向，不能记为成功或调度异常。两机均核验无残留v7服务，适配容器继续运行；证据为 `eager-service-v7-20261104` 日志及各Host的 `eager-service-v7-cleanup-20261104/result.json`。

改用原生支持的 `kv_cache_memory_bytes` 控制 cache 容量；该分支仍执行 `profile_run`，实际分配及请求仍须通过OOM与正确性验证。没有修改预算函数。先以实际 Plugin cache spec 和原生 `get_kv_cache_configs` 对16个worker进行CPU元数据核算：stage0为26个spec，stage1为22个；50k上下文、1024批token、16序列下，逐spec最低内存和分别为93,591,936与74,223,360字节。256/512/1024 MiB候选均经原生planner返回配置，GPU分配为0。首轮探针误读 `.tensors` 字段的失败保留；v2保存真实dataclass字段后通过，未改产品实现或planner规则。

容量证据为 `02-issues/mx-103/cache-capacity-v2-20261104/result.json`。当前eager v8候选使用每rank 536870912字节KV cache、1024批token，保留50k上下文、16序列、TP8/PP2、async及prefix；移除与显式预算无关的利用率覆盖，使用框架默认值。该核算证明元数据可规划，不能替代真实GPU分配、初始化前向、最长上下文、并发或graph验收。

完整容量结果SHA-256为 `67f9e8dfc9b7d488d1888f2959dbaa8a8c47c8fb486e71dc7d993d6a70a05ac6`。进一步核对实际 `kv_cache_tensors` 字段：原生V4 packed布局的多个descriptor共享同一底层slab，不能将其size直接相加。`_get_kv_cache_config_packed` 为各offset发出相同size和block_stride，明确声明共享backing。本轮512 MiB输入对应每rank 7169块、block stride 74880字节、唯一底层536814720字节；stage0有7个offset描述、stage1为2个。此前汇总直接求和产生的“超过预算”疑点已澄清，未修改planner或Plugin cache实现。实际GPU别名/stride与生成仍待运行验证。

eager v8 于23:18完成真实初始化，HTTP `/health` 返回200。两机各8个rank加载完成；102每rank57.49 GiB、103每rank33.59 GiB。原生引擎报告cache容量277438 tokens、50k请求最大并发估算5.55x，profile/cache/warmup耗时414.65秒。该结果证明当前容量方案可以启动；实际生成、最长上下文、PP并发/流式和graph仍待验证，不能据此通过完整验收。
