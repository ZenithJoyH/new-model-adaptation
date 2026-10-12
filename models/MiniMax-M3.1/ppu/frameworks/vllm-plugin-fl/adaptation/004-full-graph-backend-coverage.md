# 004：MiniMax M3 sparse/indexer 后端阻止 prefill 与 decode 全量图

## 元数据

- 状态：`full-blocked; decode-full-service-validated`；2026-09-30 首次及最后验证，Host `PPU-07`，`minimaxM3.1` 容器，镜像 `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`。
- 模型：`/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`；TP16，BF16，50k context，128 token block，prefix cache enabled，服务端口 8025。
- 修订：Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加本任务未提交 diff；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389` 未修改；FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`。

## 签名及原始证据

请求全量图的脚本：Host/容器同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/01-environment/start-graph-full-20260930.sh`，SHA-256 `0a9e79a34e239146f9169b39beb8ca9e65c4555fd164eed661dec7beadec7424`，明确 `--compilation-config '{"cudagraph_mode":"FULL","cudagraph_capture_sizes":[1,2,4,8,16,32]}'`。引擎配置最初为 `CUDAGraphMode.FULL`。随后 16 个 TP worker 在 `/workspace/vllm/vllm/config/compilation.py:1358` 报 `CUDAGraphMode.FULL is not supported with MiniMaxM3SparseBackend/MiniMaxM3IndexerBackend backend (support: AttentionCGSupport.UNIFORM_BATCH); setting cudagraph_mode=FULL_DECODE_ONLY`。实际只捕获 `Capturing CUDA graphs (decode, FULL)` 6/6，未捕获 prefill。原始日志 `/mnt/nfs/users/jinghao/minimaxM3.1/04-runs/graph-full-service-20260930.log`，停止后 SHA-256 `be466f5e4ae4cef29bc653db5134eb937db83af72c5f71094496f16e6bdbea34`。

在该自动降级服务上的真实聊天请求 `1+1` 返回 HTTP 200、`</mm:think>2`、1.701 秒，回执 `/mnt/nfs/users/jinghao/minimaxM3.1/04-runs/graph-full-requested-chat-20260930.json`，SHA-256 `7fafadd7eb43ed7d78a480b3f0d246f652ab6f05d7806545cc4d64003fb5d2c5`。服务仍健康；此结果只证明 decode 图路径和一次输出，不能记为 full graph。

## 诊断、受控对照和根因

| 轮次 | 唯一变量 | 配置 | 结果 |
|---|---|---|---|
| 0 | eager 基线 | `--enforce-eager`，其余 TP16/模型相同 | 聊天输出 `2`，暖请求 HTTP 200 |
| 1 | 请求 FULL | 上述精确 `FULL` 配置、prefix cache enabled | 后端能力检查自动降为 `FULL_DECODE_ONLY`；6/6 decode 捕获与真实请求通过 |
| 2 | 显式 decode-full | `FULL_DECODE_ONLY`，其余参数相同 | 明确模式完成 6/6 decode FULL 捕获；聊天及两次变输入 replay 正确 |

已验证的阻塞点是当前 vLLM MiniMax sparse attention 与 indexer backend 将图能力声明为 `AttentionCGSupport.UNIFORM_BATCH`（`/workspace/vllm/vllm/models/minimax_m3/common/sparse_attention.py:164`、`/workspace/vllm/vllm/models/minimax_m3/common/indexer.py:216`）；`compilation.py:1320-1360` 要求 mixed prefill/decode FULL 的后端支持 `ALWAYS`。属于当前 vLLM backend 能力边界，不能通过仅修改启动参数或把自动降级标称为 full 来满足。尚未证明上游后端可安全支持 full prefill；不得直接将能力标志改成 `ALWAYS`。既往问题索引未发现同一模型、同一 revision 的已验证 full graph 修复。

## `FULL_AND_PIECEWISE` 可行性（2026-09-30）

当前 vLLM `v0.24.0` 的 `/workspace/vllm/vllm/config/compilation.py` 定义该模式为 decode FULL、prefill/mixed PIECEWISE；piecewise 需要 `VLLM_COMPILE` 与非空 attention `splitting_ops`。MiniMax 架构在 `/workspace/vllm/vllm/config/vllm.py:1077-1104` 自动启用 `VLLM_USE_BREAKABLE_CUDAGRAPH=1` 并把编译模式设为 `NONE`；当前服务日志 `04-runs/graph-decode-full-ctx65k-service-20260930.log` 的实际 EngineCore 配置确认 `mode=NONE`、`splitting_ops=[]`。按 `compilation.py:1140-1167`，空分割算子下显式 `FULL_AND_PIECEWISE` 会先转为 `FULL`，再因两个 MiniMax 后端仅声明 `UNIFORM_BATCH` 转为 `FULL_DECODE_ONLY`。因此只切换图模式不能开启 prefill piecewise 图，未用未经验证的配置替换现有健康服务。要实现该模式，需先解决此模型的 torch.compile/attention 分割支持，再验证有效配置、prefill/mixed 图捕获、输出精度、replay 和性能。此项是源码及实际配置推断，尚未进行独立服务启动实测。

## 处理与退出条件

按 profile 允许的最低图级别显式启动 `FULL_DECODE_ONLY` 并验证捕获、replay、十并发、正式精度及性能。保持 Plugin/vLLM 现有 dispatch 和模型语义；本问题不做未经验证的 vLLM 源码改动。未来仅在两个 backend 具备经数值、混合 batch、捕获及性能验证的 `ALWAYS` 语义，且 `FULL` 不再自动降级时，才退出 decode-full。服务操作：仅对本任务 FULL 首试 API host PID `2913239` 经精确命令及容器 cgroup 核对后发送 TERM；8025 关闭，`minimaxM3.1` 容器仍运行。知识库决定 `local-only`，不推断其他 revision 或平台。

## 显式 decode-full 结果

`01-environment/start-graph-decode-full-20260930.sh` SHA-256 `f892b05b24133e7a2482ae7d03ae614ecf0b60c2756a6dbe547e164e0f9b03ad`，与 FULL 首试仅图模式和日志文件不同。日志 `04-runs/graph-decode-full-service-20260930.log` 的 API/EngineCore 配置均为 `CUDAGraphMode.FULL_DECODE_ONLY`，无自动降级警告；6/6 decode FULL 图捕获，服务完成 startup。真实聊天 `1+1` HTTP 200、`</mm:think>2`、1.41 秒；回执 `04-runs/graph-decode-full-chat-20260930.json` SHA-256 `16e715481804fd0e6e76bd15b0cc4ff4e32299c85e9e12d8545fbbc7e1234fab`。随后两次改变输入 replay 得 `5`、`3`（1.021 和 0.573 秒），回执 `04-runs/graph-decode-full-changed-input-20260930.json` SHA-256 `10667232973d4c7d9ad589359134c5f095739ccdfbda35d0b87ed9b60366683e`。服务 host PID `3459830`、容器仍运行。固定十题、全量精度和性能仍待正式验收。
