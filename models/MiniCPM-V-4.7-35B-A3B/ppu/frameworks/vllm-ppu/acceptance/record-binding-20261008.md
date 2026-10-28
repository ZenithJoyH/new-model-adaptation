# 基础记录绑定与复核

2026-10-08，复用模型级中文架构分析，未改写分析正文。新 checkpoint 配置 SHA
`3973e7ad0bd9f96887341cb134173118b0e445695014a73e736de48e9a9b5646`
与既有分析对应配置一致；本轮进一步验证了真实 MoE 骨干、处理器及 canvas 算法。
新 profile 使用自身上下文绑定，未复用旧 Plugin 的阶段回执作为新容器通过证据。

部署清单、环境身份、三处实际产品增量、真实权重 eager/graph 结果均已核实，随后保存
environment、adaptation、execution-mode 基础回执。正式 acceptance 汇总保持未完成，
experimental profile 不签发完整精度/性能验收或 optimized 状态。

仓库原生记录校验工具与必要控制元数据部署在批准根
`03-acceptance/record-check-20261008/`，使用 `--verify-records` 和实际批准根读取远端
原生证据。该目录不是 vLLM 源码副本，不参与服务导入。首轮因缺 inventory 元数据失败，
失败保存在 `04-runs/bringup-20261008/record-verification.json`。添加仓库原样 inventory
别名元数据后，`record-verification-v2.json` 记录 exit 0，明确输出：
`Framework gate passed: vllm-ppu; selected=environment,adaptation,execution-mode; mode=record-verification`。
没有复制 SSH 配置、group variables 或连接凭证，实际检查仍只针对 PPU-13。

最终本地 `audit-workspace` 对新 profile 无错误或警告。全仓库另有 12 个其他 profile
的历史版本/证据错误，本轮未改写这些记录。本地审计不能代替上述远端原生证据复核。
