# 双机PP服务的验收身份

2026-10-28，当前101的API PID1594537监听18530；102的PID1822374使用`--headless`，
没有本地API。原`scripts/evidence_contract.py:service_binding`要求每台目标Host都拥有
本地API，无法表达该原生multi-node mp拓扑。不能把101的API回执重命名为102，也不能为
迎合检查器增加无意义的代理或重复模型服务。

拟限定修改管理工具的上述验证函数、对应`test_collaboration_contract.py`和v2契约说明，
支持显式`distributed`绑定：保留101原有本地API现场challenge/PID/socket检查；另对全部
参与Host引用同轮进程取证，包含根PID/容器/boot/start/cmd哈希、实际CLI拓扑、后代关系和
进程拥有的跨机ESTABLISHED TCP连接，并要求两端连接四元组互逆、所有target Host精确覆盖。
102仍作为headless参与节点记录。取证脚本是本任务一次性工件，放批准根02-issues，
不新增管理工具入口、不修改profile快照、不改变模型推理或精度阈值。

本地回归须保留单机行为，覆盖缺少参与Host、重复/外部Host、旧run/部署/nonce、PID身份
变化、非headless、拓扑不一致、无互逆连接和证据篡改的拒绝；现场需在双机当前进程实际
取证后通过相同验证器。冻结新的原生工具bundle，不改写既有bundle或历史回执。
