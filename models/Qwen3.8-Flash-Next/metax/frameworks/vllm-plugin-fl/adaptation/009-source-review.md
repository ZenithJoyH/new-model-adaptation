# 009：当前真实安装差异审查（本轮RoPE复验后）

范围仅mx-101的qwen3.8-flash，模型BF16文本TP8。逐文件/逐块审查了请求PR及本任务增量；
已在无诊断graph复验后重新核对全部真实源码；不宣称正式精度/性能或完整验收通过。

## 基线与差异身份

| 组件 | 已核实基线 / 本任务差异 | 审查范围 |
| --- | --- | --- |
| Plugin | main f41b7de883ed71526716738a7e05d810f49ded58，初始clean；用户请求PR455 head65759c43三方应用53文件；另改worker工厂入口、新增compat工厂及13项测试、RoPE编译边界及测试、MetaX编译产物兼容及测试 | 完整补丁473aa021d1661c7dc74c06d9240fe2c9c24c62daf1b6f7e14ff5f79e523ae0af |
| FlagGems-vllm | main c9003571a6bd06bdc94ca3dbfad4cc606a8d82f8，初始clean；PR959 head22194f0b两文件，另有fusion同步及MetaX QSA wrapper/selector/测试/benchmark | 完整补丁28c4645ed2edb611f5cd9a32a80a2f60bc41d7b0afd524277c8308bcb95ff88d |
| FlagGems | master e510c6bbe3ffd9eb22c41021d82f15c21098f998，原权限位差异保留，无本任务源码变更 | 完整diff a34ba80cbad468f0a3dd7c81c855754a3494c957aa5c74b59c6009bfb327f3ed |
| vLLM | ee0da84ab9e04ac7610e28580af62c365e898389，只读，原权限位差异保留 | 完整diff仍2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec |

完整补丁包含tracked/staged/unstaged和新增文件，不把git diff HEAD当作新增文件的完整审查。
原生快照 `01-environment/installed-identity-after-rope-functional.json`（SHA256
85fbbd4dc82526a5c8fb13c34d71315a151463abf49c6792192e289d14fba5c9）；
补丁位于 `02-issues/{plugin,flaggems_vllm}-after-rope-functional.patch`。未提交、推送或开PR。

## 职责、替换与边界

PR455按用户指定整体同步，原有ROCm分类/后端优先级及少量格式差异属于上游补丁，未扩展
为本任务独立重构。模型结构、权重路由、HC与PLE token history在模型注册/状态扩展；QSA
及PLE通过正式custom op边界与FlagGems-vllm公共入口；KV typed-view绑定复用compat owner hook。
检查了模型注册幂等、可选NVIDIA依赖能力守卫、量化排除、MTP拒绝、legacy/V1状态桥接、
worker请求移除/替换、完整权重fragment事务及新增测试断言。没有把模型名/机器名放进公共热路径。

本任务Plugin的Mamba增量仅替换_get_mamba_bufs的一次性工厂调用：同质spec完整委托原生；异构non-spec
按各层真实state数分配容量，逐类型copy callbacks必须是全局tuple前缀，保留原group ID。
继续调用原生preprocess、请求清理、byte-copy kernel；没有重复更新请求或复制整套scheduler。
异构spec/不同block/不兼容callback明确拒绝，原先同质spec路径不变。见006的改前清单与负对照。

Plugin RoPE边界仅FGV选中且正在编译时使用一个out-of-place私有custom op，再以显式copy_
表达公共inplace/alias契约。原mutable私有op在整模internal producer优化下产生越界clone，
已精确撤回；所有原上游测试字节保留。38项覆盖三dtype、inplace两侧、外部/图内producer、
Inductor compile-time autotune与两次变输入CG重放，共享216项也全部通过。eager及FGV关闭
路径保持原调用，不修改FGV数值代码或删除日志。MetaX旧standalone补丁仅选择Torch原生
具体产物类型，构造替换1行；不复制序列化/加载实现，其他厂商无新增导入。
新Torch真实缓存两种格式、
独立进程恢复通过；旧MetaX软件分支仅保留兼容逻辑，未实际测试旧版本。详见008。

FGV PR959保持用户原修复；独立fusion仅在短历史重叠条件增加barrier，保留接口和全部原测试。
MetaX wrapper复用现有通用数值kernel，只约束合法M tile；split selector限定已测dtype/shape，
未命中仍走单kernel。workspace继续由调用方预分配，capture miss不扩容；没有增加Torch计算
fallback或绕开dispatch。新增auto benchmark复用既有bench框架，不改原性能基线。详见002/003。

FlagGems没有源码修复；CPU RNG clone使用进程级追加黑名单；clone-only新整模仍报randn非法地址后，graph候选保留randn/normal_原生入口，影响也包括GPU路径，已披露
移除条件及尚无整模性能量化的限制。FGV开关、prefill6400和内存SQL均是当前任务运行配置；
无全局默认值修改。主FlagGems clamp兼容性未证实，未借性能观察替换其实现。

## 已执行与待验证

- PR959：211通过、无skip；fusion：37通过及24组合×30次最小对照；组件性能无明显回退。
- Qwen算子组合：340通过/42跳过；selector后QSA51通过/8跳过；auto benchmark18项均≥0.9倍Torch参考实现。
- PR455初版回归111通过/4平台限制skip；Mamba兼容后受影响模型/worker/KV/metadata回归108通过。
- 新Mamba测试含同质委托/拒绝守卫、两种group顺序、三state、padding、MetaX真实byte-copy及变输入graph replay。
- activation控制21通过；FGV clamp完整设备72通过；整模eager短问与8730-token真实6400命中均正确。
- RoPE当前完整38项（含图内producer回归）及共享216项通过；MetaX编译缓存四组合通过、无skip。
- 当前源码eager与诊断graph三类请求均通过，10例/105token相同，最大logprob差0.0088574；无诊断graph也通过（最大差0.0051913）；正式数据集和吞吐验收尚未执行，其它硬件未实际执行。

本轮结论：Plugin可作为PR候选，FlagGems-vllm可作为PR候选；FlagGems无源码变更，
vLLM完整diff与初始基线相同。所有增量仍对应001–008的范围清单，RoPE最后两个文件逐块
复核；删除的仅本任务失效mutable私有op，原测试字节完整保留，无其他试验产品残留。
当前installed-identity-after-rope-functional.json及完整补丁SHA在graph结束后再次逐项核对，
HEAD、完整diff和新增文件集合/内容均未变化。组件贡献结论限本机及声明的契约/隔离矩阵，
其它硬件和旧MetaX版本实际运行未验证，不把本轮数值对照当作正式精度验收。
graph保留clone,randn,normal_进程级workaround及内存SQL；未改库默认值，正式性能影响
未量化，退出条件在004/008。纯FULL受GDN UNIFORM_BATCH限制，显式下一档实际通过。
完整阶段原生绑定、最终launcher与镜像交付仍待后续整体适配，当前不标记optimized。

## 2026-11-02：Plugin适配测试收敛（计划）

用户要求收敛当前Plugin测试，目标仅mx-103 / qwen3.8-flash，安装路径 `/opt/vllm-plugin-FL`，HEAD `7094141e28a2680644fc41073aa9dfdfbf1f0044`。初始差异为4个产品文件和3个测试文件，先保留精确原文及哈希。当前版本未检出AGENTS/CONTRIBUTING文件，采用现存 `tests/README.md`、pytest fixtures、pyproject及pre-commit配置为工程约定。适用plugin:C1/E1/E3/F1/F2/F3/F4/F5/F7。

限定修改2个已有适配测试：`tests/unit_tests/ops/test_rotary_embedding.py` 将外部strided别名与图内producer两组GPU测试统一为参数化测试，仍保留原18种GPU组合、6400×4×256原始触发形状、dynamic/autotune选项、原数值容差与精确别名/输入断言、两次变输入replay；复用独立RoPE数学参考，添加输出哨兵，保留全部CPU编译契约和FGV关闭路径。`tests/unit_tests/worker/test_mamba_cache_compat.py` 将原生拒绝异构的负对照并入两种group顺序的分配测试，复用eager/replay的状态拷贝校验循环并对目的状态填NaN；保留5种失败边界、同构透传、两dtype/两顺序GPU组合、完整backing及padding断言。替换的旧测试由同一参数矩阵/负对照等价覆盖，不缩减支持契约。

MetaX standalone编译测试本身已紧凑，保留CPU/CUDA×binary/unpacked及fresh-process加载四项，不修改。沿用现有测试文件位置及GPU marker，不借本次任务迁移上游已有测试布局。四个产品文件、FlagGems/FlagGems-vllm/vLLM、启动脚本和正在运行的模型服务不变；停止的评测不恢复。验证采用当前容器的原生pytest入口，运行3个测试文件完整回归、相关共享编译/worker回归及配置要求的formatter/linter/pre-commit，保留结果与未验证范围，不提交或推送。

## 2026-11-02：测试收敛实施与验证结果

已直接修改mx-103目标容器 `/opt/vllm-plugin-FL` 的上述2个测试文件；Plugin仍为4个产品文件+3个测试文件的既有适配差异集合，没有新增或删除测试文件。RoPE两组GPU回归统一为一个参数化入口，18种GPU组合、6400-token图内producer原始触发形状、原容差与精确别名/原输入断言保留；每次replay更新输入和位置并先填充输出NaN。新增局部独立数学参考，并用NumPy复数旋转公式在CPU上核对三dtype×两布局×两种head数共12组合；GPU数据改用局部CUDA Generator，避免改写全局随机状态。Mamba原生拒绝异构的负对照合并进两种group顺序的分配用例，保留不分配断言；eager与两次replay共用完整backing/padding校验循环，目的状态先填NaN，不改变零容差。适用的operator:E1/E2/E4/E5/E6已核对；未修改算子库或kernel，不据此宣称完成算子交付。

逐块增量审查完成：替换的测试逻辑由相同参数矩阵和更强哨兵断言覆盖；上游RoPE原始文件前缀逐字不变，MetaX standalone测试原文不变，4个产品文件哈希与修改前一致。测试收集由55项变为54项，减少的是已并入两种顺序用例的单独负对照。最终RoPE文件430行（原439），Mamba231行（原238）；重点是复用脚手架与保留覆盖，不以机械删行减少测试。没有修改启动脚本、运行中的服务或已停止的模型评测，没有提交/推送。

验证分开记录，不将未运行项冒充通过：

- Ruff 0.14.0（仓库固定版本）check与format检查均通过；git diff --check通过。
- 最终两个修改文件的原生CPU测试：24 passed、26 deselected，21.39秒；JUnit无failure/error/skip。26项硬件用例明确未验证，未把deselected算通过。
- 未修改的standalone编译文件4项在初次运行中逐项PASSED，涵盖CPU/CUDA、binary/unpacked和binary新进程加载；该整轮随后因图测试阻塞被终止，不将该轮退出码或缺失的完整JUnit当全套通过。
- GPU图复验阻塞于torch.cuda.graph构造默认stream。最初怀疑Inductor工作进程池，测试进程改为单编译线程后仍复现，故该假设未被证实。独立只导入Torch、初始化CUDA并创建Stream的GPU0/GPU1探针均在35秒内报 `MXKW ioctl create queue block timeout`；准确资源/驱动根因尚未定位。保留堆栈/探针结果后，只结束本任务挂起的pytest及其编译子进程，未调整skip、容差或修改产品以掩盖问题。
- pre-commit hook环境在共享NFS的setuptools元数据备份报Errno5；更换独立临时目录和工具构建setuptools77约束后仍失败。Ruff/pre-commit工具仅安装在批准根下独立临时venv，未修改模型服务解释器的依赖。完整pre-commit未完成，不能宣称PR-ready。
- 最终服务health200，running0/waiting0，容器保持运行，未恢复GPQA或ERQA；半小时汇报已在用户停止评测时删除。

原始文件归档、差异、pytest日志/JUnit、工具版本、失败尝试、探针和最终校验均在
`/public-flash/jinghao/qwen3.8-flash/04-runs/plugin-tests-consolidation-20261102`。
`test-consolidation.diff` SHA256为 `ad774a840d0d9a5bd3e043522bb4677ced9a10641245bffdc4e0628dc000fa19`；
`final-verification.json` 状态为 `code_consolidated_validation_incomplete`。
代码收敛已实施，真实图与完整pre-commit复验保留为未完成，不提升framework.yml状态。

## 2026-11-02：MXKW/NFS定位与剩余检查补齐

继续范围仅mx-103 / qwen3.8-flash（容器ID `31022d2372f941b64ad4da9c7cde8d1be5aacbaff650857e49e8f4e6d1201d89`），批准根仍为 `/public-flash/jinghao/qwen3.8-flash`。用户要求排查服务占用对MXKW的影响并补齐GPU/pre-commit检查。依远端操作政策，在核对PID命名空间、start_ticks、cmdline哈希和端口归属后，仅停止本任务Qwen服务的11个进程，容器PID1及其他任务不动；旧owner和评测停止记录保留。停止前服务占用每卡约56–57GB，停止后8卡均858MiB且无GPU进程。此前GPU0/1独立Stream探针都超时，释放后相同探针均成功，未改驱动或测试断言。

剩余26项GPU测试在实际安装Plugin中全部通过：26 passed、24 deselected，66.01秒，JUnit的failure/error/skip均为0，覆盖Mamba原生拷贝、上游RoPE及18组compiled真实capture/replay。与此前24项CPU通过、未改动standalone文件4项逐项PASSED合计54项；这些来自分开运行，不虚构一份54项完整成功JUnit。MXKW与服务共驻时GPU资源占用存在明确受控对照关联，仍未细分显存与驱动队列配额；不能据此认定驱动本身无问题。继续遵循plugin:F2/F3/F4，不添加skip或放宽容差。

NFS故障独立定位到Python `shutil.copystat → _copyxattr → os.setxattr(system.nfs4_acl)` 返回Errno5。相同目录普通读写、copyfile、utime、chmod均通过，copy2/copytree失败；服务停止后ACL复制仍报相同EIO。另试原hook源码的legacy工具构建仍因元数据ACL复制失败。故不能把NFS错误归因于GPU占用，也不能宣称存储故障已修复；没有修改NFS挂载、ACL、系统依赖或Python库。

静态检查改在本机macOS临时目录执行：只传两个修改测试及原pyproject/pre-commit配置，四文件SHA256与远端实际文件在检查前后逐项一致，没有模型运行时导入替换或PYTHONPATH。pre-commit 4.7.0使用原配置及固定hook版本，退出0；merge-conflict、private-key、EOF、trailing-whitespace、Ruff check/format、typos均通过。symlink和shellcheck因两个输入均为普通Python文件按原配置无适用项；没有人为跳过hook。临时文件检查后内容未变，已回到远端再次核对哈希。此为本轮两测试文件的完整适用静态检查通过，不将其表述为远端NFS hook安装成功。

4个产品文件与此前基线哈希一致，3个测试文件仍为此前收敛后的哈希，Plugin HEAD仍 `7094141e28a2680644fc41073aa9dfdfbf1f0044`，git diff --check通过。未新增产品修复，未修改FlagGems/FlagGems-vllm/vLLM或启动脚本，未提交推送。新证据位于 `/public-flash/jinghao/qwen3.8-flash/04-runs/plugin-test-recovery-20261102`，包含服务停止记录、前后Stream/NFS探针、GPU JUnit、哈希绑定的本机pre-commit原始日志/结果及 `verification-before-service-ready.json`。此前失败证据不覆盖。

测试后已用原 `start-model.sh` 无参数恢复graph服务，launcher SHA256仍 `5c5bd7ce11d468e1606399d054c04fd32cd179bc13fea6b66d78f02d999216ab`，argv与旧实例完全一致，prefix开启且无新增缓存/数据库/PYTHONPATH覆盖。新实例 `mx103-graph-restored-after-tests-20261102`，host PID301751/container PID3969357，精确身份写入新 `restored-owner.json`，不覆盖旧owner。当前记录写入时正在加载模型，恢复就绪与最小推理结果待下文核实；GPQA/ERQA保持用户停止状态，不提升framework.yml或全模型验收状态。

恢复补验完成（北京时间2026-11-02 13:32）：11/11 mixed PIECEWISE及7/7 decode FULL图捕获完成，health200；一次文本恢复检查正确回答 `7×8=56`，HTTP200、finish_reason=stop，端到端2.016秒（单次恢复检查，不作性能基准）。检查后running0/waiting0、抢占0；恢复日志未见MXKW或OOM，容器保持运行，评测没有恢复。原始请求/响应及署名审查绑定在 `restore-sanity-*.json`，最终 `final-verification.json` 状态为 `scoped_validation_passed_service_restored`。仅补齐本轮测试收敛的硬件/静态门禁；NFS ACL故障、MXKW具体配额机制、其他硬件/旧MetaX版本及全模型正式精度/性能未验证的限制保留。
