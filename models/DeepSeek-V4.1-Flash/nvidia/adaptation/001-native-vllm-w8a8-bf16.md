# 001：原生 vLLM 支持 W8A8 视觉塔与 BF16 Engram

## 元数据

- 状态：`resolved`（组件、整模启动和最小真实推理均已通过）
- 首次出现时间：2026-09-22
- 最后验证时间：2026-09-23
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- 平台与 Host 别名：NVIDIA H100 80GB x8，`H100-149`
- 容器名称与镜像：`deepseekV4.1-flash-native-driverfix`，镜像 digest `sha256:7d0be028059e116ba2f0d00425d45f96e268f4c6f9faaa5c2879f52a6cedbfed`
- vLLM 身份：wheel `0.1.dev20904+g179dd0fa9.cu129`；安装源码位于 `/usr/local/lib/python3.12/dist-packages/vllm`
- 执行模式与负载：原生 CUDA，TP8，BF16 compute，compressed-tensors W8A8，FP8 KV，`max_model_len=2048`

## 问题现象

- 视觉塔 checkpoint 含 `vision.*.weight_scale`，但 upstream `DeepseekV4*` 视觉线性层固定使用 `quant_config=None`；首个 `vision.patch_embed.proj.weight_scale` 因模块没有 `weight_scale` 参数而失败。
- checkpoint 配置声明 `flagos_bf16_engram=true`，两个 Engram 表为 BF16 且没有 `weight_scale_inv`；upstream `ParallelEngramEmbedding` 固定分配 FP8 权重与 uint8 scale。
- 第一版修复进入视觉 profile 后，图像 patch 被按已量化权重的 INT8 dtype 转换，触发 `dynamic_scaled_int8_quant_kernel not implemented for 'Char'`。
- 第二版修复继续进入文本 attention profile 后，`wo_a.weight.view(...)` 无法处理 Cutlass 权重加载后的非连续布局；同时共享 `o_proj` 只实现了 FP8/BF16 分支，没有该 checkpoint 所需的 W8A8 分组逻辑 BMM。
- 原始诊断证据：`H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/native-w8a8-bf16-check-20260922/retry-initialized-group/compatibility-result.json`，SHA-256 `634c471cc51aa3d277288f466c07e5e34d9470a03bc788e64e0a2f0add32b9f9`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 本次决定 |
|---|---|---|---|
| MetaX DeepSeek-V4 INT8 scale mapper | 都涉及 compressed-tensors W8A8 scale | 本 checkpoint 已使用 `.weight_scale`；失败来自视觉层未启用 quant config | 不复用 mapper 修复 |
| NVIDIA 原模型驱动编译库问题 | 同一容器与 Host | 驱动库已通过只读挂载修复，本问题发生在模型参数契约 | 保留既有驱动挂载与本地 cache |

## 根因

vLLM 的 DeepSeek V4/V4.1 实现只覆盖发布时 FP8 Engram、未量化视觉塔和 FP8/BF16 attention output projection 的 checkpoint 契约。该 W8A8-BF16 变体新增了三项显式格式：视觉线性层使用 per-channel INT8 weight / per-token dynamic INT8 activation；Engram 表已经离线转换为 BF16，并通过 `flagos_bf16_engram` 标记；`wo_a` 使用相同的 W8A8 channel/token 量化，但执行语义是分组逻辑 BMM。运行时没有完整读取和执行这些契约。

## 解决方法

用户明确授权本次 NV 原生适配直接修改 vLLM 源码，作为 `vllm-plugin-fl` 默认只读规则的特例。修改限定为：

- `vllm/models/deepseek_v4/common/vision.py`：向 ViT、block、attention、MLP、patch embedding 与 aligner 传递 `quant_config` 和完整参数前缀。
- `vllm/models/deepseek_v4_1/nvidia/vl_model.py`：用 `vision.*` / `aligner.*` 前缀构造量化视觉层；量化路径避免 module-wide dtype 转换将 FP32 scale 转为 BF16；保存 BF16 视觉计算 dtype，避免按 INT8 权重 dtype 转换输入 patch。
- `vllm/models/deepseek_v4_1/common/engram.py`：当 `flagos_bf16_engram=true` 时分配 BF16 分片、不注册 scale 参数，并用独立 Triton kernel 完成 resident/UVA 查表；未命中该标记时保留原 FP8 + E8M0 scale 路径。
- `vllm/models/deepseek_v4/nvidia/ops/o_proj.py`：为 W8A8 `wo_a` 增加分组 Cutlass INT8 路径，按组切分加载后的非连续 `[K,N]` 权重和 scale，复用动态 token INT8 activation quantization 与 `cutlass_scaled_mm`；原 FP8/BF16 路径保持不变。

补丁、原文件和修改后文件位于
`H100-149:/public/flagos/jinghao/deepseekV4.1/02-issues/native-w8a8-bf16-adaptation-20260922/`。
最终统一补丁为 `deepseek-v41-w8a8-bf16-v3.patch`，SHA-256 为 `9dedc5c3fa11b22c175d247e00bc1b845631419df4b75bc1de93d8ca93ab5c85`。

源码基线 → 修改后 SHA-256：

- `vision.py`：`980b219ead4150fa4f0dd7a0d5fd5a41b9e78e4ff2cde7669c080050acffeda2` → `79a2d3959ebe2fc5bd5f5e1c790f3421a3344ac913a52e82e687f9cad7935fc1`
- `engram.py`：`41c5bdf25cf8337088247be768e3d43fa41e6358397800f8b602ebf1ede69480` → `b755a2d953e4877ebdb411282c83f34ef56e8bc9d9071cb2fed73ef0cfbbd77d`
- NVIDIA `vl_model.py`：`ab698e56c83a345ea73e41359cab79b5e484ccfc116ed131347d50cdfe896251` → `80319ea3a6dfa1fd536c46227ba79b89e64a10d4feefd3ca1cba3d6f3eb2f115`
- NVIDIA `o_proj.py`：`542dcb9ca265a6e788b7f061a2e33a2e74ab6f704b089d23ba4034317409406a` → `4acb21d3174b8fc8f6de4055ab6f797caa1a9177264e6786eaa548478d676f4f`

两次中间失败分别保存在 `full-serve/service-v1-char-input-failure.log` 和
`full-serve/service-v2-o-proj-view-failure.log`。容器未停止、重启或移除。原模型服务进程组在切换整模验证前以 SIGTERM 正常退出，记录为
`04-runs/native-w8a8-bf16-adaptation-20260922/full-serve/stop-original-service.json`。

## 验证结果

- 组件回归：通过。5 类代表性视觉 scale、2 个 aligner scale 都可加载，所有运行时 scale 保持 FP32。
- BF16 Engram：HBM resident 与 pinned-host/UVA Triton lookup 均通过，`max_abs_error=0.0`；FP8 weight + uint8 scale 契约仍存在。
- 视觉 dtype 回归：量化权重为 INT8，patch 与输出 embedding 为 BF16，通过；证据为 `components/vision-input-dtype-result.json`。
- 分组 INT8 `o_proj`：在 stride `[1,128]` 的非连续加载后权重上通过，BF16 输出形状 `[9,4,64]`，相对参考实现 `max_abs_error=0.00390625`、`mean_abs_error=0.000749935`；证据为 `components/int8-grouped-o-proj-result.json`。
- 组件原生证据：`H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/native-w8a8-bf16-adaptation-20260922/components/component-result.json`。
- 整模启动：通过。TP8 权重加载耗时 `1915.28s`，每 rank 约占 `66.32 GiB`；vision/text profile、kernel warmup、FlashInfer autotune、PIECEWISE 与 FULL graph capture 均完成，API 已 ready。这里仅记录启动行为，不作为正式 graph acceptance。
- 最小真实推理：通过。`GET /health`、`GET /v1/models`、`POST /v1/chat/completions` 均返回 HTTP 200；确定性请求“17+25”返回内容 `42`，`finish_reason=stop`，请求耗时 `0.943s`。原生结果为 `full-serve/inference-result.json`，运行身份与哈希为 `full-serve/verification-manifest.json`。
- 最终启动脚本：宿主机和容器路径均为 `/public/flagos/jinghao/deepseekV4.1/start-model.sh`，SHA-256 `8eb3e7b6417d6a1cd6ecb8188f7d95eaed7de6112f87f16cf1eafbd87d229ee1`；语法、路径映射和当前服务存活均通过，证据为 `full-serve/root-launcher-verification.json`。
- 验证结束时容器仍为运行状态，`StartedAt=2026-09-22T09:07:42.453119756Z`，说明本次源码适配和验证没有重启容器。

## 限制与下一步

- 当前运行镜像没有 vLLM Git 元数据，因此证据以 wheel 版本、镜像 digest、原文件/补丁/修改后文件哈希绑定。
- 本轮只执行 adaptation 验证，不执行正式 accuracy、performance 或 acceptance summary。
- 当前只验证了单 Host、TP8、`max_model_len=2048` 的文本最小推理；多模态正式正确性、长上下文、正式 accuracy 和 performance 仍需在相应验收阶段执行。

## 经验沉淀

- 可复用范围：带相同 `flagos_bf16_engram` 标记和 compressed-tensors 视觉 W8A8 格式的 DeepSeek V4.1 checkpoint；其他模型需重新核对参数名、分片和 dtype。
- 知识库处理状态：`validated-single-host`；在其他 checkpoint 或 vLLM revision 上复用前仍需重新核对契约并回归。
