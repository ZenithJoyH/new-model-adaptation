# MetaX 平台适配计划

目标固定为 `mx-104` / `qwen3.6-35B`，host/container root 均为
`/data/jinghao/qwen3.6`，模型为 `/data/Qwen3.6-35B-A3B-nomtp`。模型结构见
`../../architecture-and-inference.md`，环境与源码身份见 `environment-analysis.md`。

## 变更范围

- 只修改可编辑安装的 `/workspace/vllm-plugin-FL`；保持 `/workspace/vllm`、
  `/workspace/FlagGems` 和模型权重只读。
- 在 MetaX GDN patch 中通过 FlagGems-vLLM 顶层公开符号接入 chunk prefill 和 recurrent
  decode；保留 vLLM 的门控预处理与未覆盖接口回退。
- 在 `TritonExpertsFL` 的 MetaX、无 LoRA、无 expert-map 快速路径调用
  `flaggems_vllm.runtime.backend._metax.ops.outplace_fused_experts`；其他平台及 LoRA/EP 路径
  保持分阶段结构，不直接调用内部 `fused_experts_impl`。
- 保留分阶段路径在 `default.flagos` 的 dispatch 所有权，将 MetaX 的 align、GEMM1/GEMM2
  和 sum 固定分发到 `flagos`，并在 FlagOS adapter 内导入 FlagGems-vLLM 的 no-TLE align、
  MetaX staged GEMM 和 MetaX sum；不再调用旧 `flag_gems` 的这三个实现。
- 先对 clean `/workspace/FlagGems-vllm` 执行 `git pull --ff-only` 并记录同步结果；不对
  dirty Plugin 做 pull/rebase/reset。

## 实施与验证顺序

1. 保存四个源码树的 revision/status 和目标文件 diff；建立独立复现与结果目录。
2. 通过 Ansible 将最小补丁送入批准根，先 `git apply --check`，再应用到 Plugin。
3. 运行 `compileall`、lint/diff 检查、导入/注册和 mock 契约测试，确认 exact caller、
   MetaX specialization、guard miss 与 LoRA 保留路径。
4. 在空闲 MetaX 设备上分别比较 GDN prefill/decode 和 fused MoE 的旧/新输出，包含变长
   metadata、state 更新、不同输入及多次重复。
5. 若算子对照通过，再以最小配置启动本任务服务做 eager 推理；graph 只在 eager 通过后验证。
   服务日志/缓存/运行输出分别留在 `04-runs/` 与 `06-cache/`。不进入正式验收。

任何 import、ABI、数值或 graph 失败都保留首个失败证据并停止扩大范围；不以 broad exception
静默回退来掩盖目标路径失败。
