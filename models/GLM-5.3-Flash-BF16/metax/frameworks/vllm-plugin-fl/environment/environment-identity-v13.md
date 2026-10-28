# 双机环境身份复核（v13，2026-10-28）

范围为mx-101/mx-102的运行中glm5.3-flash容器，批准host/container根均为
`/public-flash/jinghao/glm5.3-flash`。完整容器ID、运行状态、/public-flash同路径映射及
实际安装源逐机核实；各8×C550 64GiB，TP8/PP2、native multi-node mp、inbond1 Socket。
容器保持运行，RDMA未验证。基础依赖、默认服务缓存和外部只读输入沿用environment-analysis.md。

Plugin `/opt/vllm-plugin-FL@4e23ae8f`、FG `/opt/FlagGems@3eab0949`、
FGV `/opt/FlagGems-vllm@ddce1d66`，解释器/opt/conda/bin/python，无PYTHONPATH覆盖。
33个任务文件由 `01-environment/source-snapshot-v13-<host>.json` 逐机绑定。本轮仅模型和
PP测试变化，另外31文件逐一保持v12 SHA；vLLM只读HEAD ee0da84a与完整继承diff SHA
2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec不变。
Plugin tracked diff SHA仍为6774165427ec0822ec9fe0718eb53f899ba68833ca9a12ca190e88ee5d14b7c5，
完整源快照包含尚未tracked的模型文件，不能仅靠tracked diff判断新代码身份。

v12 FULL在capture前真实失败于indexer Hadamard的Dynamo SymNode hasattr检查；随后独立
Hadamard/FP8 query负对照均eager通过、严格动态编译失败，后者停在真实MetaX logger.debug。
仅在GLM模型中按原注册机制补齐这两处opaque边界，真实数学和参数继续经原CachedOp，
fake只分配相同shape/dtype/stride元数据。FG/FGV、Torch/vLLM/SDK均没有本轮新增修改。
两机 `indexer-compile-fixed-v13b-20261028/<host>` 全81项通过：102164.48s、101337.00s。
原71项字节前缀与断言保留；新增十项覆盖CPU Hadamard、FP8 scale/误差界/原字节对照、
32头×128维、BF16/FP32、动态compile、schema/fake及两次变输入graph replay。
首次新测试错误地把底层ValueError当作CachedOp接口，失败保留；仅改新测试的无效shape
校验到fake边界，不改变产品错误行为。下发脚本解析失败也保留，见014。其他平台未实测。

模型SHA f3bdadcff159ecc66ccb51cf5f7eefcbb752881987dffb1e170cba12c83ba48b，
PP测试SHA 643c1ce020ed9226d197b48f7c139d80abc037dd249347bdb0c3bb4dc7664ea0。
13个模型集成文件manifest为 `01-environment/glm-model-integration-source-manifest-v13.json`，
归档SHA 0a9e617d2a82cb4858dde7433fb8ed72104930c46c2551ac2483bbbd866ce9e7。
完整33文件部署身份为 `01-environment/deployment-identity-bringup-v13-20261028.json`，
指纹017445896d06d51f61dc7a1e772ef98a004ba84667e7ee91213dafa719291bd5。

MetaX standalone产物兼容文件与四组合测试保持v12精确SHA，复用两机各四例及独立新进程
恢复证据，不声称本轮重跑。FGV源也保持v9确定Top-K与其他局部算子回归身份；未声明
其他硬件验证。v11 eager六请求、idle及四chat参考保留为历史；本轮模型调用边界变化，
须新跑v13 eager/FULL，不用历史结果代替。回执中v11 eager预检仅为历史补充，当前源码
以v13快照、当前81项与上述影响审查为准。

权重120分片、642652070880 bytes及模型/tokenizer/模板元数据SHA不变。GPQA198离线
数据与CPU FlagEval已准备，最长输入2901 token，计划温度1/top-p0.95/max_gen_toks60000，
65536上下文可容纳，未意外携带top_k。用户strict-match最低0.88；最终服务绑定、正式精度、
性能和适配镜像验证仍pending。性能业务目标未冻结，不宣称optimized。
环境身份通过不等于整模型或正式验收通过。未提交、推送或创建PR。
