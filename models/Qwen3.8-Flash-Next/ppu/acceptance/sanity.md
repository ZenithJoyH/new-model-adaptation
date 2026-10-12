# Graph 八并发 sanity

2026-09-11 在 `PPU-01` / `qwen3.8-flash` 的当前 graph 服务
`execution-mode-graph-7ba32ded-20260911` 上执行固定 8 请求。服务配置与源码 revision 见
[执行模式验收](execution-mode.md)。

- 客户端并发和实际峰值 in-flight 均为 8；完成 8/8，正确 8/8，错误与超时均为 0。
- 用例包含 7 个短算术或字母请求及 1 个 3,635-token 长 prefill；每个请求均关闭 thinking，
  `temperature=0`、`max_tokens=64`。
- 总耗时 30.860 秒；最长单请求 30.851 秒；结束后服务健康检查为 200。该耗时仅作明显回归筛查，
  不作为正式性能成绩。
- 原始结果：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/execution-mode-graph-7ba32ded-20260911/sanity-result.json`，
  SHA-256 `b0c8292a66e5fa1193dcb01802337bbde5f00bf9a9f58fe2a9d858be0bdf4253`。
- 固定 runner：`/mnt/nfs/users/jinghao/qwen3.8-flash/03-acceptance/sanity-8.py`，SHA-256
  `f2eab2387ca7f5103cb9e648455132c3d726ef512afcbe254983633a8bd28e3d`。

结论：当前 graph 服务通过正式精度前置 sanity，可进入全量 GPQA；正式精度必须继续使用同一服务
实例并单独验证 198 条完整样本、最终分数、错误和超时。
