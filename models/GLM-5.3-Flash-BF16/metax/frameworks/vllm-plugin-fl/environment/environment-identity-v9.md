# 双机环境身份复核（v9，2026-10-28）

范围为mx-101、mx-102的 `glm5.3-flash` 容器，host/container工作根均为
`/public-flash/jinghao/glm5.3-flash`，已逐机核实同路径映射。两机各8×C550 64GiB，
TP8/PP2、native multi-node mp、inbond1 Socket通信；RDMA未验证。
安装路径、依赖与运行缓存默认路径沿用environment-analysis.md的已核实记录。

Plugin `/opt/vllm-plugin-FL@4e23ae8f`、FlagGems `/opt/FlagGems@3eab0949`、
FlagGems-vllm `/opt/FlagGems-vllm@ddce1d66` 均是实际安装组件，没有PYTHONPATH覆盖。
两机全部31个任务文件与 `01-environment/source-snapshot-v9-<host>.json` 一致。
GLM接入13文件manifest为 `01-environment/glm-model-integration-source-manifest-v9.json`，
归档SHA `1ef0e9b26ae57b8ca99b3721e74964c345d05b6f5b19045c08a5e5036486fb27`。

v9为FGV两个Top-K公共入口和MetaX wrapper增加可选canonical_output，默认False，
复用既有标准Triton确定分支，没有新增数学kernel。仅GLM模型两处调用显式True，
Plugin provider只透传。两机各57项Plugin回归、38项新增算子数值/边界/变输入graph通过。
原测试前缀和断言保留，默认TLE重复性测试的修改前失败也保留，不宣称它通过。
v8状态块384修复和既有算子修改保留。设计与真实负对照见adaptation/011，
既有完整设计审查见adaptation/010；其他平台实机及整模新路径尚待验证。

vLLM `/opt/vllm@ee0da84a` 保持只读，继承87个mode-only差异的完整SHA仍为
`2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`。
未提交、推送或创建PR。只读权重 `/public-flash/models/GLM-5.3-Flash-BF16`，
120分片、642652070880物理bytes；模型/tokenizer/模板身份未变。

FlagEval独立CPU容器和离线GPQA198题已准备。最长chat输入2901 token，60K生成预算
可放入65536，见 `01-environment/gpqa-token-budget-v2-20261028.json`。
离线参数审计 `01-environment/gpqa-generation-kwargs-v3-20261028.json` 核对实际CLI合并，
温度1、top-p0.95、max_completion_tokens60000，未继承top_k；没有发送请求。
用户strict-match最低0.88，正式精度未执行，性能业务目标未冻结。

本轮预检 `01-environment/preflight-eager-v9-<host>.json` 核验容器映射、安装路径及源码。
原始身份 `01-environment/deployment-identity-bringup-v9-20261028.json` 指纹
`0f484d886af8c63b0941861a491f5ae5fa0ddefe38a391f2b757809742012a40`。
配置仍为eager诊断、65536/seq8/2048、BF16、align、glm45、prefix开启。
v8六请求功能通过但数值控制失败，不能代替v9整模结果。

环境身份通过不表示整模数值、graph、GPQA、性能或镜像通过。最终执行模式确定后须重绑。
容器保持运行，基础镜像尚未包含全部适配修改，适配镜像验证仍pending。
