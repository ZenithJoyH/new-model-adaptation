# Hy4-preview / PPU：验收文档

返回[平台概览](../README.md)。本目录只保留验收计划、验收结果和最终总结，不保存
Python wrapper、Playbook、JSON/YAML 配置、缓存、日志或原始输出。

## 当前结论

- 2026-09-08 用户重启后的 graph 服务已通过本轮 c8 sanity（8/8），并额外通过 c16/c32
  短请求阶梯验证；三轮均未出现致命服务错误，c8/c32 均为 0 preemption。
- 全量 GPQA Diamond 198 题按并发 32、thinking/high、`max_gen_toks=80000` 运行后再次触发
  `sample_tokens` 1800 秒超时并使服务退出；只有 3 条真实返回且 strict 3/3 正确，其余 195 条
  为服务崩溃无效项，正式 accuracy 失败。
- `--max-num-batched-tokens 2048` 单变量缓解验证已失败：固定 c8 sanity 为 8/8，但
  c32/high/80K 的前 32 题长输出诊断只有 8 个真实响应、24 个 timeout，服务在 99.9% KV 和
  preemption 后的“14 decode + 2,034 recompute”步骤挂起并于 1,800 秒后退出。8 个真实响应
  strict 8/8 正确，不能把失败聚合分数解释为模型精度下降。
- 复核发现失败服务实际使用了缩减后的五项 blacklist，相对 Plugin HEAD 放开了 34 个 FlagGems
  ATen 算子；原计划先恢复完整默认 blacklist 做 A/B，随后按用户要求扩大为关闭全部 ATen 注册。
- 用户随后要求扩大对照为关闭全部 FlagGems ATen 注册：当前 `thead.yaml` 已加入由 FlagGems
  当前注册表解析出的 982 个函数名，显式 W8A8/MLA fused/dispatch 路径保留；新服务 graph 51/51、
  health 200，c8 sanity 8/8。相同 32 题 c32/high/80K 的 rerun1 已于 2026-09-09 09:30:47 +08:00
  启动，尚未进入高 KV 阶段，不能标记通过，也不启动正式 198 题。
- 2026-09-06 graph 正式精度覆盖 198 个唯一样本，6 个样本达到 40,000-token
  生成上限后仍无最终答案；该历史轮仍为失败基线。
- 用户已按 87% 业务阈值接受最新 strict 90.91% 精度。正式性能中 `1024/4096 → 1024` 两档各
  3 轮成功，`16384/32768 → 1024` 各 3 轮超时；`65536 → 1024` 第 1 轮超时、第 2 轮按用户
  决定终止、第 3 轮未运行，场景级标记为超时。2026-09-14 用户决定不再继续性能测试，performance
  状态为 failed，不生成 passing receipt，也不标记 optimized。完整路径见
  [Plugin 2fa 性能测试记录](performance-plugin-2fa-indexoff-20260911.md)。

## 文档索引

| 文档 | 内容 |
|---|---|
| [acceptance-plan.md](acceptance-plan.md) | 当前验收顺序、配置摘要和通过条件 |
| [execution-mode-and-sanity-20260907.md](execution-mode-and-sanity-20260907.md) | 当前栈 eager/graph 与并发 8 前置验证 |
| [sanity-and-gpqa-launch-20260908.md](sanity-and-gpqa-launch-20260908.md) | 重启服务 c8/c16/c32 验证与全量 GPQA 80K 启动证据 |
| [gpqa-80k-failure-20260908.md](gpqa-80k-failure-20260908.md) | 全量 GPQA 80K 的失败 receipt、部分响应判分与服务退出根因证据 |
| [gpqa-plugin-ff87-flaggems-bca-launch-20260910.md](gpqa-plugin-ff87-flaggems-bca-launch-20260910.md) | Plugin ff87 / FlagGems bca 同步版 c64、80K 全量 GPQA 启动与前置验证 |
| [gpqa-plugin-2fa-indexoff-launch-20260910.md](gpqa-plugin-2fa-indexoff-launch-20260910.md) | Plugin 2fa、保留通用 index 黑名单后的 c64、80K 全量 GPQA 启动与前置验证 |
| [performance-plugin-2fa-indexoff-20260911.md](performance-plugin-2fa-indexoff-20260911.md) | prefix-cache-disabled 正式性能服务、默认五工况、dry-run 与终态结果 |
| [adaptation-summary.md](adaptation-summary.md) | 当前适配与验收总结 |
| [accuracy-results.md](accuracy-results.md) | 各轮 GPQA 精度结果、远端证据与当前判定 |

后续验收继续使用仓库公共 `test/Accuracy_test/llmrun.py`。模型专用配置、部署辅助文件、
原始 result/sample、性能输出和每轮日志应放在用户批准的远端 `04-acceptance/` 或
`05-runs/`，并在对应验收文档中记录准确路径和摘要。
