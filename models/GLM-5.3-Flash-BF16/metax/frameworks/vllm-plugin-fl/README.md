# GLM-5.3-Flash-BF16 / MetaX / vllm-plugin-fl

范围：`mx-101`、`mx-102`，各8×C550 64GiB，当前 `glm5.3-flash` 容器。
工作根及容器根均为 `/public-flash/jinghao/glm5.3-flash`；固定profile v7、证据契约v2。

已达到functional：双机同源v13两机各81项Plugin回归、源码审查、原生执行模式及四并发
sanity gate通过。最终v14共35文件，原33个推理/测试文件不变，补齐README与真实chat示例。
eager冷/热最大logprob差0.025711；显式full-and-piecewise四请求最大差0.032315，均小于
冻结0.05。16rank capture119～124、每请求各新增2次replay、累计8次。
纯FULL修复编译边界后仍受原生MLA/indexer UNIFORM_BATCH能力限制，按序回退证据保留。
FGV38项、clone31项及编译产物四组合/独立进程恢复按精确未变源身份复用，不冒充重跑。

- [环境分析](environment/environment-analysis.md)：真实安装、镜像、映射、网络与评测环境。
- [适配问题索引](adaptation/README.md)：限定变更、失败及回归结果。
- [模型结构与链路](../../../architecture-and-inference.md)：模型级中文架构与本次MetaX复核。

用户确认GPQA Diamond198题、strict-match≥0.88；性能先测量吞吐/时延，业务目标未冻结，
不能声明optimized。正式GPQA已于2026-10-28启动：4并发、完整198题、temperature1/top_p0.95/
max_gen_toks60000，超时计错误且无重试。原生预检通过；中间计分助手schema初始化失败，
主评测正常运行，不据此给出中间通过结论。最终以全量原生回执为准。
性能测量、适配镜像验证和English部署指南待完成。
脚本、原始日志、源码和缓存留在批准远端根及实际安装组件中，不存入本目录。

- [当前源码设计审查](adaptation/010-source-review.md)：覆盖Plugin/FG/FGV全部35个任务文件，用户批准以公开基线SHA和冻结补丁/镜像交付，暂不发布。
- [执行模式](acceptance/execution-mode-final-v14.md)与[小集合](acceptance/sanity-final-v14.md)：对应原生gate已通过。
- [双机服务取证](adaptation/015-distributed-service-evidence.md)：101为API、102为headless，不重复计算请求数量。

最终部署指纹`ed8b2a8a5ee91fcb8279b479db55661be9c5ed5c86cab249a1a49eb4df9728f7`。
两机根级及容器路径均为`/public-flash/jinghao/glm5.3-flash/start-model.sh`，SHA
`a9ccaa4159df8790dd8c7c1833913e239d3f55ba347a65976cf6be29ba6b6626`，默认prefix开启、
`--performance`才关闭；该同一脚本已用于sanity和当前GPQA服务。当前API运行目录
`04-runs/glm-api-graph-final-v13-20261028/<host>/`，精度运行
`04-runs/glm-gpqa-final-v14-20261028/`，原生结果另在
`04-runs/accuracy-results/glm53-metax-final-v14/glm-gpqa-final-v14-20261028/`。
