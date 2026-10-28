# 013：接入 FlagGems-vllm 的 MoE 与 FlashAttention

## 范围与组件身份

2026-10-09，用户要求基于当前启动脚本，将完整 MoE 与原 vLLM unified
attention 的调用切换到容器已安装的 FlagGems-vllm。本轮是适配阶段的定向验证，
不包含正式 GPQA/ERQA、性能验收或镜像打包。

- Host：`PPU-13`；容器：`minicpmV4.7-35B`，ID
  `145f15078dc1c953d9e136ce595e3185003a6606c28993e30061a2047d3f3653`。
- 宿主和容器批准根均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`；
  `/mnt` 为 RW bind，device:inode 为 `41:14016406509`。
- 模型：`/mnt/cpfs/models/MiniCPM-V-4.7-35B-A3B`，BF16、TP2；
  本轮没有操作另一容器 `minicpmV4.7-ppu` 或其原生 35B/1B 服务。
- Plugin 的实际 editable 安装为 `/workspace/vllm-plugin-FL`，HEAD
  `aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68`，开始时工作树干净。
- FlagGems-vllm 的实际 editable 安装为 `/workspace/FlagGems-vllm`，HEAD
  `31fcc73c76eb41cc003f5890c5faeca24814ba5b`，0.1.0；未修改该库。
- vLLM 0.24.0+empty 的实际导入来自 site-packages，保持只读。
  前后逐文件核对其 1,886 个 Python 文件和 FlagGems-vllm 的 595 个 Python
  文件，均未变化。未使用 `PYTHONPATH` 或另一份源码覆盖安装。

## 旧调用链与接入选择

当前 PPU 的 `PlatformFL` 为 `PlatformEnum.OOT`，`is_cuda()` 返回 False。
旧 `TritonExpertsFL.apply` 因此进入分阶段 MoE，使用 FlagGems 的
`invoke_fused_moe_triton_kernel` 等算子，不能通过修改 NVIDIA fast path 自动切换。
旧默认 attention backend 已在 fresh process 验证为
`vllm.v1.attention.backends.triton_attn.TritonAttentionBackend`。

新调用链：

1. `TritonExpertsFL.apply` 对 PPU 的无量化 FP16/BF16、SiLU、无 LoRA、无 clamp
   输入进入完整融合分支，经 `CachedOp("fused_experts")`、`vendor.thead`，调用
   `flaggems_vllm.fused_experts_impl`。实际 public API 已由库自身 runtime 替换为
   `runtime/backend/_thead/ops/fused_moe.py` 的平头哥实现。
2. attention 经原有 backend dispatch 选择 `TheadGemsVllmAttentionBackend`；
   复用 Plugin 的 FA2 metadata、cache writer 和 out buffer 协议，计算经
   `CachedOp("flash_attn_varlen_func")` 调用库的 public API。
3. 服务只对这三个符号设置 `vendor:thead` 顺序；其他算子不改变策略。
   普通 FlagGems complete-MoE 实现仍注册为 `default.flagos`。

重要限制：当前模型 full-attention 的 `head_dim=256`、dtype BF16。
库内平头哥专用 FlashAttention 接口要求 INT8、head_dim 64/128，并要求相应
block descale。因此本轮 attention 使用 **FlagGems-vllm 自身的通用 BF16 内核**，
不能宣称使用了平头哥 INT8 attention。没有为启用它而改变模型精度或 KV 量化。
GDN 和视觉 MM encoder 保持其原有计算链；本轮替换的是 decoder full-attention。

## 逐文件职责与设计审查

目标 PR base 未由用户指定，本轮不创建 PR、提交或推送。相对已核实的上述 HEAD，
本轮为 7 个 tracked 文件修改和 3 个新文件，没有 inherited dirty diff。
完整 diff 与文件哈希保存在远端 `plugin-switch.patch` 和 `plugin-switch-manifest.json`。
diff SHA-256：`3a0775b910ca5412b9bdaf82bbf41d1cd32d960f4b9d855a16d0fac60e0cf90c`。

| 文件（相对 Plugin 安装目录） | 职责与必要性 |
|---|---|
| `ops/fused_moe/fused_moe_utils.py` | 完整 MoE 进入已有 dispatch；增加受 dtype/量化/激活/LoRA/clamp 限制的 PPU 分支 |
| `dispatch/backends/flaggems/flaggems.py`、`register_ops.py` | 原 FlagGems complete-MoE 的默认注册，保留可选择的原 provider |
| `dispatch/backends/vendor/thead/thead.py`、`register_ops.py` | 厂商能力、计算前拒绝不支持的输入、惰性导入和普通 vendor 注册 |
| `dispatch/backends/vendor/thead/impl/attention_gems_vllm.py` | 复用 FA2 backend，仅指定计算 provider，无模型专属视觉实现或 SDK 全局 patch |
| `dispatch/backends/vendor/thead/impl/__init__.py` | 旧 FA3 导出改为惰性加载；其 eager import 原本会触发 vLLM 0.24 API 不兼容 |
| `dispatch/backends/flaggems/impl/attention.py` | 给 decoder、encoder、DCP、cascade 复用同一计算 hook；默认仍使用原 FlagGems 函数；移除 cascade 调用原本不接受的 `s_aux=None` |
| `tests/unit_tests/dispatch/test_thead_gems_vllm.py` | 注册、可选依赖、能力守卫、默认 attention 选择及未命中新分支的契约 |
| `tests/functional_tests/test_thead_gems_vllm.py` | 实际 MoE、KV 写入、分页 attention、图回放和 cascade 数值检查 |

没有引入新选择框架、绕开 dispatch、复制完整 backend 或吞异常的新增回退。
选择缓存沿用 `CachedOp` 的 policy epoch 失效；只在选择计算 provider 后加载可选库。
未量化以外的 PPU MoE、LoRA、其他激活/clamp/平台路径的守卫未命中测试已通过。
非 PPU 平台默认 attention 选择与可选依赖隔离通过测试；没有其他平台整模运行证据。

## 已验证结果

| 检查 | 结果与实际范围 |
|---|---|
| 库接口直接数值与 graph | 18 项通过：MoE 的 decode、prefill、实际 TP2 expert 形状；dense/paged/mixed BF16 attention，均含两次变输入 replay |
| Plugin 单测 | 17 passed、0 skipped；包含 six-way fast-path miss 与可选 SDK 隔离 |
| Plugin 设备功能测试 | 8 passed，加 cascade 数值 1 passed；真实计算、FP32 参考、新旧 MoE provider 对照和 cache write；KV 页含 16 和实际 544 tokens |
| 隔离整模服务 | GPU6/7、8011、TP2，FULL_AND_PIECEWISE；PIECEWISE 和 FULL decode 各 7/7 图捕获 |
| 隔离服务 HTTP | 35/35 正确且 HTTP 200、finish_reason=stop，含文本/图片/两帧视频各 10 并发；前缀缓存新增命中 4,896 tokens |
| 根级脚本实际启动 | GPU0/1、8010，PIECEWISE 与 FULL decode 各 7/7，默认上下文 262144，显式前缀缓存开启 |
| 主服务 HTTP | 35/35 正确且 HTTP 200、finish_reason=stop，包含相同三类输入各 10 并发；另新增缓存命中 4,896 tokens |
| 实际 provider | 两个 rank 的 startup/first-use 日志均命中 `fused_experts` 与 `flash_attn_varlen_func` 的 `vendor.thead` |

数值检查容差在测试前固定为 `atol=rtol=0.02`，且归一化 RMS 误差必须小于 0.015。
直接算子测试最大归一化 RMS 误差约 0.0044。没有通过修改容差、提取规则或评测参数获得通过。
保留初始接入失败的 XML/日志，后续修复明确解决 OOT 守卫和旧 FA3 eager import。

正式精度、性能、其他模型/平台和 DCP 多 rank 未执行；不能据此声明速度提高、
历史 GPQA/ERQA 分差解决或完整适配验收完成。设计审查在上述范围内可作为 PR 候选，
公开 PR 前仍需维护者确认 base 与补齐声明需要的跨平台验证。

## 启动脚本与原生证据

已更新根级 `start-model.sh`，并在容器内部
`/workspace/model-launchers/MiniCPM-V-4.7-35B-A3B-ppu-flagos/start-model.sh`
放置内容一致的交付副本。两者 0755，SHA-256
`03c096bdd0c7b191544e9a7b733059826d732082d8c03f1589c8650faea23298`；
均通过 `bash -n`，已有 8010 服务时均拒绝启动，未包含自动杀进程逻辑。

脚本使用 GPU0/1、8010、原服务名和黑名单，图规模 `[1,2,4,8,16,32,64]`。
按 remote-operations 交付要求将前缀缓存从用户基线的关闭改为显式开启；
日志位于脚本目录的 `04-runs/service.log`，缓存位于 `06-cache/`。
新增的 provider 选择与缓存路径设置分别用于确定调用实现和约束资源写入位置。
模型权重仍是明确的外部 `/mnt/cpfs/models/` 输入；内部副本不是备用源码 checkout。
未构建新镜像，fresh-image 验证待执行。

全部运行证据位于批准根的 `04-runs/flaggems-vllm-switch-20261009/`，
备份和诊断脚本位于 `02-issues/flaggems-vllm-switch-20261009/`。
重点包括 `baseline.json`、`dispatch-before.json`、`direct-operators.json`、
测试 XML、`service-check-smoke.json`、`unchanged-components.json`、
`launcher-verification.json`、`plugin-switch-manifest.json` 及服务切换记录。

## 最终服务与证据绑定

最终核验为 **2026-10-09 22:28:34 +08:00**。先核实旧 API `2098168` 的命令、
GPU0/1 环境和两次零在途请求，再 TERM 本任务 API，确认其原进程树全部退出。
新 API 为 `2195726`，start tick `427070972`；Worker TP0/TP1 为
`2196774` / `2196775`。实际由已更新的根级脚本启动，主服务测试前后命令与 PID
身份一致，最终 `/health=200`、running/waiting 均为 0。

隔离服务 API `2110845` 和四个关联进程已正常退出，GPU6/7 各降至 1 MiB。
GPU0/1 的主服务保留运行；没有操作其他服务。容器 ID 与
`2026-09-28T07:25:17.93918051Z` 启动时间均未改变。

`final-verification.json` SHA-256：
`9e056fca3cedc6b5844c1849f369b43c6ed62e6cb2682847ad0122caa3a45e0c`。
该文件绑定全部组件核对、代码 diff、两个服务的结果、provider 来源、脚本、
进程身份、容器映射与原生证据哈希。Plugin 的其他基线 Python 文件未变化；
FlagGems 5.3.5 实际安装的两份 split-KV 修复文件哈希仍与 [011](011-flaggems-splitkv-vision-fix.md)
一致。两个启动脚本副本位于已核实的挂载边界内/外，内容相同；镜像验证仍待执行。

本轮算子切换和上述定向回归完成。`framework.yml` 的历史状态和回执未改写，
不替代正式验收。workspace audit 仍返回既有 12 项 profile revision 错误和
78 项需复查的历史材料；本轮没有改写旧证据消除这些错误，也不以布局检查证明远端成功。
