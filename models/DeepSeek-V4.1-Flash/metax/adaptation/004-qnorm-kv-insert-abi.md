# 004：DeepSeek V4 Q/KV 插入的新旧 ABI 不匹配

## 元数据

- 状态：`mitigated`（run19 越过原 ABI 错误，尚未取得整模数值证据）。
- 日期 2026-09-21；Host `mx-59`、容器 `deepseek`；身份和版本沿用 [002](002-metax-hash-topk-routing.md)。

## 问题现象与根因

run18 越过显存 profile 后，在带 attention metadata 的 kernel warmup 抛出
`fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert expected at most 8 argument(s) but received 9`。
当前 vLLM 新契约含 `padded_heads` 并返回补齐后的 Q；MetaX mcoplib 0.4.5 和当前 FlagGems-vllm
均为旧八参数、原地修改 Q 的契约。PR 的 FlagGems backend 转发 reference，再直接调用旧 `_C` schema。
这是 Plugin 接口适配缺失，尚未进入该内核，不归类为 FlagGems 数值缺陷。

## 已有经验与实现选择

仓库未发现同签名记录。不能直接丢弃第七个 `padded_heads`，否则会丢失返回值和 padding 语义。
选定现有 FlagGems backend adapter，调用 FlagGems-vllm 的八参数实现后按需要补零并返回 Q。
保留 OpManager 入口、厂商 kernel 自动选择和 device guard；CUDA vendor 实现不变。
没有改 vLLM、权重或 FlagGems 源码。

## 受控尝试与证据

- 基线 run18：工作根 `04-runs/pr427-eager-tp8-20260921-18-hash-topk-fix-blacklist-mm/service.log`。
- 生产适配：Plugin `vllm_fl/dispatch/backends/flaggems/impl/deepseek_v4.py`。
- 回归测试：Plugin `tests/unit_tests/dispatch/test_deepseek_v4_ops.py` 校验八参数转发、原地 Q 修改及零 padding。
- 相关测试 50 passed、3 skipped；证据 `04-runs/pr427-related-unit-after-qnorm-abi-20260921/`。
- run19 仅变更 ABI adapter：`04-runs/pr427-eager-tp8-20260921-19-qnorm-abi/`。109 个分片加载完成，显存 profile 成功，在 mixed 16-token warmup 越过 Q/KV 插入；随后在稀疏 MLA 调用 NVIDIA 扩展时失败，见正确 V4 工作区的 [005](../../../DeepSeek-V4-Flash/metax/frameworks/vllm-plugin-fl/adaptation/005-flaggems-sparse-mla-bridge.md)。本记录历史上误归入 V4.1，不能作为 V4.1 的证据。

## 限制与设计审查

真实设备缓存数值、无 padding/非法 head 数分支、graph 和非 MetaX 平台尚未验证；可选依赖测试隔离还需完善。
当前仅单测通过，不能标记整模 functional。知识库状态 `local-only`，通过真实请求前不推广。
