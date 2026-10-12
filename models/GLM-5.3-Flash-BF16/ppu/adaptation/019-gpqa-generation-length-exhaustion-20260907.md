# 019：GPQA 长推理耗尽 30000-token 上限导致正式精度失败

## 元数据

- 状态：`open`
- 首次出现时间：2026-09-07 02:17:44（UTC+8，本轮结束时间）
- 最后验证时间：2026-09-07 07:58（UTC+8）
- 模型：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / `hy4-ppu07-snapshot:20260903`
- Plugin / FlagGems / vLLM revision：`support-hy4-preview@5329cb1` 加 BF16 适配 /
  `34bd6d68928c8b0039c42987840929da52aa6a62` /
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：PIECEWISE graph，TP16，GPQA Diamond 198 题，客户端 c64，
  temperature 1、top_p 0.95、max_gen_toks 30000

## 问题现象

- 正式 contract 为 `failed`：strict-match `166/198 = 83.8384%`，低于 88%；
  flexible-extract `71/198 = 35.8586%`。
- 396 行样本覆盖 198 个唯一 doc_id。19 题为 `<TIMEOUT>` 占位，全部保留
  `completion_tokens=30000`；另有 13 题正常 stop 但 strict 不匹配。
- 19 个占位对应原始 API 返回均为 `finish_reason=length`、`content=None`、reasoning
  非空，不是 EngineCore/RPC 退出。服务结束后 health 正常、16/16 worker，四类既有故障
  签名为 0。
- 19 个 doc_id：`8,15,32,47,48,64,71,76,81,88,94,127,130,145,147,162,170,185,194`。
- runner exit `1`；结果、样本、contract SHA256 分别为
  `d057d61b7c10b69d3e1585e5d36452096156e09f71d433d4e97a78c2b6352fd1`、
  `7477fd810474f782c6a82517402ae4eb91d76eb1725b3efa9bb94b9f205dec46`、
  `b25d17821708c70bb472fe38d7b62b77930aa980f0514b130d651d5b0e0ee153`。
- 原始证据目录：
  `/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-flaggems-db-timeout`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [007](007-gpqa-timeout-marker-diagnosis-20260904.md) | 同为 GLM、30000-token、length/content=None 被转换成 TIMEOUT；多个 doc_id 重合 | 007 属于被撤销的早期权重/适配轮；本轮绑定正确 BF16、padded-slot 修复及 SQLite mitigation | 中高（仅复用症状链路） | 重新验证当前 198 题产物，不继承旧分数或权重结论 |
| Hy4 40K GPQA 记录 | 同一平台/runner 对 reasoning-only length 返回的处理一致 | 模型、权重与采样配置不同 | 中 | 仅作为“增加 token 预算不保证全部恢复”的边界证据 |

## 诊断与假设

已验证：19 题全部在 30000 completion tokens 结束；OpenAI chat completion 解析只读取
`message.content`，因此 `content=None` 被后续并发路径转换为 `<TIMEOUT>`。19 题 reasoning
均无 Unicode replacement 字符，不是乱码。18 题主要是持续过长的推敲；其中一题 zlib
压缩率 `0.0158`、重复行比例 `0.9667`，属于明确机械重复。其余 length 题的中位 zlib
压缩率 `0.2897`、重复行比例 `0.0131`，不能统称为同一种文本死循环。

当前假设：temperature 1 / top_p 0.95 下，部分难题的 reasoning 未在 30000 token 内收敛。
尚不能证明它完全是模型固有行为，也不能排除 PPU 数值路径导致采样轨迹偏移；需要用同一
题集做单变量对照。调大 `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS` 不会改变生成 token 上限，
不是本问题的修复。

正确权重的 `generation_config.json` 声明 `temperature=1.0`、`top_p=0.95` 和 EOS IDs
`154820,154827,154829`；当前正式轮与权重默认采样一致。权重配置未声明 top_k、
reasoning_effort 或 max_new_tokens，tokenizer 配置只声明 `<|endoftext|>`。

19 个 length 返回耗时 `3118.04–6943.51` 秒，中位 `4487.22` 秒，均小于 7200 秒；179 个
stop 返回耗时最大 `7196.92` 秒。本轮日志另有 52 个 `asyncio.TimeoutError` 的失败尝试，
它们经过配置的重试后仍形成 198 个最终返回；不能把“有重试尝试超时”与“19 个最终
length/content=None 占位”混为同一原因。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| r0 | 正式基线 | 无 | 30K、temperature 1、top_p .95、c64 | acceptance 正式目录 | 166/198，19 length，占位失败 | 正式 accuracy 未通过 |
| r0-analysis | 只读长尾统计 | 19 个 `<TIMEOUT>` | 不改变请求 | runner.log / samples JSONL | 19/19 为 30K length；无乱码；1 题明确机械重复 | 生成上限耗尽为直接原因，底层收敛原因待对照 |

下一步候选首先是只对 19 题做 40K 单变量诊断，保持服务、采样、prompt 和 graph 不变；
不得把定向诊断拼接成正式通过结果。只有它证明可恢复足够样本后，才决定是否用新的独立
run id/cache 做全量正式重跑。

在任何新远端执行前，先读取正确权重自带的 generation/tokenizer 配置，确认模型声明或
chat template 是否已有 reasoning 控制参数；只读命令：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''for f in /mnt/cpfs/models/GLM-5.3-Flash-BF16/generation_config.json /mnt/cpfs/models/GLM-5.3-Flash-BF16/tokenizer_config.json /mnt/cpfs/models/GLM-5.3-Flash-BF16/config.json; do echo FILE=$f; test -f "$f" && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); keys=[k for k in d if any(x in k.lower() for x in (\"temperature\",\"top_p\",\"top_k\",\"reason\",\"think\",\"max_new\",\"eos\",\"chat_template\"))]; print({k:(\"<chat_template present>\" if k==\"chat_template\" else d[k]) for k in keys})" "$f"; done'\'''
```

汇总 length/stop 请求耗时，核对这些返回是否在 7200 秒以内；不输出正文：

```bash
ssh PPU-13 'python3 -c '\''import ast,pathlib,re,statistics; s=pathlib.Path("/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-flaggems-db-timeout/runner.log").read_text(errors="replace"); groups={"length":[],"stop":[]}
for line in s.split("\n"):
    if "[async] get generate_until response" not in line or "output=" not in line: continue
    try: d=ast.literal_eval(line.split("output=",1)[1]); sec=float(re.search(r"use ([0-9.]+)s, output=",line).group(1)); groups[d["choices"][0]["finish_reason"]].append(sec)
    except Exception: pass
print({k:{"count":len(v),"min":min(v),"median":statistics.median(v),"max":max(v),"ge7200":sum(x>=7200 for x in v)} for k,v in groups.items()})'\'''
```

## 根因

- 已验证的直接原因：19 个 reasoning-only 返回耗尽 30000-token 上限，没有最终 content，
  被 runner 按无效响应计零；连同 13 个正常 stop 错题，使 strict 只有 166/198。
- 未完全证实的底层原因：为何这些题不收敛，以及 PPU 与参考后端是否存在可观测差异。

## 解决方法或 Workaround

- 当前尚未选择生产修复；不修改 vLLM，不篡改 reasoning 中的候选答案，不降低门槛，不按
  179 个有效题重算通过。
- 如开展 40K 定向诊断，wrapper 放在 `acceptance/`，远端原始输出放独立 NFS 目录；不得把
  一次性诊断代码写进 Plugin。
- 核实准确 PID、端口和服务身份后将健康的旧 PID `951344` graceful TERM；中间 graph PID
  `1332509` 验证 65K 可启动后，因补齐 `workspace.roots` 改变部署指纹而由同一 supervisor 停止。
  最终 PID `1339072` 于 09:55:35 ready，实际参数为 TP16、PIECEWISE、seq32、
  `max_model_len=65536`，deployment fingerprint
  `9531e3e7fd695d477a12f3e02f8363856d02096f09740501154c4d82d61af94b`；两次均未停止或
  重启容器。
- 最终轮 120/120 权重分片加载完成；KV cache 为 3,982,626 tokens，服务报告 65,536-token
  请求最大并发约 60.77。16/16 workers 存活，health 通过；最终 supervisor PID
  `1089029` 管理服务、sanity 和定向评测生命周期。
- Plugin、vLLM、FlagGems 字节未改；本轮 adaptation 只改变服务配置和验收 wrapper。
- vLLM 未修改证明仍需在下一轮启动前复核 `/workspace/vllm` 工作树。

## FlagGems 证据

- 当前没有新的 FlagGems 算子异常；该轮已验证 issue 018 的 SQLite mitigation 能覆盖全量
  c64 运行。
- 不创建新的 `/bug` operator reproducer；本问题是生成终止行为，不是已证实算子缺陷。

## 验证结果

- 最小回归、eager、graph c8 既有通过不变；本问题只在长推理正式 workload 暴露。
- graph 正式 c64 服务稳定跑完 198 题，但 accuracy/zero-timeout contract 失败。
- 最终通过标准仍为 198 个唯一有效 doc_id、零 timeout、strict-match 至少 175/198。
- 新 65K 实例 readiness 已通过；尚未把 readiness 当作 sanity，c8 控制文件仍未放行。

## 限制与下一步

- 本地工作流新增的 `environment/deployment-identity.yml` 仍缺失；任何新的正式 acceptance
  前必须基于真实远端状态补齐并重新核对受影响绑定，不能虚构或只刷新哈希。
- 权重 generation 声明及 length 请求耗时已核对；下一步设计 19 题单变量诊断。
- 当前本地工作流还缺 `environment/environment-target.yml`，因此
  `adapt-model --steps adaptation` 在创建 deployment identity 前即停止；按阶段隔离规则，
  未自动补跑/重写环境前置阶段。
- 2026-09-07 按用户要求计划将服务 `max_model_len` 从 50000 提高到 65536，并把定向评测
  `max_gen_toks` 从 30000 提高到 40000；模型声明上限为 1048576，因而参数关系可行。
  但组合 adaptation/accuracy `--check-only` 被缺失的 `environment-target.yml` 阻止；
  8010、16 个物理 PPU 与三个 checkout 身份也尚未完成现场复核。未改服务、未占用设备、
  未启动定向评测。
- accuracy 未通过前不启动性能验收。
- Plugin diff 尚不能因本结果推断有新的代码修复需求；若对照证明平台数值差异，再更新
  `environment/plugin-change-review.md`。

### 40K 定向重放输入与入口复核

在编写 acceptance wrapper 和部署 supervisor 前，只读定位正式轮的唯一 samples JSONL、
确认 19 个 doc_id 都存在，并核对远端用户启动目录和两个容器中的 Python：

```bash
ssh PPU-13 'find /mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-flaggems-db-timeout -type f -name "samples_*.jsonl" -print -exec sha256sum {} \;; docker exec flageval_llmeval-jinghao python3 --version; docker exec glm5.3-flash python3 --version; find /mnt/nfs/users/jinghao/glm5.3-flash -maxdepth 1 -type f -printf "%f\n" | sort'
```

不输出题面，只核对输入结构、唯一 ID、原始 generation kwargs 和 19/19 覆盖：

```bash
ssh PPU-13 'docker exec flageval_llmeval-jinghao python3 -c '\''import json,pathlib; p=next(pathlib.Path("/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260906-c64-flaggems-db-timeout").rglob("samples_*.jsonl")); rows=[json.loads(x) for x in p.open() if x.strip()]; ids={str(x["doc_id"]) for x in rows}; wanted={"8","15","32","47","48","64","71","76","81","88","94","127","130","145","147","162","170","185","194"}; first=rows[0]; print({"rows":len(rows),"unique":len(ids),"wanted_present":len(ids&wanted),"keys":sorted(first),"arg_keys":sorted(first["arguments"]["gen_args_0"]),"generation":first["arguments"]["gen_args_0"]["arg_1"]})'\'''
```

服务、sanity 和定向 accuracy 都由同一 supervisor 管理。控制文件分成 `run-sanity` 与
`run-targeted` 两步，确保新
实例的 service-state/execution-mode 先登记、sanity 通过并绑定后，才允许 19 题启动。

部署 playbook 先验证 PID `951344` 的模型、端口和 50000 参数，再次核对 deployment
identity 后才发送 TERM；随后由同一 supervisor 启动 65536 graph 服务。容器本身不停止、重启
或删除。按单主机 mutation 规则执行：

```bash
./scripts/playbook models/GLM-5.3-Flash-BF16/ppu/environment/deploy-ppu13-graph65k-targeted40k.yml --syntax-check --limit PPU-13
./scripts/playbook models/GLM-5.3-Flash-BF16/ppu/environment/deploy-ppu13-graph65k-targeted40k.yml --check --diff --limit PPU-13
./scripts/playbook models/GLM-5.3-Flash-BF16/ppu/environment/deploy-ppu13-graph65k-targeted40k.yml --limit PPU-13
```

actual 只提交驻留 worker；readiness 另以短轮询读取
`runtime/graph-65k-40k-20260907/service-ready.env`，不会用长时间阻塞 SSH 掩盖进度。

```bash
ssh PPU-13 'run=/mnt/nfs/users/jinghao/glm5.3-flash/runtime/graph-65k-40k-20260907; test -f "$run/supervisor.pid" && ps -p "$(cat "$run/supervisor.pid")" -o pid,ppid,stat,etime,comm,args || true; test -f "$run/service-ready.env" && cat "$run/service-ready.env" || true; tail -n 40 "$run/launcher.log" 2>/dev/null || true; tail -n 80 "$run/supervisor.log" 2>/dev/null || true; docker exec glm5.3-flash bash -lc '\''ps -eo pid,ppid,stat,etime,args | grep -E "[v]llm serve|VLLM::Worker"; curl -fsS --max-time 3 http://127.0.0.1:8010/health && echo HEALTHY || true'\'''
ssh PPU-13 'docker exec glm5.3-flash tail -n 120 /workspace/glm53-adaptation-runtime/graph-65k-40k/service.log'
```

前两次 launcher 分别在 09:17:30、09:18:14 进入 supervisor 后于 preflight 静默
返回 1；`service-ready.env` 未生成，PID 951344/50K 与 16 workers 始终健康，因此未发生服务
切换。为定位具体断言，supervisor 增加只记录失败行/命令/rc 的 ERR trap；前置条件允许覆盖
“PID 文件存在但该 PID 已退出”的精确 stale 状态，仍拒绝任何存活的已有 worker。修改后
重新执行同一 syntax、check/diff、actual 三步。

带定位的第三次提交仍在 TERM 前退出；复核脚本发现宿主 heredoc 调用容器 Python 时使用了
`docker exec` 而非 `docker exec -i`，stdin 未附着，导致 Plugin untracked manifest 被算成
空列表，与已登记摘要不符。这是部署验证器错误，旧服务仍健康。修正 `-i` 并启用
`set -E` 让 ERR trap 继承到函数后，再走同一三步预检/执行。

新实例 ready 后，为 service-state v2 采集容器内 `/proc/<pid>/stat` start ticks，并复核
服务命令行与 health：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''pid=$(cat /workspace/glm53-adaptation-runtime/graph-65k-40k/service.pid); printf "pid=%s start_ticks=" "$pid"; awk "{print \\$22}" "/proc/$pid/stat"; tr "\\0" " " <"/proc/$pid/cmdline"; echo; curl -fsS --max-time 5 http://127.0.0.1:8010/health; echo HEALTHY'\'''
```

上述首次 start-ticks 子命令多转义了一层 `$22`，awk 报错；同一命令的 health 仍为
healthy。只补采 start ticks：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''set -euo pipefail; pid=$(cat /workspace/glm53-adaptation-runtime/graph-65k-40k/service.pid); python3 -c "import pathlib,sys; p=sys.argv[1]; print(\"pid=\"+p,\"start_ticks=\"+pathlib.Path(\"/proc/\"+p+\"/stat\").read_text().split()[21])" "$pid"'\'''
```

`adapt-model --steps adaptation --check-only` 随后暴露 `workspace.roots` 新门禁。用户已指定
并授权 `/mnt/nfs/users/jinghao/glm5.3-flash`，三方挂载已验证，因此补入 host/container root。
配置 SHA 变为 `56e53b33...eb6f`，部署指纹变为 `9531e3e7...f94b`。不能把这个新指纹
事后写给 PID 1332509，故需同配置重启一次；并同时把新工具、run 日志/结果、tmp/cache
迁入该工作根。

受控 handoff 会核对旧 worker PID 728093 和服务 PID 1332509，先向已确认的当前服务
发送 TERM，等待旧 worker 随服务退出，再启动新 fingerprint 的实际 worker；
不停止容器、不影响无关进程。仍使用上述同一 playbook 的 syntax、check/diff、actual 命令。

最终 v2 readiness、服务日志与控制状态从工作根读取：

```bash
ssh PPU-13 'run=/mnt/nfs/users/jinghao/glm5.3-flash/runs/graph-65k-40k-20260907-v2; ps -p "$(cat "$run/supervisor.pid")" -o pid,ppid,stat,etime,comm,args || true; test -f "$run/service-ready.env" && cat "$run/service-ready.env" || true; tail -n 80 "$run/supervisor.log" 2>/dev/null || true; tail -n 120 "$run/service.log" 2>/dev/null || true'
```

最终实例的稳定 ID 与 scoped 环境使用以下只读命令复核：

```bash
ssh PPU-13 'run=/mnt/nfs/users/jinghao/glm5.3-flash/runs/graph-65k-40k-20260907-v2; pid=$(cat "$run/service.pid"); docker exec glm5.3-flash python3 -c '\''import pathlib,sys; p=sys.argv[1]; print("pid="+p,"start_ticks="+pathlib.Path("/proc/"+p+"/stat").read_text().split()[21]); env=pathlib.Path("/proc/"+p+"/environ").read_bytes().split(b"\0"); print(sorted(x.decode(errors="replace") for x in env if x.startswith((b"FLAGGEMS_DB_URL=",b"TRITON_CACHE_DIR=",b"TMPDIR=",b"PYTHONDONTWRITEBYTECODE="))))'\'' "$pid"'
```

历史运行在远端留下的辅助副本未由本次仓库整理删除；本记录不把本地机制移除解释为远端
清理授权，也不改写既有 run 证据。

## 经验沉淀

- 是否可跨模型或平台复用：reasoning-only length 被误称 timeout 的诊断链路可复用；模型
  级收敛结论不可直接复用。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：区分 HTTP/RPC timeout 与 reasoning 达到 max token 后 content 为空。
