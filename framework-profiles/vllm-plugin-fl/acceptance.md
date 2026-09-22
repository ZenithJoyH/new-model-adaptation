# vLLM + vllm-plugin-FL 验收要求

- 最小推理必须分别在 eager 和 graph 模式跑通。graph 必须先尝试并优先采用覆盖 prefill 与
  decode 推理链路的全量图（`full`）；只有在当前模型、平台与 revision 上留下可复现的失败、
  定位及阻塞证据后，才允许降级为 decode 阶段全图（`decode-full`）。不得跳过全量图尝试，
  也不得把 `decode-full` 当作默认配置。
- `decode-full` 是 graph 验收的最低通过线。仅 eager、分段/可断图、非 full decode 或更低
  覆盖级别不能通过执行模式验收。回执必须记录 `graph_level`；降级时还要记录全量图的准确
  配置、失败签名、证据、原因、限制和退出降级条件。
- 后续十并发小批量验证、正式精度和性能验收使用执行模式验收选出的最高可用 graph 级别；
  不能在后续步骤中无证据地从 `full` 降为 `decode-full`。
- 正式精度使用 FlagEval 容器及仓库统一精度入口，按冻结阈值判定。
- 所有非性能工作保持前缀缓存开启。
- 性能服务必须显式使用 `--no-enable-prefix-caching`，并验证实际启动命令和服务实例；性能后
  恢复普通的前缀缓存开启配置。
- 最终 `start-model.sh` 使用已验收最高可用 graph 级别的最小生产命令，不携带性能专用的
  `--no-enable-prefix-caching`、诊断、profiling、dump 或临时参数。
- 完成前记录 vLLM 未变化证据、Plugin/FlagGems revision、实际 diff、服务身份及全部验收回执。
