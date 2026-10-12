# 009：FULL_AND_PIECEWISE 启动时 FlagGems normal_ HGGC 加载段错误

## 元数据

- 状态：`open`，通用原生回退已验证
- 首次出现时间：2026-09-12
- 最后验证时间：2026-09-12
- 模型：Qwen3.8-Flash-Next，BF16
- 平台与 Host 别名：T-Head PPU，`PPU-01`，仅使用 PPU 8–15
- 容器名称：`qwen3.8-flash`
- Plugin / FlagGems / vLLM revision：Plugin
  `939600b323c02c21916f1f76bfb4cd8c2b02578d`；FlagGems
  `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`；三棵工作树均 clean
- 执行模式与负载：TP8、`FULL_AND_PIECEWISE`、max model len 65536、max seqs 32、
  max batched tokens 4096、GPU memory 0.90、capture sizes 1/2/4/8/16/32

## 问题现象

- clean revisions 下服务完成权重加载和 Dynamo transform，随后在启动期 memory profile/compile
  中段错误。
- 两次相同启动分别由不同 TP worker 首先退出；所有崩溃栈均包含
  `at::_ops::normal_::call` → FlagGems dispatcher/binary loader → `hgModuleLoadData` →
  `hggc::_HGcontext::moduleLoadRawElf` → segfault。API 的 `RuntimeError: cancelled` 是 worker 退出后的
  次生错误。
- 原始日志：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/execution-mode-full-and-piecewise-2aacb2ed-20260912/service.log`
  （SHA-256 `f6bc446eec7263c02f620ea8e37796623f0162745733bb2110dc9e1e4cbb500a`）和
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/execution-mode-full-and-piecewise-r2-2aacb2ed-20260912/service.log`
  （SHA-256 `a530fd14729cb4b3f7928805eec04856ad8adbf355014a2fac96cfd7037f9f25`）。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [008：PCCL graph→eager collective 停滞](008-pccl-graph-eager-collective-stall.md) | 都由 graph 配置触发验证 | 008 在长负载的 PCCL uncaptured launch 前停滞；本问题在启动 profile 的 HGGC module load 中直接段错误 | 高 | 分成两个问题处理，不能用增大 RPC timeout 处理本问题 |
| `qwen3.8-flash-test` 历史启动 | 同一模型和 `FULL_AND_PIECEWISE` 能完成启动 | 镜像、dirty Plugin/FlagGems 工作树及大量历史编译缓存不同；只有 vLLM 与 PCCL 二进制相同 | 高 | 历史容器证明参数组合可行，但不是 clean revisions 的源码对照 |

## 诊断与假设

已验证 `FULL_AND_PIECEWISE` 会启用 `VLLM_COMPILE`，其 splitting ops 包含 Qwen PLE/QSA；启动
profile 会执行 `torch.randn` / `aten::normal_`。连续两次相同调用栈与单变量原生回退结果证明，
直接故障位于 FlagGems `normal_` 生成二进制的 HGGC 加载路径。当前证据尚不能区分缓存制品损坏、
生成 ELF 与当前 runtime 不兼容，或 loader 并发/生命周期缺陷，因此不把底层 HGGC 根因标记为已修复。

`max-model-len=100000`、GPU memory 0.85、capture sizes 到 128 不是触发本次段错误的必要条件：
较小的 65536、0.90、1–32 已稳定复现。`VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS` 只控制 RPC 等待，
不能修复原生段错误。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 重跑 | clean revisions 原配置 | 完全相同参数再次启动 | `02-issues/pccl-graph-eager-transition-20260911/start-model-full-and-piecewise.sh` | 两次均在 `normal_` HGGC module load 段错误，首个失败 rank 不同 | 可复现且非固定设备偶发 |
| 2 | `normal_` dispatch | FlagGems `normal_` | 仅向既有通用 blacklist 追加 `normal_`，走 PyTorch 原生实现 | 同一 launcher；运行目录 `04-runs/execution-mode-full-and-piecewise-normal-aten-2aacb2ed-20260912/` | mixed PIECEWISE 与 decode FULL 捕获全部完成，HTTP 200；最小推理返回 `2`，health 200 | `normal_` FlagGems 路径是启动失败必要变量；通用回退有效 |

## 根因

- 已验证直接根因：启动 profile 调用 FlagGems `normal_` 时，生成二进制在 HGGC
  `moduleLoadRawElf` / `hgModuleLoadData` 中段错误并杀死 TP worker。
- 缺失证据：尚未得到失败 ELF 的独立最小复现和 loader/vendor 侧诊断，底层生成或加载缺陷仍待收敛。

## 解决方法或 Workaround

- 当前 workaround 使用 Plugin 既有、模型通用的算子 blacklist 扩展：
  `VLLM_FL_FLAGOS_BLACKLIST_APPEND=_conv_depthwise2d,index,normal_`。没有加入模型名判断。
- Plugin、FlagGems、vLLM 源码均未修改；该回退属于启动配置，避免把通用算子缺陷塞进 Qwen 模型文件。
- launcher：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/02-issues/pccl-graph-eager-transition-20260911/start-model-full-and-piecewise.sh`，
  SHA-256 `bfbd8e0fdbe66a5887b2dbded319dc0e2e2fac4670d8785d3e6d86905fa0d21d`。
- 成功服务 PID 由本任务启动；适配容器保持运行，未停止、重启或删除。
- 退出条件：FlagGems `normal_` 最小复现通过、整模 capture 与数值回归通过后，才移除回退并重新验证。

## FlagGems 证据

- FlagGems 为 clean `support-qwen3.8-flash@2aacb2ed7b116baee0acc147cdc770b4176a6cdd`。
- 当前直接失败落在通用 `normal_` dispatcher/binary loader，不属于 Qwen 模型语义，也不应由 Plugin
  模型适配代码专用 dispatch 修补。
- 待在 `/mnt/nfs/users/jinghao/qwen3.8-flash/07-bugs/flaggems-normal-hggc-load/` 建立最小复现；
  在复现前不提交 FlagGems 源码更改。

## 验证结果

- 最小回归：确定性 chat 请求返回模型 `Qwen3.8-Flash-Next`、正文 `2`、finish reason `stop`；
  随后 health 200。
- `graph` capture/replay：mixed prefill/decode PIECEWISE 6/6、decode FULL 6/6 完成；首次请求成功。
- 成功日志：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/execution-mode-full-and-piecewise-normal-aten-2aacb2ed-20260912/service.log`，
  SHA-256 `53cf91a3a9d86e80576a3dc691c263de6c7b45e45f9651e1eb96c193cc66363f`。
- 响应 SHA-256：`d65c19d081ae31583502469051bb801083718991ef9b1ea4bbbd242c204dc8db`。
- 当前通过范围仅为启动、capture 和最小推理；full198/c64/60K 精度与长期 graph 稳定性尚未通过。
- full198/c64/60K 已完成且无服务 fatal，说明 `normal_` 原生回退能支持长期执行；最终 strict
  114/198（57.58%）未达 88%，数值/输出一致性仍未通过。

## 限制与下一步

- 建立 `normal_` 独立最小复现，冻结 dtype、shape、generator、并发 rank、缓存命中状态和失败 ELF。
- 在通用回退配置上运行同一 full198/c64/60K，以验证 PIECEWISE mixed 路径是否解决 008 的长负载停滞。
- 设计审查结论：当前不改变 Plugin PR 范围；若确认 FlagGems 算子缺陷，修复应提交到 FlagGems
  的通用 `normal_` 实现或 loader 兼容层，并覆盖其他模型调用方。

## 经验沉淀

- 是否可跨模型或平台复用：诊断和通用回退对所有触发同一 FlagGems `normal_` HGGC 栈的模型可复用；
  当前只在 Qwen3.8-Flash-Next / PPU 验证。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：graph compile profile 阶段 `normal_` → HGGC module load 段错误的单算子收敛方法。
