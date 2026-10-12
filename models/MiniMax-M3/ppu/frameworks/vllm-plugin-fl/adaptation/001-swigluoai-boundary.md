# 001：SwiGLUOAI 空张量与别名边界测试失败

## 元数据

- 状态：`root-cause fix validated on PPU-07`；2026-09-24 完成受控对照、算子与 Plugin 聚焦测试、整模 eager/目标 graph 实推及 198 题诊断；其他平台未实机验证。
- 模型/平台：MiniMax-M3，T-Head PPU-ZW810E，`PPU-07`。
- 容器：`minimaxM3-latest-20260924`，镜像见 `../environment/README.md`。
- 代码：Plugin `cafe6363`，FlagGems-vllm `1f9ac0e`，FlagGems `3c6f7537`，vLLM `ee0da84`。
- 执行模式：FlagGems-vllm 单算子 eager 数值与 CUDA graph replay，Plugin PPU 测试，整模 eager 与 `FULL_AND_PIECEWISE` 真实推理。

## 现象与证据

新容器导入及 Plugin dispatch CPU 测试 8/8 通过。随后运行 `python3 -m pytest -q -p no:cacheprovider tests/test_minimax_m3.py tests/test_swigluoai_uninterleave.py`：13 项通过、4 项失败。原始输出：`/mnt/nfs/users/jinghao/minimaxM3-new/04-runs/flaggems-vllm-focused-20260924.log`；CPU 测试回执：同目录 `plugin-dispatch-cpu-20260924.log`。

- `test_swigluoai_uninterleave[shape2-dtype0/1/2]`：`shape2=(0,128)`，独立空输入/输出被抛出 `ValueError: out must not alias input`。
- `test_swigluoai_uninterleave_rejects_alias`：测试以 `out=x[:, :128]` 传入与输入共享存储的切片，实际先抛出 `NotImplementedError: out must be contiguous`，未达到预期别名错误。
- MiniMax-M3 fused preprocess 的数值及 graph replay 用例通过；非空 SwiGLUOAI 数值用例通过。上述结果不覆盖整模 forward。

## 诊断与当前假设

原实现在输出连续性检查前后使用 storage 基址指针判断别名。独立空张量的指针相同，导致边界误判；共享存储的非连续测试切片则先触发了布局错误。第一次修复后，19 项 FlagGems-vllm 和 22 项 Plugin PPU 测试通过，但整模 full graph `04-runs/validation-full-20260924.log` 在 MoE 激活处失败：不同 FakeTensor 的 `data_ptr()` 均为 0，误判为别名。第二次修复改用 `torch._C._is_alias_of` 元数据，20 项聚焦测试及 22 项 Plugin 测试通过；整模 `04-runs/validation-full-postfix2-20260924.log` 再次在 MoE 激活失败。vLLM `WorkspaceManager.get_simultaneous` 从同一 storage 分配不重叠切片，故“共享 storage”仍不足以拒绝实际合法调用。第三次修复在同 storage 时比较连续输入/输出的 `storage_offset` 区间，仅对真正重叠时报错；非连续共享视图仍按保守别名错误拒绝。第三次聚焦测试 21/21 与 Plugin PPU 测试 22/22 通过。

整模 full graph 第三次尝试完成加载与推理，但日志 `04-runs/validation-full-postfix3-20260924.log` 显示 MiniMaxM3IndexerBackend/MiniMaxM3SparseBackend 不支持混合批次完整图，vLLM 自动降级为 `FULL_DECODE_ONLY=(FULL,NONE)`；这不是 prefill piecewise 图。随后整模 eager 启动并返回真实答案 `4`；显式 `FULL_AND_PIECEWISE=(FULL,PIECEWISE)` 启动，在 `04-runs/validation-decode-piecewise-graph-target-20260924.log` 中分别完成 `mixed prefill-decode, PIECEWISE` 与 `decode, FULL` 捕获，health 200，真实推理返回 `4`。用户指定目标为 decode + piecewise 模式，因此后续评测绑定显式目标服务，不采用自动降级实例。

已有 PPU-13 同模型适配记录对 `SWIGLUOAI_UNINTERLEAVE` 非空 BF16 实际路径已做数值/graph 验证，但平台、镜像和源码修订不同，本轮不沿用为当前通过证据。没有发现与这组空输入/异常优先级完全匹配的已验证知识条目。

## 范围、方案与下一步

2026-09-24 用户明确授权修复并按顺序验证，同时授权把已核实的 editable FlagGems-vllm
加入 profile 可写组件；只修改新容器 `/workspace/FlagGems-vllm` 中现有算子和聚焦测试。
该 checkout 为 `1f9ac0e`、tracked clean，`flaggems_vllm` 实际从其 `src/` 导入。
目标仓库 `AGENTS.md` 与 `workflow.md` 已阅读；其提及的 `optimization.md`、`deep_opt.md`
在当前 checkout 根目录不存在。本次是 Python host guard 修复，不改变 Triton kernel 或调参。

### 编码前项目真相

| 项目 | 本轮冻结值 |
|---|---|
| 接口/归属 | `flaggems_vllm.swigluoai_uninterleave`；FlagGems-vllm 现有自定义推理算子，非独立 `torch` API |
| 可改文件 | `src/flaggems_vllm/ops/swigluoai_uninterleave.py`、`tests/test_swigluoai_uninterleave.py`；Plugin、FlagGems、vLLM 不改 |
| 构建/验证 | editable 安装，无重编译；先聚焦 17 项及新增边界测试，随后 Plugin 设备与整模 eager/graph |
| 性能/调优 | 本轮不更改 kernel、launch 或 autotune；热点非空路径保持原样。正式性能验收不在本次 GPQA 请求范围 |
| 活跃集合 | PPU，FP16/BF16/FP32，`(1,128)`、`(7,3072)`、`(0,128)`；连续非空、独立空输出、共享存储切片与非别名非连续输出 |
| 超时/分析 | 聚焦测试 10 分钟；GPU profiler 未用于此纯 host guard 修复。禁止 torch compute fallback |

### 算子契约与路径

| 项目 | 本轮契约 |
|---|---|
| 输入/输出 | 连续二维 accelerator 浮点输入 `[tokens,2*width]`；输出 `[tokens,width]`，同 dtype/device；可传 `out=` |
| 计算 | 现有 kernel 对 gate/up 使用 FP32 中间值，clamp 后计算，结果转回输入 dtype；本轮数值公式不变 |
| 空输入 | 独立零元素输出有效并直接返回，不发射 kernel；零元素共享存储无数据重叠，亦可直接返回 |
| 别名 | 非空 `out` 与 `input` 的实际连续元素区间重叠时先报 `ValueError`；同 storage 但互不重叠的 vLLM workspace 切片允许；非连续共享视图保守拒绝 |
| 不支持 | 非别名但不连续输出报 `NotImplementedError`；CPU/meta、错误 rank/dtype/shape/参数保持原有拒绝 |
| 训练 | 推理 forward-only；autograd 未承诺；测试中的 torch 计算仅用作参考，不进入生产路径 |
| 路由 | empty → early return；非空合法 → 原 Triton kernel；其他 → 明确错误；不新增 external library 或 torch fallback |
| 调优豁免 | 原有固定 `BLOCK_SIZE=256` 保持不变；此轮不改 autotune，性能结论限于无新增计算路径 |

若聚焦测试通过，继续检查相关调用者、graph replay 和整模。修复前后保留同一测试命令、
完整输出和 `git diff`；不得以旧服务的评测结果冒充新代码结果。

- 算子归属 FlagGems-vllm，Plugin 通过 FlagOS dispatch 调用；仅新容器的 FlagGems-vllm 算子与聚焦测试有 tracked diff，Plugin、FlagGems、vLLM 源码未改。用户 fork `ZenithJoyH/FlagGems-vllm` 的 `support-minimaxM3` 分支在 `1f9ac0e0caf3c32111f6be44c8e4d2fef2359546` 上接收同内容提交 `e7a88149c3ca73b23f03f14e9a1bc6b21981015a`，远端 tip 已核对；运行容器仍是 detached 基线加未提交同内容 diff，未改服务实例。项目 profile 已按用户明确授权升级为 v4；共享 profile 变更会令其他模型既有记录提示需复核，未擅自修改那些记录。
- 修复是明确空张量的返回/别名语义，并让别名与非连续输入的错误优先级和测试一致；已在 FlagGems-vllm 做三次受控修订并增加边界回归用例。非连续共享视图保守拒绝，连续同 storage 但不重叠的 vLLM workspace 允许调用。
- 依据项目窄到宽顺序，第三次修复后 FlagGems-vllm 聚焦测试 21/21、Plugin PPU 测试 22/22、整模 eager/目标 graph 实推均通过。固定十题 strict 9/10，后续 50K 全量诊断 178/198、高于用户当前 88% 门槛，但 runner 回执失败且正式前置阶段不完整；见 [002](002-gpqa-first10-doc8-long-generation.md)、[003](003-gpqa-runner-config-conflict.md) 与 [全量诊断报告](../acceptance/gpqa-diamond-gen50k-diagnostic-20260924.md)。不得把诊断结果描述为整模正式验收通过。
- 用户授权临时停下的原优化服务曾精确停止 PID `1534829`；原容器保持运行。恢复脚本第一次因新写的 `set -u` 与厂商 `envsetup.sh` 不兼容而在模型加载前退出，日志 `04-runs/restore-opt-8013-20260924.log`；修正后日志 `04-runs/restore-opt-8013-retry1-20260924.log` 显示 59/59 加载、decode-full capture、ready，`04-runs/restore-opt-chat-20260924.json` 记录真实聊天响应包含“北京”。随后为 PPU-07 新代码诊断，8013 服务再次经精确身份核对后停止以释放设备；两个适配容器均保持运行。
- vLLM checkout 保持 `ee0da84`、无 tracked diff；Plugin 目标提交 `cafe6363` 无 tracked diff，镜像继承的四个 `.orig` 未跟踪文件保留。
- 设计审查：问题位于通用算子库的输入契约，非 PPU 专属实现缺失；先在算子库修复边界，不在 Plugin 或 T-Head vendor 目录添加例外。其他平台实机未测。
- 最终 diff 审查：目标 fork 分支在本轮前与运行容器基线均为 `1f9ac0e`，目标提交为 `e7a8814`，仅上述两个 FlagGems-vllm 文件；提交前本地隔离 checkout 无 inherited dirty/untracked，diff SHA-256 `1acdb40e31b333fd29328574160265fa6051c5b6e7498e7a38d65f418a38a764` 与运行容器完全一致。`git diff --check`、Python AST 语法检查通过；现有 PPU 测试覆盖空张量、FakeTensor、真实不重叠共享 workspace、别名错误及数值。热路径 Triton kernel 未修改、未引入 torch compute fallback，其他平台实机与正式性能未测；这限制跨平台支持的验证结论，但不影响该修复作为独立代码提交。

知识库处理状态：`local-only`；待跨环境复验后再决定是否提升为通用故障知识。
