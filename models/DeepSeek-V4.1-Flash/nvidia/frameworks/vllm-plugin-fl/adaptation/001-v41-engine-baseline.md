# 001：目标 vLLM 缺少 DeepSeek V4.1 基础模型与 tokenizer

## 元数据

- 状态：`open`（Plugin-only 实现中；模型导入被核心接口差异阻塞）
- 首次出现及最后验证：2026-09-23
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- 平台与 Host：NVIDIA H100 × 8，`H100-145`
- 容器与镜像：`xingchen4-flagos`，`sha256:d0af16489bc171d5434fc225c7afd89d32da7946af53655b9ad6dc7b50c745ca`
- Plugin / FlagGems / vLLM：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `7cd137ccaf09f25ce3012ba86438682072a69bc9` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式：尚未进入模型加载；eager 与 graph 均未验证

## 问题现象与诊断

W8A8-BF16 检查点声明 `DeepseekV41ForCausalLM` 和 `deepseek_v41`。
初始 vLLM 的 registry 与模型目录均没有 V4.1 类/模块，Plugin 也没有
V4.1 注册或实现。静态注册检查足以判定初始服务栈无法构造该架构；为避免
无意义的权重加载及 GPU 占用，尚未启动服务。此后仅在 Plugin 中实施选择性
移植，vLLM 源码和安装保持原样。

| 经验 | 相同点 | 关键差异 | 本次决定 |
|---|---|---|---|
| [H100-149 NV-native W8A8/BF16](../../../adaptation/001-native-vllm-w8a8-bf16.md) | 同一 checkpoint、H100 TP8 | 该现场已有完整 V4.1 原生 vLLM，且用户仅对 NV-native 路线授权直接改 vLLM；本现场所选 Plugin profile 要求 vLLM 只读 | 借鉴权重契约和数值验证，不搬用源码授权 |
| [Plugin PR #427](https://github.com/flagos-ai/vllm-plugin-FL/pull/427) | V4 系列、W8A8 量化和 H100 算子 | PR 的 model shim 继承 `DeepseekV4ForCausalLM`，不实现 V4.1 CED/CSA2/Engram/tokenizer | 作为 Plugin dispatch 设计参考，不当作 V4.1 底座 |
| MetaX V4 INT8 mapper 问题 | compressed-tensors INT8 | 本问题先于权重映射，缺的是整套模型入口与语义 | 不套用该 mapper 结论 |

现有 `ModelRegistry.register_model()` 与 `TokenizerRegistry.register()` 是入口扩展点，
但注册不生成模型计算。H100-149 参考 V4.1 树有 26 个 Python 文件、约 12,235 行，
还依赖 V4 公共实现。直接复制到 Plugin 既未证明与 vLLM 0.24.1 的内部接口兼容，
也不符合 `docs/plugin-contribution-policy.md` 的维护边界。上游 vLLM 的
[V4.1 tracking issue](https://github.com/vllm-project/vllm/issues/56400) 将模型注册、
模型定义和 kernel 分列，也印证 PR #427 的 V4 算子补丁不能替代完整 V4.1 底座。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 结果 |
|---|---|---|---|---|
| 1 | FlagGems revision | `0927d5a` | 授权的 `git fetch` + `git merge --ff-only`，目标 `7cd137c` | 成功；工作树干净，模型缺口仍在 |
| 2 | Plugin 配置与 tokenizer | 无 V4.1 入口 | 添加 `vllm_fl.configs.deepseek_v41`、`vllm_fl.tokenizers.deepseek_v41` 与窄范围注册 | 正式 `get_config()` 成功解析 40 层及 Engram `[1, 14]`；tokenizer 能编码并生成 DSML prompt；模型仍不可加载 |
| 3 | Plugin NVIDIA 模型源 | 无 V4.1 模型模块 | 将 H100-149 已验证 Apache-2.0 实现中 19 个 NVIDIA/通用源文件隔离移至 Plugin；另添加 V4 视觉塔依赖 | 25 个本次 Python 文件语法编译通过；模型导入仍失败，未注册、未执行权重加载或推理 |
| 4 | 锁定 vLLM 接口审计 | 模型导入失败 | 对 71 个 vLLM 导入模块及其符号逐项检查 | 缺 5 个模块、18 个符号；文本模型首个未补缺口为 `MEGA_MOE_BACKENDS`，后续 mHC、Engram、sequence-parallel、cache utilities；视觉路径另缺 `_plan_prompt_updates` |

第 4 轮的 5 个缺失模块为 `vllm.models.common.ops` 及其
`sequence_parallel` 子模块、`vllm.model_executor.warmup.jit_warmup`、
`jit_warmup_triton_helper`、`vllm.model_executor.kernels.mhc.warmup`。
18 个初始缺失符号中，mHC 是 `mhc_pre_delayed_tilelang` 和
`hc_collapse_triton`，Engram 是 `get_engram_dp_group/size`，缓存/注意力涉及
`CircularBufferSpec`、compressed slot mapping、sparse-SWA 元数据与索引 kernel。
另有 `MEGA_MOE_BACKENDS`、`_plan_prompt_updates` 和 SM120 FlashInfer 配置探测。
独立 Python 进程里的临时空函数只用于继续列举**导入依赖**，没有进入 Plugin
源码，也没有作为数值或推理验证；故该审计只是下界，尚未覆盖运行时方法契约。

FlagGems 首次 fetch 遭遇代理 503，未合并；同一无凭据代理重试成功。
没有使用带凭据代理。此后已分别核对 FlagGems 与 FlagGems-vllm 的 mHC、
Q/KV RMSNorm 和 top-k/SWA 算子接口，实测见 [002 号问题](002-v41-operator-contracts.md)。

后续仅在 Plugin 中补了锁定版缺失的模型局部常量、Engram DP1 守卫、
sequence-parallel 辅助函数和图像标记隔离。模型导入依次越过
`MEGA_MOE_BACKENDS`、`get_engram_dp_size`、`vllm.models.common.ops`、
`jit_warmup`，当时首先停在 `CircularBufferSpec`。目标 vLLM 的
`kv_cache_interface.py` 没有此类型；H100-149 新版除这个类型外，还新增了
`CircularBufferManager`，并在 `model_runner.py` 对其关闭通用 slot mapping、
调整 block-table 宽度。锁定版虽有 `KVCacheSpecRegistry` OOT 注册入口，
但尚未验证它能承担上述 runner 与调度语义，不能用同名空类绕过导入。

2026-09-23 后续进展：Plugin 已以固定地址每请求环形状态代替缺失规格，
局部数值和 Graph 验证见 [003 号问题](003-v41-circular-cache-contract.md)。
FP8 indexer 选择函数也已限定在 Plugin/H100 路径。最新导入首个失败为
旧版 SWA 缺 V4.1 层类型 `_LAYER_TYPE_C1A`，见
[004 号问题](004-v41-swa-layer-types.md)。因此前述 `CircularBufferSpec`
是历史失败点，不再是当前导入首错；整模仍不可加载。

## 根因与修改边界

- 已验证根因：目标 vLLM 基线缺少 V4.1 model、registry 和 tokenizer；PR #427
  只覆盖 V4 的 Plugin 模型/算子路径。
- Plugin 应承担 V4.1 特有的量化契约、算子选择、NVIDIA capability 与
  graph 适配；公共调度代码不得加入模型名/机器名分支。
- 用户明确锁定当前 vLLM，因此底座升级不在本次范围。目标是在 Plugin 中以
  正式 registry/tokenizer 和现有 dispatch/backend 接口补齐 V4.1 所需语义。
  需要先证明锁定 vLLM 的公共扩展点可承载 V4.1 cache、mHC、Engram 和
  attention 后端；不能把上游整棵模型树直接复制进 Plugin。
- 上游 V4.1 模型定义 PR #56228 涉及 47 个文件，不仅新增模型，还修改
  `vllm/v1/attention/backends/registry.py`、`sparse_swa.py`、mHC kernel、
  quantization 和既有 V4 源码。PR #56214 进一步修改 config、quantization、
  KV cache、GPU runner 等公共路径。因此需逐项找 Plugin 扩展点，不能仅注册一个
  `DeepseekV41ForCausalLM` 别名。

### Plugin-only 接入清单（实施前设计）

| 链路 | 现有扩展点或依赖 | 缺口与预定归属 | 首轮验证 |
|---|---|---|---|
| 模型配置 | Plugin 的 `register_model()` 已注册 GLM 配置；vLLM `_CONFIG_REGISTRY` | V4.1 嵌套 `text_config`、视觉配置及 `expert_dtype` 展平放 Plugin config；仅 `deepseek_v41` key 命中 | 配置加载、未命中模型行为、重复注册 |
| DSML/tokenizer | `TokenizerRegistry.register` 支持外部模块类 | 将 V4.1 编码协议和 tokenizer 封装放 Plugin；只注册 `deepseek_v41` mode，入口惰性导入 | 官方 encoding 向量、文本/工具提示词、序列化 |
| CED/CSA2 主干 | `ModelRegistry.register_model`；现有 V4 model / sparse-SWA backend | 需 Plugin 模型类及专有 cache/attention，实现前验证现有 backend `CUSTOM` 是否足够，不把 V4 类误当作 V4.1 | 模型构造、KV layer spec、短 prefill/decode |
| Engram | `get_model_state_cls()` 钩子在锁定 vLLM 可用 | Plugin model state 传递跨 chunk token 历史；缺失的 Engram DP/配置接口限制为当前 TP8、DP1 并显式守卫 | hash、查表、rank 合并、chunk 边界 |
| mHC | vLLM 已有 V4 mHC kernel，但缺 V4.1 delayed-pre 形式 | 仅在 Plugin 补必要算子/适配，不能省略 Sinkhorn 或更改 1e-20 norm epsilon | 固定张量对照、eager、graph replay |
| MoE/W8A8 | V4 MoE / compressed-tensors、FlagGems 新 revision、PR #427 | 在模型与 Plugin dispatch/backend 补 V4.1 noaux_tc、INT8 expert/`wo_a`、视觉量化与 BF16 Engram；避免全局改默认量化策略 | 参数名/dtype/layout、数值、H100 graph |
| 视觉与 DSpark | 上游专用实现，当前 Plugin 无注册 | 文本基线后单独接入视觉预处理/router；DSpark 先关闭以验证普通 AR，再独立验 draft | 图文 smoke、token span、spec 验证 |
| 服务与图 | vLLM OOT model/backend，Plugin 现有 vendor dispatch | 先 full graph，再有证据时降至 decode-full；TP8、正常前缀缓存；原有模型/平台不得改变 | readiness、eager、graph capture/replay、非目标模型导入 |

当前可先隔离实现配置与 tokenizer，这两项不触及锁定 vLLM 的源码或
公共热路径。主干移植须先核对上述接口后再扩大产品 diff；不能把一个
注册成功误称为整模适配成功。

当前 Plugin `main@fd5c727` 有本次新增的配置、tokenizer、模型文件和
`vllm_fl/__init__.py` 注册改动；原 checkout 干净，没有 inherited diff。
`git diff --check` 与 25 个 Python 文件的语法编译通过。实际 diff 尚未完成
设计审查：模型类尚不可导入，不能注册为正式架构，不能测试共享调用方、
eager/graph 或 TP8 数值。PR base 及完整影响矩阵尚未确认，不创建 PR。
vLLM/容器镜像未改，容器未停启。环境回执及部署指纹是产品修改前的基线，
待可运行实现形成后必须重新采集当前 diff、重绑定并验证，不得沿用旧指纹验收。

## FlagGems 证据

- 已授权同步后 revision：`7cd137ccaf09f25ce3012ba86438682072a69bc9`，
  `master`，`git status --porcelain` 为空。
- mHC 与 Q/KV RMSNorm 已做目标 H100 数值及局部 CUDA graph 对照；
  top-k/SWA 普通文本与 FlagGems 一致，V4.1 独有的 `out`/图像可见范围
  仍须保留 Plugin Triton 路径。详见 [002 号问题](002-v41-operator-contracts.md)。
- 尚无 FlagGems 缺陷，因此未创建 `07-bugs/` 复现。

## 验证、限制与下一步

架构、环境阶段的基线已由目标容器内项目校验器核查；
适配阶段前置检查通过。现有 Plugin 配置/tokenizer 已通过目标模型实测，
模型源和若干独立算子通过语法、数值及局部 graph 检查，尚有锁定 vLLM 的
KV 缓存与调度接口差异；最小推理、整模 eager、
全图与 decode-full graph 均未运行，不能标为 functional。需要先解决
锁定 vLLM 下的 Plugin 扩展接口缺口，然后以 W8A8-BF16 TP8 最小负载起步，
按 full → decode-full 次序做 graph，
再进入 sanity、精度和性能验收。知识库状态：`local-only`；当前问题属于
具体版本组合，不提升为跨模型故障经验。
