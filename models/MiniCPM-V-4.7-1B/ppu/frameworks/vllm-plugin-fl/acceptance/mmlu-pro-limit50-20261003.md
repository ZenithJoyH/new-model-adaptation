# MMLU-Pro 每科 50 题、32 并发诊断（未完成）

后续在所有 FlagGems Aten 注册关闭的实例上完成了 14 科各 50 题；见 [2026-10-03 完整诊断](mmlu-pro-atenoff-limit50-20261003.md)。本页保留发生持续乱码的原始对照证据。

- 日期/Host：2026-10-03，`PPU-13`，容器 `minicpmV4.7-1B` 与 `flageval_llmeval-jinghao`；Host/容器同路径工作根 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B`。
- 用户配置：`tasks=[mmlu_pro]` 展开为全部 14 科，每科 `limit=50`，客户端并发 32、缓存开启、`temperature=1.0`、`top_p=0.95`、`top_k=20`。经用户澄清，`32768` 是评测端**最大新生成 token**（`max_gen_toks=32768`），服务不显式添加 `max-model-len`。每请求超时 600 秒，API/评测重试 0，最终超时应计错而非剔除。任务原生 5-shot 提示，离线读取已缓存的 `TIGER-Lab/MMLU-Pro`。本轮 `limit=50` 且混合 PIECEWISE 图，不是 profile 正式全量精度验收。
- 最终冻结配置：`03-acceptance/mmlu-pro-all-limit50-index-maxnew32768-20261003/config.json` SHA-256 `b36dfb315a45655e7131d446eb38da99a09a326528a543f2ebc37a71073317c1`；原生 runner `03-acceptance/accuracy-v1/llmrun.py`，32 并发命令在控制日志中可核对。独立响应缓存根 `06-cache/accuracy-mmlu-pro-limit50-index-maxnew32768-20261003/`，结果根 `04-runs/minicpm-v-4.7-1b-ppu/mmlu-pro-all-limit50-index-maxnew32768-20261003/`，控制目录 `04-runs/mmlu-pro-index-maxnew32768-controller-20261003/`。
- 服务：物理 PPU2、TP1/BF16、前缀缓存开启、`FULL_AND_PIECEWISE`（mixed PIECEWISE、decode FULL），有效默认 `max_seq_len=262144`；黑名单 `nonzero_numpy,index` 仅是本次诊断实例，不是根目录 `start-model.sh` 的内容。服务日志 `04-runs/mmlu-pro-index-maxnew32768-service-20261003/server.log` SHA-256 `712811511821d493f6352722cdae4c589e9aad57f4ad4178a3e4d0807253f185`。Plugin HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319` 加本模型未提交差异，FlagGems checkout `80d0000d93dad55320df06687eb088a5b6dad07d`、包 5.3.5，vLLM 包 0.24.0。前置服务健康、模型 ID 和短文本正确性均核对，未设服务端 `max-model-len`。

| 学科 | 样本 | 正确 | 无效提取 | 最终超时 | 得分 |
|---|---:|---:|---:|---:|---:|
| biology | 50 | 29 | 8 | 0 | 58% |
| business | 50 | 16 | 9 | 0 | 32% |
| chemistry | 50 | 20 | 12 | 0 | 40% |
| computer_science | 50 | 22 | 12 | 0 | 44% |
| economics | 50 | 27 | 2 | 0 | 54% |
| engineering | 50 | 23 | 1 | 0 | 46% |
| health | 50 | 0 | 50 | 0 | 0%（输出乱码） |

七科均各有 50 条唯一题号和原生样本文件。前六科合计 `137/300=45.67%` **仅为局部观察**；health 的 50 条原始输出从开头失真，随后独立简单题也失真，故不计算 14 科总分。第八科 history 被中断，第 9–14 科未执行。评测 supervisor 和 worker 已精确停止，退出码 143；服务在空闲时精确停止，API 端口关闭、PPU2 释放，适配容器保持运行。详见 [问题 007](../adaptation/007-long-accuracy-output-corruption.md)。

七科原生 `samples_mmlu_pro_<学科>_*.jsonl` 位于上述结果根各自的 `mmlu_pro_<学科>/attempt-1/minicpm-v-4.7-1b-ppu/`。SHA-256 依次为：biology `a04400152dba5e7e50a85e6b79f211bd8efff459bf28918f270ec08391971a05`，business `aaf61c9934034aae286ffb5f7b08afaebc1b67c28d383b632cb27e7d55cf4609`，chemistry `d70be05334cb6624766cf5e33bee1763d511f483f9c49a3a261052308927f827`，computer_science `1dacf17645341df0ffe2236c2f32e73ba789142eaf555693e887094ba42a1984`，economics `b2071ed0ba6d9cde7668b59790efd60fec9b4dea01c05f399dd9b077fdabfd0a`，engineering `9ef31b4532bf9eb88ffc9f5be63913ab6074dd61e5e97029f91f60fecfb85edd`，health `f7c51478383e7111ad1331b09c226892773d0f447d710026b6c6cb64aacf94e5`。

初次使用用户原服务的运行亦已停止：其 biology 50/50 均为 `[invalid]`，配置 `03-acceptance/mmlu-pro-all-limit50-20261003/config.json` SHA-256 `59ceabaece5d68b545ddc7304e2509f078b06cdff549d243159b3933dcb71df7`、控制日志 `04-runs/mmlu-pro-controller-20261003/runner.log`。该实例在评测前没有内容正确性基线，不能单独归因于黑名单。正式 GPQA 精度状态与 `framework.yml` 均未改变。
