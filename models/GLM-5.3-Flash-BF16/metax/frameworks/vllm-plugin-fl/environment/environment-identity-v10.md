# 双机环境身份复核（v10，2026-10-28）

范围为mx-101、mx-102的glm5.3-flash容器；工作根和容器根均为
`/public-flash/jinghao/glm5.3-flash`。两机运行状态、容器ID和/public-flash同路径映射已复核。
各8×C550 64GiB，TP8/PP2、native multi-node mp、inbond1 Socket；RDMA未验证。
安装、依赖、外部只读权重和运行缓存默认路径沿用environment-analysis.md的核实记录。

Plugin实际 `/opt/vllm-plugin-FL@4e23ae8f`、FlagGems `/opt/FlagGems@3eab0949`、
FGV `/opt/FlagGems-vllm@ddce1d66`，不经PYTHONPATH。31个任务文件逐机与
`01-environment/source-snapshot-v10-<host>.json` 一致，其他组件/文件与v9的SHA完全相同。
vLLM `/opt/vllm@ee0da84a` 只读，继承87个mode-only差异的diff SHA仍为
`2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`。
未提交、推送或创建PR。

v10仅修改GLM模型三处mHC的opaque custom-op边界和原PP测试文件。真实计算仍经CachedOp
调用原FGV，fake仅正确元数据，无数学/精度或输入修改协议变化。两机各67项通过
（102 45.88s、101 84.89s），其中10项为128/4096宽度、动态1/3 token、可选norm、
schema/fake、严格fullgraph编译及两次变输入replay。原PP测试字节前缀与断言保留。
FG/FGV源码未变，v9两机38项确定Top-K回归按精确源身份复用，未声称本轮重跑。
设计审查和负对照见adaptation/010、012。

GLM13文件manifest `01-environment/glm-model-integration-source-manifest-v10.json`，
归档SHA `792724554f54e09dbd332da19364b2b7cf0f3e0c570110f64fc0199720c051ee`。
原始部署身份 `01-environment/deployment-identity-bringup-v10-20261028.json` 指纹
`9d86a814c38fc6ea4b6d5b3904e3c1c3b09ea787b4ae27652a6ddeca8d1b6d7b`；预检 `01-environment/preflight-eager-v10-<host>.json`。
配置仍为eager诊断、65536/seq8/2048、BF16、align、glm45、prefix开启。

v9整模六请求功能和idle控制通过：各组cold/hot差0，跨组差0.0393586233≤0.05；
四个chat参考4/5/56/Paris已冻结。首次FULL在capture/请求前因mHC编译边界失败，
不作FULL通过或下降档位声明；v10整模及FULL须重新验证，旧证据保留。

权重 `/public-flash/models/GLM-5.3-Flash-BF16` 120分片、642652070880 bytes只读，
小文件SHA未变。FlagEval CPU容器、GPQA198及原60K生成/65536上下文预算保留；
实际参数审计为温度1、top-p0.95、max_completion_tokens60000，无意外top_k。
用户strict-match最低0.88，正式精度尚未执行；性能业务目标未冻结。

环境身份通过不表示整模、graph、GPQA或性能通过。容器保持运行，基础镜像未包含全部修改，
适配镜像验证及最终执行模式身份绑定仍pending。
