# 参考与来源

- 实际模型配置、权重索引与模型卡：/mnt/cpfs/models/Qwen3.8-Flash-Next，摘要见architecture文档。
- 模型代码： https://github.com/ZenithJoyH/vllm-plugin-FL/tree/2b2fe95e2e4a92b9d0f94f0ed9c0104b7e591025 ，branch support-qwen3.8-flash；对应 vLLM0.24，已有组件验证但没有此分支整模验收，不能复用通过状态。
- 克隆分析命令：git clone --depth 1 --single-branch --branch support-qwen3.8-flash https://github.com/ZenithJoyH/vllm-plugin-FL.git /tmp/qwen38-plugin-reference-20260904。
- 2026-09-04查询 git ls-remote --heads 显示该分支HEAD为上述commit；当前HY4和GLM分支作为镜像历史，只读保留。
- 官方说明 https://github.com/QwenLM/Qwen3.8-Flash-Next 与 https://recipes.vllm.ai/Qwen/Qwen3.8-Flash-Next 。官方新版vLLM方案不等于当前PPU0.24已支持；本轮不升级受保护vLLM。
- PPU-01旧容器仅只读核对来源，未启动/停止或更改；共享qwen3.8-flash顶层目录无可用启动脚本。
