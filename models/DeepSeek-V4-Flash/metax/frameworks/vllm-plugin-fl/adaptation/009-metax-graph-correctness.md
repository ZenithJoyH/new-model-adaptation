# 009：MetaX 图模式编译正确性与最终运行配置

## 元数据

- 状态：`mitigated`
- 首次出现时间：2026-09-21
- 最后验证时间：2026-09-23
- 模型 / 平台 / Host：DeepSeek-V4-Flash INT8 / MetaX C550 x8 / `mx-59`
- 容器：`deepseek`
- 模式：TP8+EP，graph 主模式，前缀缓存开启

## 问题现象

- run27 默认 breakable graph 出现 allocator corruption。
- 关闭 breakable graph 后依次暴露 Dynamo generator、`torch.mm(out_dtype=fp32)` fake/runtime 和辅助 CUDA Stream 符号化问题；均在 Plugin 的既有扩展层修复。
- run31 的 Inductor 输出调用 `bmm(..., out=...)`，FlagGems 黑名单只含 `bmm,mm`，实际注册名 `bmm_out/mm_out` 未被排除，MetaX generic Triton `bmm_out` 对 K=4 不适用。
- run32 在同时排除 `bmm,bmm_out,mm,mm_out` 后可以完成标准 compile + graph 捕获，但真实请求分别输出 `ue` 和 `talags`，语义错误。
- run33 仅关闭 CUDA Graph、保留 torch.compile 后仍输出错误，证明语义破坏来自当前 MetaX torch.compile/Inductor 链路，而不是 CUDA Graph replay。

## 根因收敛（2026-09-22）

- 动态 INT8 quant + scaled-mm 最小复现位于 `07-bugs/torch-compile-int8-scaled-mm/reproduce.py`，结果位于 `04-runs/torch-compile-int8-scaled-mm-20260922-02/`。对 M=1/2/9、K=4096、N=1024 以及实际 MetaX weight stride，Dynamo eager 与 Inductor 的 quant、scale、BF16 GEMM 输出相对 eager 均逐元素一致，`max_abs=0`；排除这组 W8A8 out-variant 算子的独立 lowering。
- MHC reference 最小复现位于 `07-bugs/torch-compile-mhc-reference/reproduce.py`，结果位于 `04-runs/torch-compile-mhc-reference-20260922-01/`。参数使用模型真实结构：`hc_mult=4`、`hidden_size=4096`、`hc_eps=1e-6`、20 次 Sinkhorn。
- 纯 MHC/Sinkhorn 的 Inductor 结果只有 FP32 末位差异：`comb` 最大绝对误差不超过 `7.45e-8`，`post` 不超过 `1.19e-7`，BF16 `layer_input` 对 M=1/2 逐元素一致、M=9 最大误差 `2.38e-7`。纯 RMSNorm 编译也逐元素一致。
- 将 MHC 与随后的 RMSNorm 放入同一 Inductor 图后，BF16 `normalized_input` 在 M=1/2/9 上稳定出现 `max_abs=0.015625`、`mean_abs≈0.00112–0.00117`，且不满足 `rtol=atol=1e-3`；相同函数用 Dynamo eager backend 时逐元素一致。日志同时显示 Inductor 因拆分 reduction 动态关闭 online softmax。
- 整模型 run03 位于 `04-runs/torch-compile-backend-eager-20260922-03/`。它与 run33 同为 TP8+EP、`cudagraph_mode=NONE`、`custom_ops=['none']`、`ir_enable_torch_wrap=True`，只将 backend 从 `inductor` 改为 `eager`；历史同两条请求精确返回 `OK`、`5`。因此整模型乱码可归因于 MetaX Inductor/AOT 生成代码，而不是 Dynamo 捕获、CUDA Graph、模型权重或请求路径。
- 开启 PyTorch 内置 `torch._dynamo.config.verify_correctness` 后，8 个 rank 在服务启动期均由 eager-vs-Inductor 校验直接报 `incorrect results of backend`，无需发送请求即可复现。最初 MetaX eager FX 因 `torch.empty((SymInt, 64, 512))` 报 `SymIntArrayRef expected to contain only concrete integers`；诊断层仅将输入 shape hint 具体化后，校验继续并抓到真实数值错误。证据位于 `04-runs/torch-compile-verify-correctness-20260922-03/verify-dump/`。
- 校验器捕获的首个错误子图精确为 vLLM `SiluAndMulWithClamp.forward_native`：BF16 输入 `(1024,512)`，执行 clamp 后的 `gate * sigmoid(gate) * up`，8 个 rank 均为 `max_abs=0.00390625`。它不含 FlagGems 算子、collective、attention、KV cache、采样或 CUDA Graph，因此直接证明 MetaX Inductor 已在纯 ATen BF16 pointwise 图上改变 eager 数值语义。
- 最小复现位于 `07-bugs/torch-compile-silu-and-mul-with-clamp/repro.py`，有效结果为 `04-runs/torch-compile-silu-and-mul-with-clamp-20260922-02/result.json`：完整 clamped SwiGLU 与去 clamp 版本都为 `max_abs=0.0625`、`mean_abs=0.00062158`、`allclose=false`；clamp-only 逐元素一致。故差异来自 Inductor 融合后消除了 eager BF16 中间舍入边界，而非 clamp lowering。
- 将该共享专家激活通过注册自定义 op 隔离后，整模 compile 服务仍分别输出 `airo**aharoaaharoa` 和乱码，排除它是唯一错误点。继续把 MHC pre/fused-post-pre 隔离后，状态隔离版整图 verifier 在 8 个 rank 上仍一致失败，最终隐藏态 `(1024,4096)` 为 `max_abs=0.015625`；证据位于 `04-runs/torch-compile-verify-correctness-20260922-06/verify-dump/`。
- 再单独隔离最终 `mhc_post` 后差异没有消失，反而成为 `max_abs=5.4375`、`mean_abs=0.334162116`，证明数值分叉在进入最终 MHC 汇聚前已经形成；证据位于 `04-runs/torch-compile-verify-correctness-20260922-07/verify-dump/`。此前“具体根因是 MHC+RMSNorm”的假设因此被反证；它只是另一个可重复的 BF16 融合差异，不是整模唯一根因。
- 结论提升为：已经直接证明当前 MetaX PyTorch Inductor 至少有一个 BF16 融合区域未保持 eager 中间舍入语义；隔离该区域后整图仍存在另一处尚未精确到 kernel 的 Inductor 语义分叉，逐层误差最终会改变 token。这是 **MetaX PyTorch/Inductor codegen/优化语义错误**。首个失败子图不经过 FlagGems，且同一 FlagGems/Plugin 栈改用 Dynamo eager backend 即正确，因此没有证据把主因归为 FlagGems bug。
- 同时存在独立版本兼容缺陷：PyTorch `triton_kernel_wrap.py` 反复导入当前 Triton 不提供的 `triton.runtime.jit.specialize_impl`，失败后退化为“所有输入均被修改”。它会损害 functionalization/别名分析，但本轮未证明它单独导致上述数值错误，需作为独立上游兼容问题处理。
- run02 使用 backend=eager 的自动默认值 `custom_ops=['all'] / ir_enable_torch_wrap=False` 时，在 Plugin OpManager 懒初始化的 `RLock` 上发生 Dynamo graph break。显式恢复 run33 的两项图设置后 run03 正常；这是独立的配置/初始化缺陷，不是原乱码原因。

### 逐 piecewise 子图定位与修复（2026-09-23）

- 新增的一次性诊断层位于 `02-issues/torch-compile-piecewise-verifier/sitecustomize.py`，在 vLLM 每个 pre-Inductor piecewise FX 子图首次执行时，用克隆的真实输入分别执行 eager FX 与编译候选，并复位 `forward_context.moe_layer_index`。它只忽略由后续 split custom op 负责原地写入的未初始化 `torch.empty` attention 占位输出，其余 Tensor 均比较有限值、NaN/Inf、最大/平均绝对误差和 `allclose`。该工具是诊断代码，不进入 Plugin 产品树。
- 首个真实错误位于 segment 0 / `submod_0` 的 `deepseek_v4_fused_q_kv_rmsnorm`：Q `(1024,1024)` 最大绝对误差 `1.60473633`，KV `(1024,512)` 最大绝对误差 `4.34375`，8 个 rank 一致。虽然 policy 显示 `default.flagos`，当时 FlagGems backend 实际调用 vLLM reference Triton kernel，FX 图中仍出现 `triton_kernel_wrapper_mutation`。单算子复现位于 `07-bugs/fused-qkv-rmsnorm-compile/`；修复前编译结果与 eager 最大误差均为 `11.375`，经 Plugin opaque custom-op 边界调用真正的 FlagGems `fused_q_kv_rmsnorm` 后两路均 `max_abs=0`。
- 修复后第二个真实错误位于 segment 1 / `submod_2` 的 `deepseek_v4_inv_rope_quant_int8`。其 FlagGems backend 只是带 device guard 直接调用 Plugin 自带 Triton kernel，同样被 Inductor 展开；单算子复现位于 `07-bugs/inv-rope-quant-int8-compile/`，修复前 int8 `(1,1024,4096)` 有 `4,144,249` 个元素不一致，scale 最大/平均绝对误差为 `1.97880781 / 0.712826371`，同时命中 `specialize_impl` 导入失败后“所有输入均 mutated”的路径。把该 kernel 保留在 Plugin dispatch 后、再包入有 fake contract 的 opaque custom op 后，int8 mismatch 和 scale 误差均降为 `0`。
- 最终诊断运行 `04-runs/torch-compile-piecewise-verify-20260923-05/` 使用 TP8+EP、`VLLM_COMPILE + backend=inductor + custom_ops=['all'] + cudagraph_mode=NONE`。8 个 rank 各 44 段、合计 `352/352 PASS`，所有参与比较的 Tensor 均 `max_abs=0`，无 `MISMATCH/ERROR`；服务健康端点为 `200`，两条冻结请求精确返回 `OK`、`5`。因此在该执行模式与固定输入上未发现第三处语义异常，历史乱码已由上述两个编译边界修复消除。
- 该运行初始化总计 `410.95 s`，其中 compilation `278.00 s`。它是 execution-mode/固定请求诊断通过，不是正式 accuracy 或 performance acceptance，也尚未证明 `torch.compile + CUDA Graph` 组合通过。
- run05 遗漏 `FLAGGEMS_CACHE_DIR`，FlagGems 首次物化把进程专属生成代码写入默认 `/root/.flaggems/code_cache`；该偏差已写入 run05 `result.txt`，未删除历史缓存。后续启动脚本显式把 `FLAGGEMS_CACHE_DIR` 指向批准根下的 `06-cache/flaggems-<tag>`。

## 修复与受控规避

- Plugin 修复 generator、fp32 mm 自定义 fake/runtime op 和 MetaX 辅助 stream 能力守卫。
- 将 `bmm_out/mm_out` 与 `bmm/mm` 一并写入 MetaX FlagOS blacklist，并增加配置回归测试；用户原有未暂存 `linear` 条目保持不变。
- 当前 mcPytorch 自带 `TORCHINDUCTOR_EMULATE_PRECISION_CASTS=1`。`torch/_inductor/config.py` 明确说明它用于在 FP16/BF16 融合时保留 eager 的中间 downcast/upcast；当前容器实测默认值为 `False`，同时 `epilogue_fusion=True`。受控复验表明该开关能够修复已定位的 SwiGLU 子图，但不能修复整模型图，因此只能作为局部诊断/缓解手段，不能用于恢复生产 compile 模式。
- 最终配置使用 `{"mode":"NONE","cudagraph_mode":"FULL"}` 和 `VLLM_USE_BREAKABLE_CUDAGRAPH=0`：禁用当前错误的 torch.compile/Inductor，同时保留 vLLM 支持的 CUDA Graph。因后端能力声明，生效模式为 decode FULL graph。
- 此项是有证据的运行配置 mitigation，不宣称已经修复 MetaX Inductor 的根因；退出条件是上游 compile 模式在相同两条严格请求和正式回归中恢复语义正确。

### Plugin dispatch 到 FlagGems 的受控适配（2026-09-22）

- Plugin 原有 DeepSeek-V4 MHC 的 FlagGems backend 实际仍调用 reference，`SiluAndMulWithClamp` 也未进入 OOT dispatch。现已补齐 Plugin 的算子注册、MetaX policy 和初始化期预解析，使 `silu_and_mul_with_clamp`、`rms_norm`、`deepseek_v4_mhc_pre`、`deepseek_v4_mhc_fused_post_pre`、`deepseek_v4_mhc_post`、`deepseek_v4_hc_head` 均优先选择 `default.flagos`，不支持的参数契约才允许回退 reference。
- FlagGems `pointwise_dynamic.materialize()` 的缓存键原来遗漏 `balance_grid`，导致同一 rank/指针模式先缓存普通 grid 后，再物化 balanced-grid clamped SwiGLU 时以 `KeyError('2_True')` 中断整个 FlagGems backend 注册。缓存键已加入 `balance_grid`，定向回归 `tests/test_pointwise_dynamic_balance_grid.py::test_balanced_grid_cache_isolation` 通过；这是独立且已验证的 FlagGems bug 修复。
- 直接使用 FlagGems 新增的透明 PT2 `wrap_triton` 路径时，clamped SwiGLU 在 `torch.compile(fullgraph=True)` 下有 `958/1024` 元素不一致（93.6%，最大绝对误差约 `3.09e37`）。当前 FlagTree 为 `0.6.0+metax.gitd96f5339` / Triton `3.6.0`，缺少 PyTorch 2.8 `triton_kernel_wrap.py` 期望的公开 `create_specialize_impl`/`specialize_impl`；远端 FlagTree `main` 已到 `de7fb1758`，但 `python/triton/runtime/jit.py` 在这一区间没有相关接口变更。
- 使用当前 FlagTree 内部 `native_specialize_impl` 加兼容垫片后，导入警告消失，但上述数值错误完全不变。因此仅升级 FlagTree 当前主线或只补 `specialize_impl` ABI 均不足以修复；问题还涉及 MetaX PT2/Triton lowering 或调用 ABI。升级同时会引入重新构建与 GLIBC/二进制兼容风险，本轮不采用。
- 同一批经典 FlagGems kernel 在 `torch.library.custom_op` 不透明边界下通过 fullgraph 数值对照。Plugin 因而采用 `dispatch -> default.flagos -> opaque custom op -> FlagGems kernel`：Dynamo 能看到稳定的算子 schema/fake contract，但不再错误地展开当前 MetaX PT2 wrapper；这不是 reference 回退，也没有绕过 Plugin dispatch。
- 部署前将四个被更新文件备份到 `05-tmp/plugin-dispatch-update/pre-opaque-20260922/`，并在每次复制前用 `cmp` 确认容器目标仍与备份一致；没有覆盖并发变化。Plugin 与 FlagGems 改动均保持未提交/未推送状态，PR 427 既有暂存内容未被重写。

### 已发布独立镜像的实现对照（2026-09-22）

- 只读检查 `harbor.baai.ac.cn/flagos-inner-models-release/dsv4-flash-w8a8-metax:20260916-standalone-20260922-r1`，本机镜像 ID/digest 为 `sha256:d9b55ee2982c8a9727fe9510167431ab3a083747ce8f3f7a47b3fd8fe27659c7`。该镜像没有设置或引用 `TORCHINDUCTOR_EMULATE_PRECISION_CASTS`，因此它不是通过打开 precision-casts 开关修复通用 Inductor 语义。
- 锁定栈与当前适配容器不同：vLLM `0.20.2+empty`、Plugin `1767c90260b3d851481aa2c17495457b5c9d502f`、FlagGems `5.0.2`/revision `3123859968915e361e8452dd796dc6b27c956324`、Torch `2.8.0+metax3.7.0.7`、Triton `3.0.0+metax3.7.0.7`。它还通过 `/independent_runtime/dsv4_metax` 提供独立 MoE/MetaX runtime，而不是复用本轮最新主线三仓组合。
- 默认编译配置为 `cudagraph_mode=FULL_DECODE_ONLY`、`custom_ops=['all']`，启动器明确拒绝 `--enforce-eager`、缺失编译配置和非 `FULL_DECODE_ONLY`，并写明 prefill graph replay 不允许。即保留 torch.compile 和 decode graph，但主动限制图覆盖范围。
- `/graph_patch/metax_graph.yaml` 将 `silu_and_mul` 优先路由到 FlagGems、`rms_norm` 路由到 reference；启动期 `sitecustomize_prebind.py` 预加载 FlagGems 模块、去除 backend 函数中的运行时 import、直接绑定 33 个左右的 backend 方法并预解析 Plugin `CachedOp`，使 Dynamo fullgraph 不再进入懒加载锁或图内 import。首个纯 ATen SwiGLU 融合错误因此被 FlagGems opaque kernel 边界绕开，而不是修复 Inductor 对该 ATen 图的舍入语义。
- 同一启动补丁还把 vLLM multi-stream 强制为顺序执行；把 MHC BF16 转换改为不写 module-level cache；把 `hc_head_fused_kernel` 中 Dynamo 不可类型化的 `data_ptr()` 判断改成等价的 contiguous 判断。这些属于 graph-safe 初始化/捕获适配。
- 正确性/稳定性采取确定性 kernel policy：MHC `hc_mult=4` 尾部只保留 `BLOCK_H=8192, warps=4, stages=1`；三个 H=4096 Inductor RMS reduction kernel 固定 `XBLOCK=1, R0_BLOCK=2048, stages=1`，并按 rank/kernel 固定 4/8 warps，关闭 dynamic reduction scaling 和 coordinate-descent tuning。另有 FlagGems `mm/addmm` 共享内存 tile shrinker。
- 构建时唯一显式 FlagGems patch SHA-256 为 `70812643d9dad4f5e8fb07ec194a954fb18c8c927f7b2cda8c438c140993a8a2`：把 sparse MLA/MLA decode 的 BH/BK 从 64 级别缩到 16/32、4 warps、1 stage，并补充一个符号别名。安装后的 Plugin 包另外包含 MHC、scaled-mm、indexer、attention 和独立 MoE runtime 差异，不等同于其干净的 `1767c9026` 源 checkout。
- 发布清单声明 `weights_included=false`、`compiled_caches_included=false`、`gpu_test_performed=false`，镜像 label 同样为 `org.baai.dsv4.gpu-revalidated=false`。因此本节只证明镜像采用了何种实现/规避策略；在 `mx-59` 上用用户模型挂载实际启动、固定请求及 verifier 复验前，不能把该最终镜像自身视为新的本机 GPU 通过证据。

## 验证结果

- run34：`04-runs/pr427-graph-tp8-20260922-34-full-cudagraph-no-compile/`，decode FULL graph 捕获 1/1；两条真实请求精确返回 `OK`、`5`。
- 最终启动脚本：宿主机与容器路径均为 `/public-flash/jinghao/deepseekV4/start-model.sh`；本轮只读复核 SHA-256 为 `4cc47ab78cf11e43b907bec8a21c6ed4705c8f20025ce5f10bb3319cdd4a2112`。
- 最终复验运行：`04-runs/final-graph-20260922-004620/`；PID `639881`，decode FULL graph 1/1，`enable_prefix_caching=True`；`final-validation.txt` 状态 `PASS`，严格返回 `OK`、`5`。
- 根因诊断后的恢复运行：`04-runs/final-graph-restored-20260922-01/`；有效配置 `mode=NONE + cudagraph_mode=FULL`，PID `718293`，健康端点通过，严格请求再次返回 `OK`、`5`。
- 完成逐子图定位后的最终恢复运行：`04-runs/final-graph-restored-20260922-02/`；启动脚本 SHA-256 `de013a119dc2e9c4d22cd23576e5e1c01bd4737b23213a61655a12e151316cdb`，有效配置仍为 `mode=NONE + cudagraph_mode=FULL`，PID `872084`，健康端点通过。相同请求 SHA-256 `8a926c...` / `706ff7...` 再次精确返回 `OK`、`5`，响应 SHA-256 为 `9644f403...` / `7c4ca601...`。
- precision-casts 最小复验：`04-runs/torch-compile-silu-and-mul-with-clamp-precision-casts-20260922-01/`。在全新 Inductor cache 和 `TORCHINDUCTOR_EMULATE_PRECISION_CASTS=1` 下，完整 clamped SwiGLU、去 clamp SwiGLU、clamp-only 三组均与 eager 逐元素一致，`max_abs=0`、`mean_abs=0`、`equal=true`；reproducer/result SHA-256 分别为 `59320c87479db160f0ae9c3b79de2cafca81e904b239927af388048059919cfb` / `d594174fa6aa4320664c128513d9059ce6fd4b4ac57151808bf715165c687c0b`。
- precision-casts 整模反证：`04-runs/torch-compile-verify-precision-casts-20260922-08/`。相同开关、全新 vLLM/Inductor cache、TP8+EP、`cudagraph_mode=NONE` 下，8 个 rank 仍全部触发 `incorrect results of backend`；最终 BF16 输出形状均为 `(1024,4096)`，差异摘要为 `max_abs=nan`、`mean_abs=nan`，说明结果中存在 NaN，服务未进入就绪状态。失败整图覆盖 86 层 MHC/MoE/collective/末端 RMSNorm，不能从该结果把第二处分叉归到单个算子。
- 整模反证后再次恢复 `04-runs/final-graph-restored-20260922-02/`，新 PID `893031`，健康端点 `200`。相同两条固定请求再次精确返回 `OK`、`5`；本轮响应 SHA-256 为 `14f93d72e9217cbde131dd4c23d93bcba79aa6b97fcb0dc433f79664d37375b3` / `c747ffeaf5604ac8b58b75cf8b2e4672af184e6eea175422a66081df4c46052e`。
- Plugin 相关回归：`72 passed, 3 skipped`。vLLM 工作树干净；Plugin 42 个任务暂存路径，唯一未暂存路径为含用户原有 `linear` 的 `metax.yaml`；FlagGems-vllm 4 个任务暂存路径且无未暂存差异。
- 新增 Plugin dispatch 定向单测：`04-runs/20260922-opaque-plugin-dispatch-unit.log`，`18 passed in 28.09s`，退出码文件为同名前缀 `.rc` 且值为 `0`。
- 新增 fullgraph dispatch 数值验证：`04-runs/20260922-opaque-plugin-dispatch-compile.log`。实际选择均为 `default.flagos`；clamped SwiGLU、MHC pre、MHC post、HC head 均对 reference 通过，退出码 `0`。日志末尾沿用复现脚本旧的 `pt2` 结果标签，但本次实际源码已是 opaque FlagGems bridge。
- 通用 RMSNorm 补充验证：`07-bugs/dsv4_rms_dispatch_compile_repro.py` 与 `04-runs/20260922-opaque-rms-dispatch-compile.log`。无 residual 与 fused residual 两条路径均在 `torch.compile(fullgraph=True)` 下通过 reference 数值对照，选择 `default.flagos`，退出码 `0`。
- 首次 TP8+EP 全模型 opaque-dispatch compile 验证位于 `04-runs/torch-compile-opaque-dispatch-20260922-01/`。Inductor 生成模块实际调用 `torch.ops.vllm_fl.flaggems_dsv4_mhc_pre_rms_norm.default`，证明目标路径进入 Plugin dispatch 后调用 FlagGems；图编译完成，但 warmup 在 FlagGems MHC-pre 的 module-level `WeakKeyDictionary[Tensor]` 查询中触发 Tensor 比较 dispatch，报 `bool value of Tensor with more than one value is ambiguous`，API 未就绪。
- FlagGems MHC BF16 缓存已改为 `data_ptr + _version + is` 的身份缓存并保留 Tensor 强引用，避免指针复用；定向测试包含缓存布尔安全、in-place version 刷新、pointwise balance-grid 隔离及目标算子，共 `15 passed in 1.35s`。同一冻结配置的 run02 不再复现该启动故障。
- 完整重试 `04-runs/torch-compile-opaque-dispatch-20260922-02/` 使用全新 vLLM/TorchInductor/Triton cache、TP8+EP、`cudagraph_mode=NONE`。`torch.compile` 与首次 profiling/warmup 用时 `140.06 s`，Engine 初始化总计 `256.05 s`，健康端点返回 `200`。但该轮有效配置是 `custom_ops=['none']`：Plugin policy 日志显示 `default.flagos` 不等于 vLLM OOT CustomOp 在外层编译图中已启用，因此它只证明 compile 服务可启动，不能作为“所有目标 FlagGems 算子均在整模路径生效”的证据。
- 但 run02 的两条冻结请求虽然均返回 HTTP 200，内容分别为 `y licensieradfmосновнимkadb不及待aka` 和 ` -banay.”#/MODIS neperian factorisateдарном рођено kinaugahan`，而不是期望的 `OK`、`5`。因此结论是“compile 链路可启动，但模型语义仍错误”，不能恢复为生产配置。请求 SHA-256 仍为 `8a926c...` / `706ff7...`，响应 SHA-256 为 `3fc47cfc...` / `76852518...`。
- 变更后 Plugin、FlagGems `git diff --check` 均通过。Plugin HEAD 保持 `fd5c727fcdb607bc4354cd11384761bb5d5ecfba`，FlagGems HEAD 保持 `711cf839c4ee5557776c626e1f8b20cc4007fa63`；没有 commit、push 或重新暂存。
- run02 结束后恢复 `04-runs/final-graph-restored-20260922-04/`，启动脚本 SHA-256 为 `b30216b7...`；当前 PID `1226545`，有效配置为安全 mitigation `mode=NONE + cudagraph_mode=FULL`，decode FULL graph 捕获 `1/1`，健康端点 `200`。相同请求精确返回 `OK`、`5`，响应 SHA-256 为 `aad1e44b...` / `2e276660...`。
- 为排除 run02 的 `custom_ops=['none']` 干扰，新增严格对照 `04-runs/torch-compile-customops-all-20260922-01/`：TP8+EP、全新 cache、`VLLM_COMPILE + backend=inductor + custom_ops=['all'] + cudagraph_mode=NONE`，前缀缓存保持开启。`torch.compile` 用时 `136.82 s`，Engine 初始化总计 `298.09 s`，健康端点 `200`。生成缓存中实际出现 `flaggems_dsv4_hc_head` 24 次、`flaggems_dsv4_mhc_post` 192 次、`flaggems_dsv4_mhc_pre_rms_norm` 192 次、`flaggems_rms_norm` 24 次；原生 `sigmoid`/`clamp` marker 均为 0。共享专家激活被包在 opaque `vllm.moe_forward_shared` 边界内（计数 96），因此不能从外层生成代码宣称独立 `flaggems_silu_and_mul_with_clamp` 已出现。
- 上述 `custom_ops=['all']` 对照的两条固定请求均为 HTTP 200，但第一条返回空串，第二条返回 `vernipikaانزياح`，而非 `OK` / `5`；响应 SHA-256 为 `142f914e...` / `b07d04fd...`，`result.txt` 标记 `FAIL_SEMANTIC_CORRECTNESS`。这证明 `custom_ops=all` 确实改变了实际编译图，但它本身不足以修复当前主线栈的整模语义。
- 两个新增 opaque 边界后的完整验证为 `04-runs/torch-compile-piecewise-verify-20260923-05/`：8 个 rank 的 44 个 piecewise 段全部执行 eager-vs-Inductor 对照，汇总 `352/352 PASS`、`MISMATCH=0`、`ERROR=0`，所有实际比较 Tensor 均逐元素一致。服务健康端点 `200`，冻结请求精确返回 `OK` / `5`；响应 SHA-256 分别为 `19497d518e3cb59cbb849c348250ab8dbd170b7aedd605f79743951ee4394ac1` / `dade22e4ddaaf7e82e51ad9a03fb74c3cbc9bf287e290f0277640aae6931f24d`。这取代了此前“剩余分叉仍未定位”的结论，但适用范围仍限于 `cudagraph_mode=NONE` 与本次固定输入。
- 两个 opaque contract 的联合 Plugin 定向单测于 2026-09-23 通过：`test_flaggems_fused_q_kv_rmsnorm_uses_opaque_contract` 与 `test_flaggems_inv_rope_quant_int8_uses_opaque_contract` 合计 `2 passed in 27.12s`；随后 Plugin `git diff --check` 退出码为 `0`。
- 诊断结束后的安全恢复运行是 `04-runs/final-graph-restored-20260923-06/`，PID `2119960`，有效配置 `mode=NONE + cudagraph_mode=FULL`，decode FULL graph 捕获 `1/1`，健康端点 `200`。两条冻结请求再次精确返回 `OK` / `5`，响应 SHA-256 为 `428627421178f46c0cae1a3b143710713108f04f507cd4d0a297d6cb8ac88906` / `7ff30be8f1d365a12097df273a061b0aef61cc1ecd462cef17ce760ea618e67a`；本轮实际进程环境已核验 `FLAGGEMS_CACHE_DIR` 指向 `06-cache/flaggems-safe-restore-20260923-06`。
- 无诊断层整模验证 `04-runs/compile-clean-20260923-07/`：TP8+EP、`VLLM_COMPILE + backend=inductor + custom_ops=['all'] + cudagraph_mode=NONE`，前缀缓存开启，独立 vLLM/Inductor/Triton/FlagGems cache；实际引擎配置确认 `CompilationMode.VLLM_COMPILE`。初始化 `269.32 s`（编译 `136.69 s`），健康端点 `200`；与历史失败轮次 SHA-256 完全相同的两条冻结请求均为 HTTP 200 且精确返回 `OK`、`5`。生成图实际包含 `flaggems_dsv4_fused_q_kv_rmsnorm` 与 `flaggems_dsv4_inv_rope_quant_int8`，请求后未检出 ERROR/Traceback/incorrect-results。`result.txt` 和原始响应保存在该运行目录；这证明修复在普通服务路径生效，而不仅是诊断层对照。
- 单变量开启图捕获的 `04-runs/compile-fullgraph-20260923-08/`：请求 `cudagraph_mode=FULL`，实际引擎为 `VLLM_COMPILE + inductor + custom_ops=['all']`；MetaX 的 `DeepseekV4IndexerBackend` / `DeepseekV4FlashMLABackend` 只声明 `AttentionCGSupport.UNIFORM_BATCH`，8 个 rank 均自动降为有效模式 `FULL_AND_PIECEWISE`。实际捕获 mixed prefill-decode PIECEWISE `2/2` 和 decode FULL `1/1`，初始化 `283.95 s`（编译 `122.03 s`），健康端点 `200`。同两条冻结请求均精确返回 `OK`、`5`；10 个并发重复固定请求 `10/10` 正确（客户端总耗时 `4.945 s`）；额外长输入 `3624` prompt token，超过 `max_num_batched_tokens=1024`，仍以 HTTP 200 精确返回 `OK`。生成图仍包含上述两个修复算子，请求后未检出严重运行错误。`result.txt`、响应、并发及长输入原始结果在运行目录。此轮证明 compile 与 decode FULL/mixed PIECEWISE 图组合的功能性，但不能声称 prefill+decode 全链路 FULL 图。
- 验证后恢复到 `04-runs/final-graph-restored-20260923-09/`：PID `2753108`，有效配置 `mode=NONE + cudagraph_mode=FULL`，decode FULL 捕获 `1/1`，Engine 初始化 `255.29 s`，健康端点 `200`；两条冻结请求精确返回 `OK` / `5`，响应 SHA-256 为 `4f06920df77b94fbe4cf95fce4156f2a64622149cd78647ca272627235179e1e` / `92d8270e2ad223a59fb8b97cfd2a105d1c1ec514048a0d77632e0dec7df4cc79`。实际进程环境的 `FLAGGEMS_CACHE_DIR` 已核对为 `06-cache/flaggems-safe-restore-20260923-09`；`result.txt` 位于该运行目录。容器未停止、重启或删除。
- 验证结束后精确停止 PID/PGID `1251006`，安全恢复运行为 `04-runs/final-graph-restored-20260922-05/`。启动脚本 SHA-256 `0dd737f5...`，当前 PID/PGID `1432353`，健康端点 `200`，decode FULL graph 捕获 `1/1`；同一请求精确返回 `OK` / `5`，响应 SHA-256 为 `d32270a8...` / `95db0f41...`。

## 服务操作记录

- 为以最终脚本复验，停止本任务拥有的 run34 PID `618257`，TERM 正常退出，`forced=0`；记录在 run34 `shutdown.txt`。
- 为执行单变量 backend 对照，停止诊断前服务 PID `651317`。该进程组不响应 TERM/INT，最终在重新核验 API/EngineCore PID 和父子关系后仅终止 PID `651317/651529`；命令和结果记录在 backend-eager run01 `shutdown-current.txt`。
- 前两次停止重试各遗留一个重复诊断实例，导致 run01 因 GPU 空闲 `54.27 GiB < 57.23 GiB` 失败；精确清理重复进程组 `681322/681331` 后作废 run01。run02 暴露独立 RLock graph break后停止，run03 完成有效对照。
- run03 验证完成后仅终止其进程组 `687304`，再以原参数启动恢复运行。未停止、重启或删除 `deepseek` 容器；恢复服务 PID `718293` 保持运行。
- 本轮 verifier run05 因验证器重复执行整图而触发 vLLM MoE 层索引状态断言；在诊断层于 reference/candidate 之间复位 `moe_layer_index` 后，run06/07 才得到有效整图数值对照。该断言是校验工具与有状态 forward context 的冲突，不是模型根因。
- run06 失败后遗留 PGID `855148`（API、EngineCore、Inductor compile workers）且不响应 TERM；核验进程组所有成员均属于本次 verifier 后进行精确清理。随后启动恢复服务 PID `872084`。全程未停止、重启或删除 `deepseek` 容器。
- 为验证 precision-casts 开关，先核验并停止本任务恢复服务 PID/PGID `872084`，启动 verifier run08 PID/PGID `884427`。run08 在 8-rank 整图正确性检查失败后自行退出，未遗留 vLLM 服务进程；随后按原安全参数恢复服务为 PID `893031` 并完成健康与固定请求回归。全程未停止、重启或删除 `deepseek` 容器。
- 为验证 opaque Plugin→FlagGems 路径下能否重新开启 compile，先核验并停止本任务服务 PID/PGID `893031`。run01 PID/PGID `914357` 在 MHC 缓存故障后自行退出；首次恢复 run03 因同一缓存故障自行退出。修复 FlagGems 缓存后，run02 PID/PGID `1041408` 完成启动和两条请求，验证结束后对精确进程组发送 TERM 并正常停止。随后启动安全恢复服务 run04 PID/PGID `1226545`，完成健康与 `OK`/`5` 对照。全程未停止、重启或删除 `deepseek` 容器。
- 为验证 `custom_ops=['all']` 的真实整模效果，核验并 TERM 停止 run04 PID/PGID `1226545`，启动对照运行 PID/PGID `1251006`。固定请求完成且语义失败后，只对该精确进程组发送 TERM，验证已退出且端口不再健康；再启动安全恢复 run05 PID/PGID `1432353`并完成健康、CUDA Graph 与 `OK`/`5` 验收。未停止、重启或删除 `deepseek` 容器。
- 为继续逐子图定位，先结束此前本任务拥有的恢复服务，再启动 piecewise run02–run05。run05 PID `1868631` 完成 352 段与两条固定请求后，仅对该 PID 发送 TERM；API、EngineCore 和 worker 均确认无残留。随后启动安全恢复 run06 PID `2119960`，decode FULL graph、健康端点和 `OK`/`5` 均通过。全程未停止、重启或删除 `deepseek` 容器。
- 为完成用户要求的整模验证，仅对本任务原安全服务 PID `2119960` 发送 TERM，确认 API 与 worker 退出后启动 run07。run07 PID `2323435` 验证完成后仅对该 PID 发送 TERM，确认退出且 worker 无残留，再启动 run08。run08 PID `2521907` 完成图捕获、固定请求、10 并发与长 prefill 后仅对该 PID 发送 TERM，确认 API 与 worker 退出，随后启动安全恢复 run09 PID `2753108` 并完成健康及固定请求回归。所用启动脚本位于 `01-environment/start-compile-validation-20260923.sh` 与 `01-environment/start-safe-restore-20260923-09.sh`，SHA-256 分别为 `732b3c6b9ebf59d6fa62ef0fcbbd267a2203d77afaf55bffcdc4b2b445f87e75` / `4ed8985ca4a5ecfb67a58dd904a131550c0c96eddc01d61ee6733c15407edffd`；容器未停止、重启或删除。
- 早期 verifier 的临时诊断改动已反向应用并保存在 `02-issues/torch-compile-diagnostics-final.patch`（SHA-256 `bc39ebdc02c4b1a9b826aa2a82af53a93679acd58e6674c7c018bea19b547621`）。随后按用户要求加入的 Plugin→FlagGems dispatch 与 FlagGems cache-key 修复有意保留为未提交工作树差异；既有 PR 暂存内容未被重写，部署前备份位于 `05-tmp/plugin-dispatch-update/pre-opaque-20260922/`。
- 本轮 Plugin/FlagGems 定向测试与复现均未停止、重启或删除 `deepseek` 容器，也未停止或重启现有 PID `893031` 模型服务；只启动了短生命周期测试进程，完成后均正常退出。

## 限制与下一步

- standard torch.compile graph 已实锤存在 MetaX Inductor/PT2-Triton 语义错误。此前已确认纯 ATen BF16 融合会消除 eager 中间舍入；本轮进一步确认 vLLM/Plugin Triton kernel 被 `triton_kernel_wrapper_mutation` 展开时，当前栈在两个模型关键算子上产生大幅错误。缺失 `specialize_impl` 是独立确认的接口兼容缺陷，但仅补该接口不修复数值错误，不能认定为唯一根因。两个模型算子均通过 `dispatch -> default.flagos -> opaque custom op -> kernel` 隔离错误展开；无诊断层的 compile 服务、decode FULL + mixed PIECEWISE 图服务、固定请求、10 并发和长 prefill 已通过。仍需正式 accuracy 后，才能考虑替换当前生产 mitigation。
- 本轮不是正式 acceptance：未执行 accuracy 数据集或 performance；不得声明 optimized。
- 主修复归属仍优先在 mcPytorch/Inductor 与 PT2-Triton 兼容层；`specialize_impl` API 不兼容另案处理，当前 FlagTree 主线升级不足以解决。Plugin opaque bridge 已证明能恢复本模型的 TP8+EP compile 服务以及 decode FULL / mixed PIECEWISE 图下的所测请求，但它是针对当前编译器缺陷的受控隔离，不替代上游根因修复，也不能外推为所有 shape、请求和图模式已正确。
- 已按“单算子最小复现 → 8-rank piecewise verifier → 无诊断层 compile 服务 → compile + 图捕获服务”顺序验证。全链路 FULL 图的当前阻塞是 DeepSeek V4 indexer/MLA backend 只支持 `UNIFORM_BATCH`，vLLM 因此把请求的 FULL 降为 FULL_AND_PIECEWISE；若要达到 prefill+decode 全量图，需先适配并验证这些 backend 的图捕获能力。下一步是冻结正式 accuracy 计划并按 profile 的 execution-mode、sanity、accuracy 顺序验收；本轮 10 并发是定向 smoke，不能冒充正式回执。正式结果未就绪前保留当前 `mode=NONE + cudagraph_mode=FULL` 安全配置。

## 经验沉淀

- 知识库处理状态：`needs-validation`
- 候选条目：MetaX 上区分 CUDA Graph 捕获错误与 torch.compile 语义错误的单变量诊断序列。
