# 双机环境身份复核（2026-10-28）

范围仅为mx-101、mx-102的运行中 `glm5.3-flash` 容器，批准host/container根均为
`/public-flash/jinghao/glm5.3-flash`，已核实同路径NFS映射。两机各8张C550 64GiB，
使用TP8/PP2、native multi-node mp；通信接口inbond1，16 rank数值与图通信已通过，
当前为Socket路径，RDMA未验证。初始环境细节及失败保留见environment-analysis.md。

## 当前安装与源码

- Plugin `/opt/vllm-plugin-FL@4e23ae8f`，FG `/opt/FlagGems@3eab0949`，
  FGV `/opt/FlagGems-vllm@ddce1d66`，均为实际安装/导入目录，无PYTHONPATH覆盖。
- 25个任务文件两机逐一核对，见 `01-environment/source-snapshot-v4-<host>.json`。
  Plugin的13文件manifest为 `01-environment/glm-model-integration-source-manifest-v4.json`，
  对应归档SHA `6293f514d86b173e3580697ba3999de1f2b32ddd962d25d7241704c6a81e2822`。
- 现有FlagGems注册文件仅clone项修正；FGV仅conv、mHC norm、FP8 MQA和sparse MLA四处
  已记录修复。Plugin新增模型/cache/bootstrap及provider、MetaX gate底数修复；具体边界见
  adaptation/001、003、005～009和source-review.md。没有提交、推送或创建PR。
- vLLM `/opt/vllm@ee0da84a` 保持只读；87个继承mode-only diff的完整哈希仍为
  `2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`。
- 两机clone回归各31项、scheduler bootstrap及模型组合各32项通过。其后仅两个新测试文件
  发生格式变化，16个任务新文件均做Black/AST等价核对；原有上游文件没有整文件格式化。

## 权重、状态及评测准备

只读权重仍为 `/public-flash/models/GLM-5.3-Flash-BF16`，120分片、642652070880物理bytes，
config/index/tokenizer/template/generation小文件SHA已纳入原始部署身份。
`glm-runtime-state-dtype-20261028/mx-102` 实测模型classmethod在MetaX kernel导入前后均为
conv BF16 `[3,3072]`、recurrent FP32 `[8,128,128]`，未padding共542720 bytes。
此项核对配置契约，不以它代替运行服务cache取证。

FlagEval独立CPU容器及同路径根、4GiB tmpfs response cache已核实。离线GPQA Diamond
全198题可读；原task模板、filters及utils已核对。实际chat模板渲染后最长输入2901 tokens，
计划60K生成预算可放入65536上下文，证据为 `01-environment/gpqa-token-budget-v2-20261028.json`。
初版计数误把BatchEncoding的两个键当token数，已明确保留为无效记录，不能用于容量依据。
用户指定strict-match最低0.88；尚未发送正式评测请求，性能目标未冻结。

## 本次绑定范围

第四轮启动前重验容器ID/映射、安装路径、源码manifest、FGV四文件和vLLM继承diff，
见 `01-environment/preflight-eager-v4-<host>.json`。原始部署身份为
`01-environment/deployment-identity-bringup-v4-20261028.json`，指纹
`a0ce7e5c94297491fb498428c3caaa19f3a067e3e6e39ec9b4ba722433ac8be6`。
它绑定eager、65536、seq8、2048批token、BF16、align、glm45、prefix开启的当前bring-up配置。
两个适配容器保持运行；前三次整模失败与准确进程停止记录完整保留。

环境身份通过不表示整模数值、graph、正式GPQA、性能或适配镜像通过。最终graph/基础配置
确定后须重新核验部署绑定；基线镜像尚未包含全部适配修改，镜像验证仍pending。
