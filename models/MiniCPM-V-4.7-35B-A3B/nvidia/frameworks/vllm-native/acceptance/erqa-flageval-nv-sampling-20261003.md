# H100-149 FlagEval MM-Eval ERQA 双配置诊断

2026-10-03，仅对 `H100-149` 的原生 vLLM 8020 服务进行诊断性全量对照；没有执行 PPU 评测或正式 accuracy 验收。服务模型名 `MiniCPM-V-4.7-35B-A3B`，推理容器 `MinicpmV4.7-35B-native`。评测镜像 `flageval/mm-eval:v0.3.8_1` ID `sha256:946d2725872c7fd1a5ca643be16132bb1d22af709f52819bbe7b0f5da81900f9`，镜像内 `/app` Git HEAD `63c8c28bad8cb41c0a3a3056b53f3031fb6db1ab`。独立评测容器 `flageval-erqa-native-8020-20261003` 使用 Host 网络、只读根文件系统；工作根 Host/容器同为 `/public/flagos/jinghao/MiniCPMV4.7-35B/native`，设备号:inode 同为 `45:242118947849`。现有 MM-Eval 容器的 `/root/.cache/flagevalmm/datasets/ERQA/test` 以只读方式映射为本容器 `/erqa-data`，400 题、630 张图片，没有复制图片。使用镜像原有 `tasks/erqa/erqa.py` 提示词与 `BaseEvaluator`；两组输出的 400 个题干聚合 SHA-256 同为 `938f88e2d88c6750f9d80928adcdf6b63921942b09a494c524dfa19813`。

两组顺序运行、各 32 并发、每题 `num_infers=1`（FlagEval 客户端内部仍会重试失败请求）；公共请求配置为 `temperature=1`、`max_tokens=32768`、`stream=false`、`retry_time=300`，客户端缓存关闭。唯一配置差别是第一组发送 `top_p=0.95, top_k=20`，第二组请求不带这两个字段。配置文件分别为工作根下 `03-acceptance/erqa-flageval-native-8020-c32-20261003-with-top-pk.json`（SHA-256 `d3f126506792cb79dcd0d515ca92e17742501a34209f349c44a60373503d4021`）及 `...-without-top-pk.json`（`fdb06dd07665e31f1e0a95385527e6ac57d1b8dbc6d1c76fd13f5d9ca2814d15`）。在评测容器内以模拟 HTTP 响应检查了两种实际请求 JSON：前者包含 `0.95/20`，后者没有 `top_p/top_k` 字段。

镜像原生 `model_adapter.py` 未将 `--data-root` 传入本地 TaskManager，也未透传 `top_p/top_k`。因此在 `03-acceptance/flageval-erqa-sampling-adapter-20261003.py`（SHA-256 `1f257cfa6cb7b0b3adc29ebd17af8076cdf3de339b052bccca10bcf7f5aed7c6`）只补充这三项评测入口参数；原 FlagEval 任务、数据集、评分器和产品推理服务代码未改。第一次原生入口尝试转去下载数据、第二次自定义入口因 `/app` 未入模块路径在导入时退出，均无任何题目结果，保存在相应的失败运行目录；修正后有效运行均在下表 `-v2` 目录。运行包装脚本为 `03-acceptance/run-erqa-flageval-native-8020-20261003.py`（SHA-256 `4ae5cdb814dcf05b1969b6c8249bb787b3d326ff9abf47bb1a0d60a0e1de6bea`），要求全量文件存在且包含 400 条，不以 FlagEval 进程的零退出码单独判断成功。

| 配置 | Host/容器结果目录（工作根下 `04-runs/`） | FlagEval 原始 accuracy | reject | 全部 400 题计分 | 结果文件 SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| 带 `top_p/top_k` | `erqa-flageval-native-8020-c32-20261003-with-top-pk-v2/` | 51.14% = 202/395 | 5 | 202/400 = **50.50%** | `erqa/erqa_result.json`: `4931f001e2369aa3010e8cf50df4c457af7a976c2e3a6715f7d50e6bfce05264` |
| 不带 `top_p/top_k` | `erqa-flageval-native-8020-c32-20261003-without-top-pk-v2/` | 50.63% = 201/397 | 3 | 201/400 = **50.25%** | `erqa/erqa_result.json`: `54eb20e7b232046c58536358a7deab60ee1d561b8b5262cc891056b14b3f91d7` |

两组 `erqa/erqa.json`、`erqa/erqa_evaluated.json` 均各含 400 个唯一且相同的 ID；逐题原始结果 SHA-256 分别为 `8f7bd8d31e5dbdf38000a87df1dc07283471f48ac11f4db820181252a1f2d542` 和 `2238194715cb38184d0497b1c0476da453b1198931851825ab564c4d63f1ab40`。共同答对 177 题，配置组独对 25 题、未配置组独对 24 题；提取出的选项有 325/400 题相同。两组得分只差 1 题；各只跑一次且采样随机，不能据此认定 `top_p/top_k` 带来稳定精度提升。

FlagEval 内置 accuracy 排除 reject 后计算。5 个与 3 个 reject 都是 MM-Eval HTTP 客户端对服务响应 `content=null` 执行字符串拼接时抛出的 `TypeError`，经过其既有重试后仍失败；配置组为 `ERQA_200/217/267/270/394`，未配置组为 `ERQA_217/267/394`。原始逐题文件保留这些错误，按本项目全量覆盖规则在 400 题分母中计零。对照完成后 8020 `/health` 为 200，推理容器及评测容器均仍运行；本轮未重启服务。后续若比较 PPU，应复用同一 FlagEval 镜像、任务、适配入口和数据哈希，并单独记录拒答与采样波动。
