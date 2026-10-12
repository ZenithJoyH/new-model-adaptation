# PPU 插件精简交付与新 FP8 权重验证

## 当前结论

2026-09-04，PPU-13 / 容器 `glm5.3-flash`。
插件仍为 `/workspace/vllm-plugin-FL-glm53-hy4-adaptation`，基于
`ZenithJoyH/vllm-plugin-FL: support-hy4-preview@5329cb1293f397fd194852496cfcc710c35f1bfc`，editable 安装。
本轮已完成确认可移除的冗余、配置去重、注册路径统一和共享 hook 作用域收敛；代码可审阅。
**新权重整模验证失败，不能宣称新版本 functional 或精度通过。**

相对 HY4 HEAD：首次审计 62 文件、9958 新增/99 删除；第一批后 60 文件、9682 新增/11 删除；本轮最终为
**51 文件、8979 新增/6 删除**。数字包含模型、算子、测试和文档，不能等同于纯硬件改动量。
当前 diff SHA256：`c2fadfffe31ef3b3b39101c39a247f09fb82c62d365b9d350a95ff0080ad92fc`。
建议在上述容器目录用 `git diff HEAD --stat` 和 `git diff HEAD -- vllm_fl` 审阅；索引仍有此前迁移的暂存状态，不能仅看默认 unstaged diff。

## 精简清单

| 项目 | 结果 |
| --- | --- |
| 重复 MLA prefill | 第一批已删除，复用 HY4 CUSTOM prefill |
| 重复 sparse attention | 零 RoPE、非零 RoPE、padding/cache 裁剪的真实 PPU kernel 和 graph 测试通过后，删除 GLM 子类及模型专用 backend 选择 |
| CUDA 专属 GLM 扩展 | 归档 3 个 CUDA impl、恢复 CUDA register_ops、移除 vendor dispatcher 中 CUDA 特殊分支和 nvidia.yaml；不删除 HY4 原有 CUDA 能力 |
| 两份 PPU 配置 | 删除 examples/glm5_next/thead.yaml；唯一部署来源为 dispatch/config/thead.yaml |
| 全局 blacklist | 撤销旧 GLM 整批带入的额外列表，恢复 HY4 38 项原清单；slice 仍保留。新 YAML 仅相对 HY4 增加 6 行，绑定 4 个 GLM 算子 |
| 共享 utils/platform | 两者恢复到 HY4 HEAD；不再为当前默认启动路径保留外部 profile 兼容改动或 GLM 专用 sparse 路由 |
| 算子注册 | GLM helper 统一走 register_many；FlagGems 注册入口显式传递同一过滤函数，依赖算子过滤保留。修复原失败，不修改其 mock/断言 |
| KPool 补丁时机 | 从通用 register_model 移至 GLM config/worker 初始化；非 GLM 插件注册不安装缓存 hook |
| 说明文档 | 删除过期 CUDA/重复 subclass 声明，明确唯一配置来源、必要算子契约和验收限制 |

## 有依据保留的代码

保留 GLM 配置、KDA、KPool/tail、mHC、MoE clamp、conditional-generation wrapper/processor。
保留按输入布局选择实现的 supports/CachedOp 扩展和显式运行失败不重试策略，避免状态部分写入后再次执行；本次没有为减少行数放宽异常处理。
保留实际需要的 v0.24 分组/压缩页/混合 cache adapter，只收敛安装作用域，不宣称这些功能可由 HY4 普通 indexer 替代。
数值与 graph 测试、PPU 使用的 reference/portable 路径均保留。

## 测试与备份

- 注册统一后：原 **318 项全部通过**，其中原量化注册失败用例未改动。
- CUDA 实现移出时，同步归档 5 个 CUDA 专属测试实例：top-k 选择 2、CUDA lazy 注册 1、CUDA page contract 2。完整原测试文件随实现备份，不以跳过失败用例实现通过。
- 剩余公共/PPU 回归在最终配置上 **313/313 通过**。
- KDA/mHC/indexer/tail 专项 **28/28 通过**，含 eager/graph、数值和动态输入重放。
- 新共享 hooks 专项：prefill 8 组、sparse 4 组通过；再次以 worker 的实际 `flag_gems.enable(unused=blacklist)` 策略执行也通过。
- 普通 `register_model()` 未改写 Platform._align_hybrid_block_size 的独立断言通过。
- AST、`git diff --check`、本地 `./scripts/syntax-check` 通过。
- vLLM 仍 `ee0da84ab9e04ac7610e28580af62c365e898389` clean；FlagGems 同步前后均 `9553ae9c745bdf5fd4a25d50e0d67bf80d888030` clean。
- YAML SHA256：`b74bbec4558134b5c4cc106c755ce2dcd6946d164ee27465364ca3c320e600aa`。

可恢复备份均在容器 `/workspace/glm53-adaptation-runtime/`：
`refactor-shared-prefill-20260904`、`cleanup-registry-20260904`、`cleanup-scope-20260904`、
`cleanup-format-20260904`、`cleanup-blacklist-20260904`。
备份保存原文件、diff 和校验和；没有永久删除权重、旧插件归档或用户数据，没有 commit/push。
scope 阶段写入后曾因 model_ops.py 末尾空行导致 diff-check 失败；单独 format 阶段修复并重新验证，不曾忽略该错误。

复现入口：`cleanup-ppu13-plugin.yml -e cleanup_stage=<stage>`（一次性，有备份存在则拒绝重跑）、
`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-hy4-glm53-migration.yml`、`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-sparse-hooks.yml`、
`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-cleanup-components.yml`、`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/inspect-ppu13-cleanup-final.yml`。
均用 `./scripts/playbook models/GLM-5.3-Flash-BF16/ppu/adaptation/<file>` 执行。

## 用户更新的新权重不是原 BF16 快照

当前路径：`/mnt/cpfs/models/GLM-5.3-Flash`，served name `GLM-5.3-Flash`。
用户的远端启动脚本已同步，本轮没有覆盖用户脚本；只同步了本地 graph 脚本记录。
本目录名称保留历史 BF16 适配记录，不代表新权重仍为 BF16。

- config SHA256：`bb8f01c42cb92a52ca72e65afb4d5bd8d11aef083cd210e8de25dfb904f23e9f`。
- index SHA256：`3c3f40366a53c3fd7974b4eab7881a365a98c2a4329150befebab99fe7c18b05`。
- 62 个分片均存在且非空，文件总计 328337455672 bytes；读取头部统计 F8_E4M3=37338、BF16=1141、F32=37629 个 tensor。
- quant_method=fp8、fmt=e4m3、activation_scheme=dynamic、weight_block_size=[128,128]。
- 仍是 34 KDA + 11 sparse MLA、conditional generation，最大上下文 1048576，服务保持 50000。
- 配置加载和 EngineArgs.create_engine_config 通过；这仅是配置验证，不代表所有层可构造。

## 新权重整模失败原因

以用户脚本启动 TP16 graph：API PID425707、EngineCore PID426192，2026-09-04 14:56:43 开始，15:00:07 worker 初始化失败。
服务自动退出，8010 未监听；未停止/重启容器，诊断时未发现残留 VLLM 服务进程。
日志 `/workspace/glm53-adaptation-runtime/graph/service.log`；旧日志已保存到
`cleanup-validation-prior-service-20260904`。没有运行最小生成、并发8或 GPQA，准备的 smoke 脚本未执行。

首个失败是线性层 FP8 分块校验：
`Weight output_partition_size = 4 is not divisible by weight quantization block_n = 128.`

证据链：

1. 新 checkpoint 的 `model.language_model.layers.0.self_attn.b_proj.weight` 实际为 BF16，shape=[64,4096]。
2. quantization_config.modules_to_not_convert 包含 `model.layers.0.self_attn.b_proj`。
3. wrapper 的 language_model 前缀叠加 CausalLM 的 model 前缀，得到 `language_model.model.layers.0.self_attn.b_proj`。
4. 使用 vLLM 实际 is_layer_skipped 函数验证：原配置前缀 True，运行时前缀 False。该层误走 Fp8LinearMethod，TP16 后 64/16=4，不满足 block128。

这是新 FP8 checkpoint 的未量化层名称映射缺口，失败点尚未运行量化 kernel，不能归因于缺失算子。
本轮未改权重/config，也未绕过分块校验；需后续补充前缀映射兼容、逐层验证量化方法及新 FP8 kernel，再继续整模验证。
旧 BF16 82.32%/未达88分的 GPQA 记录仅作为历史，不用于此 FP8 快照验收。

## 用户补充的算子来源

已检查 [FlagGems-vllm](https://github.com/flagos-ai/FlagGems-vllm) 的 README：提供 vLLM 场景融合算子，通过 `flaggems_vllm` 包供插件调用，与通用 FlagGems 互补。
本容器 `find_spec('flaggems_vllm')` 为 None，当前未安装或接入新增实现；不会声称已验证 PPU 兼容性。
若后续确有缺失算子，先记录该仓库精确 revision、API、dtype/layout 和 PPU/Triton 约束，通过既有 dispatch 接入，再执行独立数值/eager/graph 测试。
当前前缀匹配错误不由替换算子解决。
