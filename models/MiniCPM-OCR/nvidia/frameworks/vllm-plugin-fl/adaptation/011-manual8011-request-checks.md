# 011：人工启动8011后的六请求正确性检查

2026-10-21，用户已自行启动服务，要求用几个请求验证正确性。本轮只发送固定请求并保存结果，不执行或修改启动脚本，不重启、停止或重新配置任何服务。

## 实际服务身份

- Host：H100-149；容器 `minicpm-ocr-flagos-public`，ID `7b125058368e142f4010df941e7020c3b26874a6552ec2a862a3286f9a6286f5`，完整 `/public` RW挂载。
- Endpoint：`http://127.0.0.1:8011/v1/chat/completions`；模型名 `MiniCPM-OCR-FlagOS`。
- Checkpoint：`/public/flagos/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`；权重SHA256 `83f4e433b044fd23f9ea7eb3acbc7d59e4fe11a1fdf3c3129b7021d0ab4f8fd4`，config SHA256 `90505bb0a5ca87b2fd8afc608bfc9c83d1cb8a0ba6e7a9d7ff29f20ff385322d`。
- API PID2257、start_ticks8980773，已核实该PID拥有8011监听socket。实际 `CUDA_VISIBLE_DEVICES=1`，上下文配置262144，前缀缓存开启，命令请求 `FULL_AND_PIECEWISE` 和视觉 `TORCH_SDPA`。
- 用户启动脚本SHA256 `9f72b8855063a038d2438fbc12e293ee5b9d6e06ad320559538fc4d7f0541d3d`，检查前后一致。此前Agent改写已恢复；本轮直接检查用户启动的进程，没有代替用户重新启动。

## 实测结果

固定六项，串行、每项超时120秒，不重试、不隐藏失败。所有请求均HTTP200，去除首尾空白后输出与冻结样例预期完全一致，`finish_reason=stop`，返回token ID个数与completion_tokens一致。

| 用例 | 关键输出 | prompt / completion tokens | 结果 |
| --- | --- | --- | --- |
| 文本计算 | `2` | 24 / 2 | 通过 |
| 小图4x OCR | `HELLO OCR`、`TEST 149` | 279 / 10 | 通过 |
| 发票4x OCR | 编号149、金额123.45、日期2026-10-20 | 1821 / 37 | 通过 |
| 发票16x OCR | 与发票4x相同的完整文字 | 486 / 37 | 通过 |
| 双图 | 按顺序返回小图和发票的完整文字 | 2080 / 47 | 通过 |
| 视频 | `HELLO OCR`、`TEST 149` | 534 / 10 | 通过 |

请求前后PID、启动时间、命令哈希、显卡环境和脚本哈希均未变，8011 health200。原生8000服务检查前后也均health200，没有对其发送推理请求或改动配置。

这些是固定样例的功能正确性结果。预期文字沿用原有已冻结样例；没有为新checkpoint重新运行独立Transformers参考，不代表完整数据集精度、性能、最大长度边界或峰值并发通过，也不继承2026-10-20旧权重的验收结论。

## 证据

批准主机/容器根均为 `/public/flagos/jinghao/MiniCPM-OCR/flagos`。原始证据在 `04-runs/manual8011-six-requests-20261021/`：

- `request-plan.json`：六项请求及完整预期；SHA256 `df35c0ab27c75ae562b6b3a81ea4d22fd7581fde3088dde9539b37739e90c2e1`。
- `results.json`：六个实际响应、逐项文字及token计数检查；SHA256 `3f98a8a74365c629ac91cbf0f3c62fe28d84c339826edb823607a2d318e4d94a`。
- `summary.json`：6/6、HTTP/文字/结束原因/token计数全部通过；SHA256 `1a32893c61e877ad3998e530a5bf566891a47f854bd6a4265132f811154d210c`。
- `service-before.json`、`service-after.json`：当前实例、监听归属、脚本和服务健康前后取证；`evidence-index.json`汇总文件哈希。

执行代码 `03-acceptance/manual8011-six-requests-20261021.py`。当前部署观察身份在 `01-environment/deployment-manual8011-20261021.json`，指纹 `27bd037ae1b9f3d1c1676a49596d3b97230dd4332e296d3eaddb538886b26ea1`；这是本次请求检查的部署身份，不是完整框架验收回执。

人工交回已通过workspace-control记录，新checkpoint和服务变化使旧阶段verification退入control.history；当前正式阶段待复核。本次不将六请求诊断改写成原生完整验收通过。
