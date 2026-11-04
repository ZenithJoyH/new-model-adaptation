# 005：mx-102 Plugin 编译产物与 MCCL Abort 兼容

## 范围与基线

2026-11-03，用户授权修复 `mx-102` / `plugin28-base` 的 Plugin 两处接口不匹配。
本条记录独立于本工作区历史 `mx-59` 适配，不更改 framework.yml 的目标、阶段或验收状态。
选用 active `vllm-plugin-fl` profile；只修改实际 editable 安装 `/opt/vllm-plugin-FL`。
HEAD 为 `37f2127367cfbc24349a1f28cb37c4c629b9ed6c`，对应 `origin/0.4.0-dev`。
Python `/opt/conda/bin/python`，Torch `2.10.0+metax3.8.2.2`，vLLM `0.28.0+empty`。
用户已有 `_kths_triton_unified_attention.py` 改动（149 增/41 删）保持原样。
容器 running；初查八张 C550 均无设备进程。没有停止或重启服务。

经 Docker inspect 验证 `/public-flash` 为同路径 rw bind，当前操作根的 Host/Container
路径均为 `/public-flash/jinghao/qwen3.6-35B`；原始日志、基线、测试产物进入该根
`01-environment/`、`02-issues/`、`04-runs/`、`05-tmp/`、`06-cache/`。
源码属于容器内部 `/opt`，不在过程根创建另一份 checkout，不使用 PYTHONPATH。

## 现象、已有经验与根因

用户 `service-test.log` 15:22:29：权重 26/26 分片加载后，显存 profiling 的编译路径
在 MetaX `fix_standalone_compile.py:127` 实例化抽象 `CompiledArtifact` 失败。
当前 Torch 原生同路径返回具体 `CacheCompiledArtifact(compiled_fn, artifacts)`。
随后退出线程调用 `MCCLLibrary.ncclCommAbort`，因 Plugin 包装层缺该方法失败。
当前源码 `use_custom_allreduce` 的默认值、用户 attention shim 和启动参数不属于本次改动。

参考 [GLM 问题 013](../../../../../GLM-5.3-Flash-BF16/metax/frameworks/vllm-plugin-fl/adaptation/013-metax-compiled-artifact-api.md)
及 [Qwen3.8 问题 008](../../../../../Qwen3.8-Flash-Next/metax/frameworks/vllm-plugin-fl/adaptation/008-graph-execution.md)：
同 Torch 版本/错误签名，Plugin revision 不同；只复用候选接口判断，在本容器重建负对照与回归证据。

## 改前限定与验证计划

| Plugin 文件/符号 | 必要变更 | 验证 |
| --- | --- | --- |
| `dispatch/backends/vendor/metax/patches/fix_standalone_compile.py` | 编译前按原生类能力选具体缓存产物；保留旧具体基类路径；未知接口明确报错。不复制保存/加载实现，不修改原 FX 遍历、cache key 或 TF32 hook | 新/旧类、缺类与抽象类分支；真实 CPU/MetaX 编译、变输入数值、binary/unpacked 保存及原生加载、独立进程恢复、真实 GPU capture/replay |
| `dispatch/backends/vendor/metax/patches/pynccl_wrapper.py` | 按真实 SDK 头文件与动态符号绑定 `mcclCommAbort`，通过现有 NCCL_CHECK 暴露 `ncclCommAbort`；保留其他通信逻辑 | ABI/参数转发、错误传播、实际加载库和本任务独立通信器的退出清理 |
| 聚焦 unit/functional 测试 | 增加能力判断、退出接口与真实编译缓存/图回归，不删除或弱化现有用例 | 先保存负对照，再运行新增与受影响既有测试、目标 revision 的格式/lint/pre-commit |

仅 Plugin 框架编译元数据与通信适配（plugin:A2/A3/A4、B3/B4、C1–C4、E3/E4、F1–F4/F7）。
不新增数值算子；不修改 vLLM、Torch、FlagTree、FlagGems、FlagGems-vllm 或 SDK。
沿用现有厂商 patch 安装入口，不新增开关、不降 graph 档位、不改变服务脚本。
旧 Torch 无实机，能力分支测试不代称旧 SDK 硬件通过；整模型服务及正式验收不在本次修复完成声明内。

## 修复与当前验证

`verified-component-fix`（2026-11-03）：两处 Plugin 修复及本条声明范围的回归完成，
不代表整模型启动或正式验收完成。

原始证据根为 Host/Container 同路径
`/public-flash/jinghao/qwen3.6-35B/04-runs/plugin-compat-20261103/`。
基线另存于 `01-environment/plugin-compat-20261103/before.json` 及两个产品文件的原字节。

- `negative.json` / `negative.log`：当前原文件经真实 CPU FX 编译后复现抽象构造错误；
  同时确认原 MCCLLibrary 缺少 ncclCommAbort。保留用户原始 `service-before.log`。
- `unit.log` / `unit.xml`：**10 passed，0 skipped，19.43s**。包括原生具体类选择、模拟旧具体类、
  缺类/仍抽象时在编译前失败、MCCL ABI/转发/错误传播/缺符号失败，以及两个既有 MetaX patch 测试。
- `functional.log` / `functional.xml`：**9 passed，0 skipped，539.76s**。
  CPU FP32、MetaX FP32/BF16 × binary/unpacked 六组合均完成真实编译、变输入数值、保存、
  原生加载及全新进程/缓存目录恢复；输入包含非连续 stride 与 storage offset。
  另有两种 GPU dtype 的真实 capture 与两次变输入 replay，每次先填充输出 NaN；
  以及真实 SDK 创建的本任务独立单 rank 通信器通过 vLLM destroy → 原生 mcclCommAbort，
  核对线程完成、无异常和重复 destroy 不再调用。
- `pre-commit-verified-snapshot.log`：全部适用原配置 hook 通过，symlink/shell 类型无匹配文件。
  远端 Git HTTP/2、默认包索引及共享盘 pip metadata/wheel Errno 5 失败日志均保留。
  用户提供的代理仅临时用于工具进程；不进入源码、持久配置或证据日志。
  最终在本地临时目录使用原始 pyproject/pre-commit 配置及实际测试包上下文检查，
  六个目标文件字节未被修改；`checked-hashes.json` 与容器实际文件逐一相同。
  Ruff 版本 0.14.0，容器内新增测试的格式与 lint 同样通过（`ruff.log`）。

测试开发工具位于批准根 `05-tmp/plugin-compat-20261103/tools`，继承原服务库，
未向服务环境安装另一份 Torch/Plugin。最终另用服务解释器 `/opt/conda/bin/python` 确认
实际导入仍为 `/opt/vllm-plugin-FL/vllm_fl/__init__.py`，具体产物为 CacheCompiledArtifact，
Abort 包装已可见。现有 SDK 头文件与动态库均实际提供 mcclCommAbort。

## 最终设计审查

新增/修改范围仅六个文件；无产品函数或旧兼容路径删除，无数值 kernel 新增。

| 文件 | 增/删行 | 审查结论 |
| --- | --- | --- |
| MetaX `fix_standalone_compile.py` | +18/-1 | 新增私有能力选择函数，编译前选择原生具体类；旧基类具体时保持原路径。仅替换最终构造类型，不复制序列化，不捕获计算错误重试，不改变 FX/cache key/TF32 逻辑 |
| MetaX `pynccl_wrapper.py` | +5/-0 | 按头文件 ABI 增加 mcclCommAbort 导出及 NCCL_CHECK 包装；不替代为 Destroy、不使用空实现，不改变原有 all-reduce 或其他方法 |
| unit `compilation/test_metax_standalone_artifact.py` | +70/-0 | 能力/失败先于副作用的真实入口测试；模拟旧类不声称旧 SDK 实测 |
| unit `distributed/test_metax_mccl_abort.py` | +65/-0 | 参数、返回码和缺符号契约；Mock 仅验证包装接线 |
| functional `compilation/test_metax_standalone_artifact.py` | +132/-0 | 独立 eager CPU 参考、缓存调用/恢复及真实图重放，不用桩替代计算 |
| functional `distributed/test_metax_mccl_abort.py` | +56/-0 | 当前 SDK 的真实独立通信器生命周期，未触碰用户通信器 |

当前 Plugin revision 未变，用户 attention 文件 SHA-256 始终为
`1f1b602c9ef670b92adc5426882ad9d2c4bd9d30be277ad38eee77f1ecb7e3bd`。
vLLM HEAD `2cf0a6915ce544dc493a0990f2ea38d81601128a`、clean 状态及 **6596** 个 tracked 文件哈希
逐一保持；六个相关 distribution 的版本与安装来源同基线。`git diff --check` 和六文件语法通过。
目标 revision 未发现 AGENTS/CONTRIBUTING 文件，采用已读 README、MetaX guide、tests/README、
pytest/工具配置及本项目标准作为具体依据；没有宣称读取不存在的指南。

`final-review.json` 绑定以上状态与最终文件哈希。仅含本任务六文件的补丁为
`plugin-compat-fix.patch`，SHA-256
`3a298ae43c47cca0e817db4efc1caf20706acf30057529ccb87a3e9a54c118c5`。
逐 hunk 核对无越界改动；修复验证阶段未 commit/push/创建 PR，后续发布记录见下。

适用 plugin:A2/A3/A4、B3/B4、C1–C4、E3/E4、F1–F4/F7 的组件证据见上。
无新数值算子/CI/模型/厂商接入，算子开发、性能优化及新厂商支持列表条款不适用。
未使用版本字符串选分支，未新增配置开关。原厂商补丁导入作用域保持不变；其他平台硬件未实测。

## 限制与下一步

旧 Torch 2.8 只有能力分支模拟覆盖；多 rank Abort、完整 TP2 模型启动/请求、正式精度及性能
未在本次组件修复中执行。MCCL 单 rank 测试仍能看到原有 bnxt_re ABI 警告，不据此宣称
RDMA 栈或全部通信能力已验收。没有重启模型服务、修改用户启动脚本或调整 graph 模式。
原 framework.yml 的历史 mx-59 目标与阶段状态保持，不能据此提升当前 mx-102 整模状态。

## 用户授权的 PR 发布

2026-11-03，用户反馈当前修复有效并明确要求向上游提交 PR。
已创建 [PR #686](https://github.com/flagos-ai/vllm-plugin-FL/pull/686)，目标为实际使用的
`0.4.0-dev`，来源 `ZenithJoyH:fix/metax-torch210-artifact-mccl-abort-20261103`。
独立提交 `a6ec10cbe7d26fa4ce47b7a484f706bb746cd367` 基于已测试的 `37f21273`；仅六个预期
文件，+346/-1。上游目标当时为 `8b1a1a086a1be7437db735f48f1b5f111c9322e5`，领先四个提交，
两处产品补丁文件未被这些提交修改；GitHub 核对 mergeable=true，未执行合并。
PR 如实记录测试基线、19 项回归、静态检查方式及旧 SDK/多 rank Abort/正式模型验收限制，
关联相近的 main 分支 PR #673。

发布前重新核实容器六文件与 checked-hashes 完全一致；不改容器分支、不在现场提交，
不包含用户既有 attention shim 及随后新增的 metax.yaml 改动，也未发布过程日志或代理凭据。
该发布不将用户反馈转换为新的原生验收回执，不更新模型阶段状态。

## PR #686 CI 回归修复计划

用户随后授权修复失败检查。首轮 CI `41603699075` 中 lint/build 通过，Ascend/MUSA/MetaX/T-Head
四组均在 unit 阶段失败：同一 `test_musa_accelerator_patch.py` 的八例失败，七例缺少
`_install_metax_compat`，一例因该 NameError 阻止 allocator 绑定而由 finally 清理错误覆盖。
这是合并检查中继承的目标分支测试夹具依赖遗漏，原六个变更文件未修改注册入口。

新增改前范围仅 `tests/unit_tests/test_musa_accelerator_patch.py:parent_registration` 的测试依赖
命名空间：为未加载的 MetaX hook 提供 Mock，并在既有跨厂商接线测试中确认 hook 被调用。
保留全部 allocator 幂等、缺 API、异常及其他厂商隔离断言，不跳过失败用例，不改生产注册逻辑。
先用 CI 精确版本源文件在本地隔离目录保存八例负对照，再跑完整该模块及原配置检查。
该纯接线测试使用 Mock，不冒充厂商数值或硬件验收（plugin:F1/F4/F6/F7）。
将目标分支作为合并父提交接入现有 PR 分支，避免复制整个新增测试造成 add/add 冲突；
原容器及用户源码不进行升级或修改。随后更新同一 PR，观察新的 CI 结果。

### CI 修复实施与验证

执行时目标分支已更新至 `131969d53c5f75291ceda45a48616eeff68bb5ff`；相对发布时的
`8b1a1a08` 仅七个 forward-sync CI 文件变化，本次目标测试、注册入口与 MUSA patch 均未变化。
本地 Python 3.12 隔离环境从精确上游源码复现 **8 failed、48 passed**；仅补齐夹具 Mock
与跨厂商测试调用断言后，完整模块串行 **56 passed**，xdist 四进程 **56 passed，0.27s**。
原配置 pre-commit 的 conflict/private-key/EOF/whitespace/Ruff/typos 均通过；无匹配
symlink/shell 文件。临时证据在 `/private/tmp/pr686-ci/`，未作为目标 Plugin 文件发布。

先创建保留原提交的合并提交 `facfe1cb488e301ceba4595aa13cfe9e57d4d74d`，再提交夹具修复
`5d1a812e6c3e910ba1ff4e593a7e930af39c55b0`，以 expected-head 校验、无 force 更新原 PR 分支。
相对最新目标共七文件 +349/-1，原六文件字节不变，新增差异严格为测试三行；无生产代码变化，
无断言删除/宽容差/skip。更新了 PR 描述的根因、精确基线与验证限制。
GitHub 随后确认 mergeable=true，当前新一轮 CI 为
[41609156919](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/41609156919)。
截至 2026-11-03 09:24 UTC，lint、build、discover 均 success；Ascend functional job
`125827679952` success：完整单测 **1873 passed、110 skipped，347.05s**，相对首轮八例失败
均已通过；独立 MetaX 标记选择检查为 2 passed、7 skipped、1976 deselected；后续功能测试
**6 passed、77 skipped，31.66s**。目标硬件相关 skip 如实保留，不记为硬件通过。
MUSA、MetaX、T-Head 及其他硬件任务、Ascend 下游 E2E 仍 queued，不能宣称全部 CI 通过。
PR 描述已同步这些当前结果及待执行限制。
本次未访问/修改远端容器，未变更模型阶段状态。

### CI 完成后复核（2026-11-04）

北京时间 2026-11-04 09:39 复核同一 head `5d1a812e`，run `41609156919` 已完成，
共 **48 success、2 skipped、2 failure**。八个平台的 unit/functional job 均 success，
MetaX inference/serving E2E 与 benchmark smoke 也 success；先前八例测试夹具失败已消失。

两个失败为同一因果链：

- [Hygon serving E2E job 125840549046](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/41609156919/job/125840549046)：
  `qwen3_6/27b_tp2_graph` 在显存预检阶段等待约 30 分钟后失败，设备 0/1 仅余
  11802/11964 MiB，而要求 55692 MiB。该用例尚未进入模型启动/测试断言阶段；同任务的
  `35b_a3b_tp2_eager` 已通过两项服务测试。失败日志为 `timed out waiting for device memory`。
- [ci-gate job 126217249073](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/41609156919/job/126217249073)：
  仅报告 `test-hygon failed with: failure`，是上述失败的汇总门禁传播，无第二个独立代码错误。

2026-11-03 已尝试通过 GitHub connector 单独重跑 Hygon job，被 HTTP 403
`Resource not accessible by integration` 拒绝。CLI 凭据在允许网络的检查中有效，但该账号
对上游同样仅 pull 权限；本次 connector 再次核实无 push/triage/maintain/admin 权限。
需有 Actions 写权限的维护者确认设备资源可用后重跑该 job 与依赖检查。
PR 描述已更新最终 CI 状态、日志链接及限制。本次没有新的产品代码修改，没有更改 CI 门禁、
降低显存要求或操作未授权 CI Host 进程；整体 CI 仍 failed，不记为完整通过。
