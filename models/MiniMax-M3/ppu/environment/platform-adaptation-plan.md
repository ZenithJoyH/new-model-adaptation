# MiniMax-M3 / PPU 平台适配计划与差距清单

## 输入材料与基线

- 模型结构：`../../architecture-and-inference.md`。
- 环境与详细差距：`environment-analysis.md`。
- 用户材料：权重 `/mnt/cpfs/models/MiniMax-M3`、Host `PPU-13`、容器 `minimaxM3`、工作根 `/mnt/nfs/users/jinghao/minimaxM3`；未提供额外 patch。
- Plugin：editable `/workspace/vllm-plugin-FL`，`29712e42dba86680577aef9f2f6b5b7f04050a89`，clean。
- FlagGems：editable `/workspace/FlagGems`，从同步前 `4d9c3477548fe9ae968fc042b09d32b179860026` 快进至 `be05ef1db6758adca7a18de3bf529c18a6ac9a87`，clean、`master...origin/master`。
- vLLM：`/workspace/vllm`，`ee0da84ab9e04ac7610e28580af62c365e898389`，detached clean，只读。
- 已阅读 Plugin `README.md`、`vllm_fl/dispatch/README.md`、`tests/README.md`、`tools/adaptation-gate-cases/README.md` 和本仓库 `docs/plugin-contribution-policy.md`。

## 修改边界

- 产品变更只进入已核实的 editable Plugin 源码与可维护 focused tests；不在工作根创建源码副本。
- vLLM 全程只读并保留前后 HEAD/status。FlagGems 仅在 clean、tracking 明确时做 `pull --ff-only`，不改实现。
- 一次性诊断与运行产物分别留在远端 `02-issues/`、`05-tmp/`、`04-runs/`；缓存留在 `06-cache/`。
- 不停止、重启或删除 `minimaxM3` 容器。只管理本适配启动的精确服务 PID/端口。

## 差距清单

| ID | 组件 | 当前路径/能力 | 算子来源 | eager / graph 影响 | 计划 | 状态 |
|---|---|---|---|---|---|---|
| G01 | config/registry/loader | vLLM 原生 MiniMax-M3 | vLLM 已支持，Plugin 平台 hook | spawn 注册、loader 与平台 ABI | config/registry/model-class import 已通过；TP16 全量加载已完成 59/59，待服务就绪 | validating |
| G02 | fused QK norm + partial RoPE + cache insert | 原始环境缺少 `torch.ops._C.fused_minimax_m3_qknorm_rope_kv_insert` | FlagGems 同步后无兼容实现；使用 Plugin-owned Triton + `vendor.thead` dispatch + `_C` ABI bridge | eager 直接失败；graph 需稳定 out/cache alias | dense/sparse/padding/独立 mapping/外部输出/graph focused 4/4，固定种子 20/20 | mitigated |
| G03 | Gemma RMSNorm | vLLM 直接用 FlashInfer | vendor wheel 可在 PPU 执行 | in-place alias 与 capture | eager 普通/fused shape 与 graph replay 已通过 | resolved |
| G04 | MSA indexer/sparse attention | vLLM common Triton 的 prefill top-k constexpr assert 在 PPU 编译失败 | Plugin 提供 T-Head-only 等价 prefill top-k kernel；decode/sparse attention 保持 vLLM 原路径 | top-k、block 128、eager break | prefill/decode index 与 sparse-attention prefill/decode 均已通过定向测试 | mitigated |
| G05 | dense attention | Plugin `vendor.thead` FA3 | Plugin 已支持候选；当前 vLLM 移除的未使用导入已清理 | KV head 复制、paged cache、graph | Thead FA3 backend class 导入已通过；整模前三层待服务推理覆盖 | validating |
| G06 | SwiGLU-OAI/MoE | vLLM FusedMoE + Plugin/FlagGems | T-Head bias router 以单 group `grouped_topk` 替代缺失 native op | FP32 sigmoid+bias router、top-4、shared expert | 候选 eager/graph 通过，组合回归 10/10；待整模 experts | mitigated |
| G07 | vision/video | vLLM vision tower/processor；Plugin partial-aware `ApplyRotaryEmbFL` | 原 OOT fallback 不支持 78/80 partial RoPE；Plugin focused 修复 | 动态 grid、partial RoPE 与 graph bucket | partial/full/graph 3/3；待整模 dummy profile、单图和短视频 | mitigated |
| G08 | TP16/cache/service | 16×96 GiB；默认 block 16 与 MSA 要求 128 冲突 | 运行配置 | load/graph/KV 资源 | 显式 block 128、max len 50000、逐级 bring-up | open |
| G09 | reasoning/tool parser | vLLM 已有 | vLLM 已支持 | 流式边界/特殊 token | 固定模板 API 测试 | open |
| G10 | MTP | checkpoint 有 7 modules，普通 loader 跳过 | 独立后续范围 | speculative metadata/cache | 首轮禁用，不宣称支持 | deferred |

## 设计选择与共享影响

| 变更 ID | 职责层级 | 复用扩展点 | 守卫与未命中行为 | 代表性回归 |
|---|---|---|---|---|
| G02/G03 | Plugin 的 PPU platform hook 或既有 dispatch/vendor backend | `register()`/custom-op schema、`CachedOp`/backend registration | 仅 `vendor_name=thead` 且精确 op contract 命中；其他平台保留现有 vLLM/Plugin 路径 | PPU dense/sparse MiniMax；非 MiniMax model import；无 PPU 依赖的 unit import |
| G04 | 先复用同步后 FlagGems；缺失时 Plugin-owned PPU kernel | 现有 operator dispatch/backend，禁止模型层直接调 FlagGems | dtype/head/block/cache contract 不满足则显式 unavailable，不在部分 cache 写入后 fallback | eager/graph、prefill/decode、padding、跨块 |
| G08 | 远端 runtime configuration | vLLM CLI 与 Plugin 平台配置 | 只绑定本服务实例；不改全局 graph/prefix-cache 默认 | TP16 load、eager、graph、并发 |

所有可选 vendor 依赖延迟到 thead 路径加载；注册必须对 fresh/spawn/repeated process 幂等。不得捕获任意执行异常后静默 fallback。临时 workaround 必须记录作用域、性能代价与移除条件。

## FlagGems 同步与检索计划

- 同步前：`origin`/`master`/`origin/master`，revision `4d9c3477548fe9ae968fc042b09d32b179860026`，clean。
- 命令：在 `/workspace/FlagGems` 执行 `git pull --ff-only origin master`，保留前后 revision/status。
- 同步后 revision：`be05ef1db6758adca7a18de3bf529c18a6ac9a87`，clean。检索结果：无 MiniMax-M3 同名算子；DeepSeek-V4 fused op 与 generic sparse attention 的 dtype/shape/layout/cache contract 均不兼容；Gemma RMSNorm 与 SwiGLU-OAI 候选仍需 PPU 数值验证。

## 运行配置与验证顺序

工作根 host/container 均为 `/mnt/nfs/users/jinghao/minimaxM3`。服务初始 TP16/PP1、`--block-size 128`、`--max-model-len 50000`，prefix caching 在非性能工作保持开启。每个 worker 的 `cwd` 为工作根，`TMPDIR` 指向 `05-tmp/`，编译/框架缓存指向 `06-cache/`，日志/结果指向 `04-runs/`。

顺序：import/registry → G02/G03 单算子 → indexer/sparse/dense attention → MoE → dummy/model construct → TP16 load → eager service → graph service → 正式验收。任何窄测试失败时不进入更宽测试。
