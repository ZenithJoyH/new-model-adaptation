# MiniMax-M3 / PPU 验收计划

## 范围与身份

- Host / 容器：`PPU-13` / `minimaxM3`，16 × PPU-ZW810E，TP16。
- 模型/Tokenzier：`/mnt/cpfs/models/MiniMax-M3`，服务 ID `MiniMax-M3`。
- Plugin / FlagGems / vLLM：执行时为 `86ec92fd` 加完整 redesign 工作树，现已按相同字节固定为 `aee54f38580e0b8b3db5ed433663ed5359ca308b` / `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85` / `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 工作根：host/container 均为 `/mnt/nfs/users/jinghao/minimaxM3`。
- 通用 graph：`FULL_DECODE_ONLY`，capture `1,2,4,8,16,32`，block 128，max model len 65536，prefix caching 开启。

## 顺序与门禁

1. `execution-mode`：分别验证 eager 与 graph 的真实 TP16 权重加载、warmup、health 与最小推理；graph 额外要求 changed-input replay。
2. `sanity`：只在已通过 graph 服务上执行版本化固定 10 个 GPQA 类问题，c10，逐题全正确、零非 timeout 错误，同时检查明显性能/资源异常。
3. `accuracy`：FlagEval `flageval-llmeval:v1` 中使用 `test/Accuracy_test/llmrun.py`，先 preflight，再 GPQA Diamond 198 全量、graph、limit 0、c64、`allow_timeouts=true`；冻结 metric 为 `exact_match,strict-match`，minimum 为 `0.80`。评测期间服务 `--max-model-len` 不得低于 `50000`，实际值为 `65536`。
4. `performance`：仅当当前 accuracy gate-check passed 后执行；切换到同一 graph 参数的专用服务，唯一服务差异是加入 `--no-enable-prefix-caching`，核实生效后先 dry-run，再运行冻结套件。
5. `evidence`：核对服务身份、参数、revision、完整样本与原生 JSON receipt/hash。
6. `summary`：只在全部子步骤通过后创建最终 `start-model.sh`、验证 SHA/就绪并更新平台状态。

## 失败与停止条件

- 不得以 smoke、聚焦单测、旧模型阈值、历史性能或 Markdown 标签代替当前原生回执。
- 固定 manifest/评分入口、精度阈值、服务绑定或样本完整性缺失时返回 `incomplete`，不自行创造。
- 任一前置不通过即停止后续交通；特别是 accuracy 未通过时不启动性能服务或性能请求。
