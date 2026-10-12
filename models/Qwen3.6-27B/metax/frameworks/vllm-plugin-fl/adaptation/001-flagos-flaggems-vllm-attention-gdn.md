# 001：FlagOS dispatch 接入 FlagGems-vLLM Flash Attention 与 GDN

> 历史记录：本文件描述首次实现及其当时的证据，不再代表当前 Plugin 源码。
> 用户指出 FA 重复分发和 GDN hook 位于 vendor 的所有权错误后，已按
> [002：纠正 FlagOS 所有权](002-correct-flagos-ownership.md) 修正；旧源码身份、
> 六文件 diff 与首次路由/冒烟回执不可用于证明当前实现。

## 元数据

- 状态：`superseded-by-002`（仅保留首次实现与诊断历史）；首次出现与最后核实：2026-09-23。
- 模型：Qwen3.6-27B，dense Qwen3.5，48 层 GDN、16 层全注意力。
- 平台与 Host：MetaX C550，`mx-58`；容器 `qwen3.6-27B`，镜像见环境分析。
- Plugin `675548ab2ee52b8124b0b6a82a2f795c0553e1fa` 开始时 clean；FlagGems
  `c6f46cc970ea0bef8927ee657c021bd8621e3bb0` clean；FlagGems-vLLM
  `05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777` clean；vLLM
  `bc150f50299199599673614f80d12a196f377655` 有继承的 recurrent 修改，不写入。
- 基线为旧服务 TP2/设备 6,7，带 profiler 和性能专用 prefix-cache 关闭参数；
  不能用作本轮非性能数值/graph 结果。

## 现象、根因假设与已有经验

Plugin FlagOS `attention_backend` 虽有 `VLLM_FL_USE_FLAGGEMS_ATTN` 分支，当前 MetaX
策略仅列 `vendor:metax`，旧服务实际选择 MACA Flash Attention 2.6.3。
GDN 层经 Plugin MetaX patch 进入 `torch.ops.vllm.gdn_attention_core` 后，prefill 为
vLLM FLA chunk，普通 decode 优先 packed recurrent；FlagGems-vLLM 未被选择。
Profiling 结果与启动日志吻合，不能据环境变量代码存在就声称已命中。
这一路由根因已由 flag 关/开对照验证：关时 `vendor.metax`，开时新增策略选择
`default.flagos`。GDN 初版数值对照还查明另一独立 ABI 差异：vLLM 缓存状态按
V×K，而本镜像 MetaX FlagGems-vLLM recurrent kernel 按 K×V；直接传状态虽可运行，
但随机非零 state 最大偏差约 0.06。仅交换 tensor view 不能修复，必须转换参与更新的
状态并回写原缓存。

本地历史 [35B 问题](../../../../../Qwen3.6-35B/metax/adaptation/001-flaggems-vllm-gdn-fused-moe.md)
证明在另一 checkout 上 FGV GDN 的 prefill metadata、FP32 gate/beta 与 decode state
需要专门处理，但该结果没有证明本模型、当前 revision 或当前 dispatch 链路正确。
本轮应逐项复验，不照搬 35B 的 MoE 路径。`docs/troubleshooting/` 未发现完整匹配签名。

## 接口决策与受控修改计划

1. 在 FlagOS `register_ops` 注册 `flash_attn_varlen_func`、
   `chunk_gated_delta_rule_fwd`、`fused_recurrent_gated_delta_rule_fwd`，实现 ID 均为
   `default.flagos`，可用性按 FlagGems-vLLM 导出检查，调用时再惰性导入。
   不直接从模型、worker、MetaX 层调用 FGV kernel。
2. 现有 `AttentionFLBackend` 的所有 varlen FA 调用改走 Plugin `call_op`；
   `VLLM_FL_USE_FLAGGEMS_ATTN=1` 时令 MetaX vendor attention 不可选，policy 从
   `vendor:metax` 进入 `flagos`，未启用时保持 MACA 默认。当前 custom attention
   只支持 FP16/BF16 KV；FGV MetaX 拒绝的 FP8 descale 参数只在该 dtype 前提下
   丢弃，FP8 不冒充支持。KV-cache 写算子仍由现有 FlagGems 路由负责。
3. MetaX GDN patch 仅在 `VLLM_FL_USE_FLAGGEMS_GDN=1` 时把 vLLM 的 prefill/decode
   扩展点接到 `call_op`；prefill 保持 7 值返回与变长 chunk metadata，decode 保持
   FP32 softplus/sigmoid 及 state indices/in-place 语义。普通 decode 关闭 packed
   shortcut，走原通用 core 的 recurrent dispatch；KDA 未由 FGV 覆盖，保持原路径。
   flag 未设置时默认行为不变；不修改 vLLM、FlagGems 或 FGV 源码。
4. 候选替代：MetaX 层直接导入 FGV（绕过 FlagOS，不符合用户所有权要求）；
   整份复制 vLLM GDN core（过大且易漂移）；默认全平台切换 attention（扩大回归面）。
   均不采用。

公共调用方包括使用 custom attention 的其他模型、GDN/Qwen3.5 与 Qwen3-Next、
MetaX vendor 默认路径及其他平台的 Plugin 导入。需分别验证 flag 开/关、dispatch
ID、依赖缺失、prefill/decode 数值、TP2 与 graph capture/replay；不能从单卡或
仅注册成功推断完整模型通过。正式准确率、性能和最终启动器不在本轮第 3 阶段。

## 证据与结果

- 架构与环境先决证据：`01-environment/identity-20260923.txt` SHA-256
  `f2e38e6657f738711250ca2207b63b6c19c796258332e8449db9106b0d40f1ac`；
  `01-environment/framework-check.json` SHA-256
  `b5f8cb57a1d0f749454024e150bd8fd6ba246f924bf9e2c505a5a7b0f2f9ec31`。
  容器内项目门禁 `adapt-model --steps adaptation --check-only --artifact-root ...`
  已通过，直接核验了 Host 工作根回执和原始证据。
- Plugin 仅改 6 个文件、226 行新增/5 行删除，保持 vLLM、FlagGems、FGV 原树不动。
  新增三个 FGV OpImpl，均经 FlagOS `call_op`；MetaX attention 策略默认仍优先
  `vendor.metax`，仅 `VLLM_FL_USE_FLAGGEMS_ATTN=1` 时进入 `default.flagos`；
  GDN 仅 `VLLM_FL_USE_FLAGGEMS_GDN=1` 时安装 Plugin patch。
- 路由对照原始证据 `04-runs/flagos-routing-20260923.txt` SHA-256
  `1e7de985c3fceaf0ffaa5a5f46a5d8321455b156cdcaa503761326e132a72e6d`：
  双 flag 开时 attention/FA/GDN prefill/GDN recurrent 均为 `default.flagos`；
  默认关时 attention 仍为 `vendor.metax`、GDN patch 未安装。
- 首次 recurrent 数值失败保留于 `04-runs/flagos-numerics-20260923.txt` SHA-256
  `9cb6ad43d94cd54264a9e27ec9a027f3166a9c355696a6cd2721b18af335dd77`；
  状态布局诊断 `04-runs/flagos-recurrent-layout-20260923.txt` SHA-256
  `e6f76ae952e7351d4e361fd956e546c5957bd308ecd95c19fce0ea3b2ebe03fa`。
  `ssm_state_indices` 不传时该版本 FGV in-place kernel 编译失败，不能靠省略索引绕过。
  有效索引重映射与仅转换活跃状态的验证见
  `04-runs/flagos-recurrent-adapter-remap-20260923.txt` SHA-256
  `e2cdf2c39227a8b17b8be57adc7ae140af0ced5b8d6504522b9498ca62db9083`。
- 经过状态适配后，模型 TP2 代表形状对照
  `04-runs/flagos-qwen27-tp2-20260923.txt` SHA-256
  `488b49e240a1232eaa83b4f70674840b8eba482594e2b0c14d23c026892c0550`：
  FA prefill Q12/KV2/D256 最大绝对误差 0.000992、paged decode 0.000221；
  GDN prefill key8/value24/dim128 输出 1.59e-5、state 0.000136；两个请求的
  非零初始状态 decode（含 in-kernel L2）输出 7.39e-6、state 分别 1.48e-6/
  1.37e-6，未使用缓存行完全不变。该证据是聚焦算子测试，不是模型级准确率。
- 变更后部署身份 `01-environment/deployment-identity-flagos-20260923.json` SHA-256
  `b760fe1f547ac022ea2dd360f7a64a845f2880db3545464befeb32e3d2ba505f`；
  原生环境回执 `01-environment/framework-check-flagos-20260923.json` SHA-256
  `292ba3b572e64c06ba95dc9c8d0b144b505fbd13f2e8cf019dea53b0fc630296`。
  容器内项目门禁对 environment `--verify-records` 和 adaptation `--check-only`
  再次通过，使用的是新身份，不是历史基线。
- eager 隔离实例：`04-runs/flagos-eager-20260923/launch.sh` SHA-256
  `9089fdb66ef79f889b8219923404b8f030948debe208ba8f021c879fb947ed06`，
  日志 `service.log` SHA-256
  `79a7a1f837498f128d49a8f809ef603e52e927806910cfbdb19e6949d518f44d`。
  TP2/GPU0,1/8001、prefix cache enabled、无 graph；16-token 请求返回 HTTP 200
  且 `completion_tokens=16`。两名 worker 日志均显示 attention、FA varlen、
  GDN chunk/recurrent 为 `default.flagos`。完成后仅停止本轮 PID 306071，
  8001 关闭、GPU0/1 释放、原 8000 服务仍 HTTP 200。
- graph 隔离实例：`04-runs/flagos-full-20260923/launch.sh` SHA-256
  `49f2f9d9031d09ff2c4c04c8975a3f7c6c704d19b4622bb28e58b2a0d620f2aa`，
  精确请求配置 `--compilation-config '{"mode":0,"cudagraph_mode":"FULL"}'`，
  同样 TP2/GPU0,1/8001、prefix cache enabled。日志 `service.log` SHA-256
  `ad38626a0806d26bce9b2fc437d6658e495fb6669177f2fd4691ed868c7b5477`：
  vLLM 在两名 worker 都报 `GDNAttentionBackend` 的
  `AttentionCGSupport.UNIFORM_BATCH` 不支持 `FULL`，自动设为
  `FULL_DECODE_ONLY`；随后 `Capturing CUDA graphs (decode, FULL): 3/3` 完成，
  FA 与 GDN recurrent 在捕获时仍为 `default.flagos`。真实请求回执
  `04-runs/flagos-full-20260923/completion-response.json` SHA-256
  `92d1a7740b0ec2feacc334db2922398b299adf4dedcbe42d7557593eefb69bab`：
  HTTP 200、16 token，与 eager 冒烟输出一致。完成后仅停止本轮 PID 360318，
  8001 关闭、原 8000 服务仍 HTTP 200。这里仅是适配阶段图路径检查，
  未作正式 execution-mode 验收或全量准确率结论。
- FlagGems 原仓库本轮不接入新算子、不修改也不同步；FGV 为已安装只读依赖。
  若后续需要改 FlagGems 原仓库或同步，需单独授权。

## 最终源码复核与影响矩阵

2026-09-23 复核 `git diff --check`、实际 6 文件 diff 与
`git diff --binary | sha256sum`：Plugin 补丁 SHA-256 为
`196ee5aa9b6a82786c8e139c86a2c89ad06b2e341de469434c84b9b7e71d9fa4`；
HEAD 为 `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`、detached HEAD，
仅上述 6 文件 modified、无本轮未跟踪产品文件。PR base 未确认；未提交、推送或建 PR。
vLLM `bc150f50299199599673614f80d12a196f377655` 的继承 diff SHA-256
`a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`
未变，工作树只有继承的 `fused_recurrent.py` 修改。FlagGems、FGV clean。

影响矩阵：MetaX attention 的 flag=0 保留 vendor MACA，flag=1 经 Plugin
policy→`default.flagos`→FGV FA；MetaX GDN 的 flag=0 保留 vLLM 路径，flag=1
的普通 prefill/decode 经 Plugin patch→dispatch→FGV，KDA/spec 仍原路径；
其他平台未切换 MetaX 策略，但直接使用 Plugin FlagOS custom attention 的调用方
会看到 FGV FA 实现。已验证缺省/开启路由、Qwen3.6-27B TP2 数值、eager 请求、
decode-full 捕获与请求；未验证其他模型、平台、FP8/FA3、DCP、spec/KDA、
可选 FGV 缺失以及多请求长稳态。`FULL` prefill graph 限制来自只读 vLLM 的
`GDNAttentionMetadataBuilder._cudagraph_support=UNIFORM_BATCH`，不是本轮
GDN kernel 数值失败；解除条件是上游/Plugin 提供经实测的 GDN prefill 全图 metadata
与 replay 支持，届时必须重新尝试 FULL 并重做回归。MetaX recurrent 的活跃 state
gather/transpose/scatter 是正确性适配而非性能优化；无正式吞吐结论，首次请求含 JIT
编译，不能用日志约 0.4 token/s 宣称稳定性能。

## 限制与下一步

状态 gather/transpose/scatter 可能带来额外 decode 开销，尚无性能结论。
后续若选择正式验收，按 profile 首先保留这次 FULL 阻塞证据，再完成
execution-mode→sanity→accuracy→performance 等原生步骤；不可把本轮冒烟等同通过。
若出现不支持的 FA3、context parallel、FP8、
speculative decode 或 graph 失败，应保留首个错误和最小复现，不能静默回退或
宣称支持。知识库状态暂为 `needs-validation`。
