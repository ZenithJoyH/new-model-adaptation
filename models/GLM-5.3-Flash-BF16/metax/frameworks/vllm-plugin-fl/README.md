# GLM-5.3-Flash-BF16 / MetaX / vllm-plugin-fl

2026-11-03当前：两机原 `glm5.3-flash` 容器的TP16/PP1服务保持运行，使用同一最简 `start-model.sh`（SHA `b4b959abacc49bb51a7984bd1bf2309db06a37239b69e63413a0d037be9ea2c8`），prefix开启。FULL_AND_PIECEWISE功能已打通：实际decode FULL 97次、短prefill PIECEWISE 1次；去掉诊断参数后的2文本+1图像均正常结束且内容审阅通过。每机当前来源242项单元、16项GPU图回归通过，TP16通信图200次变输入重放通过。捕获上限仍为16 token，超限prefill按原生NONE执行。详见[修复、来源和最终回执](adaptation/020-tp16-pp1-startup.md)。正式eager/graph数值验收、GPQA、性能和镜像交付仍未完成/暂停。

2026-11-02结构调整属于历史前置：prefill统一分发与能力判断、Sparse MLA调优候选迁入YAML，当时每机64项Plugin、7项FGV配置/ABI回归通过；其后的新来源和服务已由上述11-03结果覆盖。

2026-11-02旧a6（结构调整前源码，实例已停止）曾通过2文本+1图像，但实际自动降级为PIECEWISE，三请求约235/289/163秒。该历史结果不代表当前来源，也不能与新样本直接作正式性能比较。

范围：`mx-101`、`mx-102`，各8×C550 64GiB，当前 `glm5.3-flash` 容器。
工作根及容器根均为 `/public-flash/jinghao/glm5.3-flash`；固定profile v7、证据契约v2。

2026-11-01历史状态：Plugin主线 `7094141e` 加必要MetaX兼容修复，TP16/PP1；当时stream、编译接口和通信重建仍在定位，两机16卡被外部DeepSeek占用，服务未就绪。后续资源释放及修复见[TP16/PP1定位记录](adaptation/020-tp16-pp1-startup.md)。下述10-28结果均为历史版本，不代表当前代码通过完整验收。

10-28历史版本达到functional：双机同源v13两机各81项Plugin回归、源码审查、原生执行模式及四并发
sanity gate通过。最终v14共35文件，原33个推理/测试文件不变，补齐README与真实chat示例。
eager冷/热最大logprob差0.025711；显式full-and-piecewise四请求最大差0.032315，均小于
冻结0.05。16rank capture119～124、每请求各新增2次replay、累计8次。
纯FULL修复编译边界后仍受原生MLA/indexer UNIFORM_BATCH能力限制，按序回退证据保留。
FGV38项、clone31项及编译产物四组合/独立进程恢复按精确未变源身份复用，不冒充重跑。

- [环境分析](environment/environment-analysis.md)：真实安装、镜像、映射、网络与评测环境。
- [适配问题索引](adaptation/README.md)：限定变更、失败及回归结果。
- [模型结构与链路](../../../architecture-and-inference.md)：模型级中文架构与本次MetaX复核。

GPQA Diamond198已完整生成，逐题核实174/198＝87.8788%，达到用户后续明确批准的85%门槛；
原88%配置保留。原生报告92.06%错误排除了9个截断空答案，不能作为通过依据。
新的正式离线回执和双机gate尚未封存，已按用户要求暂停，见[当前精度与暂停记录](acceptance/accuracy-current-state-v18.md)。
实际生成配置为4并发、temperature1/top_p0.95/max_gen_toks60000，无重试或重发题目。
性能先测量吞吐/时延，业务目标未冻结，不能声明optimized。
清洁适配镜像已保存并在两机加载，同一ID的两机新容器均通过文件/导入/8卡静态核验；
模型启动与生成验证仍待完成。9个空答案均已核实为length截断，原始198题缓存、日志、报告
及用户85%门槛变更已保存。性能测量和English部署指南待恢复后完成。
脚本、原始日志、源码和缓存留在批准远端根及实际安装组件中，不存入本目录。

- [10-28源码设计审查](adaptation/010-source-review.md)：覆盖Plugin/FG/FGV全部35个任务文件，用户批准以公开基线SHA和冻结补丁/镜像交付，暂不发布。
- [执行模式](acceptance/execution-mode-final-v14.md)与[小集合](acceptance/sanity-final-v14.md)：对应原生gate已通过。
- [双机服务取证](adaptation/015-distributed-service-evidence.md)：101为API、102为headless，不重复计算请求数量。
- [镜像封装](adaptation/017-image-packaging-storage.md)：独立Docker使用两机已授权的`/data/jinghao/glm5.3-flash-image-runtime`，原Docker与适配容器保留。
- [截断空答案离线计分](adaptation/018-gpqa-truncated-empty-content.md)：严格输入绑定、15项恢复回归和真实原生过滤器夹具通过；这些不是模型精度结论。
- [小型恢复材料](../../../../../deliveries/GLM-5.3-Flash-BF16/metax/vllm-plugin-fl/README.md)：八个镜像内冻结文件的哈希一致备份，镜像生成验证状态明确为pending。

10-28历史部署指纹`ed8b2a8a5ee91fcb8279b479db55661be9c5ed5c86cab249a1a49eb4df9728f7`。
当时两机根级及容器路径均为`/public-flash/jinghao/glm5.3-flash/start-model.sh`，SHA
`a9ccaa4159df8790dd8c7c1833913e239d3f55ba347a65976cf6be29ba6b6626`，默认prefix开启、
`--performance`才关闭；该同一脚本已用于sanity和当前GPQA服务。当时API运行目录
`04-runs/glm-api-graph-final-v13-20261028/<host>/`，精度运行
`04-runs/glm-gpqa-final-v14-20261028/`，原生结果另在
`04-runs/accuracy-results/glm53-metax-final-v14/glm-gpqa-final-v14-20261028/`。
