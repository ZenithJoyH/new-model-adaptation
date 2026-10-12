# 001：FlagGems slice 不支持 bool

## 元数据与现象

模型 Qwen3.8-Flash-Next / PPU-01，容器 `qwen3.8-flash`。首次记录 2026-09-04；本页于
2026-09-06 根据已有材料整理，没有重新执行远端试验。状态：已记录 workaround，待当前
配置证据绑定。镜像和版本见 [环境配置](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/runtime-config.yml)。

首次 eager 请求在 `_prepare_inputs → discard_request_mask.copy_to_gpu → slice` 处断言，
尚未进入模型前向，API/Engine 随后退出。基线 FlagGems 为 `8416e6dab471451cc437aac3896fdc382dce382e`。

## 诊断、受控尝试与根因

原记录已在 `/bug/flaggems-slice-bool-20260904/repro.py` 独立复现 eager/graph 失败；
FlagGems slice 明确拒绝 torch.bool，是本次失败的已验证原因。未仅凭相似错误复用其他模型结论。

## 解决与验证

通过插件 `vllm_fl/dispatch/config/thead.yaml` 精确排除 slice，恢复原生 view 语义。
这属于 workaround，不是 FlagGems 上游修复。原记录覆盖布尔 pinned-memory copy、长度
1/2/8/32、graph 变输入重放；随后 eager 最小推理返回 2。vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
保持干净，容器持续运行。切换模式时只停止本任务 API/worker，具体 PID、命令和结果见原始进度。

## 证据、限制与下一步

- [完整症状、尝试和生命周期记录](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/history/progress.md)。
- [当前验收总结](../acceptance/adaptation-summary.md)。
- 复现：核实设备仍属于本任务后，在原容器运行 `CUDA_VISIBLE_DEVICES=8 python3 /bug/flaggems-slice-bool-20260904/repro.py`。
- 本地旧脚本、配置和简要原始输出不作为当前版本的验证证据。
- 当前 FlagGems 或插件版本变化时需重验；本页不声明整模型正式精度通过。知识状态：local-only。

## 2026-09-07 重验

FlagGems fast-forward 到 clean `dcd0cfeae8187dee691656c0616c1ed95899c2ae` 后，问题路径仍需回退。
最终 Plugin `a5c6f0ca373afa606b68d2daa4bb4a9dcc1833c5` 通过
`VLLM_FL_FLAGOS_BLACKLIST_APPEND` 追加 `slice`，不覆盖 T-Head 默认策略。PPU bool pinned copy 的
eager、graph capture/replay 和变输入探针通过；全模型 graph 冒烟返回 `2`。证据分别位于远端
`05-runs/workaround-probes-dcd0cfe-20260907-1721/` 与
`05-runs/full-model-smoke-dcd0cfe-20260907-1740/`。结论仍为已验证 workaround。
