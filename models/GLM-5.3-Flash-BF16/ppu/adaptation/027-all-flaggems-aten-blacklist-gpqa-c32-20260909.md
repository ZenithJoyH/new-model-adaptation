# 027：全量禁用 FlagGems ATen 后的 full-graph 惰性导入与 GPQA c32 诊断

## 元数据

- 状态：`running diagnostic`（非正式验收）
- 首次出现时间：2026-09-09
- 最后验证时间：2026-09-09
- 模型：`GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / `hy4-ppu07-snapshot:20260903@sha256:29a6712e24ca8e758ac8b33d3412892f0541bff108e2c057445fa671578237f6`；评测容器 `flageval_llmeval-jinghao` / `harbor.baai.ac.cn/flageval/flageval-llmeval:v1@sha256:bcefa10b9be062ed449ac1e7b7925fa4f9a46e1361fbb25cc6e99616bc59a4f5`
- Plugin / FlagGems / vLLM revision：Plugin base `support-glm5.3-flash@424c0dd558f5c55619e68022de4f713d9b41b2a1`，含本问题未提交修复；FlagGems `sparse-mla-opt-w8a8-moe-fix@bca444b8569294e7d4e4deff7ddfec7f05682033`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：`FULL_DECODE_ONLY`，TP16，`max_model_len=65536`，服务 `max_num_seqs=32`；GPQA Diamond 全量 198 题、32 并发、`max_gen_toks=40000`；随后只对 21 个 length-capped 样本以 21 并发、`max_tokens=60000`、客户端 timeout 14400 秒定向重跑

## 问题现象

- 用户要求先把全部 FlagGems ATen override 加入黑名单，再进行 32 并发全量 GPQA。
- `_FULL_CONFIG` 共 1,047 项、982 个唯一实现函数名；生成的逗号分隔黑名单覆盖全部 1,047 项，未覆盖项为 0。黑名单只关闭 FlagGems 对 ATen 的替换，不关闭 Plugin dispatch 显式调用的 MLA、mHC、sparse-indexer、KDA 等自定义实现。
- 首次模型图编译依次暴露两个相同错误：`torch._dynamo.exc.Unsupported: Attempted to call function marked as skipped`，用户栈进入 `_gcd_import`；先发生在 FlagGems mHC lazy wrapper，修复后发生在 T-Head sparse indexer lazy wrapper。
- 原始证据：`/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/glm53-gpqa-full-c32-all-aten-off-20260909-1710/service-attempt-{2,3}.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 023 FULL decode graph | graph 前必须完成 dispatch provider 和 lazy import 解析 | 本次全量关闭 ATen override 后暴露两个 backend wrapper 的相同缺陷 | 高 | 延续 `prepare_cached_ops()` 契约，修复 wrapper 的预热后调用路径 |
| 018 SQLite autotune 锁 | 都发生在冷启动 | 本次无 `database is locked`，首个失败栈为 Dynamo `_gcd_import` | 高 | 判定为不同问题，不套用 SQLite mitigation |
| distributed sample timeout 知识条目 | 都配置执行超时 | 本次失败发生在服务初始化，worker 明确抛出编译异常，不是 `sample_tokens` 超时 | 高 | 不用增大超时掩盖异常 |

## 诊断与假设

- 已验证事实：Plugin 的 `prepare_cached_ops()` 在模型构造末尾调用；两个 backend wrapper 都把动态导入包在 `functools.lru_cache` 中。
- 已验证事实：TorchDynamo 日志明确说明其忽略 `lru_cache` wrapper 并直接追踪被包装函数，因此即使 `_prepare` 已填充缓存，full graph 仍进入 `import_module()`。
- 已验证事实：将解析结果保存为闭包中的直接 callable 后，CPU `torch.compile(..., fullgraph=True)` 回归与实际 TP16 整模编译均越过 `_gcd_import`。
- 待解释但不影响根因的差异：正常 ATen 配置没有触发该失败；全黑名单改变了初始化/编译路径并暴露潜在契约缺陷，本轮不把该差异推断成某个 ATen 数值算子问题。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | FlagGems ATen blacklist | 正常服务无全量 blacklist | 982 个唯一实现名覆盖 1,047 项配置 | `01-environment/.../flaggems-aten-blacklist.txt` | 服务 PID `2928091` 在加载前失败 | 长任务 `TMPDIR` 使 ZMQ IPC path 超过 107 字符；与算子无关 |
| 2 | 短 TMPDIR | 长任务路径 | `05-tmp/g53a1710` | `service-attempt-2.log` | TP16 加载权重后，FlagGems mHC lazy import 被 full graph 捕获 | 需修复 FlagGems wrapper |
| 3 | FlagGems lazy wrapper | `lru_cache(resolve)` | 预热后 closure 直调 callable | Plugin FlagGems `register_ops.py` | mHC 越过；随后 T-Head indexer 同型失败 | 同一契约还需覆盖 vendor wrapper |
| 4 | T-Head lazy wrapper | `lru_cache(resolve_indexer)` | `_lazy_attr` 预绑定方法 | Plugin T-Head `register_ops.py` | PID `2940307` 完成编译、warmup、7 个 decode FULL graph capture 并 ready | 根因修复在真实模型上成立 |
| 5 | GPQA 负载 | 无本轮请求 | full 198、c32、max 40k | `04-runs/.../runner.log` | 198/198 完成；strict 163/198（82.32%）；21 题均为 40K length cap | 全量诊断未达 88%，且零 timeout 契约失败 |
| 6 | 21 题定向重跑 | 21 题 `completion_tokens=40000`、`finish_reason=length` | max 60k、客户端 timeout 14400 秒、c21 | `04-runs/glm53-gpqa-timeout21-60k-t14400-20260909/` | 21/21 HTTP 200；6 题 natural stop 且全部 strict 正确，15 题再次达到 60K；合并 169/198（85.35%） | 单纯增加计时 timeout 无效；增加 token 预算只恢复 6 题 |
| 7 | greedy 单变量对照 | 上轮剩余 15 题、temperature 1 | 仅 temperature 1→0；max 60k、top_p .95、timeout 14400 秒均不变；c15 | `04-runs/glm53-gpqa-capped15-t0-60k-t14400-20260910/` | runner PID `19989`；首个快照 15 running、0 waiting、服务近期致命错误 0 | 运行中；用于验证采样随机性是否导致长推理不收敛 |

## 根因

- 已验证根因：两个 backend 的惰性 wrapper 把动态导入隐藏在 `lru_cache` 后，但 TorchDynamo full graph 不以该缓存为不可追踪边界；预热后仍会追踪到 `_gcd_import`。
- 独立启动问题：attempt 1 的 ZMQ IPC path 超长来自任务目录作为 `TMPDIR`，使用任务范围内的短路径 `05-tmp/g53a1710` 后消失。

## 解决方法或 Workaround

- 修改思路：保持 optional backend 惰性加载；`_prepare` 或首个 eager 调用解析一次 callable，后续直接调用闭包中的已解析函数，不在 graph 热路径调用 `import_module`。
- 选定层级：修改现有 FlagGems 与 `vendor.thead` 注册 wrapper；不改 model、manager、policy、types 或 vLLM。
- 受影响调用方：FlagGems GLM BF16 adaptation ops、T-Head direct ops 与 sparse-indexer methods。未选择这些 provider 时行为不变；optional module 仍不会在 backend 未使用时导入。
- Plugin 路径：`vllm_fl/dispatch/backends/{flaggems,vendor/thead}/register_ops.py`；回归测试 `tests/unit_tests/dispatch/test_{flaggems,thead}_lazy_dispatch.py`。
- Plugin 分支：base revision 不变，当前工作树包含上述 2 个源码文件和 2 个测试文件，未 commit、未 push。
- 过程代码与证据：本问题的 launcher、smoke 与 patch 位于远端 `02-issues/` 或 `05-tmp/`；正式评测工具位于 `03-acceptance/`，运行输出位于 `04-runs/`，cache 位于 `06-cache/`。
- 服务停启：先核对并以 `kill -TERM 2893015` 停止任务范围内旧服务，确认 worker 和 8010 端口释放；适配容器未停止、重启或删除。失败 attempt 均自然退出，最终服务 PID `2940307`。
- vLLM 未修改：vLLM revision 与工作树不变。

## FlagGems 证据

- checkout：`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems`，revision `bca444b8569294e7d4e4deff7ddfec7f05682033`，本轮未修改。
- blacklist：`/mnt/nfs/users/jinghao/glm5.3-flash/01-environment/glm53-gpqa-full-c32-all-aten-off-20260909-1710/flaggems-aten-blacklist.txt`；982 项；带末尾换行 SHA-256 `1fe7b4c2aba785fc92add508f0fb0a90b9f9004cf6bfb03d03bcf45b4cb1d0fa`。
- 覆盖核验：FlagGems `_FULL_CONFIG` 1,047/1,047 条均按 registrar 使用的实现函数名被排除，uncovered=0。
- 本轮不是 FlagGems kernel 数值缺陷，不建立 `07-bugs/` kernel reproducer。

## 验证结果

- 最小回归：4 个 lazy-dispatch 单元测试通过，含 FlagGems/T-Head 的 eager 单次解析和 `torch.compile(..., fullgraph=True)` 预热后禁止 import 断言。
- `graph`：TP16 整模 `torch.compile` 222.54 秒；初始 profiling/warmup 9.78 秒；7 个 decode FULL graph 捕获完成；服务明确异常计数 0。
- 服务：`/v1/models` HTTP 200，唯一模型 ID `glm5.3-flash`，`max_model_len=65536`；真实 chat completion HTTP 200、`finish_reason=stop`、生成非空。
- GPQA 全量诊断：198/198 完成，`exact_match,strict-match=0.8232323232`（163/198），`flexible-extract=0.3535353535`；21 个 `<TIMEOUT>` 样本全部为 `completion_tokens=40000` 且 `finish_reason=length`，不是 7200 秒 HTTP timeout。服务致命错误计数为 0，评测因不允许 timeout 而以 1 退出。
- GPQA 定向重跑：`03-acceptance/rerun_gpqa_timeout21_60k_20260909.py` 复用原始 21 个 doc_id 和已安装 lm-eval 的 strict-match 正则；输出到 `04-runs/glm53-gpqa-timeout21-60k-t14400-20260909/`。只提高生成预算 40K→60K 和客户端 timeout 7200→14400 秒，原 177 题及原始结果保持不变。
- 60K 结果：21/21 HTTP 200，6 题 natural stop 且 strict 全部正确；15 题仍为 `finish_reason=length`。合并诊断分数为 169/198（85.35%），仍低于 88%。15 题均无 replacement/NUL/non-printable 字符且 `content=None`；doc 127 有明确重复退化（重复行实例占 81.5%），其余主要为持续推导而非普遍机械复读。
- greedy 对照：`03-acceptance/rerun_gpqa_capped15_t0_60k_20260910.py` 只把剩余 15 题 temperature 从 1 改为 0；输出到 `04-runs/glm53-gpqa-capped15-t0-60k-t14400-20260910/`。该轮不修改模型服务、Plugin、max tokens、timeout、prompt 或 strict-match 规则。
- 正式性：acceptance `accuracy --check-only` 因 adaptation 仍为 `in_progress` 且 deployment identity 的 `runtime_config_sha256` 不一致而阻塞；因此本轮只作为 adaptation diagnostic，不生成或冒充 `acceptance-result.json`。

## 限制与下一步

- 尚存限制：全量诊断 strict 为 82.32%；60K 定向合并后为 85.35%，仍未达到 88%，且有 15 个 length-capped 样本。greedy 单变量对照仍在运行。
- 后续动作：greedy 对照完成后检查 15/15 HTTP 成功、natural stop、残余 length cap、strict-match 恢复数及合并后的 198 题分数；若仍有大量 length cap，再以同一 15 题对照 ATen blacklist/full-graph 路径，不用继续增加计时 timeout 掩盖不收敛。
- 设计审查：修复沿用现有 dispatch 注册与 `CachedOp._prepare` 扩展点，未增加新目录或公共 manager/types API；在整轮 GPQA 完成和相关共享回归补齐前，状态保持运行中。

## 经验沉淀

- 可跨 backend 复用：full graph 下，惰性 import 的预热必须改变实际调用路径；仅给 `lru_cache` 填值不能阻止 Dynamo 追踪其函数体。
- 知识库处理状态：`needs-validation`
- 候选知识条目：`TorchDynamo full graph 穿透 lru_cache 导致 lazy import _gcd_import 失败`。
