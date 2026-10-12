# 022：远端工作根编号目录收敛

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-08
- 最后验证时间：2026-09-08
- 模型：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU，`PPU-13`
- 容器名称与镜像：`glm5.3-flash` / `hy4-ppu07-snapshot:20260903`
- Plugin：`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`，
  `support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8` 加未提交的 GLM5 适配。
- FlagGems：`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems`，
  `sparse-mla-opt-w8a8-moe-fix@bca444b8569294e7d4e4deff7ddfec7f05682033`。
- vLLM：`/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389`。
- 执行模式与负载：远端工作区维护及最终 graph 启动入口验证；没有启动 GPQA；只对已核对且
  零活动请求的模型服务做一次受控启停，容器没有停止或重启。

## 问题现象

批准工作根 `/mnt/nfs/users/jinghao/glm5.3-flash` 同时存在编号布局和早期顶层
`accuracy/`、`runs/`、`runtime/`、`cache/`、`tmp/`、`environment/`、`acceptance/`、
`archive/`、旧 Plugin checkout 及一次性脚本。它们不满足当前远端工作目录只使用
`01-repos/` 至 `08-bugs/` 的约束，也使当前启动入口和历史证据边界不清晰。

整理前只读核对确认：目标 Host 为 `PPU-13`；host root 和 container root 均为上述工作根，
容器映射为 host `/mnt` 到 container `/mnt`；没有正在运行的 GPQA/FlagEval 评测。模型服务由
旧顶层启动器托管，APIServer 自 2026-09-08 11:51:45（UTC+8）持续运行。

## 解决方法

使用仅限 `PPU-13` 的临时 Ansible playbook，先执行 `--check --diff`，逐项断言源和目标恰有
一侧存在，再在同一 NFS 文件系统内做不覆盖的 rename。未删除历史结果、缓存、补丁或旧
checkout；只对已经搬空的 `acceptance/` 和 `environment/` 执行 `rmdir`。

主要路径映射如下：

| 旧路径（相对工作根） | 新路径（相对工作根） | 分类 |
|---|---|---|
| `start_glm53_graph_host.sh`、`start_glm53_graph.sh`、`start_glm53_eager.sh` | `02-environment/legacy-launchers/` | 已取消执行位的历史启动器 |
| `environment/resource_lock.py` | `02-environment/resource_lock.py` | 运行环境工具 |
| `runtime/` | `02-environment/legacy-runtime/` | 历史运行配置包 |
| 顶层一次性 Python、测试和补丁 | `03-issues/legacy-root-artifacts/` | 历史诊断材料 |
| 顶层启动器备份 | `03-issues/legacy-launcher-backups/` | 历史诊断材料 |
| `archive/`（移出其中的 checkout 后） | `03-issues/legacy-archive/` | 已撤回适配材料 |
| `acceptance/*.py` | `04-acceptance/legacy/` | 历史验收入口 |
| `acceptance/graph-sanity-*` | `05-runs/legacy-acceptance/` | 原始验收结果 |
| `accuracy/` | `05-runs/legacy-accuracy/` | 历史 GPQA 运行包 |
| `runs/` | `05-runs/legacy-runs/` | 历史服务和诊断结果 |
| `tmp/` | `06-tmp/legacy/` | 历史临时数据 |
| `cache/` | `07-cache/legacy/` | 历史缓存 |
| 两个旧 Plugin checkout | `01-repos/legacy/` | 非当前代码树 |

最新规则要求的唯一最终启动入口为：

```text
host:      /mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh
container: /mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh
```

用户复核并明确只在容器内直接执行后，最终入口从 105 行精简为 26 行，SHA-256 为
`bc780f34d6005cb358ad4a266dedc8c7b7400d8a2513856cbcbf58630e4a335f`。host `/mnt` 到
container `/mnt` 的绑定以及两侧 `readlink -f` 已回读一致；同一文件在两侧均通过
`bash -n`。脚本本身只负责容器内启动，不再包含宿主机/容器双模式、Docker 状态解析、动态
run ID、checkout/设备资源锁、容器身份判断和重复检查。容器内启动命令为：

```text
cd /mnt/nfs/users/jinghao/glm5.3-flash
./start-model.sh
```

脚本在启动前只检查 8010 未被占用；任何已有监听都会被拒绝覆盖。日志固定
追加到 `05-runs/service/service.log`，不再维护 PID 文件。原有
`02-environment/resource_lock.py` 作为历史环境工具保留，但最终入口不再调用。保留的显式
环境变量均有以下理由：

| 环境变量 | 值 | 保留理由 |
|---|---|---|
| `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS` | `1800` | 已批准的长请求分布式 RPC 有界等待；不是生成截断根因 |
| `VLLM_USE_BREAKABLE_CUDAGRAPH` | `1` | stateful sparse indexer 的 graph 正确性边界 |
| `FLAGGEMS_DB_URL` | `07-cache/service/*.db?timeout=1800` | autotune DB 放入批准 cache，并缓解 TP16 首次建表锁 |
| `TRITON_CACHE_DIR` | `07-cache/service/triton` | 编译缓存不写入 checkout 或容器默认目录 |
| `TMPDIR` | `06-tmp/service` | 隐式临时文件留在批准根 |
| `PYTHONDONTWRITEBYTECODE` | `1` | 避免 editable 源码树产生 `__pycache__` |

显式 vLLM 参数只保留：目标模型及服务名用于身份和 API 复现；TP16 对应 16 张已核对 PPU；
`127.0.0.1:8010` 限制监听范围并固定评测端口；65,536 context、32 sequences 和 0.90 显存
比例对应已验证资源配置；`glm45` 解析器保证 reasoning/content 分离；`PIECEWISE` 是已验证
graph 模式。没有 `runtime_dir`、`VLLM_FL_CONFIG`、`PYTHONPATH`、诊断、profiling、trace、
dump、临时 workaround 或自定义 capture-size 参数。

历史运行包内部记录的旧绝对路径保持原样，以免改写原始证据；这些入口标记为 legacy，不应
直接用于新轮。后续评测应把可复用入口/配置放入 `04-acceptance/`，新结果放入 `05-runs/`。

## 验证结果

- 迁移前 `--check --diff`：34 个源/目标映射全部通过无覆盖断言。
- 实际 Ansible：`ok=10 changed=5 unreachable=0 failed=0`；changed 按 task 聚合，包含目录
  创建、两处启动路径替换、全部 rename 和两个空目录 `rmdir`。
- 迁移后再次 `--check --diff`：`changed=0 unreachable=0 failed=0`，方案幂等。
- 工作根顶层精确为八个编号目录加规则要求的 `start-model.sh`，没有其他顶层文件、目录或
  兼容 symlink。
- 根级脚本在 host/container 均通过 `bash -n`；旧三个启动器移到
  `02-environment/legacy-launchers/` 并改为 `0644`；`resource_lock.py` 保持可执行。
- 当前安装源回读：`vllm_fl` 来自 `01-repos/vllm-plugin-FL`，`flag_gems` 来自
  `01-repos/FlagGems/src`，没有切到 legacy checkout。
- 精简前 105 行版本安装后，先在旧服务仍健康时调用根级入口，脚本识别相同配置并明确返回
  `leaving it unchanged`，验证不会覆盖已有服务。
- 端到端启动前确认 running/waiting 均为 0，只向已核对精确命令的旧 APIServer PID
  `2221549` 发送 TERM；8010 随后关闭。停止 playbook 最后一项因 Docker Go template 被
  Ansible 当作 Jinja 而只在状态回读时报错；修正为 Docker JSON 后，启动 playbook在实际启动
  前确认容器仍为 `running`、restart 0。没有停止、重启或删除容器。
- 精简前 105 行版本创建运行目录
  `/mnt/nfs/users/jinghao/glm5.3-flash/05-runs/glm53-graph-20260908T075102Z/`，新的
  resource-lock 和 `docker exec` argv 均直接引用 `start-model.sh`。APIServer PID
  `2245056`；120/120 shard、11/11 PIECEWISE capture、KV cache 和 warmup 完成，health 200、
  16/16 worker、容器 restart 0。
- 32-token 最小请求因 reasoning 用尽上限，按 `finish_reason=length` 保留为负探针；相同题
  提高到 256 tokens 后返回正文 `2`、`finish_reason=stop`。服务日志无 `Unsupported h_q`、
  illegal memory、OOM、EngineCore/Worker exception 或 traceback。
- 精简前 105 行版本中，`ppu-smi` 回读的 0–15 共 16 个 Bus ID 与脚本资源锁逐项一致；
  Plugin、FlagGems 和 vLLM
  revision 分别为 `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`、
  `bca444b8569294e7d4e4deff7ddfec7f05682033`、
  `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 评测状态：没有启动新的 GPQA；FlagEval 容器仅有历史 zombie 条目，没有活动评测进程。
- 用户要求精简后，部署 playbook 每次先以 `--check --diff` 验证，再将最终入口从 105 行
  收敛到 34 行；明确只在容器内直接执行后删除容器身份判断，降到 30 行；最后删除路径变量和
  PID 写入，最终为 26 行。三次部署均为 `ok=3 changed=1 unreachable=0 failed=0`，最终
  SHA-256 如上。
- 精简版真实拉起 APIServer PID `2254900`：120/120 shard、11/11 PIECEWISE capture、
  health 200、16/16 worker。256-token 最小请求返回正文 `2`、`finish_reason=stop`；日志中的
  fatal signature 计数为 0，容器保持 running/restart 0。
- 服务就绪后再次执行入口，返回 `Port 8010 is already in use; refusing to replace the running
  service.` 且退出码为 1，验证不会覆盖已有服务。
- 26 行最终版已在容器工作目录以 `./start-model.sh` 直接调用；端口保护退出码为 1，既有服务
  health 仍为 200，running/waiting 均为 0。该版本相对已完成真实拉起的 34 行版本只删除
  容器身份判断、路径变量和 PID 写入，vLLM 命令及全部运行参数未变。

## 限制与下一步

- 本轮只整理远端工作区，不执行 architecture/environment/adaptation/acceptance 阶段，不刷新
  `platform.yml` receipt，也不改变既有 accuracy 失败和 performance 未开始的状态。
- legacy 目录暂不删除，便于用户复核和历史取证；如需释放约 2 GiB 的旧 checkout、tmp 和
  cache，必须另行确认精确删除目标后执行。
- 根级入口已经完成真实 graph 拉起和最小推理，但这不是新的正式 accuracy/performance 轮；
  既有 GPQA 83.84% 失败状态不变。

## 经验沉淀

- 可复用判断：远端整理先核对 host/container 映射、活动进程和目标冲突；历史结果以移动保留
  为主，原始日志不做路径替换；当前入口和历史入口必须分开标识。
- 知识库处理状态：`local-only`
