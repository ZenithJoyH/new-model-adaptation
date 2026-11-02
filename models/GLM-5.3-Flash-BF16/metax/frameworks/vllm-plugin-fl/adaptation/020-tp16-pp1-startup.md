# TP16 / PP1 双机启动与推理检查

当前结论（2026-11-01 13时续查）：原先GLM激活早于选卡导致的stream等待已修复，a4完整服务两机均越过原阻塞并加载完120个权重分片；随后编译产物接口错误已修复并完成两机独立测试。当前无法继续整模验证：两机全部16卡正由其他任务的 `mx8_0`～`mx8_7` 容器占用，模型为 `DeepSeek-R1-0528-Qwen3-8B`，每卡该进程约57330 MiB、总占用约58191/65536 MiB，剩余容量不足以加载本模型（a4每卡权重约41 GiB）。尚无服务就绪或实际生成，不能宣称修复闭环。

占用归属由host GPU PID、cgroup、容器ID和模型命令交叉核实；原生记录在 `01-environment/stream-fix-20261101/<host>/resource-contention-evidence/`，2026-11-01T04:59Z冻结。ownership.json SHA：101 `97efb9d89f9604f3dc10ad9bee5c20ef15a918b16dc84c6031683f9a5fa12cfd`、102 `754ae8290d8ee46912bef8a7ed6eb135d688bc27d0f19a80c538391cca73120d`。没有停止这些外部服务、reset GPU或重启主机。继续验证需外部负载结束，或用户明确批准暂时停止这16个DeepSeek容器；待批准的操作只按已冻结身份复核后停止精确CID，102试点核实后再101，保留数据及原GLM容器。尚未执行该操作。

MCCL Abort补齐结果：102旧实现负对照4项失败，修复后两机各4项通过，覆盖ctypes签名、原生转发、错误传播及缺符号失败。`pynccl_wrapper.py` 修复后SHA `8baeef8aad857daac93253d8777e220ed81e80a0441b4481897b701b3250ce45`，测试 `test_metax_mccl_abort.py` SHA `6873116399ad6f1faa5d97a19cf8a1cce92e8cee6e38642ed662f1b9e5bdcea0`。真实16rank两轮重建探针 `glm-mccl-reinit-stream-a1-20261101` 在第一轮初始化即阻塞，两机240秒有界退出并精确清理，未到达Abort，不能声称真实清理/重建通过，也不能认定缺少Abort造成SDK队列超时。

后续独立Torch探针 `glm-torch-eight-after-queue-timeout-a1-20261101` 在两机均只测到GPU0：默认stream计算通过，显式新建stream等待至90秒后终止；因遇首错即停，其他7卡未测。内核队列超时日志保留，但在上述外部负载占用期间，不能据此判定永久驱动故障或把队列异常直接归因为资源竞争。已确认的是资源不足，停止追加GPU测试及大模型重试。

本轮最终Plugin共6个产品文件、4个回归测试，两机源码一致，完整patch SHA `7ca8a1f4bb7996e78b7dbbf0356f145d16c15950eb45e53788e44a83ece48628`；封存在 `01-environment/stream-fix-20261101/<host>/final-source-resource-blocked/`。manifest SHA：101 `bd95876f0abf0e7c0719e7647366486e87278a546045e6f448c1e5a44d86bef5`、102 `b6f7487d7a56b1817c9f170048ca22ebe6206bff31e3216bfaf356801391b1f2`。vLLM、FlagGems、FlagGems-vllm的HEAD/status/diff哈希与a5启动前完全相同；未改Torch/SDK。根脚本仍为b4b959、TP16/PP1、FULL_AND_PIECEWISE、正常async及prefix开启。a4/a5及所有失败证据保留，a5功能请求绑定在新增Abort修改后已过时，不能沿用为当前服务验收。

两机原 `glm5.3-flash` 容器均保持原ID运行，最终docker top仅有PID1 bash；本任务服务/诊断进程均退出，API18530未监听，生成请求为0。新的作用域诊断回执在 `04-runs/glm-tp16-diagnosis-resource-blocked-20261101/<host>/verification.json`，状态blocked_external_gpu_capacity，非正式模型验收。诊断回执SHA：101 `7c15ecb75e2822c3e0196d902d6d7100ac93695ffbdc838711937d3aba165aa6`、102 `29f5bc8f532bd2c77849722d343216baa0590302bbe118ad788d8388364fa812`。精度、性能和镜像交付继续暂停，历史GPQA不覆盖本轮源码。本次收尾YAML解析、blocked/暂停/请求0的作用域断言及 `git diff --check` 通过；末次全库audit仍报根README和models/README指向缺失XingChen4模型的2条范围外断链错误及14条历史warning，未修改这些文件，不能声称末次全库审计通过。下文是按轮保留的调查、修改前范围及失败记录，“当前/最终”须结合相应轮次解读；此前审批环境冲突现已解除。

a5及第三处限定计划（2026-11-01）：编译类型修复后两机CPU/CUDA×binary/unpacked各4项全通过（102127.07s、101147.00s），两机独立新进程空缓存各4产物/8组新输入均rc0通过；具体修复SHA `6346ccbf6c831555df37512ce16697603b420461c6bf2fcffb334997f26009f6`、格式化测试SHA `18b2a1b93e737de496c84ab7daf413abcdae40e24fa964ae454816b14d031bde`。a5完整服务在模型加载之前出现另一阻塞：两机 `ncclCommInitRank` 中SDK `mxkwCreateQueueBlock` ioctl队列创建超时。已保存双机Python/native栈、初始/停止前身份并精确停止本run；原容器均保留。未降图、未改Torch/SDK、未重启主机或设备，仍无API/生成请求。a5冻结来源与a4均保留，不覆盖。

只读核实两机实际MCCL均为 `libmccl.so` 2.16.5，原生导出 `mcclCommAbort`，头文件声明其释放通信器并中止未完成设备操作；当前Plugin `pynccl_wrapper.py` SHA `977a9c37e7bd1335301eda53dbe031f24c04d8e952a9917535bffb82e41d4491` 没有 `ncclCommAbort` 方法。当前只读vLLM `PyNcclCommunicator.destroy` 明确在daemon线程调用该方法，解释此前销毁阶段AttributeError。两机共享内存各仅占1%，未见容量耗尽；不能据此推断缺失Abort必然造成这轮SDK队列超时。

扩大范围前限定：只新增Plugin MetaX `pynccl_wrapper.py` 的原生 `mcclCommAbort` 必需符号/ctypes签名和同名上游兼容薄方法，经既有NCCL_CHECK传播错误；不以collective Destroy或no-op代替Abort，不吞异常，不改分发/all_reduce/其他厂商。增加 `tests/unit_tests/distributed/test_metax_mccl_abort.py` 验证公开方法转发、签名、错误传播及缺少原生符号时在创建通信器前失败；保留旧实现负对照。随后以真实GLM激活、TP16组、stream与变输入all-reduce做两轮建立/销毁/再建立，检查实际清理回调与后台异常；先证明基础通信健康再重启大模型。若SDK队列问题仍存在，继续只读驱动/资源诊断，不擅自reset GPU、重启主机/容器或删共享资源。适用plugin:A2/B2/B3/B4/B5/C1/C2/E3/E4/F1/F2/F4/F7；无算子数值实现修改。

a4后续结果与第二处修复计划：原stream等待已由实际完整权重加载证实越过，但warmup于12:09:46在MetaX `fix_standalone_compile.py:127` 失败，`CompiledArtifact` 已是抽象基类（缺__call__/save），当前Torch2.10原生standalone_compile返回具体 `CacheCompiledArtifact(compiled_fn, artifacts)`。101随后失败退出；102仅按初始PID/start_ticks/命令哈希停止本run的10个残留进程，controlled-stop.json保留且all_exited=true，容器不重启。无API、推理请求仍为0，不把原stream修复等同于完整启动通过。

这是013中已验证过、主线更新后旧补丁归档未重放的同一接口差异，当前适配器SHA仍为 `e3f5f15b365079177c2a0eb73f1369c6f6752f5c10b95bebb35231434aa7e5cf`。扩大范围前限定：只增加Plugin `dispatch/backends/vendor/metax/patches/fix_standalone_compile.py` 的具体类能力导入/返回构造类型，缺失具体类时保留旧版CompiledArtifact构造路径；不改变嵌套节点遍历、cache key、TF32旧hook、签名或缓存算法，不改Torch/vLLM/SDK。从更新前归档单独复用 `tests/unit_tests/compilation/test_metax_standalone_artifact.py`（原SHA `9665f1cfb8e7b1c673cdd674b0e9cdd9fe507e4371dc8607d9b999e1fc7322d1`），先在当前未修适配器保存CPU编译负对照，再验证两机CPU/CUDA×binary/unpacked真实编译、调用、保存/原生加载及变输入数值；独立进程恢复新产物。当前接口已只读核对，旧Torch缺少实机仍须披露；不把旧通过直接改称本轮通过。适用plugin:C1–C4/F1/F2/F4/F7，复用既有厂商patch入口，不扩展数值算子修改。后续完整服务使用新a5来源/绑定，a4失败和冻结来源保留。

续查第二次恢复（2026-11-01）：审批环境恢复可用，重新核实两机原CID、running/RW映射、agent模式及既有4文件状态，之前未启动的组合复现现已执行。`glm-activation-group-late-a1-20261101` 在无权重场景重现：16rank完成distributed初始化，两机local_rank0停于Stream创建，其他14rank创建成功；两机Python/native栈均指向 `mcStreamCreateWithPriority → HostQueue::start → Semaphore::timedWait`，到180秒上限精确清理本探针组，原始失败保留。`glm-activation-group-early-a1-20261101` 仅先选卡，16rank数值检查均通过、两机wrapper均rc0。进一步 `glm-activation-group-bound-a1-20261101` 保持模块导入时序，仅在实际 `initialize_glm5_worker` 前选卡，16rank同样报告stream/all-reduce136/complete通过（wrapper终态待核对）。两种通过路径均有既有MCCL销毁线程缺 `ncclCommAbort` 的异常，单独披露，不据此宣称清理库契约无缺陷。

产品修改前限定范围：Plugin安装基线7094141e2、3产品文件+1测试的既有prefill修复保留；新增仅 `vllm_fl/worker/worker.py::WorkerFL.__init__/init_device` 与 `tests/unit_tests/glm5/test_metax_worker_startup.py`。MetaX且真实GLM架构的激活移到现有assigned→visible映射/set_device之后、distributed和ModelRunner/CustomOp构造之前，避免选卡前的GLM能力探测在所有rank默认GPU0执行；复用现有模型匹配、激活和选卡逻辑，不复制设备映射、不新增环境开关。其余平台/模型保留原构造期路径，实际初始化失败直接上抛。单元测试覆盖visible设备映射与顺序、非目标平台/非GLM守卫、失败在collective前停止；先保留旧实现负对照，再改实际安装文件并验证。随后以相同TP16/PP1共享launcher完整启动、文本/图像功能检查；仍不恢复GPQA、性能、镜像。适用plugin:A2/A3/A4/B3/B4/C1/C2/D4/E3/E4/F1/F4/F7；无数值kernel或第三方源码修改。

实现与已完成验证：102旧实现负对照2失败/2通过；相同4项测试在两机修复后各4通过，既有GLM激活/策略/异常回归102另16项通过。Worker原文件SHA `659c928b04d7ae841be72693e3061fa424c3b1e0a331e0e5365b0d2bbdd07de6`、修复后 `b65a42dd904a74847ec7db506bf4da98be6401304538ac55088eb1c93f0ff578`，新增测试SHA `690c260d17293b924bacb7a0655cfed50729456be54637451ea915f71e505abe`；原文件及manifest保存在 `01-environment/stream-fix-20261101/<host>/worker-patch/`。新测试ruff0.14.0 lint/format通过；显式检查worker整文件在修改前后均有相同2处继承的I001导入排序问题、整文件format建议也均存在，未夹带全文件整理。新增两处hunk已按模型/平台守卫、实际设备映射、激活在collective前执行及异常传播逐项复核。其他硬件仅接线验证，未声称硬件通过或完整PR门禁完成。

`glm-activation-group-bound-a1-20261101` 两机最终wrapper均rc0。完整服务a4 `04-runs/glm-plugin-tp16-startup-a4-20261101/<host>/` 已通过原共享脚本启动；101 API27169、102 headless3620535，原容器不重启。两机本地rank0分别27426/3620736的12:01非阻塞栈均实际进入 `load_weights`，原stream等待在完整服务中已越过；栈、进程身份保存在本run的 `rank-local0-progress-a1*`。当前仍处于权重加载，尚不声称就绪或推理通过。

完整当前来源封存在 `01-environment/stream-fix-20261101/<host>/final-source-a4/`：4个tracked产品文件+2个untracked测试，完整patch SHA `4314b32885cd0e0625ab0758d44e281e57cb590efaad302434d015b114d57b21`，manifest SHA分别101 `fe0e3ecab95f9fab371c7c373ea6027ad1b34831c238001cfb3881771fb88368`、102 `8da1f73c13424190916d2559b66a82fe3de0b232c46eeab2774db9de59048960`。相同6文件哈希已核实；未提交、推送或封装镜像。

a4功能请求单独绑定在 `03-acceptance/tp16-startup-check-a4-20261101/`，原生离线预检为planned、3cases、concurrency1，尚未发请求。manifest SHA `88907cd0e27483f56bdd5701779e09ab4f7b06703db76830629b412f5f5f9e5d`，binding SHA `dadde0ed812082c97e20a646d15591957ab8d37e6c5c463dc5aa6de83ba01062`，实际sanity.py SHA `7d92c2bcf3625a65265229f11d92b19d23e9c3434073cdcc6597f8f0b0086ccd`，Skill bundle SHA仍为 `a1c3dce2e0dde6304b95d5a7ee0d54bf436dd4fab94ed4719c377737122fe6a2`。这仅用于用户请求的功能修复验证，不冒充重新完成执行模式或正式service-sanity验收。

本轮12:00前本地 `./scripts/syntax-check --offline` 通过341项（19skip）+7项运维回归、13shell/3playbook，结构审计0error/14历史warning。前轮末次出现的其他模型断链本轮已不再报错，未由本任务修改，不沿用旧审计失败结论。

2026-11-01 后续定位已获用户授权恢复，范围仍为双机TP16/PP1功能修复与文本/图像推理；精度、性能、镜像交付继续暂停。重新核对两机原容器、RW映射、agent控制模式、共享launcher及既有4文件dirty状态，无其他任务进程，卡空闲。先以8进程GLM实际激活入口、选卡时序和stream测试隔离完整模型初始化差异，不加载权重；未证实前不改产品代码。后文“最终”均指此前一轮冻结结果，后续新增证据使用新run保留。

续查结果：102的 `glm-activation-stream-late-a1-20261101` 有界8进程探针通过，8个rank均完整执行实际 `initialize_glm5_worker`、选卡、显式stream创建与新输入计算，rc0，随后全部退出。每个进程在GLM模块导入后CUDA已初始化，激活完成时设备均为0；rank0创建stream约3.3秒，其余rank约0.02秒，但本测试没有distributed组，不能证明GPU0上下文是完整服务阻塞根因。未运行early对照，无必要把单次等待归结为故障。原生产物位于批准根 `04-runs/glm-activation-stream-late-a1-20261101/mx-102/`；state.json SHA `95ba66da6207d3654bb852c626378d68f0a6cf547bdfbf5106f417b88d30c418`，stdout.log SHA `68df07ceb3f26d8cbffaa3c8af83cca24d8b14a7a4bd5733aa53c2a7147b89a7`。本轮没有新增产品修改，launcher仍b4b959，服务未就绪、请求0；原容器保持running。

只读核实当前Plugin注册入口在未显式设置时已把 `VLLM_WORKER_MULTIPROC_METHOD` 设为spawn，因此不能直接用“fork继承CUDA上下文”作为已确认原因，也未叠加重复spawn开关。

已准备下一步判别实验：保留真实16rank初始化/stream/all-reduce（期望136）流程，增加GLM实际激活，并比较选卡前后激活两种次序；不加载权重，180秒上限只清理诊断自身进程组。本地临时playbook为 `/private/tmp/glm53-stream-fix-20261101/probe-activation-group-{late,early}.json`，嵌入Python及JSON结构校验通过，尚未执行。执行late的102试点被工具拒绝：`approval required by policy, but AskForApproval is set to Never`。来源是 `.codex/rules/ansible.rules` 对通用 `./scripts/playbook` 的 `decision = "prompt"` 与当前环境 `approval_policy=never` 冲突；不是用户撤销任务授权。未修改审批规则、未改用其他路径绕过。需恢复可按命令审批的执行环境后，先运行102并核实已准备/运行状态，再运行101；不能因这一拦截声称技术修复失败或根因已定位。

当前结论：TP16/PP1配置已生效并完成三轮双机启动尝试，但完整服务仍未就绪、推理请求为0，验证未通过。两机本地rank0在创建MACA stream时等待，根因尚未定位；关闭异步调度只使等待点移到MoE辅助stream，已撤回该无效诊断开关。独立Torch测试、真实16rank stream与all-reduce小测均通过，不能把该阻塞归结为TP16通信不支持。两机原 `glm5.3-flash` 容器保持running，任务服务进程已精确清理，API18530未监听。

2026-11-01，用户明确要求将共享配置改成 TP16、PP1，在 mx-101、mx-102 的原 `glm5.3-flash` 容器中重新启动并检查实际推理。沿用批准根 `/public-flash/jinghao/glm5.3-flash`。本轮只做功能启动及就绪后的代表性文本/图像推理检查，不重跑 GPQA、性能或镜像交付。

修改前两机容器均 running、未 paused，无 GLM 推理进程，8卡均空闲；实际 Plugin 同为干净主线 `7094141e28a2680644fc41073aa9dfdfbf1f0044`，版本 `0.3.0rc2.post1+g7094141e2`。vLLM 与算子库保持上轮身份及既有改动。控制模式仍为 agent，保留此前完整验收的暂停状态。

首轮变更范围仅为根 `start-model.sh` 的 `--tensor-parallel-size 8 --pipeline-parallel-size 2` → `16 / 1`。先保存原脚本及 SHA，再在102通过已验证映射修改共享文件、核实101读取同一新字节。模型、BF16、上下文65536、双节点mp、网络接口、端口、FULL_AND_PIECEWISE及正常prefix cache保持原配置。先启动102 headless，再启动101 API；只操作本任务进程，容器不重启。

验证范围：实际安装路径与参数、进程/两机通信、完整就绪、代表性文本的非空且切题输出、finish_reason及异常日志。使用本地精度Skill的 service-sanity 工具保存请求和响应并逐项审阅，作为本轮功能检查，不提升为完整模型验收。若遇新的真实依赖或运行时阻塞，先记录根因与最小必要范围，再作已授权组件内的修复；不修改只读vLLM或第三方依赖源码，不以旧GLM注册覆盖主线。

原生产物留在批准远端根，最终结果与封存回执见本文首段及末段。

首轮 `glm-plugin-tp16-startup-a1-20261101`：两机16个rank均完成TP组建立、PP均为0，随后模型构造失败，尚未加载权重。根因：`Glm5NextMLAAttention.__init__` 用 `current_platform.is_cuda()` 限定便携prefill hook，而实测MetaX `PlatformFL` 是OOT、`is_cuda() == False`、`device_type == cuda`；原生MLA选择器只候选不可用的FlashAttention。两机原始state/stdout及进程所有权快照保存在 `04-runs/<run>/<host>/`，禁止覆盖。

首次产品修复前限定范围（Plugin基线7094141e2、原始clean；FG/FGV/vLLM身份沿用019）：

- `vllm_fl/models/glm5/model.py::Glm5NextMLAAttention.__init__`：将已存在的构造期事务扩展到已核实MetaX；MetaX复用现有 `attention.mla_prefill.FlagGemsMLAPrefillBackend`，其算子经现有统一分发调用FGV公开API。原CUDA路径及NVIDIA reference保持原选择；不恢复旧模型注册。
- `vllm_fl/dispatch/backends/flaggems/impl/mla_ops.py::is_available`、`vllm_fl/attention/mla_prefill.py::is_available`：仅为MetaX的varlen attention和prefill backend开放已有能力探测，保留API可调用与黑白名单条件，不开放其他MLA算子。实测FGV已导出 `flaggems_vllm.ops.attention.flash_attn_varlen_func`，目前统一分发被平台守卫拒绝。
- 在现有GLM测试目录增加上述接线、非目标守卫、事务恢复和失败传播回归；真实MetaX以独立Torch参考检查BF16/head256的变长因果prefill数值，随后相同共享launcher双机重试。若后续再阻塞，记录新证据，不扩大到只读vLLM/第三方源码。

本次不新增数值kernel、不改cache/workspace所有权；适用plugin:A1–A4/B1/B3/B4/C1–C4/D4/F1/F2/F4/F7，算子实现未改。非MetaX硬件仅接线回归，不能宣称硬件数值已验证；图执行需由实际服务捕获/推理继续验证。完整GPQA、性能、镜像交付仍暂停。模型具备图像能力，服务就绪后同时做代表性文本和图像功能检查。

修复验证：102新增 `test_metax_prefill.py` 11项全通过（20.16s），覆盖MetaX/CUDA portable/CUDA reference/其他平台、两次构造、异常传播及事务恢复、缺失API与黑白名单。两机真实公开FGV prefill通过：BF16、head8×256、变长[1,17,33]、两组新随机输入，CPU独立FP32因果attention参考，max_abs_error为0.0083852/0.0080566（rtol/atol各0.02），显式out同址、无NaN、LSE有限。该检查未验证图捕获或LSE数值，不能替代完整算子验收。证据 `04-runs/glm-plugin-tp16-prefill-{tests,numeric}-a1-20261101/<host>/`（单测先在102执行）。

第二轮 `glm-plugin-tp16-startup-a2-20261101` 已由同一根级脚本启动：102 headless PID3595055，101 API PID4368、EngineCore4570；16rank通过模型构造并开始读取120个safetensors分片。尚未服务就绪，推理待测。原始进程归属快照留在各run目录。新增回归测试按ruff0.14.0排序/格式化，两机相同，另存 `prefill-patch/test-format.json`；运行中3个产品文件未因格式检查改写。上游pyproject默认排除vllm_fl，显式lint三个产品文件通过，额外format检查mla_ops守卫提示换行风格，暂保留本轮冻结运行字节；其余两个产品文件及新测试format通过。未运行完整pre-commit（容器无该工具），不声称PR交付检查已全部完成。

文本与图像请求已冻结在 `03-acceptance/tp16-startup-check-20261101/`，原生sanity离线预检通过，仅用于本次功能诊断；尚未发请求、不声称formal service-sanity通过。

a2进一步诊断：两机本地rank0尚未进入权重加载，而同机其他rank已加载/预读。两次非阻塞py-spy Python栈均停在 `worker/model_runner.py:803` 异步调度输出stream的 `Stream()`；102原生栈进入 `mcStreamCreateWithPriority → mcr::Stream::Create → mxr::HostQueue::start → Semaphore::timedWait`。cgroup pids.max629145、current约2450、events.max=0，未见线程数限额耗尽。不能将所有rank的状态概括为权重读取慢，也不能据此声称TP16 collective数值已通过。

下一次仅调整必要启动配置：增加原生 `--no-async-scheduling`，绕开当前等待点，保持TP16/PP1、图模式与其他参数。先保存a2线程栈、日志及精确所有权，再停止本任务API/headless及其后代，保留原容器和其他进程；保存b4 launcher备份及新SHA后运行a3。此项是受控诊断，尚不证明SDK问题根因已修复；若下一处仍发生stream等待，需要独立小型复现，不继续堆叠开关。

a2已受控停止，容器保持运行；原始日志及rank0 Python/原生栈、停止前精确PID/启动时间/命令哈希和 `controlled-stop.json` 全部保留。容器Python缺少 `os.pidfd_open`，首个停止脚本在发送任何信号前报错；随后逐PID复核启动时间和状态执行TERM/必要KILL，仅操作本run后代，结果已核实退出。没有重启Docker或容器。

两机独立Torch复现均通过：默认stream计算、显式 `torch.cuda.Stream()`、新stream计算与同步结果正确，rc0、未超时；证明不能把a2等待点归结为无条件的单进程stream故障。复现 `07-bugs/tp16-stream-20261101/torch-stream-gpu0.py`，SHA `aa155bd4e7bf5b5eaec95c0ea588ce6721097fe570d3a187f9cccf99d297d826`，证据 `04-runs/glm-torch-stream-probe-a1-20261101/<host>/`。

第三轮 `glm-plugin-tp16-startup-a3-20261101` 使用新增 `--no-async-scheduling` 的同一共享脚本，SHA `552bd6d1abdc5f8e7186328cbf42757b374045efad6a22506e28ca7d8ac73e2b`。只读核实vLLM原生arg_utils使用BooleanOptionalAction，否定开关合法；图模式保持FULL_AND_PIECEWISE、prefix保持开启。当前待实际启动和推理结果。

a3在两机本地rank0再次等待：101 PID8570（TP0）、102 PID3600042（TP8），py-spy非阻塞栈均为 `torch.cuda.Stream.__new__ → vllm.utils.torch_utils.aux_stream:753 → shared_experts.py:70 → moe_runner.py:280 → FusedMoEFL → GLM模型构造`。关闭async仅让等待点后移，不能作为解决方案；服务依旧未就绪、没有推理结果。不再追加禁用MoE或禁用图等开关。先保留现场、停止本run，再以小型双机通信/stream初始化复现区分触发条件，待证据支持后才改产品层。

小型复现：以真实 `init_worker_distributed_environment` 建TP16/PP1组，不加载权重，测试group初始化后创建显式stream和16rank all-reduce（独立期望136）。首版 `glm-tp16-group-stream-after-a1-20261101` 遗漏 `ParallelConfig.master_addr/master_port`，vLLM将env rendezvous改写为默认127.0.0.1:29501，两机均有界超时rc124；该无效配置不能支持产品故障结论。保留首版原始记录，v2补齐已验证双机master与inbond1地址，在 `glm-tp16-group-stream-after-a2-20261101` 重测，每机driver180秒上限，仅清理本诊断自身进程组。

v2探针也未建立有效组：torchrun继承 `TORCHELASTIC_USE_AGENT_STORE=True`，vLLM切换到29655后，所有rank（含0）按代理store客户端等待，没有进程创建该store；两机直连29655返回ECONNREFUSED，rank0栈位于 `_create_c10d_store`。按180秒上限退出rc124，不能作为产品/网络故障证据。v3仅在诊断子进程移除该代理标志，使用独立29654代理与29655原生store，并新增逐rank JSONL原生进展；前/后stream对照只移动同一个创建点相对于初始化的位置，import/config保持相同。原始v1/v2保留，不覆盖、不放宽产品验证条件。

v3正确握手后，16rank均报告 `distributed_initialized`、`create_stream_done`、`all_reduce_passed(expected=136)`、`complete/passed`，逐rank JSONL完整覆盖0–15；说明TP16组与通信初始化后创建stream的最小路径可以工作，不能把完整服务等待归结为TP16通信不支持。当前继续比较GLM初始化额外路径，尚不改worker顺序或SDK。候选检查是 `runtime._concat_handles_zero_rope`：若原生_C_cache_ops入口存在，会在worker选卡之前向默认CUDA设备分配小张量做ABI探测；先做独立复现，未证实前不修改该逻辑。

最终核验与封存：v3双机小型复现均rc0，16rank阶段与all-reduce值136完整，root wrapper状态passed。102独立零RoPE能力探测后创建stream的测试也rc0，未复现等待；该假设未证实，未据此修改runtime或worker。保留仅已验证必要的3个Plugin产品文件及1个接线测试，逐hunk已复核；vLLM、FlagGems、FlagGems-vllm和SDK均无本轮修改。

最终共享launcher恢复正常async默认值，仍是TP16/PP1、FULL_AND_PIECEWISE、prefix开启，SHA `b4b959abacc49bb51a7984bd1bf2309db06a37239b69e63413a0d037be9ea2c8`。两机最终来源、容器ID/映射、脚本、4文件哈希、终止进程身份与无API均已重新核实。完整补丁、4文件tar和manifest分别在 `01-environment/tp16-pp1-20261101/<host>/final-source/`，原始失败及所有无效诊断均保留。没有镜像封装、提交、推送或新精度/性能评测。

最终功能检查回执 `04-runs/glm-tp16-functional-final-20261101/<host>/verification.json` 明确status=failed、service_ready=false、inference_verified=false、generation_requests_sent=0，不是正式模型验收回执：

| Host | verification.json SHA-256 | final-source/manifest.json SHA-256 |
|---|---|---|
| mx-101 | `75ac444c75ab792b599e2c16f2f5d1fe2d84e0f20d6350a6df12fba2963f12f3` | `1347aa8cd71669b825a7b90d30ecd0e55a083d8cfe413dc68b28620f58fb7a1c` |
| mx-102 | `0f9d30bff049bd177cdb08e80c5c29626efa753b518361b270825d08af272874` | `8eb4b88f5d1a20185b37a9801bf48fa0703a4baed0396b8abafc821dac1702af` |

本地 `./scripts/syntax-check --offline` 通过341项工作流回归（19skip）、7项运维回归、13个shell/3个playbook；audit为0error、14条其他历史工作区待复核。完整适配、原GPQA离线计分和性能/镜像验收继续保持用户先前的暂停状态，本轮不更新为functional或optimized。后续若恢复修复，应从已保存完整GLM worker初始化现场继续缩小复现，不重复无依据的图降级、async禁用或大权重重启。

收尾时单独运行 `./scripts/audit-workspace --json`，出现2条本轮范围外错误：根README及models/README指向缺失的 `XingChen4-29B-A4B/README.md`，另有上述14条历史warning。本轮GLM/MetaX记录没有审计错误；未修改这些其他模型或全局链接。该末次全库审计不算通过，与此前完整syntax-check的通过时间和范围区分。作用域结果结构断言、TP/PP配置、blocked状态及暂停状态校验通过，所改工作区 `git diff --check` 通过。
