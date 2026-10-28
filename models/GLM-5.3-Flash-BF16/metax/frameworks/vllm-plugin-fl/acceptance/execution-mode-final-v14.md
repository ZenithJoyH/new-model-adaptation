# 执行模式测量（2026-10-28）

mx-101/mx-102，16×MetaX C550 64GiB，BF16文本、TP8/PP2、65536上下文、2048批token、
8序列、align及prefix caching开启。原33个推理/测试文件与source-snapshot-v13完全同源；
最终v14仅补齐README与真实chat示例。部署身份ed8b2a8a5ee91fcb8279b479db55661be9c5ed5c86cab249a1a49eb4df9728f7。

eager实测来自glm-eager-bringup-v13-20261028及其六请求、四chat参考、prefix-idle四请求。
冷/热四项最大logprob差0.02571076155；冻结容差始终0.05。不是旧v11的零差异结论。

FULL先修复真实编译阻塞再复验；全16rank因MLA/indexer的UNIFORM_BATCH能力自动变为
FULL_AND_PIECEWISE，驱动拒绝档位不符，rc1，未发送数值请求。逐级阻塞、配置、整改、
限制与退出条件在01-environment/full-fallback-proof-v13-20261028.json，不将自动回退算作FULL通过。

显式下一档glm-full-and-piecewise-diagnostic-v13-20261028：四请求输出4/Paris/yellow/yellow
均等于eager；logprob最大差分别0.005013006739、0.01419890672、0.01911354810、
0.03231409937，均低于0.05。16rank有效模式一致，capture119～124，每请求各新增2次
真实replay，累计8次。worker hook成功恢复，结果SHA
d40da4bfbe99cf9954fe33fbde325b771b7059ce17a117657418268a15fd5911。
各原始request/inference与worker-initial/after0～3均留在该原生运行目录。

该诊断原始结果明确标注非正式验收；本轮在核对源、权重、拓扑、基础参数和逐级回退后，
创建新的execution_measurements及逐Host framework_check，由原生v2 gate独立校验。
最终API使用同一根级start-model.sh，SHA a9ccaa4159df8790dd8c7c1833913e239d3f55ba347a65976cf6be29ba6b6626，
默认prefix开启且不含诊断反序列化设置。API真实chat示例已匹配独立eager参考。
四组诊断耗时包含冷编译和通信初始化，不作为正式性能结果。

原生退出的semaphore/shared-memory资源跟踪警告保留，102精确任务PID已清理，容器始终
运行。该运行后新的API服务保持运行；正式sanity、GPQA198/88%、性能和镜像验证另行记录。
本记录不证明视觉/视频、MTP、RDMA或其他硬件通过。
