# HY4 PPU 原生算子清单：full Indexer、W8A8 与 MoE

## 范围与基线

- 核查日期：2026-09-03
- 目标：`PPU-07`，运行中适配容器 `hy4`（本轮未停止、重启或移除容器）
- 插件：`/workspace/vllm-plugin-FL-hy4-preview`，分支 `support-hy4-preview`，基线 `11848598449f6d650df64170db4187c387361ce5`，工作树原本已 dirty
- vLLM：`/workspace/vllm`，`ee0da84ab9e04ac7610e28580af62c365e898389`，本轮前后 clean
- FlagGems：`/workspace/FlagGems`，`60d043094d0217cad75528cb0e47a606c87ab1e4`，本轮前后 clean
- 正确参考镜像：`egslingjun-registry.cn-wulanchabu.cr.aliyuncs.com/egslingjun/inference-xpu-pytorch:26.04-v2.1.0-vllm0.23.0-torch2.10-cu130-20260710`
- 固定 digest：`sha256:fb48fe779ca7b91741b0248cf6cda4ab3785c69dd91dfe88890c7cafdc2996ac`
- 参考软件：vLLM `0.23.0+v0.2.0.ppu2.1.0`、Torch `2.10.0`、PPU SDK `2.1.0`
- 服务状态：停止；本轮没有启动模型服务或执行端到端性能测试。

这里的“原生”指上述固定镜像中由 PPU 工具链构建并注册 CUDA dispatch kernel 的二进制实现。名称中保留 `cutlass` 或 `_C` 不代表使用 NVIDIA 设备；实际测试设备为 `PPU-ZW810E`。

## SO 清单与插件内位置

按用户要求，已把需要继续完成原生链路验证的三个 SO 放到：

`/workspace/vllm-plugin-FL-hy4-preview/vllm_fl/dispatch/backends/vendor/thead/lib/`

| 文件 | 大小 | SHA-256 | 用途 |
|---|---:|---|---|
| `_C.abi3.so` | 143446208 B | `10054e23f66011437ad1e33078ad67832393585d368e877448b4976952243d90` | Indexer top-k、INT8 quant、候选 scaled-MM/MoE MM |
| `_C_stable_libtorch.abi3.so` | 130695032 B | `286f17d0ee7144d695d005c8b6f3c9003ef2ac83c5ff22cb1abef6184b904bab` | MLA query concat、MLA/Indexer cache write |
| `_moe_C.abi3.so` | 165806288 B | `8fb2361800d359b5d4c287c1beb6b02337dd66092a249909a21f79238be0b172` | MoE routing、排列、归约与相关候选实现 |

来源、digest、版本、大小和 hash 同时保存在插件的 `lib/PROVENANCE.md`。二进制没有复制到本管理仓库。

三个 SO 必须在 PPU 平台插件注册的早期、`_C_ops_registry` fallback schema 之前加载。第一次尝试在 dispatch manager 初始化后延迟加载时，进程因 `_C::*` schema 重复 `def()` 退出；修复后由 `vllm_fl.register()` 在检测到 `PPU_SDK` 时加载完整 bundle，并发布与真实扩展相同的空 Python module surface，阻止 fallback registry 再覆盖 native kernel。非 PPU 平台不执行该加载逻辑。

## full Indexer 当前链路与原生映射

当前 HY4 使用的是 **BF16 full Indexer**，不是参考 vLLM 的 FP8 Indexer。模型调用入口为 `vllm_fl/models/hy_v4.py` 中的 `hyv4_bf16_sparse_attn_indexer` custom op。

| 阶段 | 当前输入/行为 | 当前实现 | 参考镜像原生候选 | 结论 |
|---|---|---|---|---|
| Q 投影 | `wq_b`，输出 `[T,H,128]` | 模型 W8A8 linear | `_C::dynamic_scaled_int8_quant` + `_C::cutlass_scaled_mm` | quant 已切 native；MM 尚未切换 |
| K/weight 投影 | BF16 merged GEMM，输出 K=128 与 head weight | vLLM linear / PyTorch | 无专用 Indexer 投影 op | 保持现状 |
| K norm + RoPE | K/Q 均保持 BF16 | vLLM/torch op | `_C::fused_deepseek_v4_qnorm_rope_kv_rope_full_cache_bf16_insert` | 该 op 面向 DeepSeek-V4 SWA/full attention cache，输入和 cache contract 不同，不能直接替代当前 Indexer |
| Indexer cache write | `keys=[T,128] BF16` 写 `[blocks,64,128]` | **已切 `vendor.thead`** | `_C_cache_ops::concat_and_cache_mla`，以空 `k_pe` 写入 | eager/graph、逐元素精确通过 |
| prefill paged gather | Python 读取 chunk metadata、逐 request gather | `_paged_sequence` + Python list/loop | quantized cache 的 `_C_cache_ops::cp_gather_indexer_k_quant_cache` | 只支持量化 cache contract，不能直接用于 BF16 cache；当前仍有 host sync/循环 |
| prefill logits | BF16 Q×K、per-head ReLU 后加权 | `_select_topk` 的 torch matmul/ReLU/sum | PPU DeepGEMM `int8_mqa_logits`、`fp8_mqa_logits`、FP4 版本 | 没有同 contract 的 BF16 原生 MQA logits；不能无基线地隐式量化 |
| decode paged logits | Q `[B,N,H,128]` BF16，cache BF16，输出 `[B*N,50000]` FP32 | FlagGems `bf16_paged_mqa_logits` | PPU DeepGEMM 仅 `int8_paged_mqa_logits`、`fp8_paged_mqa_logits`、FP4 版本 | **无可直接替换的 BF16 PPU 原生 kernel**；继续 FlagGems，50K logits 物化仍是主要性能缺口 |
| decode top-k | 按每个 speculative row 的有效长度选候选 | **已切 `vendor.thead`** | `_C::top_k_per_row_decode`；另有 K=512/1024/2048 的 `_C::persistent_topk` | 当前 K=2048 的 row-wise op 已通过 eager/graph、`next_n=2` 有效长度语义测试。`persistent_topk` 也在 `[32,50000]`/K=2048 上通过精确集合与 graph 测试，但输出未按值排序，不能直接替代现有完整链路 |
| 候选重排 | gather 2048 logits，再按值排序 | `torch.topk` + gather | `_C::persistent_topk` 只完成无序候选选择 | 仍需排序，因此不能消除当前重排；50K logits 也仍会完整物化 |
| sparse MLA | top-k indices + BF16 MLA cache | `vendor.thead` 调 `flash_mla_sparse_fwd` | 平头哥 `flash_mla` | 已通过数值、eager、graph；不再 padding 4→64 heads |

参考镜像的 `vllm::ppu_sparse_attn_indexer` 不是当前 BF16 full Indexer 的直接替代：其 paged logits 分支明确只接受 `q_dtype` 为 INT8、FP8 或 FP4，并配套量化 K cache。若后续要采用该完整 PPU 路径，必须把 BF16 Indexer 改为 INT8 cache/query，并先建立 GPQA/定点 logits/top-k 一致性基线；不能作为纯性能替换直接启用。

## W8A8 路径清单

### Dense/shared linear

当前 checkpoint contract 为 activation dynamic per-token、weight per-output-channel：A=`[M,K] BF16→INT8`，B=`[K,N] INT8`，A scale=`[M,1] FP32`，B scale=`[N] FP32`。

| 子阶段 | 当前实现 | 原生候选 | 状态 |
|---|---|---|---|
| activation quant | 原先 `flaggems_vllm.scaled_int8_quant`，再退到插件 Triton | `_C::dynamic_scaled_int8_quant` | **已切 `vendor.thead`**；M=8/K=6144 eager/graph 与 torch reference 精确通过 |
| scaled GEMM | `flag_gems.scaled_mm` | `_C::cutlass_scaled_mm(out,a,b,a_scales,b_scales,bias)` | 已完成 5 组 HY4 代表 shape、bias/no-bias、数值和 graph 测试；原生 op 只接受 `[K,N]` 且 stride=`[1,K]` 的 column-major B，当前插件/FlagGems 权重是 contiguous row-major，不能直接切换。需要独立的 T-Head weight preprocessing/linear kernel 路径 |
| graph boundary | `vllm::fl_w8a8_dynamic_per_token_linear` opaque custom op | 保留该框架边界 | 正确；后续只替换边界内部 quant/MM backend，不在模型文件直接调用 SO |

### Routed MoE expert

当前 `FlagGemsW8A8Experts` 将 BF16 hidden states、INT8 `w1/w2`、per-channel scale 和 routing 交给 `flag_gems.fused_experts_impl`。`VllmFunctionalW8A8Experts` 是 NVIDIA/vLLM functional fallback，不应误当 PPU 原生实现。

| MoE 子阶段 | 当前插件实现 | 参考镜像原生 op | 可替换性与下一步 |
|---|---|---|---|
| FP32 router GEMM | `GateLinear` 的 FP32 `F.linear`；HY4 明确 `allow_dsv3_router_gemm=False` | `_C::dsv3_router_gemm` / `_C::dsv3_fused_a_gemm` | 参考 op 的 dtype/shape 不是当前 FP32 gate contract；保持禁用 |
| grouped routing | **已切 `vendor.thead`**，FlagGems fallback | `_moe_C::grouped_topk` | E=256、top-k=8、correction bias、scoring_func 0/1、renormalize、scale=2.827 的集合与权重数值通过，graph replay 通过 |
| top-k softmax | **已切 `vendor.thead`**，FlagGems fallback | `_moe_C::topk_softmax` | E=256、top-k=8，renormalize 与 bias 的四种组合通过数值/eager/graph；原生 index layout 为 rank-major，wrapper 已按既有 contract 暴露 |
| token align | **已切 `vendor.thead`**，FlagGems fallback | `_moe_C::moe_align_block_size` | E=256、top-k=8、block=64，普通、`expert_map` 过滤、小 token 边界通过数值/invariant/graph；batched 原生 schema 也完成独立 contract 测试，但当前未增加不需要的 dispatch 入口 |
| token permute | 当前融合进 FlagGems experts | `_moe_C::moe_permute` / `moe_permute_with_scratch` | 原生完整链路候选；需要固定 workspace 和 graph 地址，不能只替换单函数 |
| expert W8A8 GEMM | FlagGems `invoke_fused_moe_triton_kernel` | `_C::cutlass_moe_mm` + `get_cutlass_moe_mm_data` | 已验证不是当前硬件可用路径：`PPU-ZW810E` capability 80，而 helper 要求 90/100/120、kernel 要求 90/100；手工构造 problem sizes 仍报硬件不支持。保持 FlagGems，不注册伪 fallback |
| activation | FlagGems fused SiLU/gate | 无单独必要替换；可位于 native expert pipeline 内 | 与 expert GEMM 一并验证 |
| unpermute/combine | FlagGems fused combine | `_moe_C::moe_unpermute` | 需与 permute/expert GEMM 成套验证 |
| final expert sum | **已切 `vendor.thead`**，FlagGems fallback | `_moe_C::moe_sum` | `[32,8,6144]` BF16 与 FP32-reference→BF16 精确一致，eager/graph 通过 |
| shared experts | 普通 W8A8 dense linear | 同上 dense quant/scaled-MM | quant 已 native，MM 仍 FlagGems |

因此，MoE routing、align 和 reduction 已通过插件标准 vendor dispatch 使用平头哥原生 op；真正影响主要算力的 **W8A8 expert GEMM 在当前 capability 80 硬件上没有可用的该 bundle 原生实现**，完整 expert pipeline 仍由 FlagGems 承担，不能宣称 MoE 已全原生。

## 已启用的 vendor dispatch

当前 T-Head policy 已改为 vendor-first：

- `concat_mla_q`
- `mla_kv_cache_update`
- `bf16_indexer_cache_write`
- `bf16_indexer_topk`
- `dynamic_per_token_quant_int8`
- `grouped_topk`
- `topk_softmax`
- `moe_align_block_size`
- `moe_sum`
- `attention_backend`（既有 PPU `flash_mla_sparse_fwd`）

`bf16_paged_mqa_logits` 仍明确保持 `[flagos]`，未伪造不存在的 BF16 vendor 实现。上述 MoE ops 在 `thead.yaml` 中为 vendor-first 并保留 FlagGems fallback；模型层仍只通过 `CachedOp`/dispatch 使用它们，不直接 import SO。

## 验证结果与问题记录

1. 三个 SO 在当前 vLLM 0.24/Torch 2.10/PPU SDK 2.1.0 中可加载。
2. 一次错误的晚加载方案在 manager 初始化后触发重复 `_C` schema 并使测试进程退出；没有启动/影响模型服务。根因是插件 fallback registry 已先定义相同 schema。
3. 修复为平台注册早期加载后，manager 正常初始化，没有重复注册警告；五个目标 op 均解析为 `vendor.thead`。
4. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_thead_bundled_native_dispatch.py`：cache/query、BF16 Indexer cache、`next_n=2` top-k、K=6144 INT8 quant 的数值、eager、graph 全通过。
5. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_thead_native_sparse_mla_integration.py`：H=4、D=576、V=512、top-k=2048、sink 路径数值/eager/graph 全通过。
6. `/workspace/vllm` 与 `/workspace/FlagGems` revision/status 前后未变；模型服务保持停止。
7. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_thead_native_remaining_ops.py` 完成剩余原生 contract 矩阵：`persistent_topk`、dense `cutlass_scaled_mm`、routing、align、permute/unpermute、sum、`cutlass_moe_mm`。它明确识别了 column-major dense 权重约束、INT8 permute 不支持，以及 capability 80 不支持 native expert MM。
8. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_thead_native_moe_dispatch.py` 验证 `grouped_topk`、`topk_softmax`、`moe_align_block_size`、`moe_sum` 均实际解析为 `vendor.thead`，数值/eager/graph 通过。
9. 部署后的两组既有回归再次通过：bundled-native dispatch 输出 `EAGER_OK`/`GRAPH_OK`，sparse MLA 输出 `STRUCTURE_OK`、`DISPATCH_EAGER_OK`、`DISPATCH_GRAPH_OK`、`NATIVE_EAGER_OK`、`NATIVE_GRAPH_OK`。

## 下一步顺序

1. 若要切换 dense scaled-MM，新增 T-Head 专用 column-major 权重加载/preprocessing 路径，并验证 checkpoint loader、所有 shape、显存、graph 与精度；不能改变 FlagGems 等其他平台的 row-major contract。
2. 为 capability 80 寻找另一套平头哥原生 W8A8 expert MM；当前 bundle 的 `cutlass_moe_mm` 不可用。在找到前保持 FlagGems fused experts。
3. 对 BF16 paged logits 做 profile。若它仍是主要瓶颈，只能在“编写/取得 PPU BF16 paged-MQA 原生 kernel”与“把 Indexer 改为原生 INT8 cache/query 并重新做精度验收”之间选择，不能直接套用参考镜像的量化 Indexer。
4. 后续经用户安排启动服务时，依次做 graph capture、8 并发正确性/性能 sanity、全量精度，最后才做正式性能测试。本轮按边界不启动服务。

## 可复现文件

- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-reference-native-operator-inventory.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-reference-focused-native-schemas.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-reference-ppu-indexer-implementation.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-hy4-native-extension-coverage.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test-ppu07-reference-native-extension-compatibility.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-hy4-native-extensions.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/update-ppu07-hy4-native-loader-module-shims.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/run-ppu07-thead-bundled-native-dispatch-test.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/run-ppu07-thead-native-sparse-mla-integration-test.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-native-w8a8-moe-contracts.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/fetch-ppu07-native-w8a8-moe-reference-sources.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/run-ppu07-thead-native-remaining-ops-test.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_thead_native_remaining_ops.py`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-thead-native-moe-dispatch.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_thead_native_moe_dispatch.py`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/verify-ppu07-hy4-native-bundle-final.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_loaded_ppu_vllm_native_extensions.py`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_thead_bundled_native_dispatch.py`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_thead_native_sparse_mla_integration.py`
