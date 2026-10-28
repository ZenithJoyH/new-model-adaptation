# 双机环境身份复核（v12，2026-10-28）

范围为mx-101、mx-102当前运行的glm5.3-flash容器，批准host/container根均为
`/public-flash/jinghao/glm5.3-flash`。容器完整ID、运行状态、/public-flash同路径映射及
实际安装路径逐机核对；拓扑仍各8×C550 64GiB、TP8/PP2、native multi-node mp、
inbond1 Socket。容器保持运行，RDMA未验证。默认缓存路径和外部只读输入沿用
environment-analysis.md的现场记录。

Plugin `/opt/vllm-plugin-FL@4e23ae8f`、FG `/opt/FlagGems@3eab0949`、
FGV `/opt/FlagGems-vllm@ddce1d66`。33个任务文件与逐机
`01-environment/source-snapshot-v12-<host>.json`一致；原31个SHA逐一保持v11。
本轮只改MetaX standalone编译返回构造类型并新增四组合回归测试，具体边界见013。
Plugin tracked diff SHA为6774165427ec0822ec9fe0718eb53f899ba68833ca9a12ca190e88ee5d14b7c5。
FG/FGV及只读vLLM保持v11身份；vLLM完整继承diff SHA仍为
2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec。
服务解释器仍/opt/conda/bin/python，未通过PYTHONPATH选择第二份组件。

两机CPU/CUDA×binary/unpacked各四例通过（102105.06s、101124.92s），均实际编译、
调用、保存、原生加载并验证两次变输入。随后两机各用独立新进程、新缓存目录恢复全部
四份产物，每份两次变输入数值对照，state/result均passed。原生证据分别为
`04-runs/metax-artifact-cacheable-v12-20261028/<host>/`及
`04-runs/metax-artifact-independent-load-v12-20261028/<host>/`。
101第一次独立启动守卫在父测试尚未退出时阻断，没有创建恢复任务；待四例通过后启动
同名新任务成功。失败保留，不将其隐藏为首次即通过。其他Torch版本/平台实机未验证。

13个模型集成文件manifest仍为v11、归档SHA
07945a99e9fed64f9e8953ec7c7132dbb410f205351655e5071fc048357bab60。
完整33文件部署身份为 `01-environment/deployment-identity-bringup-v12-20261028.json`，
指纹d69d7bf666be5ae7331ec764f296c5c82355e7b8af4ec32ea3e9a3281187e5eb。
环境回执中的v11 eager预检是历史补充，当前源码以v12快照和新增测试绑定为准。

v11模型六请求、idle及四chat参考实际通过，冷/热组内差0，跨组最大0.0067621311≤冻结0.05。
原生日志明确enforce_eager禁用torch.compile和CUDAGraph；新构造仅在standalone编译返回
执行。因此按013的影响审查复用v11 eager作为对照，不声称重跑v12 eager。新FULL必须
实际编译、核实各rank生效档位和capture/replay，再比对变输入数值，尚未通过。

权重120分片、642652070880 bytes及模型/tokenizer/模板小文件身份不变。独立CPU
FlagEval和离线GPQA198已准备，正式参数预算审计输入最长2901 token、生成60000，
温度1/top-p0.95、无意外top_k，65536上下文足够。用户strict-match门槛0.88。
正式精度、性能、适配镜像和交付验证仍pending；性能业务目标未冻结，不作optimized声明。
环境身份通过不等于上述验收通过。未提交、推送或创建PR。
