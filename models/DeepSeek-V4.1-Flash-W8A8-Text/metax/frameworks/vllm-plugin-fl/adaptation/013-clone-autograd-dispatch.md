# 013：初始化期间 CPU clone 被错误替换

状态：open。用户已恢复整模启动和评测；TP8、PP2、异步调度开启的 eager v5 已完成权重加载，但在初始化 profile 中失败，尚未发送模型请求。该异常不能证明 PP 与异步调度有问题。

首发栈为原生 embedding masking 编译 → Torch Inductor/AOT 保存 RNG 状态 → CPU `torch.clone` → FlagGems CUDA device guard。103 的最小复现已确认：仅启用 `clone` 就会先出现注册警告，再报 `Expected a cuda device, but got: cpu`。原始证据保留在远端 `07-bugs/clone-cpu-autograd-v1-20261104/`，v5 日志保留在 `04-runs/eager-service-v5-20261104/`。两机适配容器保持运行，失败的本任务服务进程已清理。

## 修改前范围

FlagGems 实际安装树为 `/opt/FlagGems`，HEAD 为 `e584bded1ddb0ea2a638653043ef0d48931119a3`，修改前干净。注册器已经支持嵌套 `(dispatch_key, implementation)` 项；当前 clone 配置漏了一层容器，导致字符串 `Autograd` 被注册为 clone 实现，后续函数对象被误作 dispatch key 而报错。

仅计划修改 `src/flag_gems/__init__.py` 中 clone 的注册项和 `tests/test_clone.py` 中相关回归测试：使用注册器既有的 per-key 格式，并将 Autograd fallthrough 限定到当前设备。保留原 clone kernel、公开签名、其他算子与第三方源码。直接数值/梯度测试沿用公开 `flag_gems.clone`；CPU/GPU 自动分发另测，并证明 GPU 实际 kernel 命中。补充 CPU RNG、Torch 编译与新输入图重放检查，使用既有 clone benchmark 验证注册路径无明显退化。

适用 `operator:A1–A4/B1–B5/C1–C3/D1/E1–E7/F1–F4` 及 FlagGems 自身贡献规范。原有厂商 clone 副本无须数值改动，注册项使用当前后端 dispatch key。先在 103 验证，再同步 102；冻结修改前后文件、完整 diff 和实际导入身份。未运行或失败的检查不记为通过。

## 首轮修复与复核

两机实际安装树各通过同一套 64 项测试，包括原公开 API 数值/梯度测试和新增 CPU 分发、CPU RNG、GPU kernel 实际命中、Inductor 编译及两次新输入图重放。日志为 `04-runs/<Host>/deepseek-v41-clone-registration-v1-20261104.log`。103 的两文件 diff SHA-256 为 `aec8615984fbf443a21b379a958b481e3674c569ed029dcc742406d77e8f9e82`。固定版本的 formatter/linter 钩子在两文件快照通过；全仓库检查仍待核验，不能将切片通过称为全仓库通过。

既有 clone benchmark 已测 kernel、cudagraph、operator 三种口径，包含三种浮点 dtype 与五种 shape。原始结果保留在 `04-runs/mx-103/clone-benchmark-v1-20261104/`；逐项结果仍需完整复核。小张量 operator 口径相对原生 ATen 存在明显 host 开销，不能声称所有口径性能通过，也不能据此声称新增 GPU kernel 优化收益。

真实安装树的 exports 与 diff 检查通过，但另外三项 CI 输出“0 changed operators / None ... found”，未覆盖目标 clone。核对发现该 revision 的 `conf/operators.yaml` 缺少 clone 条目。因此在后续 PR 准备中增加该文件的一条有序 clone 元数据记录，按现有 ATen schema、marker 和仓库 stage 格式补齐；不改其他算子。新增记录后必须断言检查确实选中 1 个目标，不能沿用首轮退出码 0 作为通过证据。

CONTRIBUTING 引用的 `docs/contribution.md` 在该 HEAD 的跟踪列表中不存在；实际指南位于 `docs/content/en/contribution/`，继续使用现有 AGENTS/CONTRIBUTING、目标源码和本项目适用标准，并核对实际指南内容。两次 `git archive` 传输停滞记录保留，改为只读读取已安装的跟踪文件，避免依赖缺失 Git 对象获取。

开发服务 eager v6 已在两机启动整模重载，保留 TP8/PP2、async on、prefix on，使用经核对可写且不依赖额外 bind 的容器默认服务缓存。此轮仍不是正式验收；后续 FULL graph、真实请求、精度、性能与 PP/async 结果均待验证。

## 最终 clone 切片 v3

两机均已安装相同三文件结果：clone 注册项、clone 测试、clone 元数据。v3仅额外补齐元数据并使新增测试在非CUDA后端使用设备同步抽象、明确限定 CUDA graph/Inductor 专项的范围；数值 kernel 保持原样。两机各64项测试全部通过，无本目标跳过。源码清单SHA-256为 `71dfa867496e98c935c36cb847fe3abff1a0ed227883b1461f220cd960053690`，远端安装与日志位于 `02-issues/<Host>/clone-final-v3-20261104/` 和 `04-runs/<Host>/deepseek-v41-clone-final-v3-20261104.log`。

103 实际源码全25份导出检查、clone元数据、marker、ATen名称及真实Torch schema、diff检查通过；后三项确认均选中1个目标，见 `02-issues/mx-103/clone-ci-v3-20261104/result.json`。原零目标结果保留，不充当该通过证据。

取得官方同一固定提交的6952文件快照后，逐文件核对103实际安装树，所有文件哈希集合与本地v1快照完全一致，集合SHA-256为 `9784e8ff5360eb0416c64ee6c8e2e0816241485651db4fff1a96992367df0d3b`；真实修改仅两份已知文件。原生绑定回执为 `02-issues/mx-103/fg-full-source-bind-v1-20261104/result.json`。在此基础上叠加v3候选，完整 Python/YAML/元数据 hooks通过且快照未变化；所有钩子版本保持目标配置，镜像地址换成同项目官方GitHub地址。首轮全文件检查的clang-format13因本地CPU架构不匹配未能执行，另有system hook缺少python PATH；后者修正后通过。后续完整检查明确排除不适用于本次三文件修改的C/C++格式化，保留原失败及范围限制，不宣称完整C/C++检查通过。

clone benchmark 每种口径15案例、均无执行错误：kernel速度比范围0.9661–1.4457，cudagraph为1.0025–9.9245，operator为0.1325–1.5424。三种原始JSON的SHA-256依次为 `9d48541e7fb5743398cee28cddc7534a894a3cf255992d04af6d54b378b2f2c5`、`57bb4a496e2d5f4114e3b642a63cb8f3aed50fdf09d4f773a999635a5dcefa6b`、`f2473cbf772702228a666d0de6b89c2ecb798eb8d5eb04cdbbd5e55721fa3f28`。该注册修复没有修改复制kernel；小shape host开销限制保留，不能声称operator全场景通过性能门槛。

v6已通过原CPU clone故障点，后续失败为独立的[cache显存预算](014-memory-budget-and-startup.md)；当前没有PP异步调度通过结论。
