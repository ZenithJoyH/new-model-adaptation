# 003：FlagGems MetaX 窄输出 MM 编译失败

## 元数据

- 状态：`mitigated`；日期 2026-09-21；Host `mx-59`、容器 `deepseek`。
- 模型、版本和工作根沿用 [002](002-metax-hash-topk-routing.md)。模式 eager，TP8/EP8。

## 问题现象、已有经验与根因

修复 hash top-k 后，profile 的完整 forward 到达 `hc_head`，其中 `F.linear(x, fn)` 被全局
FlagGems 接管为 MetaX `mm_kernel_splitk`。`BLOCK_N=4` 配置在 FlagTree MetaX pass
`TritonMETAXGPUPipelineAsyncNT` 触发 `shape_judge && "tm and tk not meet conditon"`。
最早明确 Python 异常见 run16 rank4；后续 `ncclCommAbort` 缺失是退出阶段附带错误。
仓库无同签名经验，不能用通信超时条目解释。

## 受控尝试

| 运行 | 唯一变量 | 结果 |
|---|---|---|
| run16 | hash top-k 修复；profile batch 16 | hc_head 的 MetaX MM 编译失败 |
| run17 | batch 改为 1024 | 同签名失败，排除只由 batch16 引入的假设 |
| run18 | 在既有 bmm 黑名单上增加 mm | 越过 profile，进入有缓存的 attention warmup，随后遇到问题 004 |

证据分别位于工作根 `04-runs/pr427-eager-tp8-20260921-16-hash-topk-fix/`、
`04-runs/pr427-eager-tp8-20260921-17-hash-topk-fix-1024/`、
`04-runs/pr427-eager-tp8-20260921-18-hash-topk-fix-blacklist-mm/` 的 `service.log` 和 `identity.txt`。

## Workaround、验证与限制

启动配置使用 `VLLM_FL_FLAGOS_BLACKLIST_APPEND=bmm,mm`，让对应运算走 PyTorch/MACA 原生实现。
这是当前服务配置的缓解措施，没有修改 FlagGems/FlagTree。现有 bmm 排除用于此前 MHC K=4 故障，
mm 排除的独立设备复现与数值比较仍待补充。原始错误归属为 FlagGems MetaX MM 与当前编译器组合，
尚未进一步区分配置约束缺失还是编译器支持缺陷。性能影响未测，graph 未测。
上游修复后需在同 shape/dtype 和全模型回归通过才移除 workaround。知识库状态 `local-only`。
