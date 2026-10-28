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
