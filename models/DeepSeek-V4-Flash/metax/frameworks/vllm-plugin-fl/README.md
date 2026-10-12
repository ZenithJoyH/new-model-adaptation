# DeepSeek-V4-Flash / MetaX / vllm-plugin-fl

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

2026-09-22 结论：PR 427 及 MetaX/FlagGems-vllm 聚焦修复已以未提交的暂存差异合入 `mx-59` 的 `deepseek` 容器。W-INT8-PerChannel/A-INT8-PerToken 模型已在 TP8+EP eager 和最终 graph 配置下完成真实请求；目标明确不是 DeepSeek V4.1。

- 主机和容器工作目录均为 `/public-flash/jinghao/deepseekV4`，由 `/public-flash:/public-flash` bind mount 映射。
- 已完成：109 个分片完整加载；TP8/EP eager 真实请求精确返回 `OK`；sparse MLA prefill/decode、hash top-k、INT8 mapper、Q/KV ABI、W8A8 scaled-mm 与 compressor 的分阶段修复验证。Plugin 相关回归 `72 passed, 3 skipped`。
- 历史阻塞：整模 run19 在 prefill 调用不存在的 NVIDIA FlashMLA 扩展；接入 FlagGems-vllm 后出现 163840 B > 65536 B 共享内存超限，见 [005](adaptation/005-flaggems-sparse-mla-bridge.md)。这不是 glibc 报错。
- 最新修复：用户授权后调整 sparse MLA 的 MetaX tile 到 BH/BK=16、4 warps、1 stage，编译 shared 约 40–42 KiB；追加无效首 tile 的 NaN 保护。设备 eager 聚焦回归 **21 passed**，见 [006](adaptation/006-metax-sparse-mla-config.md)。
- 图模式结论：`bmm_out/mm_out` 黑名单遗漏已修复并有配置回归；标准 torch.compile 在 MetaX 上可捕获但产生错误输出。PyTorch 内置 eager-vs-Inductor verifier 已在 8 个 rank 上直接失败；首个错误子图是纯 ATen BF16 `SiluAndMulWithClamp`，最小复现证明 Inductor 融合消除了 eager 中间舍入。最新 TP8+EP 严格对照已启用 `custom_ops=['all']`，生成图确认出现 FlagGems MHC/RMSNorm opaque 算子，原生 clamped SwiGLU marker 从外层图消失，但两条固定请求仍返回空串/乱码。因此 Plugin dispatch/FlagGems 适配已生效但不足以修复整模 compile 语义；主因仍是当前 MetaX PyTorch/Inductor 栈及与发布镜像不同的 runtime/kernel policy，不能归因于 CUDA Graph 或一个 FlagGems 算子。最终仍采用 `mode=NONE + cudagraph_mode=FULL`，详见 [009](adaptation/009-metax-graph-correctness.md)。
- 最终脚本位于宿主机/容器同一路径 `/public-flash/jinghao/deepseekV4/start-model.sh`，本轮只读复核 SHA-256 为 `4cc47ab78cf11e43b907bec8a21c6ed4705c8f20025ce5f10bb3319cdd4a2112`；前缀缓存开启，不含性能专用关闭参数。最新安全恢复运行目录为 `04-runs/final-graph-restored-20260922-05/`，有效配置 `mode=NONE + cudagraph_mode=FULL`，decode FULL graph 捕获 `1/1`，健康与 `OK`/`5` 复验通过，服务 PID `1432353` 保持运行。
- 未提交/推送源码；vLLM 未修改且 clean。Plugin 有 42 个任务暂存路径，唯一未暂存路径仍为含用户原有 `linear` 的 `metax.yaml`；FlagGems-vllm 有 4 个任务暂存路径且无未暂存差异。
- 当前具备功能性实测证据，但没有伪造 profile 原生 execution-mode 回执或 deployment fingerprint，因此本地结构化状态仍保持 `blocked`。正式 accuracy/performance 与完整 acceptance 未执行，不能声明 optimized。

精确版本和运行证据见 [环境身份](environment/README.md)。早期 001—004 曾误存于 V4.1/MetaX，保持历史位置并标注身份更正，不复用其模型身份和验收状态。

本地 `./scripts/audit-workspace` 未通过：本工作区记录的 profile revision 已变化，必须按项目契约重新复核证据（1 error）；另有其他历史模型记录的 70 项待复核。没有为消除错误静默刷新 revision、伪造指纹或前置阶段回执；这些记录是失败诊断交付，不是完整适配验收。
