# FlagGems-vllm KDA 验证与接入

范围：GLM-5.3-Flash / PPU-13 / `glm5.3-flash`，2026-09-04。
本轮用户要求验证并接入新安装的 KDA；只修改插件，不修改 vLLM，不重启容器。

## 修改前基线与同步

- 插件 `/workspace/vllm-plugin-FL-glm53-hy4-adaptation`，`support-hy4-preview@5329cb1293f397fd194852496cfcc710c35f1bfc`；保留已有 dirty 工作树，51 文件 +8979/-6。
- vLLM `/workspace/vllm`：`ee0da84ab9e04ac7610e28580af62c365e898389`，干净。
- FlagGems origin `https://github.com/flagos-ai/FlagGems.git`，master/origin/master，干净；fetch + pull --ff-only 从 `9553ae9c745bdf5fd4a25d50e0d67bf80d888030` 更新至 `71d3736797ed2cefc23cddc075179156343a785f`。
- FlagGems-vllm origin `https://github.com/flagos-ai/FlagGems-vllm.git`，main/origin/main，干净；fetch + pull --ff-only 后仍 `5865ed53b183e6d3aff69ad1823622a11679d257`。
- 精确命令存于 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/inspect-ppu13-kda-integration.yml`。流程前置 `adapt-model ... --steps adaptation --check-only` 通过。

## 接入缺口与验证门槛

| 项目 | 当前插件/新库差异 | 计划 |
| --- | --- | --- |
| prefill KDA | 当前 `chunk_kda_with_safe_gate` 为 vendor.thead 的 portable 实现；新库有 chunk_kda | 优先验证新库，再通过现有 DEFAULT dispatch 注册薄适配层 |
| beta | 现有接口接收已激活 beta，新库公共入口强制内部 sigmoid | 禁止二次 sigmoid；选择支持关闭激活的兼容入口或调整明确的模型调用契约 |
| gate | 当前 raw_g + A_log + g_bias；新库使用 g + A_log + dt_bias | 核对 bounded gate 数学和 dtype，不改语义 |
| metadata | 新库 prepare_chunk_indices 使用动态 arange/repeat_interleave 和 tensor cache | 必须测试变长、原地址 metadata 更新后的 graph replay；不能只依赖 warmup 缓存 |
| state | 当前 FP32 初始状态，prefill 返回终态供模型写回 | 验证初态不被意外修改、终态布局和数值 |
| decode | 当前 fused_recurrent_kda 支持索引状态更新，非 chunk 接口 | 本次不因存在 chunk_kda 就替换 decode |

独立测试 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/test_flaggems_vllm_kda.py` 不依赖模型、vLLM 或插件，固定 seed=5304；
BF16 q/k/v/raw gate/beta，FP32 初态/A_log/bias，H=4,D=128，长度33以及[17,16]；
参考为 CPU FP32 逐 token recurrence，门限 rel RMS < 1%，atol=.004、rtol=.03。
graph 测试更新 q/state，并对变长情况更新原地址 cu_seqlens。任何失败需先记录、复现，不能进入更宽的测试。

## 已复现的问题及处理

1. **auto 选中不支持的 TLE**：新库检测 HAS_TLE_KDA=True 后走 generic TLE，PPU 编译器拒绝 `tle.gpu.copy.tensor_descriptor`、`tle.warp_specialize`。已在容器 `/bug/flaggems-vllm-kda-ppu-5865ed5/repro.py` 独立复现，未改新库源码。插件绑定明确使用新库 plain-Triton 内核，不依赖启动环境变量，也不在运行失败后重试。
2. **变长 graph 陈旧 metadata**：库自带 plain-Triton 路径定长 eager/replay 正确，但 warmup 后原地址 cu_seqlens 从 [0,17,33] 改为 [0,16,33]，graph 输出 rel RMS=.170867、max_abs=.0214372。其 tensor_cache 保留旧 chunk table。相同 /bug 脚本 `--graph --varlen` 已复现；eager output rel RMS=.0035998、state=.0030002。复现命令加 `FLAGGEMS_CHUNK_KDA_BACKEND=triton`。
3. **beta 契约**：当前插件收到已激活 beta，而新库公共入口强制 sigmoid。绑定选择支持 `apply_beta_sigmoid=False` 的内核包装，不改模型接口，不反算 logit，不重复激活。

两个上游问题的精确环境、输入和命令已放入同一算子复现包的 README。只打包，不向外提交 issue。

## 实际接入与边界

当前 editable 插件中只新增/修改两个生产文件：

- `vllm_fl/dispatch/backends/flaggems/impl/chunk_kda.py`：90 行绑定，对应本目录 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/chunk_kda_binding.py`。
- `vllm_fl/dispatch/backends/model_ops.py`：新增 15 行 DEFAULT 注册，op=`chunk_kda_with_safe_gate`，impl_id=`default.flagos`，有依赖可用性/输入 supports 检查，`allow_runtime_fallback=False`。

调用仍为模型 → CachedOp → 现有 dispatch → 薄绑定 → FlagGems-vllm `_kda_fwd_intra_triton` / `_kda_fwd_h_o_triton_kernel`。
后者的 `chunk_offsets` 参数在固定 revision 下未被内核读取；绑定不调用会生成陈旧 metadata 的外层包装。
新库计算内核未复制、未修改；vLLM 也未改。未新增启动参数、环境变量或 YAML 设置。
既有 vendor 路径保留供不满足新绑定契约的输入选择，decode `fused_recurrent_kda` 不变。

**上游缺失项**：在同步后的两库版本及 `flaggems_vllm/ops/FLA/index.py` 搜索/检查未发现适用于本契约的 graph 动态 chunk table 生成接口。
插件自有 Triton `_chunk_metadata` 补齐此项：固定容量 `ceil(total_tokens/16)+N-1`，GPU 读取实时 cu_seqlens、前缀计数并生成映射；多余项落到末序列越界 chunk，由上游内核直接返回。
无 `.item()`、CPU 元数据搬运、按设备值决定的分配或 tensor_cache；capture/replay 使用固定形状和稳定地址。
输入 contiguous 转换用于支持模型/调用者的非连续视图，graph 中为可捕获的设备拷贝，不是计算失败后的 reference fallback。

支持当前 TP16 的 B=1、H=4、D=128、BF16 q/k/v，BF16/FP32 raw_g/beta，FP32 A_log/bias/初态，int32/int64 cu_seqlens；状态 KV 布局。
新权重实际 `text_config.linear_attn_config` 为 num_heads=64、head_dim=128、gate_lower_bound=-5，TP16 对应本地4头。
layer0 的 safetensors header 核实 A_log 为 F32 [64]、dt_bias 为 F32 [8192]；模型 config SHA仍为 bb8f01c42cb92a52ca72e65afb4d5bd8d11aef083cd210e8de25dfb904f23e9f。
当前 focused 测试覆盖 int32 metadata；库原始接口测试覆盖 int64。全零 token、其他 head/dtype/shape 不宣称支持。
私有内核接口固定在 5865ed5；未来更新 FlagGems-vllm 时必须重核签名、chunk_offsets 使用和数值/graph 回归。

## 验证结果

- 原库 plain-Triton 定长 [33]：eager 和两次 graph replay 通过；output rel RMS 约.0037、state约.0032。
- 独立薄绑定 5 组 eager/graph 通过后才部署；部署后新进程默认 dispatch 5 组通过，断言实际 provider 为 `default.flagos`。
- 开启当前真实 FlagGems blacklist 的集成验证：扩展到 **8 组全部通过**，长度 [1]、[16]、[17,16]、[0,33]、[9,7,17]、[129,128]、8×[17]、32×[1]。
- 覆盖 FP32 beta、CPU FP32 reference、非法 dtype guard、空序列、非连续 q、初态不被覆盖、无初态、有/无终态，以及两次 q/raw_g/cu_seqlens 改值后的 graph replay。
- 现有 PPU 数值/graph **28/28 passed，15.18s**；插件/dispatch **313/313 passed，12.61s**。
- 本地语法/工作流检查通过；AST 解析与注册 patch 结构检查通过。所有成功验证的目标均为 PPU-13，不涉及其他主机。

## 复现与交付

- 独立验证：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-flaggems-vllm-kda.yml`（默认 TLE 预期失败）、`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/package-ppu13-kda-bug.yml`（复现 auto 缺陷并验证 Triton 定长）、`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-kda-varlen.yml`（原库变长 replay 失败）。失败结果保留，不能作为通过项。
- 薄绑定验证：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-kda-binding.yml`。
- 首次部署：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/integrate-ppu13-kda-binding.yml`（一次性备份 guard，不应盲目重跑）。
- 已安装回归：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/regress-ppu13-kda-integration.yml`、`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-kda-expanded.yml`。
- 最终路径/版本/只读保护核对：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/verify-ppu13-kda-final.yml`。
- 最终运行时 Python3.12.3/GCC13.3.0、Torch2.10.0、Triton3.6.0；新进程确认绑定从当前 editable 插件目录加载，默认 YAML SHA 未变化。
- 恢复材料：容器 `/workspace/glm53-adaptation-runtime/kda-integration-20260904/model_ops.py`、`before.patch`；原有未提交修改未清理或重置。
- 文件 SHA256：绑定 `58c7f73ffedfa5ffe6c1d61d882e391c94cc674e0d0dc68b2668adc68d330505`；model_ops `ec98b3a29e7505f540f1655a84fed676887ed4a3871fae6042e2cf7317705fbd`。
- 新绑定文件尚为 untracked，未暂存/提交；`git diff HEAD --stat` 不会计入该文件，应结合 `git status --short` 审阅。

状态：**KDA prefill 算子级接入与验证完成**。容器持续运行，未启动整模、未执行精度/性能验收。
新 FP8 权重的未量化层前缀匹配故障仍独立存在，平台继续 blocked；本结果不能替代整模 eager/graph 或 GPQA 88 分验收。
