# PPU-07 MiniMax-M3.1 W8A8 适配问题与设计审查

- [001：W8A8 MoE split SwiGLU-OAI](001-w8a8-split-swiglu-oai.md)：FlagGems 干净快进后仍缺少兼容的 fused 路径；Plugin 两段 INT8 分支完成单卡数值和 TP16 eager/decode-full 真实请求验证。
- [002：M3.1 compressed-tensors 融合投影映射](002-compressed-tensors-packed-mapping.md)：Plugin metadata helper 聚焦测试及目标权重 48/48 shard 加载、文本生成通过；视觉请求及旧 M3 共享调用尚未整模验证。
- [003：PPU prefill index top-k 编译断言](003-prefill-index-topk-autotune.md)：默认上游 autotune 在首个整模请求失败，Plugin 仅 PPU/topk=16 固定上游 JIT 合法配置后，eager 与 decode-full 真实请求通过。
- [004：MiniMax M3 后端阻止 prefill/decode 全量图](004-full-graph-backend-coverage.md)：精确 FULL 首试因 sparse/indexer 后端能力检查自动降为 decode-full；显式 `FULL_DECODE_ONLY` 完成 6/6 捕获、三次正确聊天输出与变输入 replay。

## 2026-09-30 当前实际源码审查

Host `PPU-07`、容器 `minimaxM3.1`、镜像 `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`。Plugin editable tree `/workspace/vllm-plugin-FL` 为浅克隆 detached HEAD `cafe6363c8c3de5ba4693b91643089c17b3ab87c`，`origin/HEAD` 指向 `origin/main`，后者本地修订 `29712e42dba86680577aef9f2f6b5b7f04050a89`；本次工作树差异以已核实的 `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 为设计审查基准修订；因浅克隆无法在本地求 `origin/main` merge-base，未来真正 PR 的目标分支尚未确认，需在准备 PR 时重新核对完整分支历史。未进行 fetch、提交、推送或 PR。当前工作树相对 HEAD 的实际新增差异仅在 `vllm_fl/__init__.py`、`vllm_fl/ops/fused_moe/fused_moe.py`、`vllm_fl/patches/minimax_m3.py`、`vllm_fl/quantization/w8a8/moe_experts.py` 四个 tracked 文件，以及 `vllm_fl/patches/minimax_m31_w8a8.py`、`tests/test_minimax_m31_w8a8.py`、`tests/unit_tests/dispatch/test_minimax_m3_topk_compat.py` 三个本任务 untracked 文件；`git diff --check` 为 0。四个本任务开始前已有 `.orig` untracked 文件保持原样，不属于本轮变更。Plugin 无暂存/提交。原生身份 `01-environment/identity-after-topk-20260930.json` SHA-256 `54a303b65c08ac377eaa871d615c8f9509c5f8362616e7d25772fe8d37c77c37`，记录本轮完整 diff/文件清单与部署指纹 `803853bb265fc97fbeb3f1cac74f34e6ae20832624a5fb4a8ba71668d2087915`。

| 变更 | 职责与调用方 | 现有路径及守卫 | 已验证 / 剩余范围 |
|---|---|---|---|
| M3.1 metadata helper 与 `register_model` | 模型权重 packed mapping、vision 三路选择、BF16 head 与显式 OAI 参数 | 复用 general plugin 注册、compressed-tensors scheme 与 MoE quant config；幂等，非 CT 不设置 head 标记 | CPU 聚焦测试、48/48 权重与文本生成；视觉实推、旧 M3/其他平台整模未测；旧 `/mnt/cpfs/models/MiniMax-M3/config.json` 无 quantization_config，当前目标为 compressed-tensors，降低旧无量化路径的量化映射风险但不替代实测 |
| Plugin 两段 W8A8 MoE | PPU INT8 split gate/up 与已有 quantized MoE pipeline | `SWIGLUOAI_UNINTERLEAVE` 独立分支；`SILU` 仍经 FlagGems；缺失参数显式报错；未用 vLLM 不兼容的 `TritonExperts.apply` | PPU 数值 max_abs 0.1565 在冻结容差内、18 项聚焦测试、TP16 eager/decode-full；无性能结论 |
| PPU M3 prefill top-k | 当前 PPU Triton autotune 编译断言 | 仅 T-Head/topk=16，调用上游原 JIT 的固定 K128/warps4/stages2；其他 topk/vendor 沿旧路径；不复制 kernel | 单卡参考集合、3 项守卫测试、general plugin loader 与 TP16 服务通过；长序列性能及其他 PPU 版本未测 |
| FULL 图降级 | 当前 vLLM MiniMax sparse/indexer 后端能力限制 | 只在服务配置中选显式 `FULL_DECODE_ONLY`，未改 vLLM 共享引擎/后端 | 精确 FULL 首试、两个后端声明、6/6 decode 捕获、三次请求；full prefill 尚不可用 |

vLLM `/workspace/vllm` HEAD `ee0da84ab9e04ac7610e28580af62c365e898389` 与 FlagGems `/workspace/FlagGems` HEAD `6b49cff993956bff8cef495abd84f2acb6a63df6` 均 clean；FlagGems-vllm `/workspace/FlagGems-vllm` 有两处继承 tracked 修改，本任务未触碰。FlagGems 同步和 inference 服务停启操作、命令、核对结果分别在 001/003/004 与环境分析中记录。适配容器始终运行。

**阶段 3 设计审查结论：可作为以当前 `cafe6363` 修订为基准的受限 PR 候选。** 上游模型 loader 中该类 packed mapping 只在量化配置存在时传给 quant config；现场旧 M3 无 `quantization_config`，本目标是 compressed-tensors。目标 checkpoint 权重和推理已通过，`silu` guard miss、非 CT head、vision/text 分支、topk 其他形状/vendor 均有聚焦测试。旧 M3 实际服务、视觉请求和其他平台硬件未运行，不能声称已验证；真正 PR 的目标分支与完整祖先关系仍须在准备 PR 时确认。形式化十题、精度、性能、最终 launcher 属下一验收阶段，当前不宣称整项适配完成。若修改 Plugin，须重新采集部署指纹并重跑受影响的 eager/graph 与正式证据。复用经验仅保持本地问题记录，暂不提升为跨平台故障库条目。

## 2026-09-30 65k 上下文重测前源码复核

用户要求将 GPQA 生成上限提高到 60,000 后重测。新部署身份 `01-environment/identity-ctx65k-20260930.json` SHA-256 `3fc9bccc17fec5f723f1111eb01e227f1c3a0f852c5daec1a523c01bb654a0e5`，指纹 `f37fdc7e9b8677ab2a057b6c7df886fe556e7f941a034857dfd2ccca96643afd`；Plugin HEAD、tracked diff SHA-256 `eb6a48112f6b07a5e0fc456feb9571f967b2cdf927dca7253b3c8af7400db6fe`、工作树状态与所有 untracked 文件哈希均同上一轮，vLLM 和 FlagGems 仍 clean，FlagGems-vllm 的两处继承修改仍未触碰。变化仅为服务最大上下文 50,000→65,536 及评测生成上限。65k 服务再次尝试 FULL 后因同一 sparse/indexer 能力声明自动降为 decode-full；显式 decode-full 完成 6/6 图捕获、真实聊天及变输入 replay，十并发简单题 10/10。旧 50k eager 证据仍可证明相同源码的 eager 能力，未把它称为 65k eager 实测。适配代码职责、调用方、未测范围及 PR 基线限制维持上述设计审查；新源码复核回执将引用新身份和当前运行证据。
