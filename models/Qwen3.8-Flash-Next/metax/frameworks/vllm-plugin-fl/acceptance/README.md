# mx-101 验收记录

范围：qwen3.8-flash，BF16文本TP8；远端根 `/public-flash/jinghao/qwen3.8-flash`。

- [冻结计划](acceptance-plan.md)：GPQA full198 strict-match≥88%；按2026-10-25用户更新，仅测量报告graph九场景。
- [100K执行模式](execution-mode-100k.md)：原生验收通过；10例105token相同，最大生成token logprob差0.0029179352≤0.02；实际18尺寸捕获及166次图执行。
- [100K并发小集](sanity-100k.md)：原生验收通过，8题均与eager参考一致。
- [正式精度](accuracy-gpqa-100k.md)：`gpqa-full198-c2-100k-20261024`原生绑定及journal验证通过；183/198（92.42%），1题预算截断保留计错。原始汇总183/197另行保留，未作为全198指标。
- [graph性能](performance-graph-100k.md)：cache-off九场景27轮，756请求成功、0失败；已取消的eager部分结果保留，不设置或推断业务性能目标。
- [2026-10-25适配交付记录](adaptation-summary.md)：保留原脚本/实例的全量结果及交付回执。
- [当前默认本地数据库启动脚本](launcher-default-db-20261027.md)：DB覆盖删除，实际normal启动、两组24请求、105token数值回归和暖延迟对照通过，当前交付仅2项环境导出。
- [此前四项缓存删除记录](launcher-default-cache-20261027.md)：四项路径导出全部删除，normal冷缓存启动及105token回归通过；性能分支完成参数预检，内部交付同步，镜像验证pending。
- [第一次精简记录](launcher-minimal-20261027.md)：保留此前删除6项环境变量和冗余命令的历史及备份。

当前为functional，本次用户选择范围已完成；无业务性能目标，不声明完整v2性能门禁通过或optimized。原生产物留在远端，本地仅保存摘要与引用。

[性能测量方法与工具](performance-method.md)：冻结完整九场景请求；慢速Req/s舍入边界40项回归通过，原精度控制快照不变。完整报告原生校验覆盖9场景、27轮和63份产物。
