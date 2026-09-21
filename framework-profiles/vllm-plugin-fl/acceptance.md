# vLLM + vllm-plugin-FL 验收要求

- 最小推理必须分别在 eager 和 graph 模式跑通。
- 后续十并发小批量验证、正式精度和性能验收使用已通过的 graph 服务。
- 正式精度使用 FlagEval 容器及仓库统一精度入口，按冻结阈值判定。
- 所有非性能工作保持前缀缓存开启。
- 性能服务必须显式使用 `--no-enable-prefix-caching`，并验证实际启动命令和服务实例；性能后
  恢复普通的前缀缓存开启配置。
- 最终 `start-model.sh` 使用最小 graph 生产命令，不携带性能专用的
  `--no-enable-prefix-caching`、诊断、profiling、dump 或临时参数。
- 完成前记录 vLLM 未变化证据、Plugin/FlagGems revision、实际 diff、服务身份及全部验收回执。
