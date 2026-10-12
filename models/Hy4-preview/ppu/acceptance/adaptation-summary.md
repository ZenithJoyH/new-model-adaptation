# Hy4-preview / PPU 适配与验收总结

本文件从 2026-08-28 的早期 INT8/PPU-13 分析记录演进而来；当前实际适配目标为 PPU-07、`hy4`
容器和 `/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`。截至 2026-09-11，Plugin topk 职责修复与
T-Head 通用 `index` blacklist 已完成，Plugin/FlagGems/vLLM revision 分别为 `2fa5f181`、
`bca444b8`、`ee0da84a`。19 个聚焦 UT、graph capture、c8 sanity 和 c64/high/80K GPQA 服务稳定性
均已验证，用户按 strict 90.91% ≥ 87% 接受精度；适配阶段标记 complete。2026-09-14 性能验收
只有 1K/4K 输入档成功，16K/32K/64K 三个长上下文档按场景标记超时，用户决定停止后续性能测试；
因此性能状态为 failed，平台只标记 functional，不标记 optimized。

## 最终 graph launcher

- Host 与容器路径：`/mnt/nfs/users/jinghao/hy4-preview/start-model.sh`。
- SHA-256：`6bf2e151423f65f860d6f7e45e164e29ee99ca0de656cdd32150cf6bffd02748`；mode 0755；Host/容器
  device/inode 均为 `41:21506731259`；2026-09-11 容器内 `bash -n` 通过。
- 完整服务配置：Hy4 W8A8 权重、served model `hy4`、0.0.0.0:8010、TP16、100K context、
  `--max-num-batched-tokens 2048`、显存预算 0.9、`FULL_DECODE_ONLY` graph、可信远端代码、
  `hy_v4` reasoning parser 与 safetensors load。日志/结果定向到 `04-runs/`，缓存定向到
  `06-cache/`；白名单审查未发现敏感赋值或破坏性命令。
- 已有服务保护通过实测：当前服务运行时调用 launcher 返回 1 并拒绝启动第二实例；之后 health
  仍为 200、服务进程数仍为 1。launcher 不停止、重启或删除容器。
- 参数保留依据：TP16 对应 16 张 PPU；100K 是本轮精度已验证上下文；2,048-token 上限抑制已知
  超大 recompute 调度；0.9 是当前 KV 容量配置；graph 模式是后续验收统一执行模式；其余参数
  固定模型/API/解析和加载契约。未保留 profiling、trace、dump 或实验性开关。

精度结果的 doc_id 81 单条 `<TIMEOUT>`、runner exit 1 和缺失原生 passing receipt 仍如实记录；
用户接受的是 87% 业务阈值结论，不是零 timeout 声明。性能失败终态见
`performance-plugin-2fa-indexoff-20260911.md`；没有 passing performance receipt，不能标记 optimized。

## 2026-09-14 性能终态

- `1024/4096 → 1024`：各 3 轮成功；汇总输出吞吐分别为 37.40、10.45 tok/s。
- `16384/32768 → 1024`：各 3 轮达到 21,600 秒单轮 timeout。
- `65536 → 1024`：第 1 轮 timeout，第 2 轮按用户决定终止，第 3 轮未运行；场景级标记 timeout。
- runner PID 2619354 及其 controller/benchmark 子进程已停止，`exit.code=143`；模型服务 PID
  2617179 与容器未停止，health 200，实时请求 running/waiting 均为 0。
- 原始结果未改写，终态 JSON 位于远端性能 run 根目录；用户决定不再继续本轮性能测试。

## 已完成与证据

- 核对官方配置、模板、词表 JSON，使用限定 HTTP Range 审计全部 131 个分片头；原始张量 payload 未下载。头部与索引一致，参数元素数与旧版去 scale 后相同。
- 只读核对容器镜像身份、依赖版本、插件/vLLM/FlagGems revision、工作树状态、旧量化配置和部分张量 dtype。远端检查 changed=0、unreachable=0、failed=0。
- 当前 Transformers 5.8.1 可解析 TokenizersBackend；新旧词表/规则全部字段规范化哈希一致。完整新 tokenizer 加载和模板生成尚未执行。
- 识别 packed expert 的 INT8 scale/命名合约风险、SwiGLU limit 未决语义、MTP dtype 差异及旧长时稳定性遗留风险，形成按正确性优先的实施顺序。
- 本地脚本与 playbook 的语法/元数据一致性检查见本轮验证记录；未生成或应用任何推理补丁。

## 验收状态

| 验收项 | 新版结果 | 原因/下一步 |
|---|---|---|
| 新 INT8 权重完整性/加载 | 未执行 | 路径、量化配置和报告尚未提供 |
| BF16/INT8 数值对齐 | 未执行 | 需要新版参考输出/实现、容差与量化信息 |
| eager 推理 | 未执行 | 不沿用旧模型成功记录 |
| graph capture/replay | 未执行 | 需同输入对照 eager 并覆盖 padded batch/cache |
| 正式 GPQA 精度 | 未执行 | 使用规定 flageval 镜像与 llmrun.py，先 preflight；预先确定通过阈值 |
| 最终性能/通信 | 未执行 | 正式精度通过后才使用 perf_test；按需 nccl_test |

若使用 GPQA Diamond，预期 198 样本，不能把部分完成或 timeout 样本混合评分当作通过。新评测容器、数据集版本、服务参数、指标阈值、产出路径和时间必须在实际运行时记录，不能从旧评测复制成新证据。

## 现有 W8A8 服务的 PPU-07 对照评测

2026-08-29 对 `/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/` 完成规定 FlagEval v1 / `llmrun.py` 的 GPQA Diamond thinking/high、40K、32 并发对照评测。原始评测和内置重试后剩余 8 个失败项；独立 86,400 秒 timeout 重跑仅发出这 8 个请求，最终获得 198 个唯一题目、396 sample rows、strict `0.9090909091`、flexible `0.4444444444`，但仍有 4 个无效项。

诊断确认这 4 项不是网络或客户端 timeout：请求约 5,745 秒后返回 40,000 completion tokens、`finish_reason=length`、reasoning 存在且 `content=None`；lm-eval 将它们缓存为 Python `None` 并在 samples 中标成 `<TIMEOUT>`。因此 0-timeout 条件未通过，不启动性能验收，也不继续加长 timeout。该结果只作为已有 W8A8 服务的对照证据，不能转移为新版 INT8 的验收结果；完整路径、配置和失败 doc_id 见[精度验收汇总](accuracy-results.md)。

## 遗留问题及后续输入

1. 新 BF16 配置仍有 swiglu_limit=10，当前旧插件不截断；新版执行语义尚未确认，本轮没有猜测性修改。
2. 新源 checkpoint 是 packed BF16，不能由结构相同推断新 INT8 一定遵守已有 compressed-tensors 约定。
3. 当前容器插件工作树 dirty，镜像 tag 不代表全部适配内容已固化；后续保存基线与增量补丁并保持 vLLM 源码只读。
4. 旧模型存在 GPQA 长时中断的历史，133 项 blacklist 与 top-k bool 兼容补丁不能替代新模型完整精度/稳定性验收。
5. MTP、1M 上下文、EP 优化均不在本轮已验证能力内；先完成普通自回归推理。

## 现有 W8A8 服务的 PPU-07 原生算子接入进展

2026-09-03 在服务保持停止、容器保持运行的边界内，完成平头哥原生 bundle 与插件 vendor dispatch 的窄验证。模型层没有直接调用 SO；入口保持 `CachedOp`，经 dispatch policy 选择 `TheadBackend`，再由 `vendor/thead/impl/native_extensions.py` 调用固定版本原生 op。`concat_mla_q`、MLA/Indexer cache write、BF16 Indexer decode top-k、dynamic INT8 quant、`grouped_topk`、`topk_softmax`、`moe_align_block_size`、`moe_sum` 均实际解析为 `vendor.thead`，通过数值、eager 和 graph capture/replay；原有 bundled-native 与 sparse MLA 回归也通过。vLLM 与 FlagGems revision/status 前后未变。

剩余边界已经通过 contract 测试明确，而不是仅凭符号存在推断：BF16 paged MQA logits 没有同 contract 的原生实现；`persistent_topk` 返回无序候选，不能消除候选重排或 50K logits 物化；原生 dense scaled-MM 只接受 column-major B，与当前跨平台 row-major 权重 contract 不兼容；原生 `cutlass_moe_mm` 不支持当前 capability 80 的 PPU-ZW810E。因此 paged logits 和 W8A8 expert GEMM 继续使用 FlagGems。本轮没有启动服务，不能据这些窄测试声明端到端 graph、性能或精度验收完成。完整证据见 `../environment/native-operator-inventory-ppu07-20260903.md`。

具体环境、引用文件、复查命令、量化约定和执行顺序分别见 `../environment/environment-analysis.md`、`../environment/history/runbook.md` 和 `../environment/new-bf16-int8-readiness.md`。本轮无服务生命周期变更，也无新算子实现或缺失算子断言。
