# BF16 重新适配差距清单

目标：PPU-13、`glm5.3-flash`、`/mnt/cpfs/models/GLM-5.3-Flash-BF16`。
基线：ZenithJoyH `support-hy4-preview@5329cb1` clean；vLLM `ee0da84a` 只读。

| 组件/阶段 | 基线差距 | 计划实现位置 | eager/graph 影响 | 验证 |
|---|---|---|---|---|
| 模型注册/配置 | HY4 无 Glm5Next | plugin config/model/processor/registration | 两者 | import、真实 config、权重审计 |
| 34层 KDA | 缺 KDA runner、短卷积、状态缓存 | plugin dispatch + PPU vendor/FlagGems | 两者 | 数值、状态、动态 graph replay |
| 11层 sparse MLA | 零RoPE、indexer、KPool压缩及paged MQA缺口 | plugin公共MLA与GLM KPool adapter | 两者 | prefill/decode、边界、graph replay |
| mHC | 4路 residual 及融合 post/pre 缺口 | plugin FlagGems/reference dispatch | 两者 | FP32 reference、动态输入 |
| MoE | sigmoid noaux router、clamped SwiGLU | plugin FusedMoE/router/activation | 两者 | 路由及clamp专项 |
| 混合cache | 默认布局不识别压缩KPool/KDA状态 | plugin v0.24 config/runner patch | graph关键 | cache shape/copy/capture |
| 服务配置 | 支持1048576，初始按规则50000 | NFS最小启动脚本 | graph | health、最小生成、c8 sanity |

先同步 FlagGems/FlagGems-vllm；已有兼容实现经插件 dispatch 接入，缺失部分才使用 plugin-owned
Triton/portable 实现。禁止绕过插件或修改 vLLM。归档旧实现只作对照，必须在正确 BF16 快照上重测。
