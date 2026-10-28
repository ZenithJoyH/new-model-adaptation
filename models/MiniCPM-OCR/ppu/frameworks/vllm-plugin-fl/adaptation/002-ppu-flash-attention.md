# 002：FlagOS 中启用平头哥 Flash Attention

2026-10-27，用户要求在现有 PPU FlagOS 环境使用平头哥 Flash Attention。目标为 PPU-01 / minicpm-ocr，工作根 `/mnt/nfs/users/jinghao/MiniCPM-OCR`；Host/container 映射已核验为相同 dev:inode `41:5457325353`。原 8011/9999 服务保留，在空闲 PPU5 使用独立实例验证。当前为适配验证，不签发正式框架验收。

## 基线及改前限定计划

实际安装 Plugin `/workspace/vllm-plugin-FL`，HEAD `06014201f8ea8cd7092a56a945d8fc7998c5a46c`；继承 dirty diff SHA `52aee2ba258189339f395aa566c88b661c3b0d369defceeaae8f0272eb1aa0bc`，既有改动保持。vLLM 0.24.0+empty、Torch 2.10.0、厂商 FA2 2.7.4.post1 和 FA3 3.0.0b1 已安装，不升级或替换依赖。

已通过现有 `VLLM_FL_PER_OP=attention_backend=vendor:thead` 选中厂商后端；预检在导入时失败，原因是适配器引用 vLLM 0.24 已不存在的 `flash_attn_supports_fp8`。FA3 扩展加载成功。失败保留在 `04-runs/flagos-ppu-flash-20261027/preflight.log`，未启动模型服务。

修改限定为 Plugin：

| 文件/符号 | 计划变更与必要性 | 验证 |
|---|---|---|
| `vllm_fl/dispatch/backends/vendor/thead/impl/attention.py` | 删除经引用核查未使用且导致导入失败的 fa_utils 兼容旧导入；支持当前 backend 能力检查新增的 use_mm_prefix 参数，并对 FA3 不支持的能力明确拒绝。保留现有厂商路由和实际 FA3 调用。 | fresh-process 导入、能力边界、实际 BF16 eager/graph 数值与模型请求 |
| `vllm_fl/attention/utils.py` / `_patched_maybe_get_vit_flash_attn_backend` | vLLM 的非 CUDA 扩展 stub 可能提供 None 函数；仅在预检证实后将非 callable 情形交给已安装 flash_attn 的既有 fallback，避免选中 FLASH_ATTN 后返回 None。 | 导入边界用例，已安装视觉 Flash Attention 实际执行 |
| Plugin 现有单元/功能测试 | 在现有体系加入上述能力/导入边界及目标硬件数值/graph 回归；不把 mock 选择测试当作设备计算正确的证据。 | 运行聚焦测试与明确记录跳过项 |

不改 vLLM、FlagGems、FlagGems-vllm、权重、驱动、全局 thead 默认配置或现有启动脚本；不检查/整合新 FlagGems 算子，不进行仓库升级。无另建 checkout 或 PYTHONPATH 覆盖。只通过现有单算子 policy 选择厂商语言注意力，并在本实例显式选择视觉 FLASH_ATTN。配置、一次性诊断和原始结果位于本工作根标准目录。

源码中未发现适用 AGENTS.md 或 CONTRIBUTING.md；已读取当前 dispatch/config/policy、厂商实现及调用方，并遵循本仓库 contribution policy。现有其他平台导入及非厂商路径须保持隔离。若实测需要扩大修复，先记录失败及新增限定范围。

## 当前状态

首次语言适配器导入修复后已能导入；第二次预检脚本误用 vLLM 旧视觉函数名，作为测试程序错误保留，不算新的产品失败。

进一步源码核对发现 vLLM 0.24 已把视觉计算移到 `vit_attn_wrappers`；旧 Plugin 写入的 `maybe_get_vit_flash_attn_backend` 属性在当前版本没有调用方。同时 PlatformFL.is_cuda() 对 thead 返回 False，既有 NVIDIA OOT hook 不覆盖 PPU，选中 FLASH_ATTN 仍可能走 forward_native 的 SDPA。改前范围据此修订：

- 保留旧版本视觉 hook，避免影响其他版本/平台；不删除现有逻辑。
- 新增 Plugin 厂商叶子实现 `vllm_fl/dispatch/backends/vendor/thead/mm_encoder_attention.py`，经已有 `patch_mm_encoder_attention()` 的 thead 分支连接 `MMEncoderAttention.forward_oot`。放在不触发 `impl/__init__.py` 的厂商模块，避免视觉初始化提前导入语言侧 FA3 SDK。仅 FLASH_ATTN 自注意力进入已安装 PPU FA2，SDPA 和非目标后端保持原 native 路径；跨注意力保持原处理。
- 不覆盖 vLLM 文件或通用 fa_utils 全局函数，不影响语言侧 FA3 命名空间。新增相应厂商单元/硬件功能测试，真实执行数值与变输入 graph replay；视觉动态 max_seqlen 的捕获能力按实测披露，不声称新增整段视觉图支持。

最终状态：独立 PPU5/8015 实例已就绪并保持运行，真实图像请求后有 FA2 调用证据，语言使用 vendor.thead FA3。6 个冻结 OCR 案例全部完整且逐字匹配，57 项聚焦测试通过。未重跑三场景性能、全量精度或正式框架验收。见[功能验证与启动说明](../acceptance/004-ppu-flash-attention.md)。

第一次真实模型启动已进入 decode FULL 捕获，失败于 vLLM 0.24 新传入的 `dynamic_causal` 参数，原厂商 wrapper 尚未接收。调用方核查还包含 `mask_mod`、`aux_tensors`。新增限定修复：同一 FA3 wrapper 显式接受三者默认 None，非 None（需要 FA4 的逐序列 causal/自定义 mask 模式）明确拒绝；不吞任意 kwargs。新增当前调用签名的真实设备 paged decode 回归和拒绝边界。保留失败 run，修复后新建模型启动 run，不覆盖旧启动结果。

第二次模型已完成图捕获并启动 API，但控制器在发出图像请求之前要求出现 FA2 调用日志，因此未通过该检查并停止本次实例。曾假设 `custom_ops=["none", ...]` 禁用了该层，后经实际配置实例及源码核对否定：MMEncoderAttention.enabled() 固定返回 True。额外 `+mm_encoder_attn` 参数撤回；错误假设、测试程序语法错误及错误负对照结果均保留。新增真实全局 none 配置下视觉仍执行 FA2 的正回归；模型运行核验改在真实图像请求后检查调用证据，不能把缺失启动日志直接判为禁用。

## 最终增量审查

仅修改 Plugin 两个已有源文件，新增一个厂商视觉叶子模块和一个测试模块；无删除文件、全局策略修改或模型路径特例。四处 diff 均对应上述导入、调用协议和实际路由缺口，未使用任意 kwargs、吞并异常、第二份源码或 PYTHONPATH。

厂商 SDK 在相关路径选择后导入；旧视觉 hook 和其他平台分支保留。FA3 显式拒绝需要 FA4 的新特性；视觉只接入 FP16/BF16 自注意力，其他 dtype/后端和跨注意力保持原 native 路由。57 项测试覆盖目标 PPU/BF16、数值、变输入图回放及路由边界；其他模型、其他平台硬件和整段动态视觉图未实测。

继承 dirty diff 逐字节保持，vLLM checkout/安装 Python 文件集合及 FlagGems、FlagGems-vllm 身份均未变。实际最终补丁在 `02-issues/flagos-ppu-flash-20261027/task-source-final.patch`，SHA-256 `6082ff5c6c3673bf8b02e8876743cdb7dde82b7d096e6c5241f31ce88d0b2601`；审查清单和文件 SHA 在 `04-runs/flagos-ppu-flash-20261027/source-final.json`。未确认上游 PR base，未 commit/push/创建 PR，不声称完整上游或多平台验收完成。
