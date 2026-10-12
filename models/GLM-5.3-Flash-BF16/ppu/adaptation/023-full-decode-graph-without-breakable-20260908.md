# 023：去除 breakable workaround 并启用 FULL decode graph

## 元数据

- 状态：`verified root-cause fix`（正式 accuracy/performance 仍未执行）。
- 首次出现/最后验证：2026-09-08。
- 模型、主机、容器：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`，`PPU-13`，
  `glm5.3-flash` / `hy4-ppu07-snapshot:20260903`。
- Plugin：`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`，
  `support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8` 加未提交 GLM 适配，editable 安装。
- FlagGems：`sparse-mla-opt-w8a8-moe-fix@bca444b8569294e7d4e4deff7ddfec7f05682033`，
  editable 安装且工作树 clean。
- vLLM：`/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389`，工作树 clean。
- 最终模式：TP16、65,536 context、32 sequences、`FULL_DECODE_ONLY`；prefill eager，
  uniform decode 使用 FULL graph；不设置 `VLLM_USE_BREAKABLE_CUDAGRAPH`。

## 完整失败签名与已有经验

PIECEWISE 基线通过 `VLLM_USE_BREAKABLE_CUDAGRAPH=1` 把有状态 indexer 留在 eager 区段，
因而没有 decode FULL graph。直接去掉变量并使用 `FULL_AND_PIECEWISE` 时，Dynamo 依次在
dispatch manager/registry 的 `threading.RLock`、lazy import、logger、capture-state 查询、
FlagGems pointwise scalar、动态 `CachedOp` 和 vendor indexer import 路径遇到不可捕获 Python
行为。该签名与 [008](008-graph-correctness-fix-20260906.md) 同模型、平台和 TP，但当前
Plugin/FlagGems revision 已变，因此只把 008 当负对照，不继承 eager-break workaround。

Hy4 preview 的关键设计不是删除或替换 `RLock`，而是模型构造/首次解析后由 `CachedOp`
保存 `impl.fn`，图热路径直接调用，不再经过 manager。GLM 的 shape-aware `supports`
此前强制每次回到 `mgr.call`，绕开了这条 fast path，这就是 RLock 被 Dynamo trace 到的直接原因。

## 受控尝试

| 轮次 | 唯一变化 | 结果 | 结论 |
|---|---|---|---|
| R0 | 去掉 breakable，直接 `FULL_AND_PIECEWISE` | `CachedOp` manager/registry `RLock` trace 失败 | graph 热路径不能做动态 manager dispatch |
| R1 | shape-aware candidates 在构造期预解析，运行期只做纯 metadata predicate | 越过 RLock | 采用 Hy4 的图外解析/图内直调边界 |
| R2–R8 | 每轮只处理下一个首错：lazy op、logger、capture bool、bounded swiglu、capability、vendor indexer import/lru wrapper | 最终完成 FULL 与 PIECEWISE capture | Python 动态行为均移到构造期或 custom-op 边界；没有修改 vLLM |
| R9 | `FULL_AND_PIECEWISE` 整模请求 | 首个请求正常；后续串行请求输出 256 个 `!`；同输入并发时一条正常、一条 `!` | capture 成功不代表 state replay 正确，该模式拒收 |
| R10 | vendor causal-conv 与 fused recurrent KDA changed-index raw graph replay | `conv_changed_index=PASS`、`kda_changed_index=PASS` | 两个原生 PPU primitive 不是污染源 |
| R11 | 只把执行模式改为 `FULL_DECODE_ONLY` | 7/7 decode FULL 捕获；两次串行 256-token 正确；两轮 c8 共 16/16 正确 | 污染来自 PIECEWISE prefill 与 FULL decode 的组合，decode FULL 本身可用 |
| R12 | 用根级最终脚本重新启动，并将 vLLM 编译 cache 放入批准的 `07-cache/` | 首次 NFS 编译 205.67 秒，7/7 decode FULL；最终 c8×2 仍 16/16 | 最终配置复现通过；NFS 首次编译较慢但持续推进且无故障 |

## 根因与修复

根因分两层：

1. RLock 是 dispatch 生命周期边界错误。GLM 的输入相关选择把 manager、registry lock 和
   ContextVar 留在 graph 热路径；修复为构造期 `prepare_cached_ops()` 预解析有序 candidates，
   运行期只按输入 metadata 选择已经解析的 callable。lazy MHC/indexer 同样使用显式
   `_prepare` closure cache；不是删除锁，也不是把锁换成不安全的无锁全局状态。
2. `FULL_AND_PIECEWISE` 的 PIECEWISE prefill capture 会污染后续有状态 replay；changed-index
   primitive 复现排除了 causal-conv/KDA 原语，执行模式单变量对照证明 decode FULL 单独正确。
   最终使用 vLLM 原生 `FULL_DECODE_ONLY`：prefill eager、decode FULL，不依赖 breakable。

为完成 full graph trace，还保留了最小配套改动：logger debug 的 Dynamo ignore、FlagGems
dynamic bounded swiglu 的 `torch.library.custom_op` 边界、capability `CachedOp` 单例化以及
vendor indexer 的构造期解析。这些改动均服务于同一 graph contract；没有新增模型名/机器名
特判，没有修改 vLLM 或 FlagGems 源码。

## 验证与证据

- 最终 launcher：host/container 均为
  `/mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh`，`bash -n` 均通过，SHA-256
  `031923efe0f33a5ce4052f69cc076b48eaad9e8559b4b7e28ba37f759320740f`。
- 当前实例：PID `2893015`，16/16 worker，health 200；命令行含
  `{"cudagraph_mode":"FULL_DECODE_ONLY"}`，进程环境无
  `VLLM_USE_BREAKABLE_CUDAGRAPH`。日志完成 7/7 `Capturing CUDA graphs (decode, FULL)`，
  当前启动段没有 PIECEWISE capture，错误签名数为 0。
- cache：进程环境的 `VLLM_CACHE_ROOT` 为
  `/mnt/nfs/users/jinghao/glm5.3-flash/07-cache/service/vllm`，日志确认 torch compile cache
  实际写入该目录；FlagGems/Triton/tmp 继续位于 `07-cache/`、`06-tmp/`。
- 最终并发结果：
  `/mnt/nfs/users/jinghao/glm5.3-flash/05-runs/023-full-decode-graph/final-cache-root-c8-r2.json`；
  两轮各并发 8，共 16/16 通过，16/16 `finish_reason=stop`，答案分别为
  `9、0、巴黎、56、H₂O、东京、25、蓝色`，无 `!` 重复。
- changed-index reproducer：
  `/mnt/nfs/users/jinghao/glm5.3-flash/08-bugs/023-state-index-replay/repro.py`，只保留一个
  operator reproducer 位置；causal-conv/KDA 均通过。
- 回归：`test_input_support.py` 14 项、`test_glm5_support.py` 22 项，共 36/36 通过；
  231 个 Plugin Python 文件 AST parse 通过；`git diff --check` 通过。唯一 warning 是
  FlagGems 在当前 Triton backend 无 replay benchmarker 时回退 event timing。
- 安装身份：`vllm_fl.__file__` 指向上述 `01-repos/vllm-plugin-FL`；FlagGems import 指向
  上述 `01-repos/FlagGems`。容器保持 `running`、RestartCount 0；PPU 原生命令
  `ppu-smi` 返回成功。
- 启动安全：服务运行时再次执行 launcher 返回 1，并准确输出端口 8010 已占用，PID 未被替换。

## Diff 审查与影响面

最终审查基线是 `support-hy4-preview@d56f7b2`。已跟踪 diff 为 11 文件、+139/-20；此外
GLM 模型/adapter/kernel/patch bridge 与两份 focused tests 仍为未跟踪的适配文件。工作树
未提交是继承状态且用户未要求 commit/push。公共影响集中于 `CachedOp` 与三类 backend
注册；无 `supports` fast path、带 `supports` shape 切换、strict/fallback 和 policy epoch
由 focused tests 覆盖。模型语义仍位于 GLM adapter/kernel，硬件实现仍位于 thead/FlagGems
backend。未发现需要继续删除的诊断、dump、profile、临时代码；过程 runner/reproducer 均在
远端 `04-acceptance/`、`08-bugs/`，不在 Plugin 产品代码中。

## 限制与退出条件

- 本记录证明 functional graph correctness，不替代正式 GPQA accuracy 或性能验收；历史
  GPQA strict 83.84% 结论不刷新。
- prefill 当前为 eager；`FULL_AND_PIECEWISE` 已因静默错误拒收。若未来要求 prefill graph，
  必须继续定位 PIECEWISE state replay，并重新执行串行 changed-input、c8 及正式 accuracy，
  不能重新打开 breakable 当作根治。
- 当前 NFS compile cache 首次构建比容器本地 cache 慢（205.67 秒 vs 70.32 秒），但满足目录
  边界、后续可复用；正式性能测试必须排除首次编译时间并单独记录。

## 经验沉淀

shape-aware operator dispatch 的可复用结论是：锁可保留在注册/解析控制面，但 graph 热路径
必须调用预解析 callable；capture 成功之后仍必须做变输入和并发 replay 正确性验证。当前仅在
GLM-5.3-Flash / PPU / 上述 revisions 验证，尚不提升为跨平台知识条目。
