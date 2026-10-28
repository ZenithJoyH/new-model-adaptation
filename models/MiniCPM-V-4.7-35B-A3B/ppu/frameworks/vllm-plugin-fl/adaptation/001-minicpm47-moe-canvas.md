# 001：MiniCPM-V 4.7 注册、MoE 骨干与 canvas M-RoPE

## 元数据与签名

- 日期：2026-09-28 至 2026-09-29；状态：`implemented`，正式验收待完成。
- Host / 容器：`PPU-13` / `minicpmV4.7-35B`；镜像 ID 与组件修订见[环境分析](../environment/README.md)。
- 模型：`/mnt/cpfs/models/MiniCPM-V-4.7/weights/35b-a3b`，配置 SHA-256
  `3973e7ad0bd9f96887341cb134173118b0e445695014a73e736de48e9a9b5646`。
- 基线：Plugin 只有 Qwen3.5 文本兼容 shim，vLLM registry 只有 MiniCPM-V 4.6。
  4.6 的稠密文本骨干和顺序位置与 4.7 的 256 专家 MoE、canvas 位置不符。

## 归属与实现

Plugin 可编辑源码 `/workspace/vllm-plugin-FL` 基准 HEAD
`3a27a6fb2d514cdf55c00481bf813225dac63319` 且初始干净。
现有入口 `vllm_fl.register_model()` 用 lazy registry 路径；新增
`vllm_fl.models.minicpmv4_7` 模型类，仅登记 4.7 架构。该类复用 vLLM 4.6
视觉处理与 embedding 接口，改由已有 `Qwen3_5MoeForCausalLM` 构建文本，
从权重自带的模块调用 canvas 位置算法。vLLM 安装及源码均未修改。
4.6、Qwen3.5 和其他模型的注册名不变，registry 未命中继续走原有路径。
若需要处理器缓存命中时的视觉尺寸，须另行设计可保留元数据的路径；当前
`--mm-processor-cache-gb 0` 是已知前置条件，缺失尺寸时明确报错而非静默退回顺序位置。

## 受控检查

| 顺序 | 唯一变量 / 核查 | 结果 |
| --- | --- | --- |
| 1 | 4.7 `AutoConfig` 与 `AutoProcessor`，只读权重，缓存限于工作根 | `MiniCPMV4_7Config`、`Qwen3_5MoeTextConfig` 和 4.7 图像/视频处理器均成功导入。 |
| 2 | 新增独立注册与模型专用模块 | Plugin 正式入口将 `MiniCPMV4_7ForConditionalGeneration` 解析到 `vllm_fl.models.minicpmv4_7`；实际导入成功。 |
| 3 | canvas 位置 CPU 合成输入 | `02-issues/check_minicpm_positions.py` 对文本、单图、图像加视频的三通道位置逐项等于 checkpoint 参考算法；缺失视觉尺寸明确拒绝。 |
| 4 | decode delta 对照 | 初版直接返回权重函数 delta：纯文本为 -1；核对 vLLM 的 `max(position)+1-prompt_length` 合同后，仅加 1。相同三例复测为 0、-1、-2；源模块 SHA-256 `910c551d4f2694534c7f8046842781ac6a48020c5c4ce7b94c59d7a89e011b61`。 |

一次性安装与对照代码保存在工作根的 `02-issues/`；中间待验模块放在
`05-tmp/`，正式产品实现仅在上述 editable Plugin 内。
初始 eager TP2 配置及加载日志路径见环境分析。17 个 shard 已加载，服务
`/health`、`/v1/models` 均通过。纯文本最小请求返回 `42` 且正常停止，结果
`04-runs/eager-tp2-v1/text-smoke.json`；图像最小请求输出 128 个 `!`，
见[002 问题](002-visual-garbage.md)。

## 后续验证与审查

产品候选在 eager 下完成文本、红/蓝单图最小推理；graph 请求 `FULL` 时受
GDN 限制自动降为 `FULL_DECODE_ONLY`，decode 图 4/4 捕获，文本、红/蓝单图、
双图和红蓝两帧视频均返回预期答案且正常停止，见[004](004-gdn-full-graph-limit.md)。
旧轮次只提供诊断：其前缀缓存生效为关闭，违反非性能阶段前置条件。
2026-09-29 新 eager/graph 服务显式开启缓存，EngineCore 生效值均为 `True`；
相同文本与红/蓝单图在两模式重新正确，graph 的双图和两帧视频也正确。
新图实例再次因 GDN 从 `FULL` 降至 `FULL_DECODE_ONLY`，捕获 4/4；
证据见[004](004-gdn-full-graph-limit.md)和[005](005-prefix-cache-effective-default.md)。
这些最小请求仍不证明高分辨率切片、长上下文、十并发与正式精度/性能。
FlagGems 未获单独同步授权，未作源码同步或算子覆盖结论。

2026-09-29 审查实际 Plugin 工作树：本地可见 PR 基线 `origin/main` 与
`HEAD` 同为 `3a27a6fb2d514cdf55c00481bf813225dac63319`；初始干净，
当前仅 `vllm_fl/__init__.py` 修改，以及
`vllm_fl/models/minicpmv4_7.py`、
`vllm_fl/dispatch/backends/vendor/thead/vision_attention.py`、
`tests/unit_tests/dispatch/test_thead_vision_attention.py` 三个未跟踪文件。
四文件 SHA-256 依次为
`27670060ca2a66b2f339ea54f542132765ac9f1b1cc09f321c384fd0204ebaa9`、
`31fbd56b0b92c4ef5d702e64d9fadb131b489b0bf3a30b9175b7a13bfd8c7759`、
`0fba92cd39a34f202befc808c2f421e6b23e5f68866c71a0e70224e7e748c3db`、
`2310f409f3e760550c7c51bafcc2d98d99749d09e6be82264a70ca8df8338388`。
`git diff --check` 通过；`/workspace/vllm` 与 `/workspace/FlagGems` 的
`git status --short` 均为空。未提交、推送或创建 PR。

影响矩阵：注册只增加 4.7 架构名，4.6/其他模型的 miss path 仍走原有 registry；
模型适配器的 MoE 和 canvas 逻辑只在 4.7 类内，视觉 FP32 helper 只在
`current_platform.vendor_name == "thead"` 且窗口 merger 后的层绑定；非平头哥
路径保留 vLLM 原实现。data 模式加载标记仅在 `load_weights` 期间更改并由
`finally` 恢复，非 data 模式直接调用父实现。替代方案为修改 vLLM 全局
`MMEncoderAttention`/loader 或把模型特例放入共享执行路径；这些路径会扩大
影响范围，也违反此 profile 的 vLLM 只读边界。

测试证据：平头哥视觉 helper 的 4 个 CPU 合成数值对照（长度 5/133，带/不带
mask）全部通过，检查 BF16 输出、FP32 参考与重复绑定幂等；真实 PPU 服务
缓存开启的 eager 与 decode-full 上述请求通过，四个 Plugin 文件的身份与
本次审查时相同。其他模型在 PPU 上未运行回归；
NVIDIA 平台上的本候选未实测。新轮次冷红图 graph 延迟 219.513 秒，属于待正式
性能验收的限制；`--mm-processor-cache-gb 0` 仍是 canvas 元数据正确性前置。
