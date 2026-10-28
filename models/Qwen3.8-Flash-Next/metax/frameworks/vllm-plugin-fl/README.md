# Qwen3.8-Flash-Next / MetaX / vllm-plugin-fl

范围为mx-101既有qwen3.8-flash容器，BF16文本TP8；远端根
`/public-flash/jinghao/qwen3.8-flash`，权重只读`/public-flash/models/Qwen3.8-Flash-Next`。
当前functional；本次选择的适配、数值对照、正式GPQA精度、graph性能测量和最终启动交付已完成。

Plugin PR455、用户PLE PR959及冻结FlagTree main源码安装已完成。PLE fusion同步、
MetaX QSA tile/分派、异构Mamba状态缓冲、RoPE partial-view图编译和MetaX编译产物
兼容性均已定向验证。完整修改范围、回归结果及贡献审查见[适配索引](adaptation/README.md)。
vLLM保持只读，FlagGems没有本任务源码变更；未提交、推送或创建PR。

本轮正式运行配置为上下文100000、prefill6400、max_num_seqs32、prefix caching开启/
align、qwen3 reasoning parser，显式FULL_AND_PIECEWISE。相同源码100K eager/graph
10例105token完全一致，最大生成token logprob差0.0029179352≤0.02；实际11个mixed及7个
decode尺寸捕获，冻结日志记录FULL161/PIECEWISE5次执行。并发小集8题均匹配eager参考。
纯FULL受GDN UNIFORM_BATCH静态能力限制，大prefill走编译NONE路径；逐级尝试与限制见
[执行模式验收](acceptance/execution-mode-100k.md)。50K较早运行保留为历史，不作为当前服务身份。

2026-10-25两种模式使用clone,randn,normal_追加排除、现有FGV接入和内存SQL；
2026-10-27当前普通服务已改用库默认本地SQLite，定向精度和延迟对照通过。随机入口为有退出条件
的运行配置workaround，未声称底层随机缺陷已修复；不会用另一个源码副本或PYTHONPATH替换安装。

- [环境身份](environment/README.md)：环境正文在gate前冻结，最终结果与原生引用以framework.yml为准。
- [阶段3复核](adaptation/010-stage-verification.md)：当前安装HEAD、完整diff、新增集合及文件内容再次一致。
- [验收计划与结果](acceptance/README.md)：GPQA full198 strict-match≥88%；性能九场景仅测量，不判断业务达标。
- [正式精度](acceptance/accuracy-gpqa-100k.md)：183/198（92.42%），包括1题预算截断计错；原生绑定和journal已验证。
- [graph性能结果](acceptance/performance-graph-100k.md)：9场景27轮、756请求全部成功；最后长输入高并发工况保留12次抢占重算。
- [2026-10-25适配与交付记录](acceptance/adaptation-summary.md)：保留当时全量评测、启动实例和交付证据。
- [当前默认本地数据库启动脚本](acceptance/launcher-default-db-20261027.md)：进一步删除DB覆盖，仅剩2项导出；两组24请求、105token回归及延迟对照通过。
- [默认数据库环境](environment/database-defaults-verified-20261027.md)：实际FlagGems/FlagGems-vllm数据库路径、worker文件描述符与独立读取。
- [四项缓存删除历史](acceptance/launcher-default-cache-20261027.md)：保留上一版3项导出时的启动与回归证据。
- [默认目录实测](environment/cache-defaults-verified-20261027.md)：UID0真实写入/冷缓存启动通过，没有用外层变量、软链接或目录迁移替代。
- [第一次精简记录](acceptance/launcher-minimal-20261027.md)：保留此前6项变量删除及曾保留缓存覆盖的判断，已由当前实测结论接续。
- [结构化状态](framework.yml)：部署指纹7d11fb14；性能仅测量报告，不判定业务达标或optimized。

GPQA运行ID为gpqa-full198-c2-100k-20261024，xhigh thinking、单题96000生成上限、并发2，
API/eval重试均0。198题及396条双过滤器记录完整保留，原生汇总排除超时的183/197未作为本次指标。
性能在正式精度通过后完成cache-off的
graph九场景测量，每场景一次warmup及两次无profiler测量，现已恢复普通prefix-enabled服务。
2026-10-25用户取消eager端到端性能测试；已停止本任务eager客户端、旧控制器及服务，
部分性能产物保留，不再安排eager性能或计算完整eager/graph性能比。既有数值一致性验证保留。
最终脚本为远端根start-model.sh，容器内部副本为/opt/qwen3.8-flash-delivery/start-model.sh；
2026-10-27移除缓存和数据库覆盖后，两份SHA256均为c207cc11bfba76819ec04510cd34c8647ecc5fec92492dd48e8ba1eff6e3eda3。
normal服务PID4113542、8000端口、100K上下文，保持运行；10例105token与eager参考完全一致，
最大生成token logprob差0.004307605326≤0.02。默认本地DB的24请求及延迟对照通过。正常调用开启prefix，唯一--performance分支仅关闭prefix。
本轮性能分支只做shell/配置预检；全198题GPQA及九场景性能没有重跑，仍绑定2026-10-25旧脚本/实例。
镜像打包及新容器验证未请求，image_validation=pending。

仅覆盖本机BF16文本TP8；其他硬件、多模态、量化及MTP未验证。
本次用户选择范围已完成；未冻结业务性能目标，不声明完整v2性能门禁通过或optimized。
