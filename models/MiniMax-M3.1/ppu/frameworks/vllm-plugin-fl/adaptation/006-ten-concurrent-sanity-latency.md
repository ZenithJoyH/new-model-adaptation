# 006：十并发简单题延迟高于串行对照

## 元数据与签名

- 状态：`hypothesis`；2026-09-30；`PPU-07`、`minimaxM3.1`、当前 TP16 `decode-full` 服务实例 `ppu07-m31-container1ac783da-api565730-start344462218-cmd6e6c40f30ebf73c5`，prefix cache enabled，48/48 shard 已加载。Plugin/FlagGems/vLLM revision 见[005](005-gpqa-first10-two-errors.md)。
- 固定简单科学题 manifest `03-acceptance/service-sanity-20260930/manifest.json` SHA-256 `0863b924195c07a0cb3afc3da9b81960c738358cf3b3c016576f2af84a497d73`；10/10 正确、HTTP 200、正常停止，无超时、OOM 或服务失活。

## 受控比较

| 轮次 | 单一变量 | 原生报告及 SHA-256 | 10 题用时、吞吐 |
| --- | --- | --- | --- |
| 0 | c10，运行中 0.5 秒一次 `ppu-smi` | `04-runs/service-sanity-20260930/report.json` `2ca11c7a61e96a28e1b392c375e7cc329c516c5280ada5b843541c45c6995793` | 70.103 秒，0.1426 请求/秒 |
| 1 | 仅移除运行中 PPU 轮询，仍 c10 | `04-runs/service-sanity-no-monitor-20260930/report.json` `95243965293eab473ddc9e79295ec5f90c541c8aefc09f49c15139f832f512ee` | 48.299 秒，0.2070 请求/秒 |
| 2 | 在无轮询配置中仅改 c10→c1，相同十题顺序 | `04-runs/service-sanity-c1-control-20260930/report.json` `3e9a7cd6d0e191b0b977b9fd48a0a01d90f83a9ebc95a9cec8bca7193d37a669` | 34.551 秒，0.2894 请求/秒 |

轮询引入约 21.8 秒额外时间，但不是全部延迟的解释。无轮询十并发比串行慢约 13.7 秒；部分单题串行延迟达 4–9 秒，十并发响应几乎同时返回。服务日志在 c10 期间出现运行中短暂零吞吐，但没有报错或 rank 退出。轮询轮次的 `ppu-smi` 采样观测利用率最高 100%，显存约每卡 86,705→86,729 MiB；对照轮次不做运行中监控以免扰动。

## 判断与后续

现有基线不能证明这是本次 Plugin 改动引入的回归，也不能证明推理性能达标；未进行性能专用服务或正式 benchmark。预检没有预先冻结的吞吐阈值，且十并发完整正确、服务正常，暂不认定为阻断性性能故障。正式精度通过后，以性能专用无 prefix cache 服务和冻结场景量化；若相同负载下复现吞吐低于基线，逐一检查调度、prefill/indexer、MoE 与监控干扰。未改源码或配置，未动其他服务；知识库处理状态 `needs-validation`，PR 范围暂不扩大。
