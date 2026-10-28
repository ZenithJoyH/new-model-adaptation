# 2026-10-25 mx-101 适配与交付记录

用户本次选择的工作已完成：指定PR与源码FlagTree部署、RoPE图编译修复、整模数值对照、
完整GPQA精度、仅graph的九场景端到端性能测量，以及最终脚本实际启动验证。
范围为mx-101 / qwen3.8-flash / 8×MetaX C550 / BF16文本TP8。
性能只测量报告，不判定业务目标；framework保持functional，不声明optimized或完整v2性能门禁通过。

## 代码与精度

Plugin PR455应用head65759c432cef847c311ccd0ab9dc077ab91454ed；用户PLE PR959应用
head22194f0b2ee0cebb51f945a20a157b82c4e19c65。实际修改的是容器安装组件
/opt/vllm-plugin-FL和/opt/FlagGems-vllm，含必要的PLE同步、QSA、Mamba状态和RoPE适配。
FlagTree按源码安装，冻结main2f1229e51c03b345a1c72207854828eed7282de9；
源码来源、编译二进制及元数据区别见[环境记录](../environment/README.md)。
vLLM保持只读；FlagGems无本任务源码变更，继承的文件模式差异保留。
未提交、推送或创建PR；完整修改范围、每组件diff审查及回归见[适配索引](../adaptation/README.md)。

RoPE在FGV编译分支使用编译器私有的非原地算子加显式copy_保持原接口，修复partial-view
图编译及后续越界问题；未修改vLLM或通过PYTHONPATH选择其他源码副本。
graph采用显式FULL_AND_PIECEWISE，mixed-prefill和decode捕获均已验证。
纯FULL受GDN UNIFORM_BATCH静态能力限制；较高优先级诊断发生于50K运行，100K纯FULL未另测。
大prefill可以走编译后的NONE路径，不能称所有请求都完全由整图执行。

GPQA Diamond完整198题：183正确/198=92.4242%，达到strict-match≥88%（至少175正确）。
15题错误中包含1题96000生成上限截断，按错计入分母，无HTTP/服务执行错误。
原FlagEval汇总因排除TIMEOUT显示183/197，未拿该数作为全量成绩；
使用未改动的198份官方strict位重新核对总数，原生绑定及journal验证通过。
配置、396行双过滤器样本、失败尝试及精确哈希见[正式精度记录](accuracy-gpqa-100k.md)。

## 性能与最终服务

按用户2026-10-25更新，仅测graph。九场景各1次预热、2次无profiler正式测量，
756请求全部成功，0失败，548352输出token；63份原生产物完整校验通过。
正式轮输出吞吐范围12.50–186.35 tok/s。8192/1024并发上限32工况为52.26 tok/s，
平均TTFT304055.24ms、P99 TPOT369.43ms；三轮各4次抢占重算，影响全部保留。
完整九场景、均值/分位数定义、旧eager取消证据及包装指纹错误修复见[性能报告](performance-graph-100k.md)。
没有完整eager性能基线，不提供模式性能比，不判定性能达标。

性能服务已按准确owner停止，最终正常prefix-enabled graph已实际启动并保持运行。
当前run_id为final-launcher-100k-20261024，PID3304826、start_ticks1123453698，
进程命令SHA256 1e5fae47d52ad00eca124651925ab5632bfa8e7c530f5d6020d9922b3bbf7b34。
100000上下文、TP8、max_num_seqs32、prefill6400、mamba align、qwen3 reasoning parser；
接口为本机8000端口的/v1/chat/completions与/v1/completions。
最终实例的10例105个生成token与同源码100K eager参考完全相同；
最大生成token logprob差0.001118862303≤0.02，所有值有限；该对照不等于全词表logits比较。

## 启动与交付

远端host与容器工作根均为`/public-flash/jinghao/qwen3.8-flash`。
最终可执行脚本为该根的`start-model.sh`；容器内部交付副本为
`/opt/qwen3.8-flash-delivery/start-model.sh`，两份SHA256均为
`cd9f4a4d2e56628597b636892e5834e6d64a9d9357c21f98184b9e51703d07b6`。
2026-10-25已验证语法、准确参数、八卡分配、实际启动就绪、数值对照、正常缓存恢复、
六组件真实安装导入路径及全部内部交付文件一致性。该目录不在bind mount/volume中。

当前服务已运行，无需重复启动。需要重新部署时，先依据当前owner核实并停止本任务旧服务，
再在容器内执行`bash /opt/qwen3.8-flash-delivery/start-model.sh`。
脚本自身仅保留服务启动和必要环境、端口冲突检查，不安装包、打补丁、评测或自动杀进程；
不带--no-enable-prefix-caching、profiling、诊断图指标或PYTHONPATH。
每个显式参数/环境的保留理由在交付restore.md中。

交付配置、两份完整源码补丁、源码清单、依赖锁及恢复说明位于
03-acceptance/delivery-20261024/，并有内容一致的/opt/qwen3.8-flash-delivery/副本。
必要代码、解释器与编译器均在容器/opt安装位置，未依赖host开发源码挂载。
外部约定输入仍为只读模型/tokenizer路径`/public-flash/models/Qwen3.8-Flash-Next`，
以及上述可写工作根的04-runs/05-tmp/06-cache。131权重分片只验证索引集合/大小，未做逐分片内容哈希。
尚未请求镜像打包或新容器验证，image_validation=pending；原基础镜像不是新交付镜像。

下列相对路径均相对已核实远端根：

| 证据 | 路径 | SHA256 |
| --- | --- | --- |
| 任务交付回执 | 04-runs/final-launcher-100k-20261024/delivery-check.json | 79e83b40c70e95a7de8e7a7e72cb5be1e05f5460c62d7025a1eb591490abec04 |
| 实际启动/探针 | 04-runs/final-launcher-100k-20261024/launcher-verification.json | ce177cb72a23ba057976f70baa480cf97742eb07bfecb8a6ee852f8b4fee7980 |
| 最终eager参考对照 | 04-runs/final-launcher-100k-20261024/eager-comparison.json | 7b8597e0f9cb887ffb5a9e3ddcf56fdd734f87ec951e0315b4ff7d32089d2b13 |
| 实际安装导入 | 04-runs/final-launcher-100k-20261024/installed-imports.json | e72caed5a83241aec79d6724a26ad274f95a665a3c1da2a3fbbf0fe8a9824264 |
| 原生交付清单 | 03-acceptance/delivery-20261024/delivery-manifest.json | b2c1ae1f2a5dacfdf34271bd2e65f7fc22298fc5cda3030fb932e492511e95a7 |
| 内部文件/挂载/服务再核验 | 04-runs/final-launcher-100k-20261024/delivery-self-contained-check.json | da805c761fda091b3e1376902b85ddaf1aab29df5f00a30904bf317dea1ad158 |

## 保留限制与状态

clone,randn,normal_排除与内存SQLite仍是已验证运行配置workaround，未声称底层随机或NFS缺陷修复。
验收仅覆盖本机BF16文本TP8；多模态、量化、MTP、其他硬件与32路满100K未验证。
未冻结业务性能目标，formal performance/evidence/summary链路不冒充passed；
本次测量和任务交付回执分别列明，用户选择范围已完成。
本轮没有执行未选择的阶段5复盘或跨工作区维护。

本地审计中Qwen工作区无新增布局错误；全仓仍有两个无关XingChen链接错误及9项历史复核提示，
未据此声称全仓审计通过，也未改动这些无关记录。精度冻结正文及原始运行证据保持未变。
