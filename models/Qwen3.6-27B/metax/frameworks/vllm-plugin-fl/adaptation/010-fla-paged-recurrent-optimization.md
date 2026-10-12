# 010：FLA paged recurrent 的布局转换与 MetaX 优化

2026-09-24；Qwen3.6-27B / MetaX / mx-58 / vllm-plugin-fl。状态：用户取消，未实现、未验证收益。

用户最新指令将范围收窄为 Flash Attention，不再优化 GDN decode。以下为已取消的设计历史，不是待执行计划。未修改任何产品源码。初始 GDN 基准进程 976650 已自行以 rc=1 退出，PID 查询确认不存在；没有停止容器或现有推理服务，也不重试该基准。过程产物保留在本文列出的远端目录，不作为成功基线或性能结论。

## 用户范围与现场身份

用户本轮明确要求优化FlagGems-vllm的FLA，公共优化归公共FLA，硬件特化归MetaX。本轮按该最新指令对既有 `/workspace/FlagGems-vllm` 做限定算子修改，覆盖前轮对该组件的只读限制；不扩大为FlagGems/vLLM修改，也不修改全局profile的源码策略或宣称通过原profile正式验收。Plugin只允许为新布局契约做必要接线，FA、vendor GDN、黑名单机制不变。

运行容器qwen3.6-27B，ID `fbff98cc36ac7fce4026538d33455a66c6ae165aa19496ed738790616f0f92e9`，保持running；镜像同009。Host/容器 `/public-flash` 同路径RW bind，工作根均为 `/public-flash/jinghao/qwen3.6-27B`。FGV editable安装0.1.0，导入`/workspace/FlagGems-vllm/src/flaggems_vllm/__init__.py`，HEAD `05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777`，clean。Plugin editable0.2.0/HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，继承009的7 tracked+4 untracked。vLLM HEAD `bc150f50299199599673614f80d12a196f377655`及既有fused_recurrent.py修改保留；FlagGems HEAD `c6f46cc970ea0bef8927ee657c021bd8621e3bb0` clean。使用 `/opt/conda/bin/python3`，系统python3无这些依赖。

FGV AGENTS、workflow、README及现有recurrent/test/benchmark已读；所引用optimization.md、deep_opt.md在checkout不存在，不能声称使用。workflow里的conv1d示例不是本轮任务。这里不新增算子族、不同步升级依赖、不提交或推送；PR base未确认。

## 性能签名与候选方案

用户9月23/24两组trace真实kernel统计：rank0总170.976→342.781s；FA增87.423s，Plugin `_transfer_state`增76.060s，recurrent本体增7.655s。recurrent调用均49152，转换98304。GEMM/排序基本一致；rank1趋势一致。该trace只用于定位，不作严格受控端到端测速。

本轮只优化FLA/GDN，不改Flash Attention。候选一：显式paged state布局契约，kernel按真实stride直接读写V-major，去掉Plugin pack/unpack。公共实现只表达layout/dtype/alias语义，MetaX配置经现有customized_ops机制选择。候选二（只有第一轮正确且性能不足才考虑）：MetaX改变BV/warp分工。避免同时更改gate融合与布局；不将既有K-major调用静默解释为V-major。旧API默认行为保留。

## 编码前三表：项目真相

| 字段 | 冻结内容 |
| --- | --- |
| Current op | FGV `fused_recurrent_gated_delta_rule_fwd`，vLLM GDN decode forward；无对应单一torch API，参考为固定vLLM/FGV源码与独立FP32递推公式 |
| Editable files | FGV公共FLA、MetaX ops/导出、对应维护性tests/benchmark；Plugin FlagOS recurrent适配及对应测试。不得改vendor GDN/FA/vLLM/FlagGems |
| Read-only | 既有reference/benchmark和前轮证据冻结；新增A/B基准在首次baseline后冻结 |
| Build | editable Python/Triton，无wheel重装；语法/导入、JIT首次编译；格式化black/isort及flake8检查变更文件 |
| Validation | 独立FP32参考，eager及至少两次变输入graph replay；BF16/FP16输出atol0.002、rtol0.02，FP32单独更严阈值；原位存储、padding/null精确不变 |
| Benchmark | 同GPU2、固定seed41、显式warmup、多轮CUDA graph event计时；报告每case中位us与旧适配链路/新kernel比，不把torch循环参考计入性能优势 |
| Active set | 重点N=1,4,16,64，H8/HV24/K128/V128，BF16 QKV和FP32 state，mixed-QKV stride，page padding0/8192；功能扩展N128/256及非方形K/V、FP16/FP32、小/空/非法/空槽 |
| Aggregation | 逐case报告，重点N64，不以平均掩盖关键回归；既有N>64分支布局与N<=64不一致，未经正确性对照不得将其当性能基线 |
| Timeout | 导入/collect 180s，定向测试600s，单轮微基准300s；超时保留失败不静默重试 |
| Profiler | 已有torch trace可用；本轮独立算子event/graph timing，必要时限定kernel torch profiler；不假定NVIDIA ncu支持MetaX |
| Autotune | 先固定保守tile；MetaX显式有界候选BV=4/8/16/32、warps=1/2/4单变量试验。新路径in-place，禁止无state restore的在线autotune。NVIDIA本轮不调优，明确豁免新增NVIDIA自动搜索，公开实验layout路径不声称NVIDIA性能达标 |
| Fallback | 无torch计算fallback；未命中新显式layout的旧调用保留原路径；新路径不支持的元数据组合显式报错 |

## 编码前三表：契约

| 字段 | 内容 |
| --- | --- |
| Device/backend | 本轮GPU测试MetaX C550；公共新路径其他平台仅代码/导入边界，不宣称硬件验证 |
| Input | Q/K `[1,T,H,K]`，V `[1,T,HV,V]`，HV可整除H，支持实际strided投影视图；gate标量perhead，beta标量perhead或pervalue；state显式V-major或K-major，四维真实stride；单步连续batch，cu_seqlens长度N+1，T=N含图padding |
| Output | 与V同shape/dtype；state原位时返回原对象，不改storage/stride；空槽和padding不写；新路径默认null策略不得改变旧API索引0有效语义 |
| Dtype | Q/K/V FP16、BF16、FP32（同dtype）；state FP16/BF16/FP32；FP32累计；g/beta浮点。其它dtype/device不支持 |
| Semantics | 数值顺序与参考递推一致；QK norm为rsqrt(sum(x*x)+1e-6)。活跃state索引必须有效且唯一，负索引和显式null槽不写；空序列/图尾padding输出清零。NaN/Inf/signed-zero按传播检查，不承诺逐bit等价 |
| Autograd | 只覆盖推理forward，不新增backward/KDA/speculative/多token递推保证 |
| Unsupported | 新显式布局只支持上述单步continuous decode；其它调用保留旧API，不扩大为任意fallback。初始state、cu、indices缺失或元数据不匹配拒绝 |
| Reference torch | 仅tests/benchmark/process reference使用，生产仅元信息/empty/no-copy view和Triton |

## 编码前三表：路径

| 路径 | 条件/实现 | 配置 | 测试/风险 |
| --- | --- | --- | --- |
| empty | T=N=0，返回空output和原state | 无autotune | alias无写入 |
| common explicit-layout | 明确layout + 单步continuous；真实state/QKV strides直接计算 | 保守tile，显式in-place autotune豁免 | 非方形、page padding、slot0策略、空序列、两次replay |
| MetaX specialization | 同语义，经FGV现有vendor replacement选tile/warp | 单变量受控候选 | 真实N64和N边界，保留公共契约 |
| legacy | 未指定新layout | 现有实现不改数值语义 | 原接口/导出/guard miss，既有测试弱点单列 |
| unsupported | 新路径非法metadata、speculative/KDA等 | 显式NotImplementedError/ValueError | 不以torch回退，不吞异常 |
| external library | 无新增 | 无 | 无 |

## 状态与限制

GPU2/3已用mx-smi核实低占用且无模型权重；现有GPU0/1与6/7服务不动，先做独立算子测试。过程产物拟放`02-issues/fla-paged-20260924/`、`04-runs/fla-paged-20260924/`、`05-tmp/`、`06-cache/fla-paged-20260924/`。本轮不是正式第4阶段验收，不更改已有环境身份以伪造当前通过。
