# PPU-13 十并发小批量验收

2026-09-29 在已通过执行模式验收的当前 `decode-full` graph 服务上执行，服务实例为 boot ID `e0f88877-608c-4443-a22d-2d773ff175f1`、PID `109945`、启动 tick `337210114`、命令 SHA-256 `de005c1cebe1acd8a90935259fddd9078fcf8e6e04e260c09ebe1d61c16abd59`；前缀缓存保持开启。仓库本地 `inference-accuracy-evaluation` Skill 明确选择 `service-sanity`，bundle SHA-256 `5ba2c9b96040324baf067405c53ff48528ae463b2dcd06f0a062ce57ac3885ca`。

固定题目清单 `03-acceptance/science-sanity-10-v2.json` SHA-256 `a1ec5ce98e194f894c788ecc0a2a94c2f5bb6a6eedf87a194bcd9cbf7bed68e1`，包含 10 道四选一科学问答，提前冻结正确选项，温度 0，生成上限 1024。首轮同题 `max_tokens=128` 有 8 个请求在回答结束前达到长度上限，只通过 2/10；原始 `04-runs/science-sanity-10-v1-20260929/result.json` SHA-256 `60c81fd67358e0c4219aeef80fe907a3b6bde7f78bd26fef000f013a1b5d81e8` 保留。v2 只提高生成上限，题目与答案不变，原始内容 10/10 正确；但初始脚本的答案正则可能命中选项正文，因此另做末尾答案审计 `04-runs/science-sanity-10-v2-20260929/audit.json` SHA-256 `4c89fe1ee6c29959197fe160c860e25e93782c683f47a73b100d36540583e32d`，10/10 通过。

正式本轮采用严格末尾答案脚本 `03-acceptance/science-sanity-10-v3.py` SHA-256 `6e268c1efd00e44b866325b7a5af520b79b4b04ca4081c36eab09185ef8cc04b`，不改变题目/答案/参数。`04-runs/science-sanity-10-v3-20260929/result.json` SHA-256 `f0b810414dd1a86b39a93c1550c4cefc60584f116b0415ce204108b53874a320` 记录 10/10 末尾选项匹配、全部 HTTP 200 且正常 `stop`，实际峰值同时运行 10、服务身份和健康前后不变。合计输入 518 token、输出 1850 token，墙钟 13.295 秒、p95 请求 13.242 秒、0.752 请求/秒。与固定多模态预热后 14.884 秒、纯文本约 500 输出 token 对照 8.072 秒均无持续停滞或错误；不同输入不能据此计算严格性能提升，正式性能另行测量。

本次小批量的逐题全对规则只用于 sanity，不作为 GPQA Diamond 全量正式精度的判定标准。
