# PPU 算子与适配边界

基线：support-hy4-preview@5329cb1；本次 GLM 扩展仅面向 T-Head PPU。

## 复用与配置

- 模型经 `CachedOp` 调用算子；FlagGems、vendor.thead、reference 在同一 dispatch 层选择。
- MLA prefill 和 sparse attention 复用 HY4 公共 backend，不保留 GLM 重复子类。
- 唯一部署配置是 `vllm_fl/dispatch/config/thead.yaml`，自动读取。
- 默认 blacklist 保持 HY4 的 38 项；GLM 只增加 bounded activation 和 mHC 的 4 个算子顺序。
- GLM cache 兼容 hook 只在 GLM 配置/worker 初始化时安装，普通插件注册不安装它们。

## 必须保留的契约

- KDA：BF16 QKV、FP32 gate/state；已测单 token decode，非连续 state 可选 PPU fallback。
- mHC：保留 Sinkhorn 和 RMSNorm 语义，不替换 HY4 hyperconnection，不全局改写上游 MHC。
- SwiGLU：保留模型训练时的 clamp；未设置 clamp 时维持原有 MoE 路径。
- Indexer：PPU 使用 BF16、32-entry 压缩页和 identity query scale，不等同于 FP8 权重量化。
- KPool/tail：压缩索引页、tail ring、MLA 和 KDA state 的布局不能互换。
- `supports` 按 dtype/shape/layout/capture 元数据排除不兼容实现；有 guard 的调用不缓存跨形状选择。
- 保留显式的运行失败不重试策略，避免部分写入后的重复执行；它不是精度通过的证据。
- pack/unpack 的变长输出依赖设备长度，现有实现只在允许的 eager-break 区间调用。

## 验证边界

PPU 数值与 eager/graph 回归、注册/dispatch 测试保留。CUDA 专属实现与 5 个对应测试用例已归档，不计入 PPU 覆盖。
conditional-generation wrapper/processor 保留以匹配 checkpoint；文本验证不代表图像/视频验证通过。
新权重 `/mnt/cpfs/models/GLM-5.3-Flash` 是 FP8 E4M3 block128 checkpoint，不能沿用旧 BF16 整模结果。
完整整模、精度和性能状态以模型适配工作区的最新记录为准，不以本文件声明验收通过。
