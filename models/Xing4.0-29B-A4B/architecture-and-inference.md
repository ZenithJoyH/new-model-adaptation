# Xing4.0-29B-A4B 架构与推理路径

## 对象与证据

本轮对象是 `PPU-13` 的只读权重目录
`/mnt/cpfs/models/Xing4.0-29B-A4B`。2026-09-16 已核对：

- `config.json` SHA-256：`253e6742d5be0094fd03d79d65cead200de11c5962be9220f8117d978bbe3cc8`；
- `model.safetensors.index.json` SHA-256：`b8aaf0fef435f8ca85448a19e50bb6a3776c8753ff896751b879d6cf5f3818e2`；
- 41 个 safetensors 分片、8,307 个索引键，索引声明 tensor 数据总量
  `62,430,071,008` bytes；
- 配置身份为 `architectures=["Xing4_0ForCausalLM"]`、
  `model_type="xing4_0"`，远程代码入口为 `configuration_xing4_0.py` 和
  `modeling_xing4_0.py`。

目录未提供可验证的模型仓库 revision，因此上述路径、哈希和权重索引是本轮身份边界；
不能把同一索引哈希解释为两个目录具有相同配置或发布身份。

参考实现为 vLLM PR
[#57135](https://github.com/vllm-project/vllm/pull/57135)，核对时状态为 draft，head
`25aa52a29131753c10e56528d3fa0c4464cead63`。该 PR 提供原生
`Xing4_0ForCausalLM`、配置注册、reasoning/tool parser、DSA/非 DSA 和 MTP 接口，
但其 `USE_FLAGOS` 是进程级 PyTorch dispatch 原型。本任务使用 vLLM Plugin 的既有
dispatch/backend 策略，不把该全局开关搬入模型实现，也不修改 vLLM 源码。

## 模型结构

- 主干为 40 层、hidden size 3584、词表 131072、BF16，embedding 与 LM head
  不共享权重。
- 第 0～1 层使用 dense SwiGLU，intermediate size 9216；第 2～39 层为 MoE。
- MoE 含 64 个 routed experts、每 token top-4、1 个 shared expert；每个 expert
  intermediate size 1024。router 使用 sigmoid、`noaux_tc`，selection 使用
  FP32 correction bias，归一化 top-4 权重后乘 `routed_scaling_factor=2.0`。
- attention 为 DeepSeek-V2/V3 风格 MLA：32 heads，Q LoRA rank 768，KV LoRA
  rank 512；每 head 的 non-RoPE Q/K 为 128，RoPE 为 64，V 为 128。
- RoPE 使用 YaRN：theta 10000、factor 64、原始长度 4096，配置声明最大上下文
  262144。初始服务配置按工作流取 `min(262144, 50000)=50000`，但这只是适配启动值，
  不是 262144 长上下文已经通过验收的结论。
- 每个 attention/FFN 子层均使用 mHC。`hc_mult=4` 表示 4 路残差流，输入 embedding
  展开到 `[tokens, 4, 3584]`，末层均值收缩回单路。
- 权重还包含 1 层 MTP（`num_nextn_predict_layers=1`）。本轮常规因果生成不启用
  speculative/MTP，loader 必须明确跳过对应层；这不代表 MTP 已被验证或支持。

## mHC 数学与权重协议

本轮只接受新协议：每个 mHC 单元直接加载 `hc_fn`、`hc_base`、`hc_scale`，不为旧
`mapping_weight`、拆分 bias 或 `alpha_*` 添加兼容映射。

对 4 路、3584 维残差流，`hc_fn` 为 `[24, 14336]`，`hc_base` 为 `[24]`，
`hc_scale` 为 `[3]`，其中 24 分解为 pre 4、post 4、combination 16。projection
之后在 FP32 中形成三组 affine：pre 使用 sigmoid，post 使用两倍 sigmoid；4×4
combination logits 按配置夹到 `[-30, 30]`，减行最大值后取 exp，再执行 20 轮
row/column Sinkhorn，epsilon 为 `1e-6`。组合矩阵随后混合旧残差流，post 权重混入
子层输出。权重成功加载不能替代该数值协议的 eager/graph 对照。

## 端到端张量与执行路径

1. tokenizer/chat template 生成 token ids，BOS/EOS/PAD 分别为 1/2/3；reasoning 和
   tool-call 边界必须沿用模型模板协议。
2. embedding lookup 得到 `[T,3584]`，复制/reshape 为 4 路 mHC 残差流。
3. 每层 attention 前执行 mHC pre 聚合、RMSNorm、Q/KV 低秩投影、部分维 RoPE、
   paged MLA attention、输出投影，再执行 mHC post 混合。
4. FFN 前再次执行 mHC pre 与 RMSNorm；dense 层运行 SwiGLU，MoE 层运行 router、
   top-k、expert dispatch/combine 和 shared expert，再经 mHC post 回到 4 路残差。
5. prefill 写入压缩 KV cache；decode 通过 block table/slot mapping 读取和追加 cache。
   调度 metadata、KV 所有权、chunked prefill 和 graph replay 都是集成风险点。
6. 最后对 4 路残差取均值，执行 RMSNorm、LM head 和 logits processing；采样路径还会
   使用 softmax、top-k/top-p、RNG 或 argmax。

## 关键算子清单

- mHC：RMS 统计、linear/mm、FP32 affine、sigmoid、clamp、max/sub/exp、固定轮次
  sum/div、矩阵混合、transpose/contiguous。
- normalization/position：RMSNorm、Q/K norm、YaRN RoPE。
- MLA：Q/KV/O projection、reshape/split、paged attention、softmax、KV-cache 写入/读取。
- dense/MoE：gate/up/down GEMM、SiLU、逐元素乘；router GEMM、sigmoid、top-k、
  gather、expert dispatch/combine、shared expert。
- 输出与采样：mean、RMSNorm、LM-head GEMM、logits gather、softmax/top-k/top-p/argmax。
- 并行通信：tensor-parallel row/column projection 的 all-reduce/all-gather；专家与
  logits 的实际通信路径取决于 vLLM/Plugin 实现。本轮配置 `ep_size=1`，不据此声称
  expert parallel 已支持。

## 并行和适配约束

静态维度可被 TP4 整除：32 heads 每 rank 8 heads，3584 hidden 每 rank 896，Q/KV
LoRA rank 768/512 也可整除。mHC 的 4 路是模型语义，不是 TP 轴，每个 rank 保留完整
stream 维。配置和既有 Plugin 路径要求 BF16、PP1；PP>1、DSA、MTP/speculative、量化
均不纳入本轮已验证范围。TP4 是否正确仍需以真实权重加载、collective 顺序、KV-cache、
prefill/decode 和 graph replay 实测，不能由可整除性直接推出。

## 适配决策与风险

- 新配置身份与当前 Plugin 的 `XingChen4ForCausalLM/xingchen4` 注册不匹配；应增加
  正式的 `Xing4_0ForCausalLM/xing4_0` 模型和 config 注册，不按目录名在 worker 热路径分支。
- 模型主体可复用现有 XingChen4 的 DeepSeek-V2 MLA/MoE 组装和 Plugin mHC dispatch，
  但新入口必须直接读取新配置字段并严格加载新权重，不保留旧协议兼容分支。
- PR #57135 自述的 mHC bias/clamp 仍是待确认正确性项；本轮以 checkpoint 自带
  `modeling_xing4_0.py` 和实际张量为语义基准，并通过 focused 数值测试验证。
- 现有 PPU Plugin checkout 含任务开始前的继承改动；本任务必须区分 inherited diff 与
  新增 diff，避免覆盖 `vllm_fl/dispatch/config/thead.yaml` 的现有 blacklist。
- `262144` 是配置能力声明，不是适配验收结果。正式长上下文、精度和性能属于后续
  acceptance 阶段，本轮只执行用户批准的 architecture、environment、adaptation。

## 未决项

- 发布方 revision、正式基线精度与推荐采样参数尚不可验证。
- PR #57135 仍为 draft，其原生实现和 parser 契约可能继续变化。
- PPU 上 eager/graph 的 mHC、MLA prefill/decode、TP4 与完整模型加载结果必须在
  adaptation 的增量验证中给出；其他平台未获授权且不作支持声明。
