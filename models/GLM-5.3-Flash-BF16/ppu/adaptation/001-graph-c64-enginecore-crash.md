# 001：graph 服务在 GPQA c64 下 EngineCore 退出

## 元数据

- 状态：`root-cause-fixed-sanity-verified`
- 首次出现时间：2026-09-06 11:17:55（UTC+8）
- 最后验证时间：2026-09-06 15:50（UTC+8）
- 模型：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / `hy4-ppu07-snapshot:20260903`
- Plugin / FlagGems / vLLM revision：`support-hy4-preview@5329cb1` 加 BF16 适配 /
  `34bd6d68928c8b0039c42987840929da52aa6a62` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：PIECEWISE graph，TP16，客户端并发 64，服务 seq32，GPQA 198 题

## 问题现象

- 11:11:52 开始 64 并发正式请求；11:17:55 API 对在途请求返回
  `EngineCore encountered an issue` HTTP 500，随后 8010 连接失败。
- runner 11:18:16 以 1 退出。结果文件包含 198 个 `<TIMEOUT>`，但它们是服务退出后
  请求失败的占位标记；`completed=0/198`，不能用于精度判定。
- 运行约 6 分钟时只完成一个 API future，未形成任何有效 GPQA 样本。
- 原始服务日志：容器
  `/workspace/glm53-adaptation-runtime/graph/service.log`；评测日志：
  `/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-indexer-break/runner.log`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| `docs/troubleshooting/distributed-sample-tokens-timeout.md` | TP worker/EngineCore 在长负载下退出，历史轮曾出现 300 秒 `sample_tokens` RPC timeout | 本轮需先确认最早异常、rank 与 work sequence；不能只凭 HTTP 500 套用旧结论 | 中 | 读取每 rank 与最早 traceback 后再决定是否属于同一签名 |
| 2026-09-04 GPQA 故障记录 | 同模型、同平台、并发 64 | 当前插件、正确 BF16 权重及 graph indexer 边界均不同 | 低到中 | 仅作为对照，不直接复用增大超时方案 |

## 诊断与假设

已验证：客户端 64 并发被服务调度为 28 running / 36 waiting；服务故障前
`generation_tokens_total=894`，PPU 有实际利用率，说明启动后曾前进。198 个 timeout
不是 7200 秒 HTTP 计时超时。

已排除本轮的直接原因：不是请求超时、OOM、collective 超时或单次
`execute_model` 超过 1800 秒。日志顺序中最早异常来自 TP rank 6 的 HGGC 非法访存；
其他 worker 的取消和 EngineCore 退出均为后果。

最终定位：分阶段同步证明非法访存首先由 plugin-owned
`kpool_decode_update_and_maybe_write_cache_batched` 产生；bounds probe 进一步确认是 padded
物理 slot 被按逻辑 pool size 4 解码。FlagGems `clamp`/`gather` 以及后续 sparse indexer
阶段均只是异步暴露点。

## 受控尝试

尚未进行任何修复或重跑。当前只执行只读诊断和独立最小复现。

用于读取最早故障上下文的可重复命令（只读；先由 `./scripts/connectivity-check PPU-13`
确认连接，再执行）：

```bash
ssh PPU-13 docker exec glm5.3-flash python3 -c 'from pathlib import Path; p=Path("/workspace/glm53-adaptation-runtime/graph/service.log"); xs=p.read_text(errors="replace").splitlines(); keys=("Traceback (most recent call last)","sample_tokens","TimeoutError","work sequence","EngineCore encountered","OutOfMemory","out of memory","SIG","Exception:"); hits=[i for i,x in enumerate(xs) if any(k in x for k in keys)]; print("LINES",len(xs),"HITS",len(hits)); keep=set(); [keep.update(range(max(0,i-12),min(len(xs),i+45))) for i in hits[-20:]]; print("\n".join(f"{i+1}: {xs[i][:1000]}" for i in sorted(keep)))'
```

用于核对容器、API、worker 与 vLLM 边界的可重复命令：

```bash
ssh PPU-13 docker exec glm5.3-flash bash -lc 'set -euo pipefail; test "$(git -C /workspace/vllm status --porcelain)" = ""; cat /workspace/glm53-adaptation-runtime/graph/service.pid; ps -ef | grep -E "[v]llm serve|VLLM::Worker" || true; curl -fsS --max-time 3 http://127.0.0.1:8010/health || true'
```

首轮精简提取已定位到 rank 12 的 FlagGems 动态 pointwise clamp kernel；以下命令只读
提取第一次完整 traceback 和相关源码调用点，不输出 scheduler 的题目正文：

```bash
ssh PPU-13 "docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph/service.log\").read_text(errors=\"replace\").splitlines(); print(\"\\n\".join(f\"{i+1}: {xs[i][:1200]}\" for i in range(11614,11754)))'"
```

第一次完整 traceback 已确认调用链为
`sparse_attn_indexer_kpool -> append_tail_to_topk -> portable.py:366 -> cols.clamp(max=history_len-1)`，
最终进入 FlagGems 动态 rank-1 clamp kernel 并非法访存。下一步只读核对该函数、调用参数
构造与 `thead.yaml` 是否已排除 clamp：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation && sed -n \"320,390p;720,780p\" vllm_fl/kernels/glm5_next/portable.py vllm_fl/kernels/glm5_next/sparse_attn_indexer_kpool.py && grep -n -E \"clamp|blacklist|unused_flag_gems_ops\" vllm_fl/dispatch/config/thead.yaml'"
```

## 根因

- 已验证到算子：plugin-owned Triton
  `kpool_decode_update_and_maybe_write_cache_batched` 是第一个产生 illegal access 的阶段。
- 已验证到表达式：vLLM tail metadata 的 slot 使用 padded 物理页编码
  `block_id * 768 + position % 768`，而 decode 与 prefill 两个 plugin tail kernel 的旧合约按
  `block_id * 4 + position % 4` 解释并执行 `slot // 4`。小 block id 时会静默读写错误 tail
  page；c64 批次增长到 block 182 时，`tail_slot=140216` 被算成 block 35054，超过 11363
  个 tail blocks 并触发非法访存。
- 直接证据：`5606 = 7*768+230`；首个失败批次
  `tail_map_shape=(25,1)`、`tail=5608..140216/45452`、`position=224..631`，而 compressed
  cache mapping 同时仍在界内。probe 在 kernel 前抛出，未执行该次越界写。
- FlagGems `clamp`/`lt`/`gather` 以及后续 paged-MQA/topk/expand/tail helper 都被分阶段同步
  排除为首发点，不应 blacklist 它们来掩盖 plugin kernel 越界。

历史窄化证据（13:43 诊断）：after-expand 探针未出现任何 `synchronizing count=` 标记；
后续复核发现该计数属于每个 sparse layer 实例，不能拿 11 层的聚合估算值 250 作为
单实例阈值。日志顺序首个 rank 0 直接在 tail helper 的
`torch.gather(topk_result, 1, safe_hist)` 进入 FlagGems `gather_rank_2.py` 时非法访存。
这一步曾把 tail helper 的 gather 列为最强假设；后续更靠近 kernel 边界的同步和 bounds
probe 已推翻该假设，并用上面的 padded slot 公式给出确定根因。

## 解决方法或 Workaround

根因修复：在 plugin-owned prefill/decode tail kernels 中从实际 tail view stride 推导
`physical_page_tokens = stride(1) / stride(2)`；block 使用
`slot // physical_page_tokens`，ring offset 继续使用 `slot % pool_size`。连续测试布局得到 4，
生产 padded 布局得到 768；无新分配、无 host sync、无需环境变量或 vLLM 修改。

不会盲目继续增大 `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS`；当前值 1800 秒，只有在确认所有
worker 存活、持续前进且没有异常/OOM/collective 分歧时才可作为受控诊断。

## FlagGems 证据

不同 rank 的异步栈分别在 `append_tail_to_topk` 的首个
`cols < history_len` 和随后的 `cols.clamp(max=history_len-1)` 暴露 HGGC 非法访存。
已展开的 rank 3 栈显示 FlagGems `lt_scalar` 动态 kernel，而 rank 12 随后显示
FlagGems `clamp` 动态 kernel。二者都使用新建的 `cols`，说明异常很可能由它们之前的
异步 kernel 写坏内存或设备状态，而非这两个简单 pointwise 运算同时独立越界。
当时 `history_len=2048`、`pool_size=4`，逻辑输入 `[1,2051]` int64。

按 FlagGems 缺陷流程，使用临时控制器 playbook
`/tmp/ppu13-glm53-flaggems-clamp-repro.yml` 在运行中的适配容器根目录创建
`/bug/flaggems-clamp-max-int64-2051-ppu`，并执行：

```bash
docker exec -e CUDA_VISIBLE_DEVICES=0 -w /bug/flaggems-clamp-max-int64-2051-ppu glm5.3-flash python3 repro.py --mode eager
docker exec -e CUDA_VISIBLE_DEVICES=0 -w /bug/flaggems-clamp-max-int64-2051-ppu glm5.3-flash python3 repro.py --mode graph
```

包固定 seed，记录 shape/dtype/stride、镜像、FlagGems revision、软件版本，原生
PyTorch reference 与 FlagGems 路径分离；eager 和 graph 分进程，避免非法地址污染后续测试。

2026-09-06 11:35（UTC+8）结果：独立 eager 与 graph 都以 rc=0 通过精确比较；
直接 `FlagGems clamp(max=2047)` 在该输入上不复现非法访存。该包仍保留，作为
“单算子不复现”的边界证据，不能作为已复现的 FlagGems 缺陷提交。

下一轮只读检查将核对生成的 clamp kernel、失败前 indexer 的各 kernel 边界与配置；
可重复命令如下：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'sed -n \"330,385p\" /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl/kernels/glm5_next/portable.py; sed -n \"730,775p\" /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl/kernels/glm5_next/sparse_attn_indexer_kpool.py; sed -n \"1,240p\" /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl/dispatch/config/thead.yaml; sed -n \"1,240p\" /root/.flaggems/code_cache/*clamp_func_max_kernel_rank_1_bptr_t512.py'"
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation && git grep -n -E \"append_tail_to_topk|eager_break_during_capture|flag_gems|blacklist\" -- vllm_fl tests | head -n 240'"
```

若上述静态检查仍不能判断首个异步故障，将先读取当前服务状态与现有启动脚本，再决定
是否以 `CUDA_LAUNCH_BLOCKING=1` 做一次诊断启动；不会先修改生产脚本：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'ps -ef | grep -E \"[v]llm serve|VLLM::Worker\" || true; curl -fsS --max-time 3 http://127.0.0.1:8010/health || true'; sed -n \"1,220p\" /mnt/nfs/users/jinghao/glm5.3-flash/start_server.sh; docker exec glm5.3-flash python3 - <<\"PY\"
from pathlib import Path
xs = Path("/workspace/glm53-adaptation-runtime/graph/service.log").read_text(errors="replace").splitlines()
for i in range(11520, 11670):
    print(f"{i+1}: {xs[i][:1200]}")
PY'"
```

首次读取确认 API 与全部 worker 已退出，容器仍在运行；启动脚本位于 host NFS，未挂载
到容器内；随后 host 侧也确认预期的 `start_server.sh` 文件名不存在，需要列出目录核对
实际脚本名。继续用下列只读命令提取第一个 rank 异常之前的所有
错误标记以及 indexer 中紧邻 `append_tail_to_topk` 的上游 kernel 调用：

```bash
ssh PPU-13 "sed -n '1,220p' /mnt/nfs/users/jinghao/glm5.3-flash/start_server.sh; docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph/service.log\").read_text(errors=\"replace\").splitlines(); hits=[(i,x) for i,x in enumerate(xs[:11595]) if any(k in x for k in (\"ERROR\",\"illegal memory\",\"WorkerProc hit\",\"Traceback\"))]; print(\"\\n\".join(f\"{i+1}: {x[:1200]}\" for i,x in hits[-260:]))'; docker exec glm5.3-flash sed -n '650,770p' /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl/kernels/glm5_next/sparse_attn_indexer_kpool.py"
```

```bash
ssh PPU-13 "find /mnt/nfs/users/jinghao/glm5.3-flash -maxdepth 2 -type f -printf '%p\n' | sort | head -n 240; docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph/service.log\").read_text(errors=\"replace\").splitlines(); hits=[(i,x) for i,x in enumerate(xs) if \"WorkerProc hit an exception\" in x or \"illegal memory access\" in x]; print(\"\\n\".join(f\"{i+1}: {x[:1000]}\" for i,x in hits[:80]))'"
```

排序结果确认实际生产脚本为 `start_glm53_graph.sh`；rank 6/7/14/8/15 等在同一秒
先后报错，说明是跨 TP rank 的同一轮模型执行故障。为确认日志顺序中第一个 rank 6
具体暴露点，并读取实际启动环境，使用：

```bash
ssh PPU-13 "sed -n '1,220p' /mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph.sh; docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph/service.log\").read_text(errors=\"replace\").splitlines(); print(\"\\n\".join(f\"{i+1}: {xs[i][:1200]}\" for i in range(8010,8155)))'"
```

该检查确认生产参数仅含 timeout、breakable graph 和必要的 vLLM 参数；首个 rank 6
栈在 `clamp` 暴露，但日志明确提示异步堆栈可能不准确。启动同步诊断前先读取 host wrapper
和现有状态文件，命令如下：

```bash
ssh PPU-13 "sed -n '1,260p' /mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph_host.sh; docker exec glm5.3-flash bash -lc 'find /workspace/glm53-adaptation-runtime/graph -maxdepth 1 -type f -printf \"%f %s bytes\\n\" | sort; ps -ef | grep -E \"[v]llm serve|VLLM::Worker\" || true'"
```

受控诊断变量：只增加 `CUDA_LAUNCH_BLOCKING=1`，保持模型、TP16、PIECEWISE graph、
50K、seq32、timeout=1800 及 plugin/FlagGems/vLLM revision 不变。使用临时控制器
playbook `/tmp/ppu13-glm53-launch-blocking.yml`，把诊断状态隔离到容器
`/workspace/glm53-adaptation-runtime/graph-launch-blocking/`；先保留故障日志副本，不修改
NFS 上的生产启动脚本，也不停止/重启容器：

```bash
./scripts/playbook /tmp/ppu13-glm53-launch-blocking.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-launch-blocking.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-launch-blocking.yml --limit PPU-13
```

首次实际运行在只读 guard 阶段停止：`pgrep` 匹配了 guard 自身的命令行，未发生任何
远端修改或启动。将 guard 收紧为仅匹配以 `vllm serve` / `VLLM::Worker` 开头的真实
进程后，重跑同一 playbook；这只修正诊断控制器，不改变服务变量。

12:48（UTC+8）隔离诊断进程已提交，PID `815174`；原故障日志保存在
`/workspace/glm53-adaptation-runtime/graph/service-gpqa-c64-illegal-access.log`。容器未重启，
生产脚本未修改。只读轮询启动状态和首错使用：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-launch-blocking/service.pid); if kill -0 \"$pid\" 2>/dev/null; then echo PID_ALIVE=$pid; else echo PID_DEAD=$pid; fi; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY || true; tail -n 80 /workspace/glm53-adaptation-runtime/graph-launch-blocking/service.log'"
```

12:51（UTC+8）诊断服务健康检查通过。复现负载前先只读核对上一轮正式 runner 的配置、
启动命令与评测容器状态，避免改变生成参数或误用缓存：

```bash
ssh PPU-13 "find /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-indexer-break -maxdepth 2 -type f -printf '%p %s bytes\n' | sort; sed -n '1,180p' /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-indexer-break/runner.log; docker ps -a --filter name=flageval_llmeval-jinghao --format '{{.Names}} {{.Status}} {{.Image}}'"
```

评测容器仍在运行；上一轮确认使用原样 `llmrun.py`、198 题、c64、timeout7200、
max_gen_toks30000 且 cache=0。为创建隔离 run id 前仅读取短配置和启动 wrapper：

```bash
ssh PPU-13 "sed -n '1,220p' /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-indexer-break/start_gpqa.sh; sed -n '1,240p' /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-indexer-break/llm_config.json"
```

同步诊断负载保持上一轮的全部 198 题和 c64，以覆盖实际触发条件；只更换 eval model、
run id、output root 与 cache root，结果明确标记为 diagnostic，不用于验收评分。使用临时
控制器 playbook `/tmp/ppu13-glm53-gpqa-launch-blocking.yml` 复制同一份
`llmrun.py`/grader/progress scorer，先 `--preflight-only`，再后台启动：

```bash
./scripts/playbook /tmp/ppu13-glm53-gpqa-launch-blocking.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-launch-blocking.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-launch-blocking.yml --limit PPU-13
```

诊断目录为
`/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-launch-blocking`，
独立 cache 为 `/tmp/lm_eval_cache-glm53-bf16-20260906-launch-blocking`。若同步堆栈定位首错，
立即停止该诊断 runner；不会把其分数计入正式 acceptance。

首轮 check mode 仅因目标目录尚未实际创建而使后续 `copy` 无法模拟，未发生远端写入。
将依赖真实目录的 copy/preflight/launch 任务在 check mode 中显式跳过，保留目录创建 diff，
再运行同一 check/diff 与实际 playbook。

12:55（UTC+8）preflight 通过，诊断 runner PID `13638`，cache 起始为空。只读监控命令：

```bash
ssh PPU-13 "test -f /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-launch-blocking/exit.code && cat /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-launch-blocking/exit.code || echo RUNNING; tail -n 40 /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-launch-blocking/runner.log; docker exec glm5.3-flash python3 -c 'from pathlib import Path; p=Path(\"/workspace/glm53-adaptation-runtime/graph-launch-blocking/service.log\"); xs=p.read_text(errors=\"replace\").splitlines(); keys=(\"illegal memory access\",\"WorkerProc hit an exception\",\"EngineCore encountered\",\"Traceback (most recent call last)\"); hits=[(i,x) for i,x in enumerate(xs) if any(k in x for k in keys)]; print(\"SERVICE_LINES\",len(xs),\"HITS\",len(hits)); print(\"\\n\".join(f\"{i+1}: {x[:1200]}\" for i,x in hits[-40:]))'"
```

同步模式下 runner 尚无完成样本时，用服务 metrics 区分“仍在前进”与“已停滞”；只读命令：

```bash
ssh PPU-13 "docker exec glm5.3-flash curl -fsS --max-time 5 http://127.0.0.1:8010/metrics | grep -E 'num_requests_running|num_requests_waiting|prompt_tokens_total|generation_tokens_total|kv_cache_usage_perc'"
```

连续两次 metrics 均停在 prompt=470、generation=3。按 PPU 平台规则使用仓库封装查询
设备利用率，并同时只读检查 worker 进程 CPU/状态，判断同步执行是极慢还是停滞：

```bash
./scripts/accelerator-check --limit PPU-13
ssh PPU-13 "docker exec glm5.3-flash ps -eo pid,stat,pcpu,pmem,etime,comm,args | grep -E 'VLLM::Worker|EngineCore' | head -n 40"
```

13:00（UTC+8）结果：16 个 worker 均为 running、CPU 约 59%–63%，PPU0–3 抽样利用率
10%–22%，所以不是死锁；但同步模式运行约 11 分钟仍只有 3 个 generation token，无法在
合理时间到达原故障约 894 token 的触发点。该全局同步实验判定为“诊断开销过高”，保留
日志后停止仅本轮诊断 runner 与服务，容器保持运行。使用临时控制器 playbook
`/tmp/ppu13-glm53-stop-launch-blocking.yml`，精确核对 PID/cmdline 后发送 TERM 并验证退出：

```bash
./scripts/playbook /tmp/ppu13-glm53-stop-launch-blocking.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-launch-blocking.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-launch-blocking.yml --limit PPU-13
```

下一实验仅在 sparse indexer 的阶段边界同步，首先在进入 `append_tail_to_topk` 前同步；
这能判断非法访存来自上游 `paged_mqa/topk/expand/dec_seq`，还是 tail helper 自身，同时
避免全模型每个 kernel 都强制同步。

TERM 后 runner 已退出，但服务在 60 秒验证窗口内未完全清理。未升级信号；先只读检查
精确 PID、worker、端口和 shutdown 日志，区分 API 主进程仍存活、僵尸进程或 worker
卡在同步 kernel：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-launch-blocking/service.pid); ps -p \"$pid\" -o pid,ppid,stat,etime,comm,args; pgrep -af \"^VLLM::Worker\" || true; if (exec 3<>/dev/tcp/127.0.0.1/8010) 2>/dev/null; then echo PORT8010_LISTENING; else echo PORT8010_DOWN; fi; tail -n 120 /workspace/glm53-adaptation-runtime/graph-launch-blocking/service.log'"
```

检查结果：8010 已关闭、worker 已退出，只有 APIServer 在等待连接关闭；这提示 runner
shell 的 Python 子进程可能仍持有连接。先只读列出评测容器中与本次 run id/目录精确匹配
的进程，再决定是否终止该子进程：

```bash
ssh PPU-13 "docker exec flageval_llmeval-jinghao ps -eo pid,ppid,stat,etime,comm,args | grep -F 'diagnostic-gpqa-20260906-c64-launch-blocking' || true; docker exec flageval_llmeval-jinghao ps -eo pid,ppid,stat,etime,comm,args | grep -E '[l]lm_eval|[l]lmrun.py' || true"
```

已解析出仅属于本次诊断目录的残留进程：`llmrun.py` PID 13647、`lm_eval` PID 13793、
progress scorer PID 13794。它们是被终止 wrapper 的子进程，未收到 TERM。使用临时
playbook `/tmp/ppu13-glm53-stop-diagnostic-eval-children.yml` 逐个再次核对 cmdline 必须
包含诊断目录后发送 TERM，并验证这三个 PID、APIServer、端口与 worker 全部退出：

```bash
./scripts/playbook /tmp/ppu13-glm53-stop-diagnostic-eval-children.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-diagnostic-eval-children.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-diagnostic-eval-children.yml --limit PPU-13
```

三者收到 TERM 后 30 秒内仍对 `kill -0` 可见。未直接升级 SIGKILL；先只读检查它们
是否为 zombie、不可中断睡眠或仍在运行，并复核服务进程是否已随连接关闭而退出：

```bash
ssh PPU-13 "docker exec flageval_llmeval-jinghao ps -p 13647,13793,13794 -o pid,ppid,stat,wchan:24,etime,comm,args; docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-launch-blocking/service.pid); ps -p \"$pid\" -o pid,ppid,stat,wchan:24,etime,comm,args; pgrep -af \"^VLLM::Worker\" || true; if (exec 3<>/dev/tcp/127.0.0.1/8010) 2>/dev/null; then echo PORT_UP; else echo PORT_DOWN; fi'"
```

结果：三个评测进程均为 `<defunct>` zombie，实际执行已结束；API PID、worker 与 8010
均已退出，适配容器仍运行。因此无需 SIGKILL。进入 indexer 边界同步前，只读保存 plugin
与 vLLM 工作树、精确函数上下文和现有相关测试清单：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'git -C /workspace/vllm-plugin-FL-glm53-hy4-adaptation status --short; git -C /workspace/vllm-plugin-FL-glm53-hy4-adaptation rev-parse HEAD; git -C /workspace/vllm status --short; git -C /workspace/vllm rev-parse HEAD; sed -n \"690,775p\" /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl/kernels/glm5_next/sparse_attn_indexer_kpool.py; find /workspace/vllm-plugin-FL-glm53-hy4-adaptation/tests -type f | grep -E \"glm5|indexer|sparse\" | sort'"
```

边界确认：vLLM `ee0da84` 工作树为空；plugin 仍是既有未提交适配树，未被本轮诊断修改。
为避免把一次性同步探针放入 plugin，使用容器临时路径
`/workspace/glm53-adaptation-runtime/indexer-sync-probe/sitecustomize.py`。它通过 Python
import hook 只包装 `portable.append_tail_to_topk`，在调用原函数前执行一次
`torch.cuda.synchronize()` 并打印一次安装标记；无其他运行时改动。诊断服务隔离到
`/workspace/glm53-adaptation-runtime/graph-indexer-sync-before-tail/`，通过 `PYTHONPATH`
启用探针。临时控制器 playbook 与执行顺序：

```bash
./scripts/playbook /tmp/ppu13-glm53-indexer-sync-probe.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-indexer-sync-probe.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-indexer-sync-probe.yml --limit PPU-13
```

启动后先验证 16 个 worker 均出现探针安装标记和 health=200，再使用新的隔离 c64 诊断
run 重放。若错误落在探针的同步行，则上游阶段已损坏设备状态；若同步通过而原函数内
报错，则继续把同步边界向 helper 内部移动。探针不属于生产实现，定位后清理。

13:08（UTC+8）探针独立 import 测试通过，服务 PID `841164` 已提交。只读轮询会同时
验证 health、安装标记数量和早期异常：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-indexer-sync-before-tail/service.pid); if kill -0 \"$pid\" 2>/dev/null; then echo PID_ALIVE=$pid; else echo PID_DEAD=$pid; fi; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY || true; grep -c \"GLM53_INDEXER_SYNC_PROBE.*installed\" /workspace/glm53-adaptation-runtime/graph-indexer-sync-before-tail/service.log || true; tail -n 70 /workspace/glm53-adaptation-runtime/graph-indexer-sync-before-tail/service.log'"
```

13:22（UTC+8）health=200、16/16 worker 安装标记、启动阶段无异常。使用同一官方 runner
和相同 198 题/c64 参数，以新目录和新 cache 运行 pre-tail 同步诊断；仍不作为正式验收：

```bash
./scripts/playbook /tmp/ppu13-glm53-gpqa-sync-before-tail.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-sync-before-tail.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-sync-before-tail.yml --limit PPU-13
```

目录：`/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-sync-before-tail`；
cache：`/tmp/lm_eval_cache-glm53-bf16-20260906-sync-before-tail`。

13:24（UTC+8）preflight 通过，runner PID `14434`，cache=0。首错监控命令：

```bash
ssh PPU-13 "test -f /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-sync-before-tail/exit.code && cat /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-sync-before-tail/exit.code || echo RUNNING; tail -n 12 /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-sync-before-tail/runner.log; docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph-indexer-sync-before-tail/service.log\").read_text(errors=\"replace\").splitlines(); keys=(\"illegal memory access\",\"WorkerProc hit an exception\",\"EngineCore encountered\",\"Traceback (most recent call last)\"); hits=[(i,x) for i,x in enumerate(xs) if any(k in x for k in keys)]; print(\"SERVICE_LINES\",len(xs),\"HITS\",len(hits)); print(\"\\n\".join(f\"{i+1}: {x[:1200]}\" for i,x in hits[-60:]))'"
```

连续约 3 分钟仍停在 prompt=470、generation=3，证明每次 indexer 调用同步仍不可用。
首次读取 config 顶层的层数字段返回 `None`，字段位于嵌套配置；下一步先解析嵌套模型
结构和精确列出本次诊断进程，然后终止本次 runner/service，保留日志：

```bash
ssh PPU-13 "docker exec glm5.3-flash python3 -c 'import json; c=json.load(open(\"/mnt/cpfs/models/GLM-5.3-Flash-BF16/config.json\")); print(c.keys()); t=c.get(\"text_config\",{}); print({k:t.get(k) for k in t if any(s in k for s in (\"layer\",\"attention\",\"expert\"))})'; docker exec flageval_llmeval-jinghao ps -eo pid,ppid,stat,etime,comm,args | grep -F 'diagnostic-gpqa-20260906-c64-sync-before-tail' || true; docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-indexer-sync-before-tail/service.pid); ps -p \"$pid\" -o pid,ppid,stat,etime,comm,args'"
```

新的探针将按 worker 本地调用计数，仅在接近历史故障窗口的有限区间同步；阈值必须先由
真实层数和历史 generation token 数推导，不猜测。

模型有 45 层，其中 11 层为 `deepseek_sparse_attention`（每 4 层一次）。正式故障时
generation_tokens_total=894，对 32 个 running 请求约为 28 个 decode step，因此每个
worker 约执行 `28*11=308` 次 tail helper；同步窗口可从本地调用计数 250 附近开始。
当前诊断精确残留为 llmrun PID 14443、lm_eval 14589、scorer 14590；使用临时 playbook
`/tmp/ppu13-glm53-stop-sync-before-tail.yml`，先终止评测树，再终止 API，并将 zombie 视为
“已结束等待容器 init 回收”，不再误判：

```bash
./scripts/playbook /tmp/ppu13-glm53-stop-sync-before-tail.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-sync-before-tail.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-sync-before-tail.yml --limit PPU-13
```

但停止 playbook 执行前，诊断在 13:29:18（UTC+8）自行稳定复现并使 runner 退出 1；
所以 guard 发现原 PID 已不存在并安全停止，没有产生额外修改。运行 284.84 秒，198 个
timeout 仍全是 EngineCore 退出后的占位，不用于评分。下一步只读提取日志顺序中第一个
`WorkerProc hit an exception` 的完整 170 行，核对是否命中 probe 同步行，并读取故障前
metrics 最后值：

```bash
ssh PPU-13 "docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph-indexer-sync-before-tail/service.log\").read_text(errors=\"replace\").splitlines(); i=next(i for i,x in enumerate(xs) if \"WorkerProc hit an exception\" in x); print(\"FIRST_LINE\",i+1); print(\"\\n\".join(f\"{j+1}: {xs[j][:1400]}\" for j in range(max(0,i-5),min(len(xs),i+170)))); ms=[(j,x) for j,x in enumerate(xs[:i]) if \"Avg prompt throughput\" in x]; print(\"LAST_METRICS\", ms[-1] if ms else None)'"
```

结果：日志顺序首个 rank 4 的异常精确落在探针
`sitecustomize.py:25 torch.cuda.synchronize()`，证明错误在进入 tail helper 前已挂起；
原先 `clamp`/`lt` 栈只是异步误归因。

下一受控实验把同步点移到 `expand_pools_to_tokens` 返回后，并避免从启动即同步：探针只在
health 通过后由 sentinel 显式 arm，按 worker 本地 indexer 调用计数，从第 250 次开始同步。
45 层中 11 个 sparse attention、原故障约 28 个 decode step，对应约 308 次调用；250
是依据该观测设置的窗口起点。临时探针与服务路径分别为：

- `/workspace/glm53-adaptation-runtime/indexer-sync-after-expand-probe/sitecustomize.py`
- `/workspace/glm53-adaptation-runtime/graph-indexer-sync-after-expand/`

控制器命令：

```bash
./scripts/playbook /tmp/ppu13-glm53-sync-after-expand-probe.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-sync-after-expand-probe.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-sync-after-expand-probe.yml --limit PPU-13
```

13:34（UTC+8）探针 import/disarmed 验证通过，服务 PID `857568` 已提交；源码未修改。
启动轮询命令：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-indexer-sync-after-expand/service.pid); if kill -0 \"$pid\" 2>/dev/null; then echo PID_ALIVE=$pid; else echo PID_DEAD=$pid; fi; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY || true; grep -c \"GLM53_SYNC_AFTER_EXPAND.*installed\" /workspace/glm53-adaptation-runtime/graph-indexer-sync-after-expand/service.log || true; grep -c \"GLM53_SYNC_AFTER_EXPAND.*armed\" /workspace/glm53-adaptation-runtime/graph-indexer-sync-after-expand/service.log || true; tail -n 45 /workspace/glm53-adaptation-runtime/graph-indexer-sync-after-expand/service.log'"
```

13:37（UTC+8）health=200、16/16 安装、0/16 armed。使用单机 playbook 在再次验证 health
后创建唯一 ARM sentinel，再创建全新 c64 诊断目录、运行 preflight 并启动 runner：

```bash
./scripts/playbook /tmp/ppu13-glm53-gpqa-sync-after-expand.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-sync-after-expand.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-sync-after-expand.yml --limit PPU-13
```

诊断目录：`/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-sync-after-expand`；
cache：`/tmp/lm_eval_cache-glm53-bf16-20260906-sync-after-expand`。

13:39（UTC+8）ARM sentinel 已创建、preflight 通过，runner PID `15078`、cache=0。只读
监控将同时观察 `armed`、`synchronizing count=` 和首个异常：

```bash
ssh PPU-13 "test -f /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-sync-after-expand/exit.code && cat /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-sync-after-expand/exit.code || echo RUNNING; docker exec glm5.3-flash grep -E 'GLM53_SYNC_AFTER_EXPAND|illegal memory access|WorkerProc hit an exception' /workspace/glm53-adaptation-runtime/graph-indexer-sync-after-expand/service.log | tail -n 80; docker exec glm5.3-flash curl -fsS --max-time 5 http://127.0.0.1:8010/metrics | grep -E 'num_requests_running|num_requests_waiting|prompt_tokens_total|generation_tokens_total'"
```

13:43:42（UTC+8）多 rank 非法访存再次稳定复现，服务端口退出。为判断错误是否正落在
第 250 次后的 after-expand 同步点，提取所有窗口标记、日志顺序首个完整 traceback 和
故障前最后 metrics：

```bash
ssh PPU-13 "docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph-indexer-sync-after-expand/service.log\").read_text(errors=\"replace\").splitlines(); marks=[(i,x) for i,x in enumerate(xs) if \"GLM53_SYNC_AFTER_EXPAND\" in x]; print(\"MARKS\"); print(\"\\n\".join(f\"{i+1}: {x[:1200]}\" for i,x in marks)); i=next(i for i,x in enumerate(xs) if \"WorkerProc hit an exception\" in x); print(\"FIRST_LINE\",i+1); print(\"\\n\".join(f\"{j+1}: {xs[j][:1400]}\" for j in range(max(0,i-5),min(len(xs),i+165)))); ms=[(j,x) for j,x in enumerate(xs[:i]) if \"Avg prompt throughput\" in x]; print(\"LAST_METRICS\",ms[-1] if ms else None)'"
```

按 FlagGems 缺陷流程，在运行中的适配容器根目录创建独立复现包
`/bug/flaggems-gather-expanded-index-ppu`。它直接构造 int32 input `[32,2048]` 和 int64
expanded index `[32,2051]` stride `[0,1]`，与原生 PyTorch reference 精确比较，eager
和 graph 分进程执行。临时控制器与命令：

```bash
./scripts/playbook /tmp/ppu13-glm53-flaggems-gather-expanded-repro.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-flaggems-gather-expanded-repro.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-flaggems-gather-expanded-repro.yml --limit PPU-13

docker exec -e CUDA_VISIBLE_DEVICES=0 -w /bug/flaggems-gather-expanded-index-ppu glm5.3-flash python3 repro.py --mode eager
docker exec -e CUDA_VISIBLE_DEVICES=0 -w /bug/flaggems-gather-expanded-index-ppu glm5.3-flash python3 repro.py --mode graph
```

2026-09-06 14:02（UTC+8）结果：控制组 rows=1 与真实布局 rows=32 的 eager、graph
四个独立进程全部 rc=0 且精确比较通过；rows=32 确认为 index shape `[32,2051]`、stride
`[0,1]`、non-contiguous。单独布局假设被否定，复现包保留为“不单独复现”的边界证据。
执行前后 vLLM 仍为 `ee0da84` 且工作树为空；适配容器未重启。

控制端首次两次 `--check --diff` 因本机 Ansible multiprocessing RPC 启动超时，均未连接
远端；在受限沙箱外重跑同一命令后通过，随后才执行实际单机 playbook。下一步只读核对
FlagGems `gather` 的 Python 入口和本次最小包是否确实命中同一生成 kernel，并检查该
kernel 如何处理 gather 维度；可重复命令：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'sed -n \"1,280p\" /workspace/FlagGems/src/flag_gems/ops/gather.py; python3 -c \"import flag_gems.ops.gather as g,inspect; print(g); print(inspect.getsource(g))\"; find /root/.flaggems/code_cache -maxdepth 1 -type f -name \"gather*\" -printf \"%f %T@\\n\" | sort -k2n'"
```

该检查确认 FlagGems 会先用 `restride_dim(inp, dim, index.shape)` 把 gather 维输入 stride
置零，再由生成 kernel 加载 index；rows=32 最小包也确实更新并使用了同一个
`gather_rank_2.py`。因此生成公式本身没有从静态代码直接证明越界。下一步读取
`topk_result` 的完整产生与消费路径、graph break/capture 标记和相关测试，判断是否存在
临时 tensor 生命周期或动态 shape 地址问题：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'sed -n \"1,860p\" /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl/kernels/glm5_next/sparse_attn_indexer_kpool.py; git -C /workspace/vllm-plugin-FL-glm53-hy4-adaptation grep -n -E \"topk_decode|append_tail_to_topk|cudagraph|graph_break|eager_break|INDEXER_BACKEND\" -- vllm_fl tests | head -n 320; sed -n \"1,220p\" /workspace/FlagGems/src/flag_gems/utils/shape_utils.py'"
```

完整 decode 路径显示 pre-tail 同步点实际位于
`kpool_decode_update_and_maybe_write_cache_batched -> paged_mqa_logits -> topk_decode ->
expand_pools_to_tokens -> dec_seq/pool_lens` 之后，因此它只能证明这整段已有挂起错误，不能
证明 tail gather 自身。为纠正 after-expand 探针阈值，先读取其计数实现和故障日志中的全部
安装/armed 标记，并统计每个 worker 的实际本地计数输出：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'sed -n \"1,280p\" /workspace/glm53-adaptation-runtime/indexer-sync-after-expand-probe/sitecustomize.py; grep -E \"GLM53_SYNC_AFTER_EXPAND\" /workspace/glm53-adaptation-runtime/graph-indexer-sync-after-expand/service.log | tail -n 200'"
```

探针确实按 module-global backend proxy 计数，但 PIECEWISE graph 的 Python 调用次数没有
达到按输出 token 粗估的 250，说明 output token 指标不能换算成 eager-break Python 调用
次数。下一实验不再依赖计数：服务启动/capture 时保持 disarmed，health 通过后才 arm；随后
只在五个 indexer 阶段返回后依次同步，日志用唯一阶段名标记首个接收到设备错误的位置：
`kpool_decode_update`、`paged_mqa_logits`、`topk_decode`、`expand_pools_to_tokens`、
`append_tail_to_topk`。探针仍位于容器临时 runtime，不修改 plugin/vLLM/FlagGems 源码。

```bash
./scripts/playbook /tmp/ppu13-glm53-indexer-stage-sync-probe.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-indexer-stage-sync-probe.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-indexer-stage-sync-probe.yml --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-stage-sync.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-stage-sync.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-stage-sync.yml --limit PPU-13
```

诊断目录：
`/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-stage-sync`；
只用于首错定位，不计入正式验收。

14:18（UTC+8）服务 PID `872521` 已提交，probe import 验证通过且仍为 disarmed；容器与
源码仓库未重启、未修改。health/16-worker 安装标记与早期异常的只读轮询命令：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-indexer-stage-sync/service.pid); if kill -0 \"$pid\" 2>/dev/null; then echo PID_ALIVE=$pid; else echo PID_DEAD=$pid; fi; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY || true; grep -c \"GLM53_INDEXER_STAGE_SYNC.*installed\" /workspace/glm53-adaptation-runtime/graph-indexer-stage-sync/service.log || true; grep -E \"GLM53_INDEXER_STAGE_SYNC|illegal memory access|WorkerProc hit an exception\" /workspace/glm53-adaptation-runtime/graph-indexer-stage-sync/service.log | tail -n 80'"
```

16/16 worker 已安装探针，但 8010 仍在初始化阶段。为确认不是停滞，读取日志尾部和进程
状态（只读）：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'tail -n 120 /workspace/glm53-adaptation-runtime/graph-indexer-stage-sync/service.log; ps -eo pid,stat,pcpu,pmem,etime,comm,args | grep -E \"VLLM::Worker|EngineCore|vllm serve\" | head -n 40'"
```

14:21（UTC+8）服务完成 PIECEWISE graph capture 并开始监听 8010；14:22 preflight 通过，
探针已 arm，隔离 runner PID `15707`。首错监控命令：

```bash
ssh PPU-13 "test -f /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-stage-sync/exit.code && cat /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-stage-sync/exit.code || echo RUNNING; tail -n 16 /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-stage-sync/runner.log; docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph-indexer-stage-sync/service.log\").read_text(errors=\"replace\").splitlines(); keys=(\"GLM53_INDEXER_STAGE_SYNC\",\"illegal memory access\",\"WorkerProc hit an exception\",\"EngineCore encountered\"); hits=[(i,x) for i,x in enumerate(xs) if any(k in x for k in keys)]; print(\"SERVICE_LINES\",len(xs),\"HITS\",len(hits)); print(\"\\n\".join(f\"{i+1}: {x[:1400]}\" for i,x in hits[-120:]))'"
```

14:27:29（UTC+8）16 rank 再次稳定同时报非法访存。提取日志顺序中第一个 rank 9 的
完整 traceback，利用其 indexer 调用行确定是哪一个 stage 的返回后同步接收到错误：

```bash
ssh PPU-13 "docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph-indexer-stage-sync/service.log\").read_text(errors=\"replace\").splitlines(); i=next(i for i,x in enumerate(xs) if \"WorkerProc hit an exception\" in x); print(\"FIRST_LINE\",i+1); print(\"\\n\".join(f\"{j+1}: {xs[j][:1600]}\" for j in range(max(0,i-8),min(len(xs),i+190))))'"
```

14:27:29（UTC+8）故障稳定复现。日志顺序首个 rank 9 栈精确落在
`sparse_attn_indexer_kpool.py:643` 调用
`INDEXER_BACKEND.kpool_decode_update_and_maybe_write_cache_batched` 返回后的探针同步，随后
五个后续阶段尚未开始；因此 tail gather、expand、topk 与 paged-MQA 均是原异步日志中的
暴露点，真正首先产生 illegal access 的阶段已缩小为 batched kpool decode cache update。

下一步只读定位这个 backend symbol 的来源、Triton 实现、shape/stride 合约和现有测试；
并确认它是 plugin-owned 还是 FlagGems operator，再决定工作根 `08-bugs/` 归档和最小修复边界；
已有用例通过容器对应路径原地执行，不再复制到 `/bug`：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; git grep -n \"kpool_decode_update_and_maybe_write_cache_batched\" -- vllm_fl tests; sed -n \"1,320p\" vllm_fl/kernels/glm5_next/indexer_backend.py; git -C /workspace/FlagGems grep -n \"kpool_decode_update_and_maybe_write_cache_batched\" -- src tests || true; git -C /workspace/vllm status --short'"
```

该名字在 model-facing backend 中只是 `CachedOp` 合约，FlagGems 没有同名符号；首次
`git grep` 也未打印具体实现，说明需要按注册名和短 kernel 名继续查找非显式同名绑定：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; rg -n \"sparse_indexer_kpool_decode|kpool_decode_update|maybe_write_cache|decode_update\" vllm_fl tests; rg -n \"register.*sparse_indexer|sparse_indexer_.*kpool\" vllm_fl/dispatch vllm_fl/kernels | head -n 320'"
```

容器内未安装 `rg`；该只读搜索未执行。按工作区规则回退为递归 `grep`：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; grep -RInE \"sparse_indexer_kpool_decode|kpool_decode_update|maybe_write_cache|decode_update\" vllm_fl tests --include=\"*.py\"; grep -RInE \"register.*sparse_indexer|sparse_indexer_.*kpool\" vllm_fl/dispatch vllm_fl/kernels --include=\"*.py\" | head -n 320'"
```

定位结果：这是 plugin-owned Triton 算子，实现在
`vllm_fl/kernels/glm5_next/kpool_compress.py:373-640`，thead backend 仅转发；FlagGems
没有该同名算子，所以无需为本问题创建 FlagGems `08-bugs/` 复现包。继续读取 kernel、wrapper、
测试与 git diff，寻找真实 shape/stride 边界和既有非必要改动：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; sed -n \"330,680p\" vllm_fl/kernels/glm5_next/kpool_compress.py; sed -n \"1,100p\" vllm_fl/dispatch/backends/vendor/thead/impl/sparse_indexer.py; find tests -type f -name \"*.py\" -print0 | xargs -0 grep -n \"kpool_decode_update\" || true; git diff -- vllm_fl/kernels/glm5_next/kpool_compress.py tests'"
```

kernel 以 `tail_slot // pool_size` 推导 tail block，而运行时 tail tensor 是从物理 padding
页（日志曾见第三维 768）切出的零拷贝 `[blocks,2,pool_size,head_dim]` view；必须确认
tail metadata 的 slot mapping 是按逻辑 `pool_size` 还是物理 padded page size 编码。若后者，
当前除法会把 block 放大约 `padded_page_size/pool_size` 并直接越界。只读追踪 cache spec、
metadata builder 与 tail slot mapping 构造：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; grep -RInE \"tail_prefix|tail_kv_cache|index_kpool|compress_ratio|KVCacheSpec|page_size\" vllm_fl --include=\"*.py\" | head -n 520; git diff -- vllm_fl/models/glm5_next.py vllm_fl/kernels/glm5_next/sparse_attn_indexer_kpool.py vllm_fl/worker/model_runner.py | head -n 900'"
```

配置确认 `index_kpool=4`，tail spec 在 `glm5_next_kpool.py` 单独定义并被 v0.24 patch
padding。为确定 slot mapping 是否仍按逻辑 block size=4 构造，读取这些精确段落和 runner
物理 tensor reshape：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; sed -n \"220,280p\" vllm_fl/models/glm5_next_kpool.py; sed -n \"55,100p;120,220p;430,510p\" vllm_fl/patches/glm5_next_kpool_v024.py; sed -n \"7180,7270p\" vllm_fl/worker/model_runner.py; sed -n \"1,140p\" vllm_fl/patches/glm5_next_runner_v024.py'"
```

静态代码仍不能证明 slot mapping 的运行时数值域。下一轮临时 probe 在调用 kpool kernel
前记录首批和每轮真实 tensor shape/stride/dtype、tail/cache/position 最小最大值及逻辑容量，
校验 `tail_slot < tail_blocks*pool_size`、`cache_loc < cache_blocks*page_size` 与 tail slot
phase；然后仅在该 kernel 返回后同步。服务与诊断目录分别为：

- `/workspace/glm53-adaptation-runtime/graph-kpool-bounds`
- `/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-kpool-bounds`

```bash
./scripts/playbook /tmp/ppu13-glm53-kpool-bounds-probe.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-kpool-bounds-probe.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-kpool-bounds-probe.yml --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-kpool-bounds.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-kpool-bounds.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-kpool-bounds.yml --limit PPU-13
```

服务加载与 graph capture 的只读轮询命令：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-kpool-bounds-r2/service.pid); ps -p \"$pid\" -o pid,stat,etime,comm,args; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY || true; grep -c \"GLM53_KPOOL_BOUNDS.*installed\" /workspace/glm53-adaptation-runtime/graph-kpool-bounds-r2/service.log || true; tail -n 100 /workspace/glm53-adaptation-runtime/graph-kpool-bounds-r2/service.log'
```

诊断 runner 与首个 bounds/异常的只读监控命令：

```bash
ssh PPU-13 "test -f /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-kpool-bounds-r2/exit.code && cat /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-kpool-bounds-r2/exit.code || echo RUNNING; tail -n 24 /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-kpool-bounds-r2/runner.log 2>/dev/null || true; docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph-kpool-bounds-r2/service.log\").read_text(errors=\"replace\").splitlines(); keys=(\"GLM53_KPOOL_BOUNDS\",\"illegal memory access\",\"WorkerProc hit an exception\",\"EngineCore encountered\"); hits=[(i,x) for i,x in enumerate(xs) if any(k in x for k in keys)]; print(\"SERVICE_LINES\",len(xs),\"HITS\",len(hits)); print(\"\\n\".join(f\"{i+1}: {x[:1800]}\" for i,x in hits[-180:]))'"
```

由于 16 rank 每轮各打印一条，后续轮询只聚合最大映射值、最大调用计数与首个异常，避免
输出完整日志：

```bash
ssh PPU-13 "docker exec glm5.3-flash python3 -c 'from pathlib import Path; import re; xs=Path(\"/workspace/glm53-adaptation-runtime/graph-kpool-bounds-r2/service.log\").read_text(errors=\"replace\").splitlines(); bs=[x for x in xs if \"[GLM53_KPOOL_BOUNDS] count=\" in x]; nums=lambda key:[int(m.group(1)) for x in bs if (m:=re.search(key+r\"=(-?[0-9]+)\",x))]; errs=[(i+1,x) for i,x in enumerate(xs) if any(k in x for k in (\"invalid mapping before kernel\",\"illegal memory access\",\"WorkerProc hit an exception\",\"EngineCore encountered\"))]; print(\"LINES\",len(xs),\"BOUND_ROWS\",len(bs),\"MAX_COUNT\",max(nums(\"count\"),default=-1),\"MAX_TAIL\",max(nums(\"tail_max\"),default=-1),\"MAX_CACHE\",max(nums(\"cache_max\"),default=-1),\"ERRORS\",len(errs)); print(\"\\n\".join(f\"{i}: {x[:1800]}\" for i,x in errs[:20]))'"
```

真实 tail view 为非连续布局，kernel 已使用 `stride(0)`/`stride(1)`；为核对大 stride、
高 block index、负 sentinel 与 graph replay 是否在现有测试中缺失，读取测试和相关调用：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; sed -n \"1,360p\" tests/unit_tests/test_glm5_tail_graph.py; grep -RInE \"kpool_decode_update|tail_kv_cache|TAIL_BLOCK_ELEMS\" tests --include=\"*.py\"'"
```

r2 探针在每层执行多个 `.item()` 并逐 rank 打印，使服务指标长时间仅为
`prompt_tokens_total=470`、`generation_tokens_total=3`；这是诊断开销，不是原始服务性能。
保留日志并停止本轮 runner/service。停止前按 cwd 和 cmdline 解析评测子进程，避免影响其他
评测；随后使用 `/tmp/ppu13-glm53-stop-kpool-bounds-r2.yml` 做单主机 check/diff 和精确 TERM：

```bash
ssh PPU-13 "docker exec flageval_llmeval-jinghao bash -lc 'ps -eo pid,ppid,stat,etime,comm,args | grep -E \"[l]lmrun.py|[l]m_eval|[s]core_progress\" || true; for p in /proc/[0-9]*; do cwd=$(readlink \"$p/cwd\" 2>/dev/null || true); case \"$cwd\" in */diagnostic-gpqa-20260906-c64-kpool-bounds-r2*) echo \"PID=${p##*/} CWD=$cwd\";; esac; done'; docker exec glm5.3-flash bash -lc 'cat /workspace/glm53-adaptation-runtime/graph-kpool-bounds-r2/service.pid; pgrep -af \"^vllm serve |^VLLM::Worker\" || true'"
./scripts/playbook /tmp/ppu13-glm53-stop-kpool-bounds-r2.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-kpool-bounds-r2.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-kpool-bounds-r2.yml --limit PPU-13
```

若 cwd 扫描没有发现活评测子进程，则用 runner.pid 精确检查其状态及直接子进程：

```bash
ssh PPU-13 "pid=$(cat /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-kpool-bounds-r2/runner.pid); docker exec flageval_llmeval-jinghao ps -p \"$pid\" -o pid,ppid,stat,wchan:24,etime,comm,args; docker exec flageval_llmeval-jinghao ps --ppid \"$pid\" -o pid,ppid,stat,wchan:24,etime,comm,args"
```

15:20:25（UTC+8）r2 probe 在 kernel 调用前捕获到确定性越界输入：
`tail=5608..140216/45452`，同时 `cache=-1..255065/17453568` 仍在界内。为确认该行的
shape、position、phase 以及第一个 worker traceback，使用：

```bash
ssh PPU-13 "docker exec glm5.3-flash python3 -c 'from pathlib import Path; xs=Path(\"/workspace/glm53-adaptation-runtime/graph-kpool-bounds-r2/service.log\").read_text(errors=\"replace\").splitlines(); i=next(i for i,x in enumerate(xs) if \"tail_in_bounds=False\" in x); print(\"FIRST_INVALID_LINE\",i+1); print(\"\\n\".join(f\"{j+1}: {xs[j][:2400]}\" for j in range(max(0,i-5),min(len(xs),i+180))))'"
```

首个小批次也揭示了编码关系：`tail_slot=5606`、`position=230`，恰好满足
`5606 = 7 * 768 + 230`；而物理 tail 页第三维正是 768。后续
`140216 = 182 * 768 + 440`。因此 metadata 给出的是 padded 物理页 slot，kernel 却把它
当成 `block_id * 4 + phase` 并执行 `// 4`，前期静默写错页，block id 增大后越界。为确定
修复应位于 tail metadata builder 还是 kernel 调用边界，读取 spec 的 padding 单位和 vLLM
slot mapping 构造公式：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; python3 -c \"import torch; from vllm_fl.models.glm5_next_kpool import KpoolTailSpec; s=KpoolTailSpec(block_size=4,num_kv_heads=1,head_size=256,head_size_v=0,dtype=torch.bfloat16,sliding_window=4,indexes_kv_by_block_stride=True,page_size_padded=393216); print(s); print(vars(s)); print(\\\"PAGE_BYTES\\\",s.page_size_bytes,\\\"PADDED\\\",s.page_size_padded)\"; grep -RInE \"slot_mapping.*block_size|block_table.*slot_mapping|compute_slot_mapping\" /workspace/vllm/vllm/v1 --include=\"*.py\" | head -n 320; sed -n \"100,175p\" vllm_fl/models/glm5_next_kpool.py'"
```

最小修复只改 plugin 的 `kpool_compress.py`、`prefill_tail.py` 和正常测试套件中的
`test_glm5_tail_graph.py`；补充 padded 物理 slot 的高 block eager/graph 覆盖。补丁保存在
容器外临时控制端 `/tmp/glm53-kpool-padded-slot-fix.patch`，进入容器后留存于
`/workspace/glm53-adaptation-runtime/patches/`。执行命令：

```bash
./scripts/playbook /tmp/ppu13-glm53-apply-kpool-padded-slot-fix.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-apply-kpool-padded-slot-fix.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-apply-kpool-padded-slot-fix.yml --limit PPU-13
ssh PPU-13 "docker exec -e CUDA_VISIBLE_DEVICES=0 -w /workspace/vllm-plugin-FL-glm53-hy4-adaptation glm5.3-flash python3 -m pytest -q tests/unit_tests/test_glm5_tail_graph.py"
```

测试先运行整个 tail 文件，必须同时通过既有 prefill eager/graph、零拷贝 view 和新增的
padded prefill/decode eager/graph；若窄化测试失败，不启动整模服务。

首次专项测试结果为 1 passed、3 failed，因此未启动整模服务。失败分成两类：

- 既有 prefill 测试用最后维 stride=2 的 view；页宽只需由 `stride(1)/stride(2)` 推导，
  不应要求 `stride(2)==head_dim`。
- 新增的两个 graph 用例在 capture 后立即检查；目标 PPU graph 需要显式 `replay()` 后再
  检查，既有测试也是这一语义。

修正只改变 prefill wrapper 的过严校验和测试执行顺序，decode 生产布局约束与地址公式不变。
使用从当前已应用源码生成的增量标准补丁，并重跑同一测试命令：

```bash
./scripts/playbook /tmp/ppu13-glm53-apply-kpool-test-corrections.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-apply-kpool-test-corrections.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-apply-kpool-test-corrections.yml --limit PPU-13
ssh PPU-13 "docker exec -e CUDA_VISIBLE_DEVICES=0 -w /workspace/vllm-plugin-FL-glm53-hy4-adaptation glm5.3-flash python3 -m pytest -q tests/unit_tests/test_glm5_tail_graph.py"
```

修正后整个 `test_glm5_tail_graph.py` 为 `4 passed`（14.43s），覆盖既有非连续 prefill、
零拷贝 logical view、新增 padded 高 block prefill 与 decode 的 eager/graph replay。继续审查
三个文件的实际 diff，并运行相邻 GLM/graph 回归：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; git diff --check; git diff -- vllm_fl/kernels/glm5_next/kpool_compress.py vllm_fl/kernels/glm5_next/prefill_tail.py tests/unit_tests/test_glm5_tail_graph.py; git status --short; test -z \"$(git -C /workspace/vllm status --porcelain)\"'"
ssh PPU-13 "docker exec -e CUDA_VISIBLE_DEVICES=0 -w /workspace/vllm-plugin-FL-glm53-hy4-adaptation glm5.3-flash python3 -m pytest -q tests/unit_tests/test_glm5_support.py tests/unit_tests/test_glm5_precision_graph.py tests/unit_tests/test_flaggems_bindings_graph.py"
```

相邻回归结果：`test_glm5_support.py` 22 项、`test_glm5_precision_graph.py` 10 项、
`test_flaggems_bindings_graph.py` 17 项，共 `49 passed`（16.01s）。连同 tail 专项共 53 项
通过。下一步启动无 probe、无额外环境开关的正常 graph 服务，复用 NFS 生产脚本，隔离
runtime 为 `/workspace/glm53-adaptation-runtime/graph-kpool-slot-fix`：

```bash
ssh PPU-13 "sed -n '1,220p' /mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph.sh; docker exec glm5.3-flash bash -lc 'pgrep -af \"^vllm serve |^VLLM::Worker\" || true; if (exec 3<>/dev/tcp/127.0.0.1/8010) 2>/dev/null; then echo PORT_UP; else echo PORT_DOWN; fi; test ! -e /workspace/glm53-adaptation-runtime/graph-kpool-slot-fix; test -z \"$(git -C /workspace/vllm status --porcelain)\"'"
./scripts/playbook /tmp/ppu13-glm53-launch-kpool-slot-fix.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-launch-kpool-slot-fix.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-launch-kpool-slot-fix.yml --limit PPU-13
```

正常服务 PID `921199` 已提交；加载与 graph capture 只读轮询：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-kpool-slot-fix/service.pid); ps -p \"$pid\" -o pid,stat,etime,comm,args; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY || true; grep -E \"Loading safetensors checkpoint shards: 100%|Capturing CUDA graphs|init engine|Application startup complete|illegal memory access|Traceback\" /workspace/glm53-adaptation-runtime/graph-kpool-slot-fix/service.log | tail -n 80'"
```

首次实际 playbook 在 `git apply --check` 停止：补丁的手写 hunk 行数元数据不一致，报
`patch fragment without header at line 32`。当时只在 host/container 临时目录复制了补丁，
plugin 源码没有修改。控制器改为对同一补丁使用 `git apply --recount --check` 和
`git apply --recount`；它只重算 hunk 行数，不放宽上下文匹配。

`--recount` 复核后又在后续 call-site hunk 上因上下文不完整停止，源码仍未修改。为避免
继续手写 hunk，从容器只读复制三个目标文件到临时目录，以本地 `apply_patch` 修改副本，
再由 `git diff --no-index --output=...` 生成标准 unified diff：

```bash
ssh PPU-13 "test ! -e /tmp/glm53-kpool-source-20260906-r3; mkdir -p /tmp/glm53-kpool-source-20260906-r3; docker cp glm5.3-flash:/workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl/kernels/glm5_next/kpool_compress.py /tmp/glm53-kpool-source-20260906-r3/kpool_compress.py; docker cp glm5.3-flash:/workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl/kernels/glm5_next/prefill_tail.py /tmp/glm53-kpool-source-20260906-r3/prefill_tail.py; docker cp glm5.3-flash:/workspace/vllm-plugin-FL-glm53-hy4-adaptation/tests/unit_tests/test_glm5_tail_graph.py /tmp/glm53-kpool-source-20260906-r3/test_glm5_tail_graph.py"
scp -r PPU-13:/tmp/glm53-kpool-source-20260906-r3 /tmp/glm53-kpool-source-20260906-r3
```

该临时副本不属于 plugin、vLLM 或 FlagGems 仓库；生成补丁后仍通过原 playbook 的源码
revision/空闲服务 guard 和 `git apply --check`，不会直接覆盖容器源码。

bounds 服务已健康且 16/16 worker 安装 probe，但实际 runner 命令因控制端误传
`--limitlvwvzt` 被 Ansible 参数解析拒绝，未连接远端、未 arm、未创建诊断目录或发送请求。
随后按 2026-09-06 更新的工作流执行：

```bash
./scripts/audit-workspace
./scripts/adapt-model GLM-5.3-Flash-BF16 --platform ppu --hosts PPU-13 --steps adaptation --check-only
```

结果：audit 为 0 error、23 个跨仓库历史 review warning；本模型 adaptation check-only
明确失败，因为 architecture/environment 的 `evidence` 与空的 `verification.evidence`
不一致，且两个前置阶段都缺少 verification 记录。按新门禁不得继续 adaptation 变更或
启动诊断负载。为避免空闲服务占用 16 张 PPU，停止仅本轮 PID 精确匹配的 bounds 服务，
不停止/重启容器：

```bash
./scripts/playbook /tmp/ppu13-glm53-stop-kpool-bounds.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-kpool-bounds.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stop-kpool-bounds.yml --limit PPU-13
```

14:46（UTC+8）bounds probe import 验证通过，服务 PID `887393` 已提交且 disarmed。
health、安装数与早期 bounds/异常轮询命令：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-kpool-bounds/service.pid); if kill -0 \"$pid\" 2>/dev/null; then echo PID_ALIVE=$pid; else echo PID_DEAD=$pid; fi; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY || true; grep -c \"GLM53_KPOOL_BOUNDS.*installed\" /workspace/glm53-adaptation-runtime/graph-kpool-bounds/service.log || true; grep -E \"GLM53_KPOOL_BOUNDS|illegal memory access|WorkerProc hit an exception\" /workspace/glm53-adaptation-runtime/graph-kpool-bounds/service.log | tail -n 120'"
```

工作流门禁出现后已通过上述精确 stop playbook 终止 PID `887393`；验证结果为 8010 关闭、
全部 vLLM worker 退出、`glm5.3-flash` 容器仍运行且 `/workspace/vllm` 工作树不变。该服务
没有 arm，也没有收到评测请求。

架构与环境重新核验并绑定证据后，adaptation `--check-only` 已通过。旧的 bounds runtime
目录作为证据保留，因此第二次诊断使用新路径，不覆盖或删除旧目录：

- probe：`/workspace/glm53-adaptation-runtime/kpool-bounds-probe-r2`
- service：`/workspace/glm53-adaptation-runtime/graph-kpool-bounds-r2`
- GPQA diagnostic：`/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-kpool-bounds-r2`

先只读确认旧服务已退出和新目标不存在，再按单主机 check/diff 后执行：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'pgrep -af \"^vllm serve |^VLLM::Worker\" || true; if (exec 3<>/dev/tcp/127.0.0.1/8010) 2>/dev/null; then echo PORT_UP; else echo PORT_DOWN; fi; test ! -e /workspace/glm53-adaptation-runtime/graph-kpool-bounds-r2; test ! -e /workspace/glm53-adaptation-runtime/kpool-bounds-probe-r2'; test ! -e /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/diagnostic-gpqa-20260906-c64-kpool-bounds-r2
./scripts/playbook /tmp/ppu13-glm53-kpool-bounds-probe.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-kpool-bounds-probe.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-kpool-bounds-probe.yml --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-kpool-bounds.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-kpool-bounds.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-gpqa-kpool-bounds.yml --limit PPU-13
```

## 验证结果

### Padded slot 根因修复后的整模验证（2026-09-06）

生产修复和 53 项专项/相邻回归通过后，先核实无 probe 服务 PID、health、启动日志、
容器状态及可复用的 sanity wrapper 路径。该检查只读，不修改或重启容器：

```bash
ssh PPU-13 "docker inspect -f '{{.State.Status}} {{.RestartCount}}' glm5.3-flash; docker exec glm5.3-flash bash -lc 'pid=$(cat /workspace/glm53-adaptation-runtime/graph-kpool-slot-fix/service.pid); ps -p \"$pid\" -o pid,ppid,stat,etime,comm,args; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY; grep -E \"Application startup complete|illegal memory access|Traceback|WorkerProc hit an exception\" /workspace/glm53-adaptation-runtime/graph-kpool-slot-fix/service.log | tail -n 80'; find /mnt/nfs/users/jinghao/glm5.3-flash -maxdepth 3 -type f -name 'graph_sanity.py' -print"
```

确认脚本后，把仓库内既有 `acceptance/graph_sanity.py` 作为固定输入复制到新的隔离结果目录，
不在 plugin、vLLM 或 FlagGems 仓库放置一次性代码。执行并发 8、保存 JSON/退出码，随后核对
服务仍健康且日志没有新增非法访存：

```bash
./scripts/playbook /tmp/ppu13-glm53-stage-kpool-fix-sanity.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stage-kpool-fix-sanity.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stage-kpool-fix-sanity.yml --limit PPU-13
ssh PPU-13 "cd /mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906 && ./run.sh; rc=$(cat exit.code); docker exec glm5.3-flash bash -lc 'curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY; grep -E \"illegal memory access|Traceback|WorkerProc hit an exception\" /workspace/glm53-adaptation-runtime/graph-kpool-slot-fix/service.log | tail -n 40'; exit \"$rc\""
```

playbook 首次返回窗口结束时若执行结果尚未显示，不重复启动，而是只读检查固定目录的
`exit.code`、Python 进程与结果摘要：

```bash
ssh PPU-13 "if test -f /mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906/exit.code; then cat /mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906/exit.code; python3 -c 'import json; p=\"/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906/result.json\"; r=json.load(open(p)); print({k:r[k] for k in (\"passed\",\"correct\",\"errors\",\"elapsed_seconds\",\"completion_tokens_per_second\",\"latency_max_seconds\",\"resource_sample_count\",\"monitor_errors\")})'; else echo RUNNING; pgrep -af 'graph_sanity.py' || true; fi"
```

只有本轮 8/8 正确、零错误、满足固定延迟/吞吐/遥测判据且服务保持健康，才解除 issue 的
最小整模验证阻塞。该 sanity 不代替正式 198 题 GPQA。

首轮结果为 8/8 正确、零错误，最大延迟 23.57895 秒、22 次 PPU 遥测且无监控错误；但
聚合输出 17.72354 tokens/s，低于固定 20 tokens/s 门槛，所以严格判为失败。为区分新服务
首次执行开销与持续性能退化，先只读保存逐请求、显存/利用率和服务异常摘要：

```bash
ssh PPU-13 "python3 -c 'import json; p=\"/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906/result.json\"; r=json.load(open(p)); print(json.dumps({\"summary\":{k:r[k] for k in (\"passed\",\"correct\",\"errors\",\"elapsed_seconds\",\"completion_tokens\",\"completion_tokens_per_second\",\"latency_mean_seconds\",\"latency_max_seconds\",\"resource_sample_count\",\"monitor_errors\")},\"devices\":r[\"devices\"],\"results\":[{k:x.get(k) for k in (\"expression\",\"expected\",\"parsed_answer\",\"correct\",\"finish_reason\",\"latency_seconds\",\"usage\",\"error\")} for x in r[\"results\"]]},ensure_ascii=False,indent=2))'; docker exec glm5.3-flash bash -lc 'curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY; grep -E \"illegal memory access|Traceback|WorkerProc hit an exception|ERROR\" /workspace/glm53-adaptation-runtime/graph-kpool-slot-fix/service.log | tail -n 80'"
```

若服务保持健康且没有 kernel/worker 错误，以完全相同的脚本、服务和参数在新目录做一次
独立热态复测，不覆盖首轮证据：

```bash
./scripts/playbook /tmp/ppu13-glm53-stage-kpool-fix-sanity.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stage-kpool-fix-sanity.yml --check --diff --limit PPU-13 -e sanity_dir=/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906-hot
./scripts/playbook /tmp/ppu13-glm53-stage-kpool-fix-sanity.yml --limit PPU-13 -e sanity_dir=/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906-hot
```

复测完成后只读核验固定摘要、结果哈希、服务 health 和修复后请求窗口内的异常签名：

```bash
ssh PPU-13 "sha256sum /mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906-hot/result.json; python3 -c 'import json; p=\"/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-kpool-slot-fix-20260906-hot/result.json\"; r=json.load(open(p)); print({k:r[k] for k in (\"started_at\",\"passed\",\"correct\",\"errors\",\"elapsed_seconds\",\"completion_tokens\",\"completion_tokens_per_second\",\"latency_mean_seconds\",\"latency_max_seconds\",\"resource_sample_count\",\"monitor_errors\")})'; docker exec glm5.3-flash bash -lc 'curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY; grep -E \"illegal memory access|Traceback|WorkerProc hit an exception\" /workspace/glm53-adaptation-runtime/graph-kpool-slot-fix/service.log | tail -n 40'"
```

结果：首轮冷态 8/8 正确、零错误，但 17.72354 tokens/s 未达到固定 20 tokens/s 门槛，
严格保留为失败证据；相同配置热态复测 8/8 正确、零错误，416 completion tokens，
8.64940 秒、48.09580 tokens/s，平均/最大延迟 8.20296/8.64467 秒，8 次 16 卡遥测无错误。
热态结果 SHA256 为
`1149e4e711e55fad712728e19c05d3272e36a4cb342fd9034dc2e652c4adef55`。复测后 API health
正常，服务日志无 `illegal memory access`、Traceback 或 `WorkerProc hit an exception`。
因此根因修复已通过最小整模 correctness/graph 验证；正式 c64 GPQA 仍需作为验收独立重跑。

- 正式 GPQA：失败且结果无效；198/198 为服务退出后的 `<TIMEOUT>` 占位。
- FlagGems clamp 最小包：eager `PASS`，graph capture/replay `PASS`；未复现服务中的
  非法访存，说明还缺少并发/调用链上下文。
- FlagGems gather expanded-index 最小包：rows=1/32 的 eager 与 graph 均 `PASS`；
  stride-0 index 不是充分触发条件，不能据此直接 blacklist 或修改生产实现。
- 该结果不改变此前最小 eager/graph 与 graph 并发 8 sanity 已通过的事实。

## 限制与下一步

- 检查失败前 sparse indexer 调用链和生成 kernel，建立包含真实调用上下文的窄化复现。
- 确认根因后只改变一个变量，先做窄化复现与并发 sanity，
  再决定是否重新运行正式 GPQA。

## 经验沉淀

- 是否可跨模型或平台复用：待根因确认。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：TP 长负载下 EngineCore 退出的分层诊断顺序。
