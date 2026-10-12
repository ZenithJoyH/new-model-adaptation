# 007：V4.1 视觉塔调用锁定版 ViT 并行接口失败

## 元数据与签名

- 状态：`resolved`（TP8 第二轮已越过视觉塔；视觉输入尚未验证）
- 首次出现及最后验证：2026-09-23
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- 首错现场：`H100-145` 的 `xingchen4-flagos`；后续目标：`H100-149` 的 `deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、eager、正常前缀缓存、`max_model_len=2048`，尚未进入权重加载

H100-145 首次 TP8 诊断越过前端注册与 Triton 缓存问题后，Worker_TP0
在 `DeepseekV41ForCausalLM.__init__` 构造视觉塔时报
`TypeError: is_vit_use_data_parallel() takes 0 positional arguments but 1 was given`。
原始日志在
`H100-145:/public/flagos/jinghao/deepseekV4.1/04-runs/h100145-eager-20260923/service.log`。
锁定版 vLLM 的 `vllm.model_executor.models.vision.is_vit_use_data_parallel()`
从当前 multimodal config 读取并行模式，签名没有参数；新 V4.1 源原本传入
`config.vision_n_heads`。该值不是锁定版函数的输入，去掉实参符合本版接口。

在用户要求迁移后，先对 H100-145 容器做不暂停的镜像快照并在 H100-149
启动新容器。仅在新容器的 editable Plugin 文件
`/vllm-workspace/vllm-plugin-FL/vllm_fl/models/deepseek_v4_1/nvidia/vl_model.py`
把调用改为 `is_vit_use_data_parallel()`；补丁保存在共享工作根
`02-issues/h100145-ring-20260923/vit-dp-h100149.patch`。变更由源文件 SHA
守卫，`git apply --check` 通过；未修改用户锁定的 vLLM 或其他模型代码。
H100-149 首次 TP8 复试在模型构造时继续失败：
`common/vision.py` 的 VisionAttention、VisionMLP 和 Aligner 还有三处相同的
带参调用，最先在 VisionAttention 报出同一 `TypeError`。随后将这三处统一改为
零参数调用，补丁在 `02-issues/h100145-ring-20260923/vit-dp-common-h100149.patch`；
先校验源文件 SHA-256 `79a2d3959ebe2fc5bd5f5e1c790f3421a3344ac913a52e82e687f9cad7935fc1`，
再通过 `git apply --check`，复查 V4.1 源码中的四处调用均为零参数。第一次服务
自行退出后重启同一 TP8 诊断，日志追加至
`04-runs/h100149-eager-20260923/service.log`。第二轮于 18:06:47 越过视觉塔并
进入第一层注意力构造，随后因独立的 SWA 缓存参数错误退出（见 008）。这验证
本项构造接口已修复；正式数值、图模式和视觉输入均未验证。

知识库处理状态：`local-only`。
