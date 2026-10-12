# 执行模式验收

当前修订验证于 2026-09-11 在 `PPU-01` 的 `qwen3.8-flash` 容器完成。源码为 Plugin
`939600b323c02c21916f1f76bfb4cd8c2b02578d`、FlagGems
`7ba32ded1365d3ce6d3b7e28f41af7ddc7ff095c`、vLLM
`ee0da84ab9e04ac7610e28580af62c365e898389`；BF16、TP8、物理 PPU 8–15、maxlen 65536、
maxseq 32、maxbatch 4096、执行超时 1800 秒。

| 模式 | 远端运行目录 | 结果 |
|---|---|---|
| eager | `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/execution-mode-eager-7ba32ded-20260911/` | 健康 200；固定请求返回 `2`、stop；响应 SHA-256 `f2fae3d0bd49de7cbd32ce697cee13bc13fd50e4be32c8b1b619877d8946468b` |
| graph `FULL_DECODE_ONLY` | `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/execution-mode-graph-7ba32ded-20260911/` | capture sizes 1/2/4/8/16/32 全部完成；健康 200；固定请求返回 `2`、stop；响应 SHA-256 `44be46aadef730384da213591d6746e5d949fea1ec63b78137cb2df2183e1709` |

两次请求均为 `temperature=0`、`max_tokens=64`、关闭 thinking。eager 验证后只终止了本轮 API PID
`1535727`，并确认其 EngineCore/worker 全部退出及 8038 端口释放；适配容器保持运行。随后由根目录
最终脚本启动 graph 服务，API PID `1675285`。后续 sanity 与正式精度均绑定该 graph 服务实例。

最终启动脚本的 host/container 路径均为
`/mnt/nfs/users/jinghao/qwen3.8-flash/start-model.sh`，SHA-256
`75be549b0d5ead31c56fba0d161047a562c37b731acb8aa1df06baecc148bf45`；语法和映射一致性通过。
