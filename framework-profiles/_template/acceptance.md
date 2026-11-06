# 框架验收模板

按该框架实际能力定义最小推理、执行模式、正式精度、性能及证据要求，与 `profile.yml`
中的有序验收步骤一致。未实现的能力明确标记不可用；experimental 不签发完整正式验收。

服务型 profile 定义按容量冻结并发的小批量检查及最小服务启动入口；纯 Python API profile
定义相应输入、调用和参考结果，不套用 vLLM 服务、graph 或 `start-model.sh` 要求。
先声明前缀缓存是否适用；适用时必须给出可验证的性能测试关闭机制，不适用时记录依据并
在 profile 中标为 `not_applicable`，不要求不存在的服务参数。完整服务规则引用
[通用工作流](../../docs/model-adaptation-workflow.md)，本文件只补充该框架的具体要求。
