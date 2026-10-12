# 003：端到端优化代码设计审查

2026-10-10，Agent 对实际安装的 Plugin 与 FlagGems-vLLM 本轮增量自审。
三个指定场景的端到端性能和正常启动验证已完成；本记录不能代替正式精度或完整适配验收。

## 身份与差异

范围仅 mx-59 / `qwen3.6-35B`，解释器 `/opt/conda/bin/python`，实际 editable 目标为
`/workspace/vllm-plugin-FL` 和 `/workspace/FlagGems-vllm`。不存在第二 checkout/import
override。Plugin HEAD `675548ab`（detached），FlagGems-vLLM HEAD `05d0ff05`；
PR base 未确认，未创建提交或 PR。完整初始身份与既有 dirty 清单在
`01-environment/e2e-opt-20261009/`，本轮 15 文件 before/after SHA 与逐文件补丁在
`02-issues/e2e-opt-20261009/product-payload-v3.json`，应用回执为
`01-environment/e2e-opt-20261009/product-applied-v3.json`。

Plugin 初始含此前 MoE 迁移以及 GDN/attention 等 9 tracked 修改、6 untracked 文件；
库初始 attention scheduling/splitkv 两项 tracked 修改及两个 untracked 测试均保留。
本轮增量不能和全部 HEAD diff 混称为同一提交。FlagGems `c6f46cc9` clean 且未修改；
vLLM `bc150f50` 保留原 `fused_recurrent.py` dirty，不能称为 clean。
每次原生性能 controller 重新冻结四组件 HEAD、完整 diff SHA、status 与全部 untracked SHA，
并在完成后逐项重验。最终handoff再次验证15个修改后SHA，正常服务30个长输入、8个
短样例和2次重复prefix检查后再次核对四组件全部身份一致。短样例只证明HTTP返回，
其中2个达到输出上限；没有用这些样例声称正式精度通过。

## 逐文件职责

下表 Plugin 路径相对其仓库；`src/`、库 tests/benchmark 路径相对 FlagGems-vLLM。

| 文件 | 必要性、调用方与兼容行为 |
| --- | --- |
| `vllm_fl/ops/fused_moe/fused_moe_utils.py` | 既有 MetaX 无 LoRA FP16/BF16 SiLU、无 expert-map 完整入口复用 modular caller workspace。交换 workspace 角色，保持 output identity；旧库/不支持布局在计算前选择原 outplace+copy，不在失败后重试。量化、LoRA、map 与其他平台原分支不变。 |
| `vllm_fl/patches/gdn_linear_attn.py` | 保留现代库下原生 packed class 流程，在其 module-bound kernel 调用点通过既有 dispatch 接入。仅创建 q/k/v metadata view，传递 caller out；能力/blacklist/vendor 守卫不命中时提前选择 native。幂等 hook；stateful dispatch 严格失败传播。 |
| `vllm_fl/dispatch/backends/flaggems/flaggems.py` | 现有 `default.flagos` GDN backend 内按 MetaX paged API 能力选择融合实现；新 `out=None` 默认不影响旧调用。不支持 output-buffer ABI 的 general adapter 提前报错，不进行部分更新后回退。 |
| Plugin `tests/functional_tests/ops/test_metax_moe_fl.py` | 对已有真实完整路径补充 workspace 交换、caller output 和实际库入口命中断言，不 mock 目标计算。 |
| Plugin `tests/unit_tests/dispatch/test_packed_gdn_dispatch.py` | 隔离选择协议、黑名单/vendor/旧库/布局守卫、失败不重试、重复安装和非 MetaX 惰性依赖；mock 只验证选择。 |
| Plugin `tests/functional_tests/ops/test_metax_gdn_prefill_fl.py` | 实际 installed backend 的独立 FP32 输出/状态参考，varlen、零长度、两次改变 descriptors 的 replay，检查原输入与 padding storage 不变。 |
| `src/flaggems_vllm/runtime/backend/_metax/ops/fused_moe.py` | 库负责有限 BF16 E256/TP2 tile、完整 MoE 可选 caller-buffer ABI 和纯 metadata alias/size 能力判断。默认分配 ABI 保留；M1025–4095 和未验证大 batch 不改。多 chunk 禁止 output/activation workspace alias。无新 Torch compute fallback。 |
| `src/flaggems_vllm/runtime/backend/_metax/ops/paged_gdn_update.py` | MetaX 专用纯 Triton，融合 gate、QK normalize 和 V-major 页状态更新，直接写 caller out。守卫限定单 token、支持 dtype/layout/head geometry；null/padding 不更新；唯一活跃 indices 为 caller 前置条件。无 GPU 数据回读能力查询，无异常重算。 |
| `src/flaggems_vllm/runtime/backend/_metax/ops/__init__.py` | 在既有 MetaX ops 中导出上述能力/API；其他 vendor 不需要导入此模块。 |
| `src/flaggems_vllm/ops/FLA/wy_fast.py` | 新 keyword-only `chunk_indices=None`，默认保持原行为；合法 caller descriptors 直接使用，避免 identity cache 在动态 replay 中复用旧映射。公共接口改变仅为可选参数。 |
| `src/flaggems_vllm/runtime/backend/_metax/fused/gdn_chunk.py` | 将既有 fwd 已接收的 descriptors 完整传到 WY；不复制 prefill 算法或修改计算 kernel，不新增原有 LICM workaround。 |
| 库 `tests/test_metax_paged_gdn_update.py` | 真实 eager/graph、两次变输入、dtype/head/layout/null/空输入矩阵与非法 alias 拒绝；检查原 state identity 及 padding 字节。 |
| 库 `tests/test_metax_moe_workspace.py` | 完整函数对 FP32 MoE，对照 caller-owned scratch、hidden/output alias、真实 modular alias、输入 router-weight、bias、多 chunk 保护和错误 buffer。 |
| 库 `benchmark/test_moe_workspace.py` | 原生 benchmark 对比同一完整算法的分配+copy 与 caller-buffer API，真实 Qwen TP2 shape；不能单凭它宣称 tile 或端到端收益。 |
| 库 `benchmark/test_FLA/test_paged_gdn_update.py` | 原生 packed native 与融合库路径对照，分别 operator/cudagraph；所有输入与缓存使用原 benchmark 体系。 |

完整入口仍发出 align、两 GEMM、activation 和 sum 等多个 kernel；Python 函数名中的
fused 不意味着只有一个 GPU launch。收益来源必须分别归因于实测 tile、workspace/输出
复用、packed 数据路径和端到端调度，不能以“完整入口必然更快”代替测量。

## 回归与限制

- 实际安装路径 196 项通过，无 skip：Plugin unit 26、functional 23，库 functional 147。
  数值测试不扩大容差，包含两次变输入 graph replay、cache/state/output 所有权。
- GPU0 补充 `[4096]`、`[8192]`、`[8129]+63*[1]` 的实际 prefill FP32/eager/replay 三项通过，
  用于更大prefill batch的调度验证；证据 `gdn-large-regression-v4/`。修正FLAGGEMS_CACHE_DIR
  指向批准根后196项与上述3项再次通过，见 `cache-regression-v6/`、`gdn-large-regression-v6/`。
- 旧大 batch 共享内存失败与旧 prefill metadata replay 失败保留；实际安装修复后的
  最小复现位于 `07-bugs/e2e-opt-20261009/`，两个 reproducer 通过。
- 本机 TP2 真正服务两个 rank 的 trace 命中完整 MoE、paged GDN、MetaX prefill、FGV attention；
  诊断严格policy与实际启动/capture已验证；最终性能服务正常dispatch policy、无全局
  strict/黑名单，三个场景各3轮剔除首轮，原生validator零错误且每轮128成功/0失败。
  4K/16K/64K输出总吞吐分别提高21.3%/65.2%/49.0%，batch8192/mem0.9为组合方案，
  不能全部归因于MoE内核。4K/64K P99 ITL变差，完整指标和取舍见适配003。
- 非 MetaX 可选依赖、量化守卫、旧库 compatibility 和 stateful 错误传播已做协议隔离；
  NVIDIA/其他平台实际硬件、量化/LoRA 数值、多 token speculative/KDA、训练反向未验证，
  不扩大支持声明。shared WY 默认参数兼容由原调用保持验证，不宣称跨平台设备验收。
- M2048 配置候选退化已撤回；FA 有限调度没有稳定收益，保留原实现与 inherited dirty。
- FlagGems 同步超时且上游差异较大；本轮不升级、不新增 FlagGems 算子选型。正式同步、
  整模精度与镜像 fresh-container 验收均不声称通过。
- 原生 graph iter500 展开过大，精确中止其 PID；失败回执保留。iter20 恢复通过，196 项
  数值回归与恢复 benchmark 合并回执 `installed-validation-v4.json`，未改写旧失败。
- 最终launcher端口检查曾因未设SO_REUSEADDR误报占用，独立临时端口复现后修正；
  按最小启动要求将端口/就绪检查移至外部控制器。第二次实际ready后发现hybrid默认
  prefix关闭，保留断言失败，最终显式启用prefix/align并完成正常请求和命中验证。
  两次失败没有重写为通过，产品代码与性能回执未改。

## 当前结论

本轮15文件增量符合现有职责与派发边界，在该受限目标完成安装验证。没有新的
模型名/服务名/Host 特例、厂商全局导入依赖、第二份源码、静默异常回退或 vLLM 写入。
最终服务PID532870/startticks451914343，GPU4/5、BF16 TP2、context262144、batch8192、
mem0.9、FULL_AND_PIECEWISE/capture64，显式prefix/align。内部脚本
`/opt/flagos/qwen3.6-35b/start-model.sh` 与工作根副本SHA256相同：
`b61577129c0c2683a3fe99ae37de3e3de9a1c807f16926c5092e7ae0dfce7adb`。
实际由内部副本启动，健康HTTP200；源码和内部脚本均在容器root filesystem，未制作新镜像。
证据相对远端批准根：`04-runs/e2e-opt-20261009/service-production-v9/`、
`production-check-v9/` 与 `finish-v9/progress.json`（后两项同一运行根）。
Hybrid prefix在安装版仍标experimental，本轮仅验证30个长输入及重复prefix，未扩大支持声明。
短样例中首都问题在128上限被截断、512补查最终答Paris，生成形式与此前服务有差异。
PR base、跨平台设备、正式精度与fresh-image仍未验收；因此不标记框架阶段或`optimized`完成。
