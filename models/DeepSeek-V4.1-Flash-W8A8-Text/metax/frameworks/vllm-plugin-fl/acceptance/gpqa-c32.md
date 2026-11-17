# GPQA Diamond 32并发测量

2026-11-05，用户要求暂不处理GSM8K精度问题，先以32并发测试GPQA。本轮使用完整Diamond 198题，独立run/cache身份`v41-gpqa-diamond-c32-v1-20261105`；启动时为无阈值测量，用户在完整分母汇总后明确设置strict-match门槛为86%，171/198＝86.3636%达到该门槛。原运行配置和报告保留，不沿用GSM8K的95%，不以分数达标替代正式回执或完整适配。

状态：完整任务已于2026-11-05 14:57北京时间结束。按用户后续授权将13条异常计错、以完整198题为分母，strict-match为171/198＝86.3636%，flexible-extract为60/198＝30.3030%；见[独立计分汇总及原始证据](gpqa-score-summary.md)。原生聚合排除13题及原最终检查失败的记录均保留，未提升正式验收状态。模型与源码保持v22不变：FULL、TP8/PP2、V2 runner、async ON、prefix ON，Plugin v35 / FGV v43 / FG clone v3。客户端并发32，当前引擎`max_num_seqs=16`，其余请求排队；不能将其报告为32条同时执行的引擎序列。32请求预检实际client peak=32、engine running peak=16、waiting peak=16，32项结果均正确，health200。

参数冻结：thinking/high、temperature0、top_p1、max_gen32768、seed20261104、timeout7200、每API一次尝试、无任务重试、limit=0。保留原GPQA prompt、MD5确定的选项排列、目标、strict-match与flexible-extract评分器；主报告指标为`exact_match,strict-match`，同时保留flexible。完整样本及超时/错误均需如实核对；本轮13条异常计错依据用户针对GPQA的新授权，未沿用GSM8K授权。

原始Diamond Arrow来自评测镜像已有缓存，198条，SHA-256`501f307f9e8bc34041af4120c8eb5a735f0ea29cd83c90167b913651071bb4c4`。为把派生缓存留在评测容器私有批准根`06-cache/gpqa-arrow-dataset-v1`，使用独立任务ID`gpqa_diamond_generative_cot_v41_cached`和只改变数据传输的Arrow配置。v1同名配置预备未明确验证任务选择，未用于推理；最终v2显式断言实际加载Arrow/指定cache，并与原生TaskManager逐题核对原文、处理后文档、选项、目标和渲染prompt相同。没有修改第三方任务或Python源码。

实际198题输入为195～2676 tokens；单条最长输入加输出预算35444小于50000，且单条请求可放入实际277438-token KV容量。客户端32个完整最大生成预算不同时预留；引擎依原生16序列及KV admission/preemption调度。该容量结论不保证32条满长度生成同时驻留或无抢占，运行中单独观察等待、KV使用和异常。

批准根为`/public-flash/jinghao/deepseekV4.1`，仅mx-102、mx-103：

- 配置：`03-acceptance/gpqa-c32-v1-20261105/config.json`，SHA-256`f0df73f265b7500cd733e2514316a9c1fb44209890856be0e0460d744180cfa1`。
- 任务：`03-acceptance/gpqa-cached-task-v2-20261105/gpqa_diamond_generative_cot_v41_cached.yaml`，SHA-256`74e708364c6f372a0dfc2c29bb886174ec5a77a9cc611c09ba0a355be49cbbb7`。任务只引用原镜像template/process_docs，原始文件不变。
- 数据/容量证据：`04-runs/gpqa-dataset-capacity-v2-20261105/result.json`；处理后文档SHA-256`62ba21e2276eb6b555871f4156183f2a35cb3e7f874da87af778ef1568d5c928`，渲染contexts SHA-256`e6c10daa18175c071363e47a0bbd526560100f1dd2d84cb96d44fac1e10d84ca`。
- 并发预检：`04-runs/gpqa-c32-probe-v1-20261105/`，保存全部原始请求、响应和metrics。
- 新两端服务绑定：`04-runs/v41-gpqa-diamond-c32-v1-20261105/service-binding.json`，SHA-256`1d71553933305b7d311ad34aa65b49eb7c21da6f7e47402ffa752eccb5b375ac`；服务契约仍为`6e072a45831f15d29492c23d618c4d211d4017840e4fa426f0b76cd11df657ef`。
- durable watcher、原始日志、被动metrics与最终检查：`04-runs/v41-gpqa-diamond-c32-v1-20261105/`。原生完整结果：`04-runs/flageval-native/deepseek-v41-text-gpqa-diamond-c32/v41-gpqa-diamond-c32-v1-20261105/`。

采用原项目`llmrun.py`及198题完整性检查，不改原生runner。当前任务别名/Arrow传输不在固定stage-score适配范围，已关闭该侧车；最终检查仍要求396行、每filter完整198题、逐题均值/分母、数据指纹、原始回答健康、服务与evaluator身份一致。原生完整任务以`formal_acceptance:false`运行，仅记录实际分数，不以无门槛测量冒充正式通过。本次accuracy Skill选择完整任务范围，bundle SHA-256`a1c3dce2e0dde6304b95d5a7ee0d54bf436dd4fab94ed4719c377737122fe6a2`；正式流程前置未通过，故不声称formal-full验收passed。

启动控制为`03-acceptance/gpqa-execution-v1-20261105/`；watcher host PID2383648、start_ticks1226500044、cmdline SHA-256`218aeb95e7be139d71bb9d39b72ed64f872491da3ad4101fe5b9ab6c987f6cc2`，watcher源码SHA-256`5f05cdb1e19758360f7aae72ef37c659cfa294780eef3fdc6bb8932951700e45`。实际子进程和终态以本轮`native-run-control.json`/`native-exit-status.json`为准，不重复启动。

启动后首批已核实13条API响应：13个唯一ID，均finish_reason=stop、最终content非空、reasoning存在，无解析错误；此为输出健康观察，不是13题精度结论。持续采集的原生metrics确认16运行/16等待。沿用用户此前每半小时检查结果的安排，已为本轮建立同聊天检查任务，完成并核验得分后删除，不影响模型服务。
