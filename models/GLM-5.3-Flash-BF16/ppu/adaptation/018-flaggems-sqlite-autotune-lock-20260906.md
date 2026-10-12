# 018：FlagGems autotune SQLite 并发锁导致 TP worker 退出

## 元数据

- 状态：`mitigated-validated-formal-c64`
- 首次出现时间：2026-09-06 16:05:41（UTC+8）
- 最后验证时间：2026-09-07 07:48（UTC+8）
- 模型：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / `hy4-ppu07-snapshot:20260903`
- Plugin / FlagGems / vLLM revision：`support-hy4-preview@5329cb1` 加 BF16 适配 /
  `34bd6d68928c8b0039c42987840929da52aa6a62` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：PIECEWISE graph，TP16，正式 GPQA 198 题，客户端 c64，服务 seq32

## 问题现象

- padded slot 修复后的正式轮在 16:05:41 由 TP7、TP14 同时进入 FlagGems
  `index_linearized` 新 shape 的 autotune benchmark 持久化。
- 两个 rank 共享 `/root/.flaggems/config_cache/TunedConfig_thead_triton_3_6.db`，在 SQLAlchemy
  反射/创建 benchmark 表时传播 `sqlite3.OperationalError: database is locked`。
- worker 退出后 API health 曾短暂返回成功，但 worker 数已从 16 降到 14；16:16:53
  EngineCore fatal，8010 关闭、worker 清零。runner 最终 exit 1。
- 正式 contract 为 `failed`；阶段缓存仅 1/198 且 matched=0，不存在有效精度分数。
- 原始服务日志：
  `/workspace/glm53-adaptation-runtime/graph-kpool-slot-fix/service.log`；评测目录：
  `/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-kpool-slot-fix`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| `models/Hy4-preview/ppu/adaptation/002-flaggems-sqlite-lock-reproducer.md` | 同为 T-Head PPU、TP16、共享 `TunedConfig_thead_triton_3_6.db`，新 shape 并发建 benchmark 表并报同一 SQLAlchemy/SQLite 锁错误 | Hy4 为 PPU-07、FlagGems `842b19d`；本轮为 GLM5.3 / PPU-13 / `34bd6d6`，触发算子为 BF16 index | 高 | 先复核当前 FlagGems DB URL 解析与数据库完整性；若一致，按该经验只增加连接 `timeout=1800` 做受控 mitigation |

## 诊断与假设

已验证事实：这是 host 侧 autotune cache DDL/反射并发，不是 PPU graph kernel、此前 padded
slot 非法访存、HTTP 7200 秒超时或 vLLM execute-model 1800 秒超时。API `/health` 在部分
worker 已退出后仍可能短暂成功，后续验证必须同时检查 16/16 worker。

待复核：当前进程是否未设置 `FLAGGEMS_DB_URL`；FlagGems 34bd6d6 是否把 URL query 的
`timeout` 传给 SQLite；现有 DB 的 `PRAGMA integrity_check` 是否为 `ok`。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| r1 | SQLite 连接等待 | 默认 DB URL / 默认短等待 | 在 `docker exec --env` 设置 `FLAGGEMS_DB_URL=...timeout=1800`，其余不变 | c8 8/8；两级 spawn 探针证明 EngineCore 与 worker 进程内均继承完整 URL | 注入边界有效；允许进入隔离的正式 c64 验证，最终效果仍以全量轮为准 |

当前 revision 的 CPU-only 复核已完成。`spawn` contender 使用 1 秒 timeout、holder 持锁
4 秒时，稳定得到 `OperationalError: database is locked`，失败 SQL 为 benchmark v2
`CREATE TABLE IF NOT EXISTS`；改为 10 秒 timeout 后成功建表。两轮独立临时 DB 的
`PRAGMA integrity_check` 均为 `ok`。证据包保留在
`/bug/glm53-flaggems-sqlite-lock-20260906`，host staging 已清理，生产 DB 未加锁或修改。

r1 启动后的首轮 `/proc/<pid>/environ` 审计曾得到 worker `0/16`，但后续受控复现证明这是
观测假阴性：两级 `spawn` 中 EngineCore/worker 在调用 vLLM `set_process_title` 前后，Python
`os.environ` 均保留完整 `FLAGGEMS_DB_URL`；调用后 `/proc/self/environ` 恰好由“可见”变为
“不可见”。vLLM 本地 `CoreEngineProcManager` 和 `MultiprocExecutor` 源码均使用普通 spawn，
没有本地环境白名单；因此当前 API 注入会传到 EngineCore 和 16 个 worker。探针执行后精确
临时目录已清理，服务未停止，容器和三个源码树均未修改。

下一步只读检查 vLLM-FL worker 启动/环境过滤和 FlagGems 初始化时机；可重复命令：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; grep -RInE \"os\\.environ|env_vars|environment|subprocess|Popen|spawn\" vllm_fl/worker vllm_fl --include=\"*.py\" | head -n 320; grep -RInE \"os\\.environ|env_vars|environment|subprocess|Popen|spawn\" /workspace/vllm/vllm/v1/executor /workspace/vllm/vllm/v1/worker --include=\"*.py\" | head -n 320'; docker exec glm5.3-flash python3 -B -c 'import pathlib; ps=[]; [ps.append((p.name,p.joinpath(\"status\").read_text(errors=\"ignore\").splitlines()[:8],[x.decode(errors=\"replace\") for x in p.joinpath(\"environ\").read_bytes().split(b\"\\0\") if x.startswith((b\"FLAGGEMS\",b\"VLLM\"))])) for p in pathlib.Path(\"/proc\").glob(\"[0-9]*\") if p.joinpath(\"comm\").exists() and p.joinpath(\"comm\").read_text(errors=\"ignore\").startswith(\"VLLM::Worker\")]; print(*ps,sep=\"\\n\")'"
```

为区分 multiprocessing 环境过滤与进程命名/`/proc` 观测语义，继续只读读取 API→EngineCore
→worker 的父子链、每级 DB URL，以及 multiproc 创建 worker 和插件 `init_device` 的相关源码：

```bash
ssh PPU-13 "docker exec glm5.3-flash bash -lc 'ps -eo pid,ppid,stat,comm,args | grep -E \"[v]llm serve|[E]ngineCore|VLLM::Worker\"; sed -n \"620,730p;1025,1085p\" /workspace/vllm/vllm/v1/executor/multiproc_executor.py; sed -n \"210,275p\" /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl/worker/worker.py; sed -n \"170,245p\" /workspace/vllm/vllm/v1/worker/worker_base.py'; docker exec glm5.3-flash python3 -B -c 'import pathlib; ids=[]; [ids.append(p) for p in pathlib.Path(\"/proc\").glob(\"[0-9]*\") if p.joinpath(\"comm\").exists() and (p.joinpath(\"comm\").read_text(errors=\"ignore\").startswith(\"VLLM::Worker\") or b\"EngineCore\" in p.joinpath(\"cmdline\").read_bytes() or b\"vllm\\x00serve\" in p.joinpath(\"cmdline\").read_bytes())]; print(*[(p.name,p.joinpath(\"status\").read_text().splitlines()[5],[x.decode(errors=\"replace\") for x in p.joinpath(\"environ\").read_bytes().split(b\"\\0\") if x.startswith(b\"FLAGGEMS_DB_URL=\")]) for p in ids],sep=\"\\n\")'"
```

先只读核实失败产物、当前无服务、数据库 URL 解析源码与数据库完整性：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-kpool-slot-fix; run="$root/outputs/GLM-5.3-Flash-BF16-gpqa-full-graph-c64-kpool-slot-fix/full-198-threshold-88-kpool-slot-fix-20260906"; cat "$root/exit.code" "$run/acceptance-result.json"; python3 -c '\''import json,pathlib; r=pathlib.Path("'"$run"'/gpqa_diamond_generative_cot/attempt-1"); fs=list(r.rglob("samples_*.jsonl")); rows=[json.loads(x) for x in fs[0].read_text().splitlines() if x.strip()] if fs else []; print({"rows":len(rows),"unique_doc_ids":len({str(x.get("doc_id")) for x in rows}),"timeout_markers":sum("<TIMEOUT>" in json.dumps(x) for x in rows)})'\''; docker exec glm5.3-flash bash -lc '"'"'pgrep -af "^vllm serve |^VLLM::Worker" || true; test -z "$(git -C /workspace/vllm status --porcelain)"; python3 - <<"PY"
import os,pathlib,sqlite3,subprocess
p=pathlib.Path("/root/.flaggems/config_cache/TunedConfig_thead_triton_3_6.db")
print("DB",p,p.exists(),p.stat().st_size if p.exists() else None)
if p.exists():
    con=sqlite3.connect(f"file:{p}?mode=ro",uri=True,timeout=5)
    print("INTEGRITY",con.execute("pragma integrity_check").fetchone()[0]); con.close()
print("FLAGGEMS_DB_URL",os.environ.get("FLAGGEMS_DB_URL"))
print("FG_HEAD",subprocess.check_output(["git","-C","/workspace/FlagGems","rev-parse","HEAD"],text=True).strip())
PY
grep -RIn "FLAGGEMS_DB_URL\|create_engine" /workspace/FlagGems/src/flag_gems/utils/models /workspace/FlagGems/src/flag_gems/utils | head -n 120'"'"''
```

复用已验证的 CPU-only `spawn` 复现逻辑，在当前容器 `/bug/glm53-flaggems-sqlite-lock-20260906`
用独立临时 DB 验证短 timeout 必然锁失败、长 timeout 成功且 integrity 均为 ok。打包和执行均
通过单主机 Ansible，绝不对生产调优 DB 人为加锁：

```bash
./scripts/playbook /tmp/ppu13-glm53-flaggems-sqlite-lock-repro.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-flaggems-sqlite-lock-repro.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-flaggems-sqlite-lock-repro.yml --limit PPU-13
```

若复核通过，使用 unchanged NFS 生产脚本启动新 runtime，环境变量只在 `docker exec`
边界注入，不写入 `start_glm53_graph.sh`，避免把运行时 mitigation 混入用户要求的精简脚本：

```bash
./scripts/playbook /tmp/ppu13-glm53-launch-flaggems-db-timeout.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-launch-flaggems-db-timeout.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-launch-flaggems-db-timeout.yml --limit PPU-13
```

服务 PID `951344` 已提交；加载与 graph capture 期间只读核实 API、16/16 worker、DB URL
继承和锁错误：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''pid=$(cat /workspace/glm53-adaptation-runtime/graph-flaggems-db-timeout/service.pid); ps -p "$pid" -o pid,stat,etime,comm,args; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY || true; echo WORKERS=$(pgrep -af "^VLLM::Worker" | wc -l); grep -E "Loading safetensors checkpoint shards: 100%|Capturing CUDA graphs|Application startup complete|database is locked|illegal memory access|WorkerProc hit an exception|EngineCore encountered" /workspace/glm53-adaptation-runtime/graph-flaggems-db-timeout/service.log | tail -n 100'\'''
```

服务健康且 16/16 worker 后，用固定 graph c8 wrapper 在新目录验证 correctness、吞吐、PPU
遥测和锁错误；不覆盖 padded-slot 轮的结果：

```bash
./scripts/playbook /tmp/ppu13-glm53-stage-kpool-fix-sanity.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-stage-kpool-fix-sanity.yml --check --diff --limit PPU-13 -e sanity_dir=/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-flaggems-db-timeout-20260906
./scripts/playbook /tmp/ppu13-glm53-stage-kpool-fix-sanity.yml --limit PPU-13 -e sanity_dir=/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-flaggems-db-timeout-20260906
ssh PPU-13 'p=/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-flaggems-db-timeout-20260906/result.json; sha256sum "$p"; python3 -c '"'"'import json; r=json.load(open("/mnt/nfs/users/jinghao/glm5.3-flash/acceptance/graph-sanity-flaggems-db-timeout-20260906/result.json")); print({k:r[k] for k in ("passed","correct","errors","elapsed_seconds","completion_tokens_per_second","latency_max_seconds","resource_sample_count","monitor_errors")})'"'"'; docker exec glm5.3-flash bash -lc '"'"'curl -fsS --max-time 3 http://127.0.0.1:8010/health; echo WORKERS=$(pgrep -af "^VLLM::Worker" | wc -l); grep -E "database is locked|illegal memory access|WorkerProc hit an exception|EngineCore encountered" /workspace/glm53-adaptation-runtime/graph-flaggems-db-timeout/service.log | tail -n 40'"'"''
```

## 根因

- 已验证根因：16 个 TP worker 共享单个 FlagGems autotune SQLite，新 shape 首次调优时并发
  反射/创建 benchmark 表；默认连接等待不足，锁竞争异常未经重试直接退出 worker。
- 待验证边界：`timeout=1800` 在当前 FlagGems revision 上是否由所有 16 个 worker 继承并
  能覆盖新 shape 调优。它是有界等待 mitigation，不是上游并发写设计的根因修复。

## 解决方法或 Workaround

- 修改思路：不改 plugin、vLLM、FlagGems 源码，不改 NFS 启动脚本；只在服务进程环境中
  为同一完整性通过的 DB URL 增加 SQLite `timeout=1800`。
- 容器不得重启；失败服务已经自然退出，启动前须确认 8010 关闭且无 worker。
- 新服务必须验证 16/16 worker、环境继承、graph capture、c8 sanity 和新 shape 调优无锁错误。
- 失败 GPQA 缓存/输出不得复用；后续正式轮必须使用新 run id、输出和 cache。
- vLLM 未修改证明：每次服务启动前后检查 `/workspace/vllm` 工作树为空。

## FlagGems 证据

- 同类受控复现：`models/Hy4-preview/ppu/adaptation/002-flaggems-sqlite-lock-reproducer.md`。
- 当前失败调用：`FlagGems/src/flag_gems/ops/index.py` → `libentry.default_policy` →
  `SQLPersistantModel.put_benchmark/get_sql_model` → SQLAlchemy SQLite reflection。
- 当前容器复现目标：`/bug/glm53-flaggems-sqlite-lock-20260906`。

## 验证结果

- 当前正式 GPQA：失败且无效；exit 1，formal contract `failed`。
- 失败产物：396 个双 filter 行、198 个唯一 doc_id，其中 394 行带 `<TIMEOUT>`，即 197/198
  题为服务退出占位；不能计算准确率。结果 SHA256
  `c0b4587899a332aa2c598a882c9b90f1207c87cb09523ed1c5207f8884937f8e`，样本 SHA256
  `65f7135a0856bc8afe1bba222e982ee4d8871761a74f5b7258c0ed0a45d6ee34`。
- 生产调优 DB `PRAGMA integrity_check=ok`；vLLM 工作树为空，失败后模型服务/worker 已退出。
- 当前 FlagGems 34bd6d6 的短/长 timeout 受控复现均按预期通过。
- r1 服务：PID `951344`，120/120 权重加载、11/11 PIECEWISE graph capture、16/16 worker，
  API health 通过。两级 spawn 进程内探针验证 EngineCore/worker 均继承 DB URL；此前
  `/proc` 的 0/16 为 `set_process_title` 覆盖原始环境内存造成的假阴性。生产脚本、plugin、
  FlagGems 与 vLLM 源码均未改。
- graph c8：8/8 正确、零错误，418 completion tokens，20.34921 秒、20.54134 tokens/s，
  最大延迟 20.34580 秒；19 次 PPU 采样且无监控错误。结果 SHA256
  `2d6b5b8772f80bbbdf1d78a404d7fab31f719e510066a936bd2d20f33047afcb`。
- c8 后仍为 16/16 worker，服务日志无 `database is locked`、illegal memory、worker exception
  或 EngineCore 故障。固定 sanity 门槛一次通过，无需热态择优复测。
- eager 不重复执行：故障位于 host SQLite DDL，不依赖 eager/graph；CPU-only 因果复现与
  graph 整模服务分别覆盖其适用边界。
- 最终结论：mitigation 已通过完整 198 题 c64 workload 验证；全程 16/16 worker、服务
  health 正常且无 SQLite lock/EngineCore 故障。该轮 accuracy 因独立的生成长度耗尽问题
  未通过，见 issue 019；不能反推本 SQLite mitigation 失败。

## 限制与下一步

- 先完成当前 revision 的 URL/DB/CPU-only 复核。
- r1 的 c8 correctness、EngineCore → worker 两级 spawn 继承及全量 c64 均已通过此问题
  的验证边界。后续若 FlagGems 提供并发持久化根因修复，应撤销环境 timeout workaround，
  重跑相同 TP16 新 shape 并发用例后再关闭本问题。

继续只读追踪 API → EngineCore → TP worker 的环境传播与初始化 RPC，并检查 worker 构造时
是否已记录该变量；该步骤仅定位边界，不修改远端源码或运行态：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''echo PROCESS_ENV; for pid in 951344 951841 952126; do printf "%s " "$pid"; tr "\\0" "\\n" </proc/$pid/environ | grep -E "^(FLAGGEMS_DB_URL|FLAGGEMS_SOURCE_DIR|VLLM_WORKER_MULTIPROC_METHOD)=" || true; done; echo CALL_SITES; rg -n "update_environment_variables|envs_list|set_multiprocessing_worker_envs|EngineCoreProc" /workspace/vllm/vllm/v1 /workspace/vllm/vllm/engine; echo EXECUTOR_CONTEXT; sed -n "60,180p;430,620p" /workspace/vllm/vllm/v1/executor/multiproc_executor.py; echo ENGINE_CONTEXT; rg -n -C 12 "update_environment_variables|set_multiprocessing_worker_envs|EngineCoreProc" /workspace/vllm/vllm/v1/engine /workspace/vllm/vllm/v1/executor; echo WORKER_LOG; grep -n -E "FLAGGEMS_DB_URL|=== ENVIRONMENT VARIABLES ===" /workspace/glm53-adaptation-runtime/graph-flaggems-db-timeout/service.log | tail -n 80'\'''
```

容器没有 `rg`；首轮结果已明确变量在 PID 951344 API 存在、在 PID 951841 EngineCore
已丢失，TP0 只是继承了 EngineCore 的缺失状态。改用 `grep` 精确定位 API → EngineCore
的进程启动代码及其显式环境处理：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''grep -RIn -E "class EngineCoreProc|EngineCoreProc\(|set_multiprocessing_worker_envs|update_environment_variables|os\.environ|env=" /workspace/vllm/vllm/v1/engine /workspace/vllm/vllm/engine /workspace/vllm/vllm/utils 2>/dev/null | head -n 500; grep -RIn -E "class EngineCoreProc|EngineCoreProc\(" /workspace/vllm/vllm/v1 2>/dev/null'\'''
```

继续读取命中的 EngineCore 启动与 runtime environment 构造上下文，并定位实际
`multiprocessing.Process` 调用：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''sed -n "360,525p" /workspace/vllm/vllm/v1/engine/utils.py; sed -n "850,970p;1120,1225p" /workspace/vllm/vllm/v1/engine/core.py; grep -RIn -E "context\.Process|Process\(|run_engine_core|target=.*EngineCore" /workspace/vllm/vllm/v1 2>/dev/null | head -n 300'\'''
```

读取本地 EngineCore process manager 的完整创建块、multiprocessing context 实现，以及
NUMA 子进程环境钩子，确认是否有 `spawn` 可执行文件替换导致环境重建：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''sed -n "110,205p" /workspace/vllm/vllm/v1/engine/utils.py; grep -RIn -E "def get_mp_context|class.*Popen|configure_subprocess" /workspace/vllm/vllm /workspace/vllm-plugin-FL-glm53-hy4-adaptation/vllm_fl 2>/dev/null | head -n 300; sed -n "500,600p" /workspace/vllm/vllm/utils/numa_utils.py; sed -n "110,185p" /workspace/vllm/vllm/utils/system_utils.py'\'''
```

`EngineCore` 经 NUMA wrapper 使用 spawn 启动；继续读取 manager 的 `proc.start()` 上下文、
wrapper 全文和相关配置值，验证 wrapper 是否重建/筛选环境：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''sed -n "185,235p" /workspace/vllm/vllm/v1/engine/utils.py; sed -n "1,240p" /workspace/vllm/vllm/utils/numa_wrapper.sh; pid=951344; echo API_NUMA_ENV; tr "\\0" "\\n" </proc/$pid/environ | grep -E "^(VLLM_NUMA|VLLM_WORKER_MULTIPROC_METHOD|FLAGGEMS_DB_URL|FLAGGEMS_SOURCE_DIR)=" || true; echo SERVICE_NUMA_LOG; grep -n -i -E "numa|wrapper|spawn" /workspace/glm53-adaptation-runtime/graph-flaggems-db-timeout/service.log | head -n 120'\'''
```

`/proc/<pid>/environ` 也看不到 API 进程启动后由 Python 写入、但 worker 已实际继承的
`VLLM_WORKER_MULTIPROC_METHOD=spawn`，因此不能把 `/proc` 当作 Python `os.environ` 的
可靠快照。用 `/tmp/glm53_env_spawn_probe.py` 模拟同样的 EngineCore → worker 两级 spawn，
每一级在设置 vLLM 进程标题前后都从进程内读取 `os.environ`，执行完清理精确临时目录：

```bash
./scripts/playbook /tmp/ppu13-glm53-env-inheritance-probe.yml --syntax-check --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-env-inheritance-probe.yml --check --diff --limit PPU-13
./scripts/playbook /tmp/ppu13-glm53-env-inheritance-probe.yml --limit PPU-13
```

在设计 c64 定向验证前，重新提取失败服务中首个锁异常的完整邻域，确认触发算子和 shape，
避免用不能覆盖故障路径的短请求作为验证依据：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''log=/workspace/glm53-adaptation-runtime/graph-kpool-slot-fix/service.log; grep -n -m 4 -E "database is locked|sqlalchemy\.exc\.OperationalError" "$log"; first=$(grep -n -m 1 "database is locked" "$log" | cut -d: -f1); test -n "$first"; start=$((first-140)); test "$start" -ge 1 || start=1; end=$((first+80)); sed -n "${start},${end}p" "$log"'\'''
```

## 经验沉淀

- 是否可跨模型或平台复用：同 PPU 平台已跨 Hy4/GLM5.3 复现，触发条件明确。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：多 TP worker 共享 FlagGems autotune SQLite 的 DDL 锁冲突与有界等待。
