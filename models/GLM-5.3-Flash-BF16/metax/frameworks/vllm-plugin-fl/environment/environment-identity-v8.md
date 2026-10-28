# 双机环境身份复核（v8，2026-10-28）

范围为mx-101、mx-102当前运行的 `glm5.3-flash` 容器，host/container工作根均为
`/public-flash/jinghao/glm5.3-flash`，已逐机核实同路径映射。两机各8×C550 64GiB，
TP8/PP2、native multi-node mp、inbond1 Socket通信；RDMA未验证。
初始依赖、运行缓存默认路径和映射细节沿用environment-analysis.md的已核实记录。

Plugin实际安装 `/opt/vllm-plugin-FL@4e23ae8f`，FlagGems `/opt/FlagGems@3eab0949`，
FlagGems-vllm `/opt/FlagGems-vllm@ddce1d66`；实际导入路径不经PYTHONPATH覆盖。
两机全部25个任务文件已与 `01-environment/source-snapshot-v8-<host>.json` 核对。
GLM的13文件manifest为 `01-environment/glm-model-integration-source-manifest-v8.json`，
归档SHA `f54e78bda153f682e17ab812bf94e8b538c2921c23f6847c076012b179a63acd`。

v8仅改变GLM专用resolver和其既有新测试：合法GLM KPool分组解析后，将原生align调度器
实际读取的cache_config.block_size同步为LCM384；tail Spec仍4、hash GCD仍4。
负对照真实Scheduler错误分块2048+1484，修复后1920+1536+76。两机完整55项组合通过
（102 38.62s、101 38.96s）。全量源快照证明FG/FGV及另外23个任务文件保持v7身份。
具体设计、失败、数值与守卫范围见adaptation/001及source-review.md。

vLLM `/opt/vllm@ee0da84a` 保持只读，继承87个mode-only差异的完整SHA仍为
`2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`。
未提交、推送或创建PR。一次性RPC追踪两次工具配置失败及其精确PID清理记录保留，
不把这些失败解释为整模通过；序列化诊断选项未进入正常API或启动脚本。

只读权重 `/public-flash/models/GLM-5.3-Flash-BF16`，120分片、642652070880物理bytes。
模型、tokenizer与模板小文件SHA继续绑定原始身份。KDA配置实测conv BF16 `[3,3072]`、
recurrent FP32 `[8,128,128]`，未padding共542720 bytes；状态未改dtype。
FlagEval独立CPU容器、离线GPQA198题和response tmpfs已准备。实际最长chat输入2901
token，60K生成预算可放入65536，证据 `01-environment/gpqa-token-budget-v2-20261028.json`。
用户最低strict-match为0.88；正式精度未执行，性能业务目标未冻结。

本轮预检 `01-environment/preflight-eager-v8-<host>.json` 核验容器ID/映射、安装路径和源码；
原始身份 `01-environment/deployment-identity-bringup-v8-20261028.json` 指纹为
`0c54175d2aef17923cd142cb64a3db5effa4a30d92c585f5ead5ffb305aaa596`。
配置仍为eager诊断、65536/seq8/2048、BF16、align、glm45、prefix开启。
第八轮整模冷/热数值正在重验；v7六请求功能证据不能代替v8结果。

环境身份通过不表示整模数值、graph、GPQA、性能或镜像通过。最终模式确定后须重绑身份。
容器保持运行，基础镜像尚未包含全部适配修改，适配镜像验证仍pending。
