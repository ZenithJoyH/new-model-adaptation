# 001：mx-59 的 Plugin MoE 调用迁移至 FlagGems-vLLM

日期：2026-10-09。范围：仅修改用户指定的现有容器中 MoE 调用并做局部回归；
完整模型适配与正式验收仍未完成。

## 已验证环境与写入边界

- Host：`mx-59`，容器：`qwen3.6-35B`，ID：
  `6821737fcd966f3026820b1a5d6122125bc5faa0750313771b1a052ce7129867`。
- 镜像：`flagos/qwen3.6-27b-metax:public-flash-20261008`；当前服务读取的模型为
  `/public-flash/models/Qwen3.6-35B-A3B`，架构为 `Qwen3_5MoeForConditionalGeneration`。
- 用户确认 host/container 工作根均为 `/public-flash/jinghao/qwen3.6-35B`。
  Docker inspect 确认 `/public-flash` 同路径可写 bind mount；两侧 root 的 realpath
  相同，stat 均为 `53:7692957`。本次只新增编号诊断、运行、临时和缓存目录，未迁移原文件。
- 解释器为 `/opt/conda/bin/python`（Python 3.12.11）。实际安装：
  Plugin `/workspace/vllm-plugin-FL/vllm_fl`，FlagGems `/workspace/FlagGems/src/flag_gems`，
  FlagGems-vLLM `/workspace/FlagGems-vllm/src/flaggems_vllm`，vLLM `/workspace/vllm/vllm`。
  不设置 `PYTHONPATH` 或其他 import 覆盖；产品改动位于未被上述 bind mount 覆盖的容器源码。
- Plugin `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，版本 `0.2.0`；
  FlagGems `c6f46cc970ea0bef8927ee657c021bd8621e3bb0`；
  FlagGems-vLLM `05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777`，版本 `0.1.0`；
  vLLM `bc150f50299199599673614f80d12a196f377655`，版本 `0.20.2+empty`。
- Plugin 原有 7 个 tracked 修改和 4 个 untracked 文件，涉及 GDN/attention 等；
  FlagGems-vLLM 原有 flash attention 修改；vLLM 原有 `fla/ops/fused_recurrent.py` 修改。
  全部保留。本任务只写 Plugin 的两个 MoE 文件及两个新增聚焦测试。

## 问题与职责

MetaX 的 `TritonExpertsFL.apply` 原先走 GEMM1 → activation → GEMM2 → sum 的分阶段
路径，`default.flagos` 的 align/GEMM/sum/top-k adapter 仍导入 `flag_gems`。
旧实现真实设备回归在 `hits["topk"] > 0` 处失败，证明没有调用 FlagGems-vLLM。
本次复用既有 backend 和无 LoRA fast-path 扩展点，不新增模型名/Host 分支或修改 vLLM。

历史参考为 legacy `metax/adaptation/001-flaggems-vllm-gdn-fused-moe.md`：同为 Qwen、
MetaX 和 out-of-place experts 契约；但原记录是 mx-104、不同源码 revision 与 expert
中间维度，不能继承其结果。本次重新检查当前已安装库并在 mx-59 验证。
按用户指定的现有库接入，保留已安装 FlagGems-vLLM 的 dirty 修改，不做升级或同步；
本任务未检索或新增 FlagGems 算子，未声称安装 revision 是上游最新。

## 实现与接口

1. `vllm_fl/dispatch/backends/flaggems/impl/fused_moe.py`：在既有 `default.flagos`
   adapter 内以 MetaX 能力守卫切换：align → `moe_align_block_size_no_tle`；
   非量化 GEMM → MetaX `invoke_fused_moe_triton_kernel`；sum → MetaX `moe_sum`；
   softmax/grouped/sqrtsoftplus top-k → FlagGems-vLLM 公共入口。lazy import 保留其他平台
   原行为；MetaX top-k 不再用旧 ABI 的宽泛异常重试。删除同文件的重复 top-k 定义。
   `ignore_invalid_experts` 保留原先排序后映射的行为，未新增过滤支持。
2. `vllm_fl/ops/fused_moe/fused_moe_utils.py`：在既有无 LoRA fast-path 下增加
   MetaX 非量化 FP16/BF16、SiLU、无 expert-map 且权重 dtype 一致的完整融合路径，
   调用 `flaggems_vllm.runtime.backend._metax.ops.outplace_fused_experts`，再写入调用方
   output；传递全局 expert 数、router-weight-on-input 标志及两层 bias。
   expert-map/LoRA/其他 activation 保留分阶段结构。量化 GEMM 保留原 ABI，避免将
   packed INT4 等布局误接到不同的库契约；W8A8 的原有专用 experts 所有权不变。
3. 未修改 dispatch 注册、MetaX policy、通用 activation 或其他平台 backend。
   两次 GEMM、返回 buffer、in-place/out-of-place、map 与 graph 契约由真实计算测试覆盖。
   无量化输入不涉及 scale ABI 改动；LoRA 与量化数值没有获得支持声明。

## 验证与证据

所有新设备测试限定物理 GPU 0（检查时空闲），使用同一安装环境和
`VLLM_FL_STRICT=1`，无 backend 静默回退。日志和缓存位于批准工作根的 `04-runs/`
与 `06-cache/`。未向运行中的模型服务发评测请求。

- 基线：`04-runs/moe-before-20261009.log`，1 个测试在库命中断言失败；
  保留原始失败，没有通过放宽误差或跳过断言得到成功。
- 单元：`tests/unit_tests/dispatch/test_metax_moe_contract.py`，8 项通过：
  非 MetaX 可选依赖隔离、错误传播、grouped/sqrtsoftplus 参数契约、四类量化 guard。
- 设备：`tests/functional_tests/ops/test_metax_moe_fl.py`，12 项通过：
  FP16 代表 shape，Qwen BF16 TP2 `E=256,K=2048,N=256,topk=8,M=1/17`；
  完整融合与非恒等 expert-map 分阶段路径，各自覆盖 eager 与 graph capture。
  每例两次修改输入和路由 logits 后 replay/重算，对照 FP32 PyTorch MoE 参考；
  路由 ID 完全相等，路由权重 `rtol=1e-5,atol=1e-6`；MoE BF16 `rtol=2e-2`、
  FP16 `rtol=3e-3`，均 `atol=3e-4`。每例要求有限输出并确认实际库函数命中。
  top-k/align/GEMM/sum 仍解析为 `default.flagos`。
- 原生 JUnit：`04-runs/moe-unit-20261009.xml` 和 `moe-functional-20261009.xml`；
  最终结果 8+12，失败、错误、skip 均为 0。
- 新测试通过 Plugin 配置对应的 Ruff 0.14.0 lint/format 检查；4 个新增/修改 Python
  文件 AST 解析通过，组件 `git diff --check` 通过。
- 备份与基线：`02-issues/moe-flaggems-vllm-20261009/{baseline.json,fused_moe.py.before,fused_moe_utils.py.before}`。
  本任务产品 diff：同目录 `plugin-moe.diff`；最终文件哈希、安装身份、JUnit 哈希与
  组件状态：`04-runs/moe-final-verification-20261009.json`。所有路径均相对批准工作根。

## 最终设计审查与限制

本任务差异为两个已安装 MoE 产品文件和两个可维护回归测试；已有 GDN/attention 改动
不属于此次提交范围。Plugin 为 detached HEAD，HEAD 保持不变；未确认 PR base，未提交、推送或建 PR。
设计沿用现有 backend 与 fast-path 所有权，无主机名特例、第二份源码、全局导入替换、
新宽泛异常回退或对 vLLM 的写入。FlagGems、FlagGems-vLLM、vLLM 的 HEAD/status 与
修改前基线一致，vLLM 的已有 dirty 修改不能描述为 clean。

当前目标的算子集成可作为审查候选；局部修改及测试已完成，框架五阶段状态保留 `not_started`，不设置 `functional/optimized`。LoRA、量化数值、
其他平台硬件、空输入/无效 expert、完整模型 prefill/decode 与多 rank collective
未验证。grouped/sqrtsoftplus 的本次验证为接口契约，不是设备数值验收。
本次没有正式精度、性能或整模 graph 验收，不修改 launcher、graph 策略或原性能服务配置。
容器及原服务/性能测试进程保持运行；已经导入旧模块的 worker 需要在后续重启推理服务时
加载新代码。没有打包镜像或验证新镜像容器；容器源码归属检查不能替代镜像交付验收。

最终产品文件 SHA-256：

- `impl/fused_moe.py`：`3b2008a16dc82069973cc89e428c8aa1cc05b723d76c7ce6267e3128b777d65b`。
- `fused_moe_utils.py`：`26840110c204499f106efeebb864a5f398f5da9d1687abdfaf634f151445a9ae`。
- 本任务产品 diff：`2baf80d00f3a9837fe61c0bb020e350bd9b16fe508b7e300973f333aee1dd090`。

复现命令（在该容器中以 `/workspace/vllm-plugin-FL` 为 cwd，使用物理 GPU 0，
`FLAGGEMS_VENDOR=metax VLLM_FL_STRICT=1`；日志/缓存沿用批准工作根）：

```sh
python -m pytest tests/unit_tests/dispatch/test_metax_moe_contract.py -q -p no:cacheprovider
python -m pytest tests/functional_tests/ops/test_metax_moe_fl.py -q --confcutdir=tests/functional_tests/ops -p no:cacheprovider
```

`--confcutdir` 限定功能测试的 conftest 搜索范围：上层现有测试钩子会调用 `os._exit()`，
截断失败详情与 JUnit；测试自身提供全部必要 fixture，不依赖上层 fixture。
首轮被截断的负对照已用上述参数重跑，完整失败保存在 baseline 日志。

经验状态：`local-only`。

本地目录审计：当前 framework 记录无问题；仓库整体 audit 仍返回 1，原因是其他记录
存在 12 项 profile revision 错误和 78 项历史布局/证据警告。本任务未修改这些无关记录，
也未将本地审计解释为远端或正式验收通过。
