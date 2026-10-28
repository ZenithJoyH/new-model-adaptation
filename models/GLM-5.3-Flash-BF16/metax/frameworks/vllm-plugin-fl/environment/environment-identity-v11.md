# 双机环境身份复核（v11，2026-10-28）

范围为mx-101、mx-102当前运行的glm5.3-flash容器，host/container根均为
`/public-flash/jinghao/glm5.3-flash`。容器ID、运行状态及/public-flash同路径映射已逐机复核。
各8×C550 64GiB，TP8/PP2、native multi-node mp、inbond1 Socket；RDMA未验证。
依赖、默认运行缓存路径和只读外部输入沿用environment-analysis.md的已核实记录。

实际安装Plugin `/opt/vllm-plugin-FL@4e23ae8f`、FlagGems `/opt/FlagGems@3eab0949`、
FGV `/opt/FlagGems-vllm@ddce1d66`，不经PYTHONPATH覆盖。31个任务文件在两机与
`01-environment/source-snapshot-v11-<host>.json` 一致。v11仅模型和原PP测试文件变化，
其余29文件、全部HEAD和tracked diff与v10相同。
vLLM `/opt/vllm@ee0da84a` 保持只读，继承87个mode-only差异的完整diff SHA仍为
`2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`。

v10的三处mHC opaque边界保留，v11仅再封装GLM自身SwiGLU。真实数学均经原CachedOp/FGV，
fake只产生正确元数据，未禁编译或修改logger/公共activation。两机各71项通过
（102 58.30s、101 53.12s）：原67项及实际本地宽256/1536、BF16/FP32、空/1/3 token、
CPU数值参考、严格Inductor fullgraph、schema/fake和两次变输入replay的四项新回归。
原测试完整前缀和断言保留。未变FGV按精确源身份复用v9的两机38项确定Top-K证据，
不声称本轮重跑；其他平台实机未验证。设计与负对照见adaptation/010、012。

GLM13文件manifest为 `01-environment/glm-model-integration-source-manifest-v11.json`，
归档SHA `07945a99e9fed64f9e8953ec7c7132dbb410f205351655e5071fc048357bab60`。
原始部署身份 `01-environment/deployment-identity-bringup-v11-20261028.json` 指纹
`43f5433576c3da0ebdc340da01679235b9555a68f980b3a3a3d7ca9d50045a8e`。
预检 `01-environment/preflight-eager-v11-<host>.json`，配置仍为eager诊断、65536/seq8/2048、
BF16、align、glm45、prefix开启。

v10六请求、idle控制及四chat参考已通过：各组冷/热差0，跨组差0.0148829371≤0.05。
首次FULL因mHC编译边界失败；邻接SwiGLU隔离探针也真实失败，均保留原始诊断。
v11整模及FULL须同源复验，不能以局部71项或旧版整模代替。

权重 `/public-flash/models/GLM-5.3-Flash-BF16` 120分片、642652070880 bytes只读，
模型/tokenizer/模板小文件SHA未变。FlagEval独立CPU容器和离线GPQA198已准备，
最长输入2901 token，60K生成预算在65536以内；实际参数审计为温度1、top-p0.95、
max_completion_tokens60000，没有意外top_k。用户strict-match最低0.88，正式精度未执行。
性能业务目标未冻结，不作optimized声明。

环境身份通过不表示整模、graph、精度或性能通过。容器保持运行，基础镜像未包含全部修改；
最终执行模式绑定、适配镜像验证及正式验收仍pending。未提交、推送或创建PR。
