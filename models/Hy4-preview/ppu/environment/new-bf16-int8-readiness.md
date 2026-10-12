# 新版 Hy4-preview INT8：适配可复用性与实施前检查

日期：2026-08-28。范围仅 PPU-13 / hy4-graph。依据：新版固定版本配置/全部权重头、旧 W8A8 配置、当前插件源码；不使用此前被否定的 `ppu_hyv4_indexer.py`，不把参考 FP8 patch 当作 PPU INT8 实现。

## 一、可以复用什么，不能直接推断什么

| 项目 | 当前可复用实现/证据 | 新版剩余验证 |
|---|---|---|
| 模型注册/配置 | `vllm_fl/configs/hy_v4.py`、`patches/hy_v4_v024.py`、`models/hy_v4.py` | 新增字段是否按预期透传，registry/config 最小构建 |
| packed BF16 experts | `HYV4ForCausalLM._packed_expert_target`、`_load_all_experts`、`load_weights` 已存在 | 不能说“插件缺 packed loader”；新 INT8 packed scale 合约仍需确认 |
| 旧逐专家 INT8 | `experts.<id>.<proj>.{weight,weight_scale}` 映射到 w1/w2/w3 loader | 新量化产物命名、shape、scale 和本地专家过滤 |
| W8A8 计算 | compressed-tensors + 插件量化/专家路径 | 不支持的 W8A16、非对称、group-wise 不能自动等同 |
| Sparse MLA | 现有 attention → 插件 dispatch → FlagGems/vendor backend 体系 | 新权重数值、sink、TP head padding、prefill/decode 对齐 |
| BF16 Indexer | 现有投影、cache writer、paged logits/top-k 和 shared index 缓冲 | 有效 seq_len、padding、跨 block、不同 graph batch |
| IHC/router/logits | 当前 FP32 计算/累积策略 | 与新版 BF16 参考一致性；checkpoint BF16 不应被误写成 FP32 存储 |
| 激活 | dense/shared 为 `SiluAndMul()`；旧补丁移除了 clamp | 新 `swiglu_limit=10` 的前向语义未确认，优先查清 |
| Decode graph | 旧 correctness 配置为 no-Inductor + FULL_DECODE_ONLY | 新模型 eager/graph 数值回归；不自动恢复 breakable/PIECEWISE |
| MTP | 主模型 loader 遇 `model.mtp_layers.*` 会跳过 | 没有由此验证 MTP 推理；新两项 dtype 改变需单独覆盖 |

以上是可复用代码和检查点，不是新版已适配成功。FlagGems 固定 revision 为 `662ca746b5841c9cb50172951388aa7153977dfe`；本轮没有发现或宣布新的算子缺失，也未新增算子。后续若遇缺口，须先查固定 FlagGems 实现，按 plugin dispatch 接入；确无兼容实现再写 plugin-owned Triton，并覆盖 eager/graph。不能绕过 dispatch 或修改上游 vLLM。

## 二、建议与量化方先对齐的 checkpoint 合约

为最大化复用，建议沿用旧版的 **compressed-tensors / int-quantized，static symmetric per-output-channel INT8 weight + dynamic symmetric per-token INT8 activation + F32 scale**。这只是建议目标，尚未看到新 INT8 产物，不能宣称其已满足。

建议首轮保持旧覆盖范围：attention 的 q_a、q_b、kv_a、kv_b、o_proj，以及 routed/shared expert；保留第 0 层 dense、attention linear_gate、Indexer、router、IHC/norm、embedding、LM head 和 MTP eh_proj 等原精度。明确“主投影 W8A8”不包含所有名为 linear 的模块，更不包含 FP8 cache/Indexer。最终 ignore 列表以新产物报告审计为准。

### Packed experts 的量化轴尤其重要

新 gate/up 为 `[E,2I,H]=[256,4096,6144]`；down 为 `[E,H,I]=[256,6144,2048]`。per-output-channel 必须在**每个专家内**沿输入维求 scale：可表示为 gate/up `[E,2I,1]`、down `[E,H,1]`，或逐专家 `[out,1]`。不能把三维张量的第 0 维 expert 误认为 output-channel；实际 scale 是否省略末尾 1 需要 loader 明确约定。

优先选已有逐专家 INT8 命名，并验证 gate/up 的顺序与拆分。若新量化器保留 packed INT8，需要增加对应的权重/scale 名称测试：当前 mapper 是字符串替换，带 `.weight` / `.weight_scale` 的新后缀不一定对应已有参数名，不能只用 BF16 packed 加载通过来证明 INT8 packed 可用。也不能为了复用而复制旧 scales。

建议先提供一个代表性 attention 权重及一个 expert 的新产物（或仅其头信息、量化配置和报告）做契约检查，再开始大规模部署。量化后的误差应在相同新版 BF16 权重上比较，旧版自然语言输出不是新版参考。

## 三、数值与稳定性风险优先级

1. **激活语义**：旧补丁 `0029` 的不截断结论不能无条件推广；新配置仍有 limit=10，需取得新版实际前向实现或对比 BF16 局部输出。
2. **路由与累积**：当前路由 weight 以 FP32 参数计算，但旧/新 checkpoint 抽查均为 BF16；主层 correction bias/sink 仍为 F32。验证 top-8 ID、probability、IHC、shared+routed 合并和最终 logits，不以“没有乱码”代替数值正确。
3. **模板与版本**：词表/规则内容相同；新版不接受 low；类名可解析不等于完整 AutoTokenizer、chat template 与 reasoning parser 已通过。首先固定 high 或 no_think，短输出 smoke 与正式评测分别记录 token budget。
4. **长时 graph/Top-K**：旧模型完整 GPQA 曾有 96 个 API 响应后中断、102/198 timeout。后续 `0030` 的 133 项 ATen 黑名单和 `0031` 的 top-k bool 兼容补丁有各自记录，但没有可移植为新版完整验收的证据。本轮观测到用户已运行服务，未测试该服务准确率/稳定性。
5. **资源与并行**：TP16 no-EP 可作为旧基线候选，不代表 EP 永远不可用。不能由当前目录大小估计直接承诺 tokens/s；复制参数、通信、KV 和 graph buffers 均会影响容量与速度。

## 四、实施及验收顺序（本轮未执行）

1. 接收新 INT8 路径、source revision、量化报告/ignore 列表和完整 index；先做不加载权重的 schema、dtype、shape、scale、tokenizer 与配置检查。
2. 保存插件当前 revision/branch/dirty diff；新增变更全部位于插件和其 dispatch/backend，保持 vLLM 只读。所有补丁/脚本保存在本目录；运行容器不停止。
3. 以新版 BF16 参考完成代表层/算子对齐，优先定位 clamp、routing、IHC、attention/Indexer、LM head。记录容差与失败条件。
4. 使用新模型独立路径/名称，先 eager 短输入及多步 decode，再 graph capture/replay。候选起点是 TP16、no-EP、no-Inductor、FULL_DECODE_ONLY、capture sizes `[1,32]`，其余参数由实际内存和新配置确定；这不是已验证启动命令。
5. 覆盖不同 prompt 长度、32 并发、跨 cache block、prefill/decode 混合，检查 token/logits 一致性、NaN/Inf、请求完成率和 warning。此处为正确性/稳定性回归，不开始性能调优。
6. 在规定的 flageval 容器内使用 `test/Accuracy_test/llmrun.py`、模型专属 llm_config，先 `--preflight-only` 后正式 GPQA。若采用 Diamond，核对 198 样本、无 timeout、进程完成、完整 result/sample 文件；准确率通过阈值需结合新版 BF16 基线事先确定。
7. 只有正式精度达到阈值后，才用 `test/perf_test/` 做性能测试/优化；必要时补 `test/nccl_test/`。记录 eager/graph、batch、输入/输出长度、吞吐/延迟和单变量比较。

## 五、继续实施前需要的信息

- 新 INT8 权重所在目录及来源 BF16 commit，不能只给名称“int8”。
- 量化格式、weight/activation granularity、scale、zero-point、packed 布局和 ignore 范围。
- 量化工具/代码 revision、校准信息、参考评测及可接受精度差。
- 可复现的新 BF16 logits/token 或官方前向实现，用于确认激活/路由语义。

这些是后续实施输入，不阻止本轮分析完成。本轮没有实际改动推理路径或生产服务。
