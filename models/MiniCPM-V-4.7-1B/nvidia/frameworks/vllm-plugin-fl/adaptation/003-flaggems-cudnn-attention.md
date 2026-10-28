# 003：视觉编码器初始化触发 FlagGems cuDNN attention CUDA 错误

## 元数据

- 状态：`verified`（广播 mask 寻址根因已复现并修复；整模去黑名单复验未执行）
- 首次出现/最后验证：2026-09-28 / 2026-10-08
- 模型/平台/Host/容器：`/data/models/MiniCPM-V-4.7/weights/1b` / NVIDIA H100 / `H100-149` / `MinicpmV4.7-1B`
- Plugin / FlagGems / vLLM：`3a27a6fb2d514cdf55c00481bf813225dac63319` 加未提交的 4.7 shim / `da6727e38f6f8eedef6cba43695a87b4996f9eca` / wheel `0.24.0+cu129`
- 模式与负载：单卡 eager 和 decode-full，`CUDA_VISIBLE_DEVICES=1`，`max_model_len=50000`，正常启用 prefix caching；首次视觉 dummy/profile 路径

## 现象及原始证据

整模权重加载后，vLLM 初始化视觉编码器的 `F.scaled_dot_product_attention` 路径
首先进入 FlagGems `_scaled_dot_product_cudnn_attention`，在 CUDA 同步诊断下报
`Triton Error [CUDA]: illegal memory access`。过滤该算子后，又进入 FlagGems
`cudnn_attention_forward` 并出现相同错误。前者在同步运行中定位到首次异常；
未同步运行的随后 `addmm` 栈只是异步观察点，不能作为根因。

原始日志在 Host 与容器一致的
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/04-runs/` 下，对应
`eager-text-*20260928/run.log`。通过运行配置环境变量
`VLLM_FL_FLAGOS_BLACKLIST_APPEND=_scaled_dot_product_cudnn_attention,cudnn_attention_forward`
过滤这两个 FlagGems 注册函数后，`eager-text-cudnn-filter-v8-20260928/run.log`
产生中文回复，退出码 0，日志 SHA-256
`1b95f296504fd43822c6f7d521c4582c2ca15ff95baf13e43862387683e2cd55`。
运行时 op-list 也在同一 run 目录内。此规避只在指定进程生效，
已写入最终服务启动脚本并在实际服务的文本、图片及十并发功能检查中验证，
详见 [功能与服务验证](../acceptance/functional-validation.md)。

## 已有经验及受控尝试

`docs/troubleshooting/` 中的 TP `sample_tokens` timeout 和 full-graph 条目没有
相同的首次失败组件、负载和错误签名，不套用其处理步骤。

| 轮次 | 关键变量 | 结果 |
|---|---|---|
| eager-text-v2 | 首次整模 eager，GPU0 | 权重成功加载；视觉 profile 中 CUDA illegal memory access；其后 GPU0 被其他容器占用。 |
| eager-text-v3 | GPU1，其他配置同前 | 错误仍在；异步栈指向后续 `addmm`。 |
| eager-text-v4 | 增加 `CUDA_LAUNCH_BLOCKING=1` | 首次失败定位到 `_scaled_dot_product_cudnn_attention`。 |
| eager-text-v5 | 仅过滤 `_scaled_dot_product_cudnn_attention` | 转为 `cudnn_attention_forward` 首次失败。 |
| eager-text-v6 | 第二过滤值使用 ATen key `_cudnn_attention_forward` | 未生效；FlagGems config filter 实际比较注册函数名。 |
| eager-text-v7 | 改为函数名 `cudnn_attention_forward` | 越过此前错误，完成引擎初始化；300 秒诊断时限在生成开始后到期。 |
| eager-text-v8 | 去掉同步调试开关，保留两个过滤值，600 秒上限 | 文本单请求 16 token 推理成功；正常 prefix caching。 |

此前第一次脚本缺少 Python `__main__` guard，导致 spawn 重入；精确终止仅由本次
脚本启动的容器内 PID 1105，确认其退出，未停止适配容器或其他服务。

## 2026-09-28 历史诊断、Workaround 与当时待验证范围

已验证的仅是此权重、此 H100 栈的进程级规避；尚无独立最小算子用例，不能断言
FlagGems 内核本身的具体根因，也不能将过滤扩大为全平台默认。FlagGems 已获授权
同步到上述 revision，源码没有因本问题修改。Plugin 产品代码只包含模型专用 shim，
这个过滤项当前位于工作根的运行配置和最终 `start-model.sh`，
未改动 FlagGems 全局源码或公共 Plugin dispatch。

下一步应在 `07-bugs/003-flaggems-cudnn-attention/` 提取相同 dtype、shape、stride、
mask、设备与调用顺序的最小复现，与原生 PyTorch 路径进行受控比较；
图片/视频与 decode-full 功能已在规避下通过，但仍须验证数值输出、延迟影响，
并确定可维护修复或受限规避及其退出条件。
最终 launcher 暂时保留该进程级过滤以启动视觉路径；具体依据和服务验证见
[功能报告](../acceptance/functional-validation.md)。正式精度和性能仍需在同样的
有效服务配置下验证，取得根因修复后应移除此过滤并重新测试。

以上为 2026-09-28 的历史判断，最新复现和修复见下节。

## 2026-10-08：独立复现与根因修复

本次范围仅为两个黑名单算子的复现、FlagGems 修复和上游贡献，不执行正式精度、
性能或整模服务重启。现有服务 PID 19200 / EngineCore 19405 保持运行；检查
`http://127.0.0.1:8001/v1/models` 返回 HTTP 200。

### 身份、源码与执行边界

- Host / 容器仍为 `H100-149` / `MinicpmV4.7-1B`，容器 ID
  `4642fce472209069ab927e6bf6af7bc1ccb3443f2fa85d4a6f76b65e92a5c637`。
- Host 与容器工作根均为 `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`；
  `/public` bind mount 与根目录 inode `45:232972481026` 已重新核实。
- 镜像 ID：`sha256:d0af16489bc171d5434fc225c7afd89d32da7946af53655b9ad6dc7b50c745ca`。
- 已安装 editable FlagGems 实际导入
  `/vllm-workspace/FlagGems/src/flag_gems/__init__.py`，解释器 `/usr/bin/python3`；
  未使用 `PYTHONPATH` 或其他导入覆盖。
- 原 checkout `master` 跟踪 `origin/master`、工作树干净；按已有授权执行 fetch 与
  fast-forward-only pull，从 `da6727e38f6f8eedef6cba43695a87b4996f9eca` 同步到
  `0dddb4628ae215931171a7f6e04a1183777dcd8a`。GitHub 直连 DNS 失败后使用已授权代理，
  凭据任务设 `no_log`，未写入源码或运行产物。
- H100 80GB HBM3、driver 580.105.08、Python 3.12、PyTorch 2.11.0+cu129、
  CUDA 12.9、cuDNN 91701、Triton 3.6.0；复现进程限定 GPU1。
- Plugin HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319` 的原有三项 dirty/untracked
  保持不变；FlagGems-vllm `e13419a429bfba65f4757a7671b1aebfe25c61a2` 仍干净。
  vLLM wheel `0.24.0+cu129` 只读，本轮没有修改 Plugin、vLLM、权重或启动脚本。

### 最小复现与对照

Host 与容器相同的用例目录：
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/07-bugs/003-flaggems-cudnn-attention/`。
脚本 `repro.py` 在此处原位执行；未使用 `/bug`、额外源码副本或模型服务依赖。
原始结果在同一工作根 `04-runs/attention-repro-20261008/`。

固定 seed 42、BF16，QKV 模拟视觉投影的 chunk/view/transpose，
Q/K/V 形状 `[2,16,S,72]`，stride 为 `(S*3456,72,3456,1)`；
mask `[2,1,1,S]`，stride `(S,S,S,1)`，内容为 0 和 BF16 最小有限值。
原生 cuDNN 与 PyTorch MATH SDPA 作数值对照；每个故障用例使用独立进程。
在容器用例目录执行：

```sh
CUDA_VISIBLE_DEVICES=1 CUDA_LAUNCH_BLOCKING=1 python3 -B repro.py --op native --seq 1024
CUDA_VISIBLE_DEVICES=1 CUDA_LAUNCH_BLOCKING=1 python3 -B repro.py --op scaled --seq 1024
CUDA_VISIBLE_DEVICES=1 CUDA_LAUNCH_BLOCKING=1 python3 -B repro.py --op cudnn --seq 1024
```

诊断命令还将 `TRITON_CACHE_DIR`、`XDG_CACHE_HOME` 分别指向工作根
`06-cache/triton`、`06-cache/xdg`；这是复现过程配置，不新增服务启动参数。

| 唯一变量 / 路径 | 修复前结果 |
|---|---|
| 原生 cuDNN，紧凑 mask，S=1024 | 通过，max abs 0.001953125。 |
| FlagGems 两个入口分别执行，紧凑 mask，S=1024 | 均在共用 `_attn_fwd` 报 CUDA illegal memory access。 |
| FlagGems 两个入口，紧凑 mask，S=128 | 均数值失败，81.6% 元素超过 atol=rtol=0.02，max abs 0.9609375。 |
| 仅将同一 mask expand 后 contiguous，S=128 | 两个入口均通过，max abs 0.00390625。 |
| 新增维护用例先在旧实现运行 | FP16 padding mask 用例失败，94.9% 元素超容差，max abs 2.118684。 |

具体证据分别是 `native-broadcast-1024.log`、`scaled-broadcast-1024.log`、
`cudnn-broadcast-1024.log`、`*-broadcast.log`、`*-expanded.log` 和
`regression-before.log`。S=1024 已重现历史 CUDA 首故障签名，S=128 说明同一寻址错误
也可能只表现为错误数值，不能依赖“没有崩溃”判断正确。

### 根因、职责与设计审查

MiniCPM 视觉路径在 `minicpmv4_6.py` 构造 `[B,1,1,S_k]` additive mask，
由 `idefics2_vision_model.py` 的 SDPA 进入两个注册入口。它们均复用
`scaled_dot_product_attention_forward`，后者此前直接传入 mask 的原始四个 stride。
内核按 head/query 索引完整 `[B,H_q,S_q,S_k]` 矩阵，size=1 的轴却未置零 stride，
导致越界 mask 读取。显式展开对照和只修正 stride 的回归共同确认了该根因。

产品修复直接落在容器已安装的
`/vllm-workspace/FlagGems/src/flag_gems/ops/attention.py`，复用现有
`flag_gems.utils.shape_utils.broadcasted_stride` 按目标 attention shape 计算 stride。
不分配完整二次方 mask，不新增设备 SDK、主机同步或模型/机器特判。
无 mask 分支保持原实现；合法完整 mask 的 stride 保持原值。
替代方案是调用方展开 mask 或继续过滤，两者都不能在共用入口修复寻址契约。

PR base 已确认是上游 `master@0dddb4628ae215931171a7f6e04a1183777dcd8a`；
本轮开始时 FlagGems 无 inherited diff。完整候选差异仅两个文件：

| 文件 / blob SHA | 职责 |
|---|---|
| `src/flag_gems/ops/attention.py` / `8a4f1a52406c861bb8e43a937580d28ce0a73b11` | 13 行增加、4 行删除；共用 forward 入口广播寻址。 |
| `tests/test_attention_mask_broadcast.py` / `577b08fa109b0a76226666d62441c56dadf5392b` | 维护用例；显式调用 public FlagGems API，覆盖两个 cuDNN wrapper 与共享 SDPA/GQA。 |

真实 checkout 的 blob 与提交候选一致，`git diff --check` 通过。
影响面为这些公共 forward 调用方；其他平台硬件、backward、LSE、dropout 和任意有限
additive bias 的其他数值语义不在本修复验证范围。设计审查结论是可作为上述范围的 PR 候选，
不代表完整模型适配或多平台验收通过。

### 已验证结果与待办

`regression-after.log`：54 项通过（48 项 eager、6 项 graph），覆盖 FP16/BF16、
65/97 的非整 tile 长度、head_dim=72、连续/非连续 QKV、带 stride=2 的 mask、
padding/batch/二维/已展开 mask。每项 graph 检查 warmup、capture 及两次变更 QKV/mask
后的 replay。`gqa-after.log` 另有 2 项通过，新增测试共 56 项均已执行；
`existing-nomask-after.log` 记录原有 4 项无 mask 用例通过。
`after-scaled-1024-graph.log`、`after-cudnn-1024-graph.log` 分别记录原崩溃用例
修复后 eager 与两次变输入 graph replay 通过，eager max abs 均为 0.001953125。
`after-scaled-none.log`、`after-cudnn-none.log` 的独立无 mask 对照也通过。

上游 issue：[FlagGems #6869](https://github.com/flagos-ai/FlagGems/issues/6869)。
上游 PR：[FlagGems #6871](https://github.com/flagos-ai/FlagGems/pull/6871)，
包含 `Fixes #6869`，待合并后关闭 issue；提交
`f76b5503e694660aa3586a520428f527a4cd0032`，分支
`ZenithJoyH:fix/attention-broadcast-mask-6869`，相对 base 为一个提交、两个文件，
136 行增加、4 行删除。提交通过 GitHub connector 建立，容器实际安装仍是
`master@0dddb4628ae215931171a7f6e04a1183777dcd8a` 加这两个完全同 blob 的本轮差异，
未重写现有 checkout 历史。上游 CI 已启动，尚不记通过。

用例目录中的 `README.md`、`manifest-20261008.json` 记录运行方法、环境、PR identity
及日志/源码/测试的 SHA-256；manifest SHA-256
`701662eb44d127ddc3b01bc88a3b375f4489a104948e6982317c764f8a9181da`，
repro.py SHA-256 `41d8154f73e90109827f86bd6b847f7081e6bfd5a0f26e1e897e48572ca2067e`。
未将完整日志或脚本复制进本地模型目录。
本轮不移除现有服务黑名单；退出条件是修复在目标安装中生效后，
以去过滤配置重新进行整模 eager/graph、图片/视频及后续精度检查。
未测整模性能或镜像打包，不宣称这些结果已通过。

知识库处理：`local-only`；本轮按请求将可复现证据提交上游，不扩展维护公共知识库。

### PR #6871 CI 修正（2026-10-08）

首轮 CI `37718565781` 中，新增 56 项测试全部通过，但 `tools/test-op.sh`
根据 `src/flag_gems/ops/attention.py` 推导出 `attention` 标记；新增文件只有
各公共入口的标记，导致随后 `pytest tests/ -m attention` 选中 0 项并失败。
`unittest-required` 是该失败的汇总结果，并非第二个独立问题。

在已核实的同一容器安装中，为测试模块增加 `pytestmark = pytest.mark.attention`。
追加提交 `ef76e47de58e2a20b8d8e06d1132ff2357b07981` 仅增加两行，不改算子、
容差、断言或 CI 工作流。测试 blob 为 `5eefc4558c60f2ff43bd1f7c2fb870e4e618001f`，
容器文件 SHA-256 为 `229de910e11274254c49cb79be75a60defd6c73fd2518dff3d62de5bbb287a6f`，
已核对与 PR 一致；原有算子修复不变，`git diff --check` 通过。

GPU1 本地验证：本文件 `-m attention` 56/56 通过，`--ref=cpu --quick`
56/56 通过（按项目参数命名，并非所有计算均在 CPU 执行）。全仓库标记扫描
在收集无关 `test_multinomial.py` 时因容器缺少 `scipy` 失败，保留该限制，
未安装无关依赖。日志位于同一批准工作根 `04-runs/attention-ci-6871-20261008/`，
分别为 `file-marker-selected.log`、`quick-cpu.log` 和 `marker-selected.log`。
新一轮上游 CI `37720153155` 已触发；同一提交的 `code-style`、
`rule-check-required`、`preprocess`、`triage` 和 CLA 已通过，GPU `python-op`
仍在运行，整体结果待核实。容器继续运行，未操作模型服务。
