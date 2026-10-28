# 005：GDN backend 阻断 mixed prefill/decode 全图

## 元数据

- 状态：`diagnosed`；首次验证 2026-09-28，最后复核 2026-09-30。
- 模型 / Host / 容器：MiniCPM-V-4.7-35B / `H100-149` / `MinicpmV4.7-35B`。
- 软件：Plugin 基础 HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319` 加本任务未提交适配；FlagGems `da6727e38f6f8eedef6cba43695a87b4996f9eca`；只读 vLLM `0.24.0+cu129`。
- 模式：GPU 4、5，TP2，BF16，50,000 token，前缀缓存开启，`--compilation-config '{"cudagraph_mode":"FULL"}'`。

## 签名与顺序

两名 TP worker 完成权重加载和初始 profiling 后，分别在 `13:10:16` 与 `13:10:22` 输出：`CUDAGraphMode.FULL is not supported with GDNAttentionBackend backend (support: AttentionCGSupport.UNIFORM_BATCH); setting cudagraph_mode=FULL_AND_PIECEWISE`。后续日志明确开始 `Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)`。这不是 full 图通过；vLLM 已自动改变请求的图级别。原始证据：`H100-149:/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/graph-full-tp2-20260928/server.log`；准确脚本：同一工作根 `01-environment/start-graph-full-tp2.sh`。

## 根因和现有经验

只读 vLLM `/usr/local/lib/python3.12/dist-packages/vllm/config/compilation.py:1333-1358` 在 mixed batch 要求 `AttentionCGSupport.ALWAYS`，否则根据 attention split 设置降为 `FULL_AND_PIECEWISE` 或 `FULL_DECODE_ONLY`。该 wheel 的 `vllm/v1/attention/backends/gdn_attn.py:83` 将 `GDNAttentionMetadataBuilder._cudagraph_support` 声明为 `UNIFORM_BATCH`。目标语言骨干有 GDN 层，因此本配置无法保持 mixed prefill/decode 全图。两个 rank 的同一警告加源码条件构成可复核的阻断证据；未修改只读 vLLM 或伪装 backend 能力。历史上其他混合架构使用 decode-only 图的记录只提供候选方向，本轮由目标 revision 的日志与源码独立验证。

## 受控尝试与缓解

| 轮次 | 唯一变量 | 设置 | 结果 |
| --- | --- | --- | --- |
| eager 基线 | 图关闭 | `--enforce-eager` | TP2 文本与单图请求通过；见问题 002 |
| full 首选 | 图模式 | `cudagraph_mode=FULL`，其余服务身份与 eager 相同 | 两 rank 均自动降为 `FULL_AND_PIECEWISE`，不满足 full 验收 |
| decode-full 候选 | 图模式 | `cudagraph_mode=FULL_DECODE_ONLY`，其余服务身份保持 | TP2 捕获 `decode, FULL`；文本、红/蓝图与变输入 replay 六题全过，原始结果见 `04-runs/graph-decode-full-tp2-20260928/minimal-service-check-v2.json` |
| 用户选定的分段图 | 图模式 | 显式 `cudagraph_mode=FULL_AND_PIECEWISE`，TP2、GPU 4/5、`max_num_seqs=10` | 2026-09-30 根目录启动脚本再次完成 `mixed prefill-decode, PIECEWISE` 5/5 与 `decode, FULL` 4/4；API 就绪，图文 6/6、混合十并发 10/10 正确；见[服务验证记录](../acceptance/service-validation-2026-09-30.md) |

该候选是框架允许的最低 graph 级别，mixed prefill/decode 将不用全图；不能把已经发生的 `FULL_AND_PIECEWISE` 降级服务当成通过。退出缓解条件是 GDN backend 与当前混合架构在 full mixed batch 图中通过实际 prefill、decode、变输入 replay 及性能回归，再移回 `FULL`。改动 vLLM 能力声明并非本任务可写范围；Plugin 尚无已证明的局部实现可替代它。

## 服务生命周期与影响范围

full 候选 API PID `11751`、EngineCore `11969`、TP worker `11993/11995` 均按模型路径、端口和 PID 文件核实。因图级别自动降级而发送 SIGTERM；capture 期间未退出，再核对四个 PID 的命令与父子关系，仅对它们发送终止信号并对残留的 API PID 强制退出。复查四个 PID 均消失，GPU 4、5 均为 0 MiB，容器 PID1 仍为 bash；没有影响其他 GPU 上的服务。decode-full 另用独立脚本和运行目录，保留 full 尝试原始日志。用户选定的 `FULL_AND_PIECEWISE` 起初使用 `01-environment/start-graph-full-piecewise-tp2-seqs10-cacheids.sh`；2026-09-30 核实其空闲后仅对该任务 API PID `24553` 发送 SIGTERM，确认整棵进程树、端口和 GPU 已释放，随后使用根目录 `start-model.sh` 启动并验证 PID `27353`；容器未停止或重启。

## 验证与限制

- full：明确失败，不能通过；首个阻断点为 GDN backend 能力限制，不是 CUDA 异常。
- decode-full：最小图文与变输入 replay 已验证；正式 execution-mode 接收和后续精度、性能仍需独立证据。
- `FULL_AND_PIECEWISE`：用户显式选择的运行配置已捕获上述两个图阶段，且实际图文和十并发功能回归通过；混合预填充是分段图，不能按本 profile 的 full 或 decode-full 正式 graph 级别标记通过。
- 影响仅在当前模型、vLLM wheel 和 TP2 实测；不推断其他模型或平台。
- 知识库处理：`local-only`，暂不推广。
