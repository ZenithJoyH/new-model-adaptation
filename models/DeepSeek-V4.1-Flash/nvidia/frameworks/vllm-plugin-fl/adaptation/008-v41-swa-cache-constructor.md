# 008：锁定版 V4 SWA 缓存缺少 V4.1 页大小与 backend 参数

## 元数据与现象

- 状态：`resolved`（TP8 第三轮越过缓存构造；运行期映射待验证）
- 首次出现及最后验证：2026-09-23
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- Host / 容器：`H100-149` / `deepseek-v41-plugin-adapt-20260923`
- Plugin / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8、eager、前缀缓存启用、`max_model_len=2048`

第二轮整模启动已越过视觉塔，但各 worker 在第一层注意力构造时统一报
`TypeError: DeepseekV4SWACache.__init__() got an unexpected keyword argument 'backend_cls'`。
原始日志为 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-eager-20260923/service.log`
中 18:06:47 的 traceback。它发生在权重加载之前。

## 诊断、根因与受控修复

锁定版 vLLM 的 `DeepseekV4SWACache` 构造函数只收 `head_dim`、
`window_size`、`dtype`、`prefix`、`cache_config`，内部固定 64-token 页和 V4
SWA backend。作为只读参考，H100-149 原生 V4.1 容器中的新版函数接受
`backend_cls` 与 `block_size`，Plugin 调用要求 32-token 页和 FlashMLA SWA
metadata backend。因此直接删掉两个实参会改变 V4.1 缓存规格与调度语义。

本次仅在 V4.1 模型的 Plugin `attention.py` 中增加 `DeepseekV41SWACache`：
继承锁定版的注册与缓存规格逻辑，再固定 32-token 页并覆写 backend 选择。
其他模型仍调用原版 V4 类；V4.1 的其他平台/backend 尚未验证。变更前源文件
SHA-256 `4717620c2146d3963deabfbb3550c20bbdbc325d019730ab72c7ca6813cd676c`，
补丁在远端
`02-issues/h100145-ring-20260923/v41-swa-cache-h100149.patch`，
`git apply --check` 通过；第三轮 TP8 服务已重新启动。此改动属于模型缓存接口
适配，不涉及缺失算子；FlagGems-vllm/FlagGems 算子复用另见 002、005。

## 验证与限制

- 基线：第二轮 TP8 在构造阶段因 `backend_cls` 拒收而失败。
- 变化：只替换 V4.1 SWA 缓存构造类，启动参数、镜像、权重和编译缓存位置不变。
- 复试：第三轮于 18:15:07 越过缓存构造，随后因独立的可选 JIT 预热配置
  属性缺失退出（见 009）；eager 数值、graph、性能均未验证。
- vLLM 保持锁定且源码未改；Plugin 实际 diff 与运行期缓存映射仍需审查。
- 知识库处理状态：`local-only`。
