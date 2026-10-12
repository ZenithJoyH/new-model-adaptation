# Qwen-Image-2.1 PPU 适配计划

## 范围

- Host：`PPU-07`；容器：`qwen-image`。
- 权重：只读 `/mnt/cpfs/models/Qwen-Image-2.1`。
- 参考实现：用户提供的固定 Diffusers ZIP，SHA-256 `0f788ee6b453d223903d1bd88bac0a7108d71bf627f2453b44c0409c75ad62f3`，源码提交 `9511e982f22ea8fcc64faf277d90b3a21f8a83f6`。
- 目标只覆盖 Diffusers 脚本 eager 推理支持；不执行正式 acceptance，不声明 graph、精度或性能通过。

## 方案选择

当前失败发生在 Diffusers 解析 `QwenImage21Pipeline` 时。权重还需要专用 DiT 和 VAE，不能通过把 `model_index.json` 改成旧 Qwen-Image 类解决。参考 ZIP 是完整、Apache-2.0 的 Diffusers 0.41.0.dev0 源码；考虑到容器 `torchao 0.11.0` 与部分开发版可选 API 存在代差，选用“stable 0.40.0 + 固定参考实现最小移植”，不向 Torch-FL、FlagGems 或 vLLM 添加模型名分支，也不覆盖整套开发分支。

## 执行顺序

1. 保存 Diffusers 0.40.0 安装身份、包清单和可恢复归档；记录基线 `pip check`。
2. 下载官方 stable 0.40.0 wheel，在工作根临时目录仅加入 Qwen-Image-2.1 的 pipeline、DiT、VAE 和必要注册项；安装使用 `--no-deps`。
3. fresh process 验证 `QwenImage21Pipeline`、`QwenImage21Transformer2DModel`、`AutoencoderKLQwenImage21` 以及旧 `QwenImagePipeline` 均可导入。
4. 验证 `DiffusionPipeline.from_pretrained` 能解析本地权重并完成组件加载。
5. PPU 空闲后按最窄到最宽顺序验证：低分辨率 latent-only 1 step；2-step KV cache on/off；低分辨率 VAE/PIL；参考默认 40-step no-CFG；50-step CFG 仅作为显式覆盖配置验证。
6. 对 `slice.Tensor` complex64 先保留无回退负对照；若复现已知 FlagGems 断言，只使用 `FLAGOS_OP_slice__Tensor=cuda` 的进程级、单算子回退，并保留退出条件。

## 影响矩阵

| 路径 | 预期影响 | 验证 |
|---|---|---|
| Qwen-Image-2.1 | 获得专用 Pipeline/DiT/VAE | 导入、权重加载、逐级设备推理 |
| Qwen-Image-2512 | 继续使用 `QwenImagePipeline` | 旧类导入；资源允许时最小回归 |
| Torch-FL dispatch | 不改源码和默认 policy | Git tree 前后 clean；运行时仅允许精确单算子回退 |
| FlagGems | 不改源码 | Git tree 前后 clean；若需算子集成则停止并先同步/记录 |
| vLLM | 不属于本模型执行链 | 包和进程只读，不修改、不停止 |

## 停止与回滚条件

- 安装引入依赖升级/降级、覆盖 PyTorch/Transformers/Torch-FL 或扩大 `pip check` 错误时立即停止并回滚。
- 旧 `QwenImagePipeline` 导入失败时立即回滚。
- PPU 被无关任务占用时不启动模型、不停止进程，保留安装级验证并等待资源。
- 发生 OOM、设备错误或非 `slice.Tensor complex64` 的异常时不做宽泛 fallback，记录第一处失败并逐项分析。

## 当前资源约束

2026-09-17 20:41，16 张 PPU 全部被无关 `VLLM::Worker_TP*` 占用。当前只能进行安装和无设备验证，设备推理步骤暂缓。
