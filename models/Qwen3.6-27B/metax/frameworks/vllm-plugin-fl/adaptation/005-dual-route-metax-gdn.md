# 005：MetaX GDN 的 vendor / FlagOS 双路由

## 元数据与问题

- 2026-09-23；Qwen3.6-27B / MetaX C550 / `mx-58` / `qwen3.6-27B`；当前为第 3 阶段适配，正式验收未选择。
- 编辑前 Plugin `/workspace/vllm-plugin-FL@675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，tracked diff SHA-256 `b681f19bd1de01745fc2f3c5cabccca8eef81f4fda2fbd13a82184664bcc19dc`；vLLM 只读，原 8000 服务与容器不停止。
- 用户要求在 MetaX vendor 链路注册 GDN 并直接调用原 vLLM/FLA 链路，使同一 GDN 调用点可由 Plugin policy 选择 vendor 或 FlagOS。此前 vendor `register_ops.py` 没有 GDN `OpImpl`，未接 FlagGems-vLLM 的 GDN 由 vLLM `gdn_attention_core` 内部直接执行；[问题 004](004-remove-flagos-registration-gates.md) 的 FlagOS hook 则只向 FlagGems-vLLM 注册项 dispatch，无法显式选择 vendor GDN。

## 设计准备（实施前）

原始调用点和接口：vLLM `GatedDeltaNetAttention.forward_cuda → vllm::gdn_attention_core → _forward_core`。prefill 的 `ChunkGatedDeltaRule.forward_native` 调高层 `fla.ops.chunk_gated_delta_rule`，返回 `(out, final_state)`；decode 的普通分支调 `fla.ops.fused_sigmoid_gating_delta_rule_update`，接收 `A_log/a/b/dt_bias` 并返回 `(out, state)`；纯非 speculative decode 可走 `fused_recurrent_gated_delta_rule_packed_decode`。已有 FlagOS 低层接口先计算 `g/beta` 再调用 FGV，不能用相同低层参数精确调用原 fused-sigmoid 链路。

拟在现有 dispatch 中定义 GDN prefill/decode 两个高层调用点，保留原始参数/返回/状态语义：MetaX vendor 实现惰性导入并直接调用上面的 vLLM/FLA 高层函数；FlagOS 实现适配后调用现有 FGV 低层实现。现有 FlagOS 低层注册不改 ABI，以免影响其他调用者。兼容 hook 应仅做调用点转发，并在 vendor 优先时保留原 packed decode；两种实现均从现有 policy 选择，不新增 GDN 专属环境变量。MetaX vendor 的 patch 可保留，但不在其中另行写一套 GDN 核。替代方案是让 vendor 低层 recurrent 调另一种非 fused 函数，虽可执行却不等同原链路，故不采用。

影响面包括 MetaX Qwen3.5/Next GDN 的 prefill、连续 decode、packed decode、KDA/spec；其他平台不应导入 MetaX 依赖或改变原实现。先做注册/选路、vendor 原函数调用与 FlagOS ABI、状态别名/数值及守卫未命中测试，再做隔离 eager/graph 模型请求。现有服务与继承 dirty 状态保持不变；每次源码变化重建部署身份，旧回执不直接复用。该方案在实施和验证前仍为待证假设；下述结果是对此假设的验证，不反写历史记录。

## 实施与受控对照

Plugin 最终仍是 `/workspace/vllm-plugin-FL@675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，没有修改只读 vLLM、FlagGems 或 FlagGems-vLLM。FlagOS 新增 `gdn_prefill`、`gdn_decode` 两个高层 `default.flagos` 候选，保留此前两个低层 FGV 注册的 ABI。FlagOS backend 内部完成原参数到 FGV prefill 七值返回、FP32 gate/beta、V-major/K-major 状态的局部适配，不重复 dispatch。MetaX vendor 新增同名 `vendor.metax` 注册，其实现惰性导入并直接调用 vLLM/FLA 的 `chunk_gated_delta_rule` 和 `fused_sigmoid_gating_delta_rule_update`；没有把 FGV 算子移入 vendor。MetaX vendor 注册完成后安装共享 GDN 调用点 hook，故 FlagOS 被现有策略过滤时仍可选原 vendor 路径；hook 幂等。纯非 speculative decode 在 vendor 优先时保留原 packed 函数；FlagOS 无对应 packed 内核时走普通 decode。KDA/spec 在执行前直接留在原 vLLM 路径。decode 原位更新 paged state，故选定候选的调用使用 `with_strict_mode()`：若内核失败立即上抛，不在可能已修改的 cache 上重试另一个候选。

没有新增 GDN 环境变量或第二个 Flash Attention 分发。默认 MetaX policy 下两候选同在，`gdn_prefill/gdn_decode` 首选 `default.flagos`；现有 `VLLM_FL_PER_OP='gdn_prefill=vendor:metax;gdn_decode=vendor:metax'` 可只切 GDN，其他算子不变。既有 `VLLM_FL_PREFER=vendor` 会在注册阶段过滤 FlagOS，故此全局配置下只剩 vendor 候选，这是框架原有 `use_flaggems_op` 行为，并非本轮的动态回退。未选候选、其他平台和缺失 FlagGems-vLLM 的环境不宣称已经完成模型验证。

受控比较均为 TP2/BF16、GPU0/1、127.0.0.1:8001、prefix caching enabled、同一模型与 16-token/temperature=0 短请求；vendor 轮只增 GDN 的 per-op 选择。eager 的 FlagOS 与 vendor 均返回 HTTP 200、16 token，前者两名 worker 的 `gdn_prefill/gdn_decode` 命中 `default.flagos`，后者 prefill 命中 `vendor.metax` 且日志声明使用原 Triton/FLA prefill。vendor 的非 speculative decode 按源码条件走原 packed 快捷路径，未观察到 `gdn_decode` dispatch 命中；这是调用链证据，非逐核 profiler 证明。两条路的图轮次均请求 `{"mode":0,"cudagraph_mode":"FULL"}`，stock GDN metadata 因 `UNIFORM_BATCH` 自动收敛到 `FULL_DECODE_ONLY`，decode 3/3 图捕获并返回 HTTP 200、16 token。针对最终 no-retry 运行代码另跑 FlagOS 图轮次，3/3 捕获和 HTTP 200 再次通过。每轮结束仅按已核实 PID 停止对应 8001 测试服务；适配容器和原 8000 服务未停止，最终 `/health` 返回成功。

Plugin 的 `tests/unit_tests/dispatch/test_metax_gdn.py` 覆盖 vendor 原函数委托、FlagOS prefill 七值契约与 dtype、decode FP32 gate/beta 与 state alias，以及 KDA/spec 不支持前置拒绝；5/5 通过，整个 `tests/unit_tests/dispatch` 为 272/272 通过。独立新进程探针 `05-tmp/metax-dual-gdn-route-20260923.py` 在默认策略确认两个候选、上下文切 vendor 再切回、hook 幂等及 vendor 惰性委托；在全局 vendor 策略确认 vendor-only 注册；模拟 decode 实现失败确认严格无重试且调用后策略恢复。该探针 SHA-256 `3c9953498e945b5ca43d90b1ff1f21b195506f3d725fd19cdc2a403b9da1bf78`。

## 证据、审查与限制

- 最终部署身份：Host/容器同路径 `01-environment/deployment-identity-dual-gdn-tested-20260923.json`，SHA-256 `07453f51fd424007e3909499b4787fb7d2acc833a8d0267a6e419d8ef0f79991`；Plugin tracked diff SHA-256 `3f22766bc58cb900e466e779e1432e0e70a6593e534c40c551fdfaa79dfab678`，未跟踪 GDN adapter `52f53620eee92c012ba56127c40cc589d9a2c2d14503a47681b14c114b185eaf`、聚焦测试 `207d86ce631968155bfc61fd73ba51a4b58308e268ed3e72dc865721087a1c66`。身份核对模型配置/索引/tokenizer、四组件 HEAD 与 dirty 状态；vLLM 继承 diff 仍为 `a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`，两个 FlagGems 源码树 clean。
- 原始测试产物均在 `04-runs/`。eager：`dual-gdn-flagos-eager-20260923` 的 log/response SHA-256 分别为 `316c0330b029836ca3a6954aeb2fd2bb153ed19720f6822431665edbb5beb38a` / `8dbd1d30990c3c2ddfe63f94768bb681aed225a8b0d580ea6d9126cbcf896163`；`dual-gdn-vendor-eager-20260923` 为 `cda4fe900fef17ee66bb4242b1d2d0116198a3d85d9cad502a439cf9ce07ddc7` / `32767c4901f2a3aeb45057b8eb35b3ccff97dbaf6caf0b3fcab7c27f0a60c449`。
- 图轮次：`dual-gdn-flagos-graph-20260923` 的 log/response 为 `85d48352e41df6bc4acf93017caf4cd5df92bcb7fe1cf0b9524d0bce2208a626` / `b16d8f6f23ee604ba5c1401ff8d68173e2c30d0e43be1fe3541b3d79793aa7c9`；`dual-gdn-vendor-graph-20260923` 为 `adae499412d2aa01d1e1b7140498ea4bfcf889027836f251c60bca31076524eb` / `69353e032ccaadeae3bb4cba6dd76eb6ab7584003a1b38b890581eef394257a5`。这四轮在 no-retry 小改动前；最终运行代码的 `dual-gdn-final-flagos-graph-20260923` log/response 为 `606ae1864fcac3fde1257c18d8c28c502179d344aed08594aef0192d1c114a14` / `1a2a3046a0abaf069921061cd393b1b2c4f958456842b4c5bfff62b8b55592a6`。随后仅增加不参与运行的聚焦测试文件，未再更改产品运行代码。
- 实际 diff 审查：从 HEAD 的累积改动涉及 FlagGems backend/注册、现有 FA backend、MetaX vendor backend/注册、`metax.yaml`，并有 GDN hook 与测试两个未跟踪文件；本轮新增的 vendor 代码只做原 FLA 委托。`git diff --check` 通过，三个非 Plugin 组件未改。PR base 未确认；当前 HEAD 和 dirty/untracked 清单已按上述身份冻结，不能把 `git diff` 当成完整 PR 比较，也未提交、推送或建 PR。MetaX Qwen3.6 eager/decode-full 冒烟和 dispatch 单测支持这次局部设计，但正式数值对照、准确率、稳态性能、chunked/mixed batch、KDA/spec、其他模型与非 MetaX 平台未在最终源码做完整回归。`FULL` prefill 图仍受上游 metadata 限制；其退出条件是上游 GDN metadata 真正支持 full prefill 并重新捕获/回放验证。

因此该 issue 的双路由调用目标在本 Host 上已有正向证据，适配阶段仍为 `in_progress`；正式第 4 阶段未选择，不能据这些短请求标 `functional`、`optimized` 或完整图覆盖。经验暂为 `local-only`，不推广到其他平台。
