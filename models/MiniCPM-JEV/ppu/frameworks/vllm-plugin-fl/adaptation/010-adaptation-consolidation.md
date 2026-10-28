# 010：视觉插值适配收敛

2026-10-23，用户要求收敛适配代码。范围为 PPU-01 / minicpm-jev-vllm / 实际 editable 安装的 `/opt/vllm-plugin-FL`，HEAD `06014201f8ea8cd7092a56a945d8fc7998c5a46c`。本轮是既有适配的结构整理，未升级依赖、改变启动参数或执行新的正式验收阶段。

原 `vllm_fl/ops/vision_position.py` 仅被 `Qwen3VisionTransformerFL` 使用，视觉子类只转发权重和网格参数。将同一 FP32 插值计算直接并入 `vllm_fl/models/qwen3_5_vl.py::Qwen3VisionTransformerFL.fast_pos_embed_interpolate`，归档原单调用方 helper，删除转发层。两文件合计 80 行收敛为模型文件 70 行；正常 PyTorch/FlagGems dispatch、FP32 中间结果、原 dtype 输出、spatial merge 顺序及多帧重复均保留。

维护测试改为直接调用真实视觉子类的方法，以仅包含位置表的模块实例隔离无关 attention 层；独立四角插值参考、CPU/PPU、FP32/BF16、两次变输入 CUDA graph replay 及非法网格检查保留。去掉测试中的未使用 import。原生模型构造没有视觉组件工厂，继续保留必要构造适配及同一 multimodal processor 注册，避免引入额外运行时替换机制。worker 输出协议和同步 pooling 的生成 token 预留修复保持原样。

最终 diff 共 5 个产品文件：修改 `vllm_fl/__init__.py`、`vllm_fl/platform.py`、`vllm_fl/worker/worker.py`，新增 `vllm_fl/models/qwen3_5_vl.py`、`vllm_fl/worker/pooling_scheduler.py`；另有 3 个针对性测试文件。相对本轮开始仅模型文件、视觉测试及被归档的 helper 有变化，其他继承修改保留。1886 个 vLLM 安装 Python 文件哈希未变，无新增权限/文件类型噪声；未提交、推送或创建 PR，PR base 未选择。

17 项回归通过。通过未修改的用户脚本 `/mnt/nfs/users/jinghao/MiniCPM-JEV/start-model.sh` 重启本任务服务，API PID165227 / start tick546288757；脚本 SHA-256 仍为 `4ddc5c3ad044f1a4cd10968282711550e8076f927f0d36d6649a3413a152ee8b`，容器始终运行。沿用已冻结的双图长度、输入构造、独立 cache_salt、无截断及参考阈值，结果如下：

| 验证 | 结果 |
| --- | --- |
| 32768 / 131072 token | 完整消费，通过 |
| 262144 token | 119.366 秒，完整消费 |
| 262144 独立冷缓存重复 | 119.416 秒，概率差为 0 |
| 262145 token | HTTP 400，正确拒绝 |
| 长请求后 12 短样例 | 最大参考误差 0.004417300 < 0.005 |
| 服务 / 资源 | health 200，采样显存峰值 90672 MiB，无 OOM |

满长度概率仍为 `[0.9100022315979004, 0.0899977833032608]`。实际 import 位于 `/opt/vllm-plugin-FL`，没有 PYTHONPATH；源码在回归期间哈希一致。此为单请求功能/容量回归，耗时仅为观察值；其他物理平台、TP/PP、长文业务准确率、正式全量精度/性能及新镜像验证未执行。

设计审查结论：可作为上述已验证范围内的 PR 候选。单调用方计算归属视觉模型，减少独立接口且未扩展适用范围；保留三个有独立故障证据的必要修复与边界测试。原生视觉插值达到等价 FP32 精度后可移除对应视觉适配；原生 pooling 正确预留零生成 token 后可移除对应 scheduler 兼容。

原始证据为批准工作根下 `04-runs/adaptation-consolidation-20261023T091527Z/`：前后源码、manifest、diff、源码审查、17 项测试日志、服务身份、长请求及短样例结果和最终校验。旧 helper 保存在此目录，首次跨文件系统 rename 失败后通过内容校验、复制归档再移除原文件完成；未丢失源码。此前记录对应历史结构，本记录说明当前结构，不重写历史验收回执。

## 2026-10-23 新贡献规范复审计划

用户指定 Plugin PR 目标为 `flagos-ai/vllm-plugin-FL:main`，查询时固定为 `f41b7de883ed71526716738a7e05d810f49ded58`。当前安装仍为 `/opt/vllm-plugin-FL` 的 OCR 分支 HEAD `0601420`；必须将 OCR 的 11 文件/1033 行既有提交和上游后续差异与 JEV 工作区增量分开。FlagGems 单独审查 `/workspace/FlagGems` 的 clone 注册及测试；FlagGems-vllm 和 vLLM 仅核实无本任务变更，不改代码。008 旧审查保留历史身份，当前复审结果以本记录为准。

| 问题 | 组件及拟复核文件/符号 | 允许的必要修整与验证 |
| --- | --- | --- |
| 002 CPU clone 被 GPU Autograd 注册拦截 | FlagGems `src/flag_gems/__init__.py` clone 条目、`tests/test_clone_registration.py` | 检查 tuple/设备 key、梯度与存储契约；补齐测试规范中的 clone marker、注册生命周期及必要格式检查，不改公共 registrar 或其他算子。 |
| 003 异步 pooling 输出误入 PP 分支 | Plugin `worker.py::execute_model`、`test_pooling_output.py` | 核对生产者/消费者协议及两处类型修改；补异步 generation 同基类返回、无 token 路径的针对性覆盖。 |
| 006/010 FP32 视觉插值 | Plugin 模型注册、`qwen3_5_vl.py`、`test_vision_position.py` | 逐段核对原生构造与 processor；补注册隔离/重复注册、支持 dtype 与直接设备 eager 断言；保留独立 oracle 和 graph 断言，不更换算法。 |
| 009 满上下文调度停滞 | Plugin `platform.py` helper/调用、`pooling_scheduler.py`、`test_pooling_scheduler.py` | 核对同步/自定义调度守卫及原生预算字段；补配置切换与混合请求边界覆盖，保留 63/64 负对照证据。 |

本轮先核实上游基线可应用性及正常 pytest 入口。仅在明确测试缺口或 lint 问题时修改对应新增测试，保留所有既有断言；产品逻辑若发现实际缺陷，先补本清单及复现，再修复。禁止整文件格式化已有产品文件、升级运行依赖、改用户脚本或把 OCR/上游同步混入 JEV 补丁。完整数据集、多平台实机与 TP/PP 未验证项明确披露，不据单机通过宣称完整验收。

## 本轮最终结论与基线

2026-10-23 09:43 UTC，逐组件、逐文件、逐 diff 块复审通过：Plugin 和 FlagGems 可作为下述声明范围内的 PR 候选；FlagGems-vllm 无本任务组件变更；vLLM 源码/安装文件未改。没有未解释增删、重复 workaround、已知未解决回归或夹带重构。本轮只修改四个既有新增测试文件，产品代码保持不变。未 commit、暂存、推送或创建 PR，实际 Git index 和运行 checkout 的 HEAD 保持原状。

| 组件 | 实际安装 HEAD | PR 基线 / 结论 |
| --- | --- | --- |
| Plugin `/opt/vllm-plugin-FL` | `06014201f8ea8cd7092a56a945d8fc7998c5a46c` | 用户指定 `flagos-ai/vllm-plugin-FL:main`，固定 `f41b7de883ed71526716738a7e05d810f49ded58`；可作为 PR 候选。 |
| FlagGems `/workspace/FlagGems` | `722854072a3329c6c33ea2850afe368c9b4f63bc` | 单独补丁按上游默认 `flagos-ai/FlagGems:master` 固定 `e510c6bbe3ffd9eb22c41021d82f15c21098f998` 检查；可作为 PR 候选。 |
| FlagGems-vllm `/workspace/FlagGems-vllm` | `db220e684094896c0e4a038bb2a44ab6e8c95aea` | clean，无组件变更。 |
| vLLM `/workspace/vllm` / 安装目录 | `ee0da84ab9e04ac7610e28580af62c365e898389` / `0.24.0+empty` | clean，1886 个安装 Python 文件哈希不变。 |

Plugin 实际安装基于 OCR 提交 `0601420`，其父提交 `25eddf9a0616b08363e5c1553fc537e44ed4c81d` 与上游 main 相差 3 个后续提交。OCR 的 11 文件/+1033 行已提交改动、上游 CI/dispatch/Ascend 等同步差异均排除在本任务补丁之外。此前 22 处权限及 1 处展开链接噪声已单独恢复，当前无此类 diff。Plugin 增量为 3 个已跟踪修改、5 个新增文件；FlagGems 为 1 个已跟踪修改、1 个新增测试。无 staged diff。

使用真实仓库对象及工作根内独立 `GIT_INDEX_FILE` 生成任务补丁，对固定上游基线执行 `git apply --cached --check` 后在临时 index 中应用并检查 diff；没有新 source checkout 或导入覆盖。Plugin 涉及的既有 platform、worker 和 Qwen3.5 text shim 文件在当前 HEAD 与目标 main 相同；其 initializer 的上游变化为独立 MetaX loader 删除，JEV 注册块可直接应用。FlagGems registrar 和 clone 算子实现与目标 master 相同。已检查上游其他差异，但未将完整新基线安装到运行环境：**补丁可应用及局部回归不等于目标分支完整 CI 已通过**。

## 逐文件 / diff 块必要性清单

Plugin 共 8 文件、+472/-2，其中产品 +107/-2，维护测试 +365；FlagGems 共 2 文件、+74/-1，其中产品 +6/-1、测试 +68。数字用于明确范围，不以行数判定设计质量。

| 组件 / 文件 / diff 块 | 问题、调用方与必要性 | 删除/替换、兼容及验证结论 |
| --- | --- | --- |
| Plugin `vllm_fl/__init__.py`：1 个注册块，+7 | 006：general plugin 在模型检查/worker 进程注册 dense Qwen3.5 VL 适配类；lazy 路径确保实际命中 FP32 插值。 | 只替换 `Qwen3_5ForConditionalGeneration` 注册，不改文本/MoE/其他 VL 注册。新进程验证两次注册幂等、目标模块未提前导入、其他 VL/MoE 条目不变且 CUDA 初始化状态不变。必要。 |
| Plugin `vllm_fl/models/qwen3_5_vl.py`：新增块的版权/import 部分 | 原生构造片段的来源与 Apache-2.0 标识明确，使用既有 Torch/vLLM 依赖。 | 无厂商 SDK 新依赖、设备分配或全局 monkey patch。必要。 |
| 同文件：视觉子类插值方法 | 006：原生 BF16 插值中间乘积提前取整导致概率超差；在已有方法边界内使用 FP32 bilinear，最终转回位置表 dtype。 | 保留 grid、merge 顺序、多帧重复、输出 shape/dtype；沿正常 PyTorch/FlagGems dispatch。CPU/PPU FP32/BF16/FP16，设备 eager 和两次变输入 graph replay 通过独立 oracle；无放宽既有容差。必要。 |
| 同文件：processor decorator、模型构造 | dense VL 的正式 registry/processor 路径；上游构造没有视觉工厂，必须建立视觉子类。 | 逐项对照 config、quant_config、tower/language 标记、prefix、parallel 标志与 intermediate tensor factory；只更换视觉类。forward、权重加载、语言主干继续继承原生。已有完整权重/双图请求证据验证，未复制完整模型。必要。 |
| Plugin `vllm_fl/platform.py`：helper 与调用两块，+16 | 009：只有默认同步 pooling 应改用零生成预留调度器；通过已有 scheduler_cls 扩展点选择。 | model 为 None、generation、async、显式 custom scheduler 均保留既有选择；重复调用幂等、不同配置无全局状态泄漏。不得改公共默认或按模型路径特判。必要。 |
| Plugin `vllm_fl/worker/pooling_scheduler.py`：新增 12 行 | 009：原生非 diffusion 一律预留 1 个输出 token，使恰好上限的 pooling 无法完成；子类在 pooling 初始化后设为 0。 | 不复制 schedule、不扩大 max_model_len/KV cache、不改变 generation 预留。真实 Scheduler/KV manager 的 63/64 边界及混合 31/64 请求通过；原生负对照 `63 != 64` 保留。必要。 |
| Plugin `vllm_fl/worker/worker.py`：返回类型与 isinstance 两块，+2/-2 | 003：ModelRunnerFL 可返回 AsyncGPUPoolingModelRunnerOutput，属于 AsyncModelRunnerOutput；旧判断误入 IntermediateTensors 分支并断言失败。 | 增加已有返回基类，与消费者契约一致；不复制 output、强制同步或改 PP 发送。新增 async generation 同基类用例；同步结果、None、0-token、PP intermediate 行为均通过。两处都必要。 |
| Plugin `test_pooling_output.py`：新增测试块，67 行 | 真实输出类型与实际 WorkerFL.execute_model 的选择契约，6 用例。 | mock 只隔离 runner/通信调用，不伪造数值；PP 真实多卡通信未测。无删除既有断言。必要。 |
| Plugin `test_pooling_scheduler.py`：新增测试块，165 行 | 5 个 guard/幂等用例、63/64 完整调度、generation 预留、混合请求，共 9 项。 | 使用真实 Scheduler.schedule 和 KV manager，无网络/权重；检查预算、实际 token 进度及上限不变，非字符串搜源码测试。必要。 |
| Plugin `test_vision_position.py`：新增测试块，133 行 | 6 个 CPU/PPU×dtype 用例、4 个非法 grid、1 个新进程注册，共 11 项。 | 原生子类实际方法，独立四角 FP32 oracle；BF16 既有 ULP+FP32 误差界不变，FP16 使用对应存储 ULP；格式仅针对本任务新增文件。必要。 |
| FlagGems `src/flag_gems/__init__.py`：clone 注册块，+6/-1 | 002：registrar 需要外层 dispatch spec 序列内嵌 `(key, impl)` pair；原扁平 tuple 错将 clone 注册到全局 Autograd alias。 | 改为正确 pair 且限定 `Autograd + backend_info.dispatch_key` fallthrough，CPU 保持原生 clone/梯度；不改 registrar、clone kernel 或其他算子。原结构无法正确表达此注册，替换有直接失败证据。必要。 |
| FlagGems `tests/test_clone_registration.py`：新增块，68 行 | CPU 梯度/stride/独立存储、PPU FP32/BF16 梯度/布局/图重放、重复注册退出生命周期，共 4 项。 | 按该组件规范补 clone marker、isort/Black/flake8；不使用 Plugin 测试代替组件测试，不删除/放宽既有断言。必要。 |

原单调用方 `ops/vision_position.py` 是本任务未提交的新文件，已在 010 经调用方核对、真实方法数值/graph 和整模型等价回归后合并；它不是上游公共 API，当前 PR 相对上游没有此文件删除。除 worker 两处类型契约和 clone 旧注册条目外，无其他上游函数、分支、测试或注册删除。三个 Plugin 修复分别处理视觉精度、输出协议、调度边界；FlagGems 修复处理 CPU/GPU 注册隔离，职责不同，不重复叠加 workaround。跨组件应用时先修 FlagGems clone 使权重加载正常，再应用 Plugin 修复。

## 本轮验证、证据与限制

- 标准入口：在实际源码根执行 `python -B -m pytest -q -p no:cacheprovider` 加对应测试路径，`CUDA_VISIBLE_DEVICES=1`。Plugin **26 passed / 28.04 秒**，FlagGems **4 passed / 1.94 秒**。本轮不再使用 `--noconftest`，完整加载组件 conftest。
- Plugin：Ruff 0.14.0 lint、3 个新增测试格式检查、2 个新增产品文件 lint、git diff --check 通过。FlagGems：flake8 7.3.0、isort 5.12.0、Black 26.5.1（实际解释器 target py312）、导出一致性检查及 git diff --check 通过。工具隔离在工作根 `05-tmp/pr-review-tools`，未改变推理依赖。未执行整个仓库所有 pre-commit hooks 或远端 CI，不声称这些检查已通过。
- 本轮四个测试文件之外的产品字节均未变。Plugin 产品哈希与 `adaptation-consolidation-20261023T091527Z` 完全一致；FlagGems 注册文件仍为 `69810ae2c6d09351470cb631425f840032ba5d353b664c6a2011514b9c5844ce`，匹配此前整模型基线。故沿用同代码的两次 262144 完整消费/概率差 0、262145 HTTP400、12 短样例最大误差 0.004417300 证据，没有把旧源码结果标成新测试重跑。
- API PID165227/start tick546288757 未变，health 200；用户 launcher 哈希不变，无 PYTHONPATH。容器和服务未重启。
- 其他硬件、TP/PP 真实通信、异步 pooling/custom scheduler 整模型、新 main 完整安装运行与 CI 未执行。完整数据集精度、正式性能、长文业务准确率和新镜像验证仍未完成，不支持 optimized 或完整验收。
- workaround 退出条件：上游原生视觉插值具备同等 FP32 中间精度并通过同一 oracle/模型回归后移除视觉适配；原生 scheduler 对 pooling 预留 0 后移除子类/选择；上游 WorkerFL 接受 async 基类、FlagGems 正确注册 clone 后分别去掉对应兼容补丁。

原始证据根：`/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt/vllm-plugin-fl/04-runs/pr-review-20261023-1/`。包含逐组件 before/after 源码与哈希、正常收集日志、测试、lint、完整继承差异、候选补丁与 final-verification。固定上游补丁：

| 补丁 | SHA-256 | 状态 |
| --- | --- | --- |
| `plugin-against-upstream.patch` | `d1c6c39079a999621a237a0075e2b1e1c7ffc7975d53171067ef10cafdce7de1` | main 固定基线 apply-check 通过；仅上述 8 文件。 |
| `flaggems-against-upstream.patch` | `e904d7117c0f4f5de4d97cc32f7958616e8cfc82587fc1826b3a3baab52306ff` | master 固定基线 apply-check 通过；仅上述 2 文件。 |

建议按两个仓库分别提 PR。Plugin 标题草案：`Fix Qwen3.5 pooling inference and full-context scheduling`；描述聚焦 BF16 视觉精度、async pooling 返回协议和满上下文预算，列出 26 项测试、已绑定长上下文证据及未验证范围。FlagGems 标题草案：`Fix device-scoped autograd registration for clone`；描述扁平 tuple/global alias 的 CPU 污染、正确嵌套 pair/device key 及 4 项回归。后续应从目标分支应用干净候选补丁，不能把当前 OCR checkout 的全部历史直接作为 JEV PR；本轮未更改运行基线。

这是源码贡献审查结论；`framework.yml` 的历史正式回执未刷新为本轮验收，旧指纹/旧报告不替代当前完整验收。

## 2026-10-23 本机代码与分支交付

用户随后明确授权拷贝到本机并提交推送。复用干净的本机仓库 `/Users/baai/Documents/ChatGPT/vllm-plugin-FL`，从重新 fetch 后仍为 `f41b7de883ed71526716738a7e05d810f49ded58` 的上游 main 创建 `support-minicpm-jev`，应用容器导出的 `plugin-against-upstream.patch`。没有带入 OCR 提交或 FlagGems 补丁。

已推送至 [flagos-day0/vllm-plugin-FL 的 support-minicpm-jev 分支](https://github.com/flagos-day0/vllm-plugin-FL/tree/support-minicpm-jev)，提交为 [995038cdc576d77794f58a71441f719fe2e74680](https://github.com/flagos-day0/vllm-plugin-FL/commit/995038cdc576d77794f58a71441f719fe2e74680)，标题为 `Fix Qwen3.5 pooling inference and full-context scheduling`。远端分支 SHA 与本机一致；相对上游 main 仅 1 个提交、8 文件、+472/-2，本机工作区干净。未创建 PR。

提交前重新核实容器 8 个源文件哈希与本轮审查 manifest 一致。本机暂存补丁及最终提交 diff 的 SHA-256 均为 `d1c6c39079a999621a237a0075e2b1e1c7ffc7975d53171067ef10cafdce7de1`，与已审查补丁逐字节一致；8 文件 Python 语法解析和 git diff --check 通过。沿用前述 PPU 的 26 项回归和长上下文证据，本次未重跑硬件推理或完整 CI。容器源码、安装状态及运行服务均未修改。

