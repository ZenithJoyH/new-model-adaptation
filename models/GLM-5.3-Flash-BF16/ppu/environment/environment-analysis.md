# GLM-5.3-Flash-BF16 / PPU-13 推理环境分析

## 2026-09-06 当前环境复核

本文旧快照中的 plugin 路径/revision、FlagGems revision 和“当前插件不含 GLM 文件”均已
过期。本轮只读复核连通性、PPU、容器身份、软件版本和三个源码边界；复核完成前不生成
environment verification binding：

```bash
./scripts/connectivity-check --limit PPU-13
./scripts/accelerator-check --limit PPU-13
ssh PPU-13 "docker inspect glm5.3-flash --format '{{.Id}} {{.Config.Image}} {{.Image}} {{.State.Status}} {{.RestartCount}}'; docker exec glm5.3-flash bash -lc 'python3 --version; python3 -c \"import torch,transformers,vllm,flag_gems; print(\\\"TORCH\\\",torch.__version__,torch.version.cuda); print(\\\"TRANSFORMERS\\\",transformers.__version__); print(\\\"VLLM\\\",vllm.__version__); print(\\\"FLAGGEMS\\\",getattr(flag_gems,\\\"__version__\\\",\\\"unknown\\\"))\"; for repo in /workspace/vllm /workspace/vllm-plugin-FL-glm53-hy4-adaptation /workspace/FlagGems /workspace/FlagGems-vllm; do if [ -d \"\$repo/.git\" ]; then echo REPO=\$repo; git -C \"\$repo\" rev-parse HEAD; git -C \"\$repo\" branch --show-current; git -C \"\$repo\" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || echo NO_UPSTREAM; git -C \"\$repo\" status --short; fi; done; test -z \"\$(git -C /workspace/vllm status --porcelain)\"; ps -ef | grep -E \"[v]llm serve|VLLM::Worker\" || true; if (exec 3<>/dev/tcp/127.0.0.1/8010) 2>/dev/null; then echo PORT8010_UP; else echo PORT8010_DOWN; fi'"
```

> 运行标识：`ppu13-environment-revalidation-20260906`。重新核验确认 `glm5.3-flash`
> 容器运行、restart count 0、8010 空闲且 16 张 PPU 空闲；vLLM `ee0da84a` 工作树干净。
> 当前 GLM plugin 为 `support-hy4-preview@5329cb1` 加未提交的本模型适配改动；FlagGems 与
> FlagGems-vllm 分别为 `34bd6d68` 和 `255ab560`，两者工作树干净。正确 BF16 权重
> 120/120 分片完整。

## 范围与身份

- 平台/目标：`ppu` / inventory alias `PPU-13`；验证日期 2026-09-06。
- 模型：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`，约 599 GiB，身份哈希见模型级架构文档。
- 容器：`glm5.3-flash`，ID `bf3487115c28f4ac45b34667ce7f3853a3eaa9879b54715a6cde5e2bc81ca6b1`，image `hy4-ppu07-snapshot:20260903`，image ID `sha256:29a6712e24ca8e758ac8b33d3412892f0541bff108e2c057445fa671578237f6`。采集时 running、restart count 0、无 vLLM/EngineCore 进程；本次没有停止或重启容器。

## 硬件与资源

- 16 × `PPU-ZW810E`，每卡 98,304 MiB；`ppu-smi` 1.28，driver `2.1.1-rbd225`，容器内 HGGC 13.0。采集时每卡约 1 MiB、0% util，无 PPU 进程。
- 主机 192 逻辑 CPU、2.0 TiB 内存（约 1.9 TiB available）、无 swap；host IPC，主机 `/dev/shm` 约 1008 GiB 可用。
- `/mnt/cpfs` 21 TiB、约 15 TiB 可用；`/mnt/nfs` 14 TiB、约 11 TiB 可用。容器以 RW bind mount 使用 `/mnt`。
- 容器 privileged，host network/IPC，挂载 `/dev/alixpu*` 与 `/dev/infiniband`，memlock unlimited、stack 64 MiB。目标机器当前未发现共享 PPU workload；这只是采集时快照。

## 容器与软件栈

- Ubuntu 24.04.2 x86_64，kernel 5.10.134；Python 3.12.3、GCC 13.3.0、CMake 4.4.2、Ninja 1.13.0。
- PyTorch 2.10.0（`torch.version.cuda=13.0` 的 PPU 兼容接口）、Transformers 5.8.1、vLLM 0.24.0、tokenizers 0.22.2、compressed-tensors 0.17.1、editable FlagGems package `5.3.5+g38653f94c`。系统存在 HGGC 13、NCCL、`libnccl-net-accl-lite` 与 PPU runtime 库。
- vLLM：`/workspace/vllm`，detached HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`，工作树干净；全程只读。
- Plugin：`/workspace/vllm-plugin-FL-glm53-hy4-adaptation`，branch `support-hy4-preview`，
  revision `5329cb1293f397fd194852496cfcc710c35f1bfc`，upstream `origin/support-hy4-preview`。
  工作树包含当前 GLM-5.3-Flash 适配的已修改和未跟踪文件；它们是正在验证的本任务实现，
  必须保留并在最小修复前后分别审查 diff/status。
- FlagGems：`/workspace/FlagGems`，branch `master`、upstream `origin/master`，revision
  `34bd6d68928c8b0039c42987840929da52aa6a62`，工作树干净。
- FlagGems-vllm：`/workspace/FlagGems-vllm`，branch `main`、upstream `origin/main`，revision
  `255ab5601b8002b32044fa3632e63eb1b3d45f4e`，工作树干净并以 editable 方式接入当前环境。

## 平台能力、约束与缺口

- 既有插件基线具备 PPU MLA/Indexer/MoE 的 vendor/FlagGems/reference dispatch 和 eager/graph 专项测试，但这些能力源于 Hy4，不能直接宣称兼容 GLM5。
- TP16 是容量与 head 分片的自然起点；BF16 权重均分约 37.4 GiB/卡，给 cache/workspace 留有空间，但 50K KV、KDA state、视觉塔、MTP 和临时 buffer 的峰值仍需实测。
- 配置最大上下文 1,048,576，故初始服务严格使用 `--max-model-len 50000`，不得为掩盖显存或 graph 问题再缩小。
- 上游 Transformers 5.8.1 与 vLLM 不原生认识 `glm5_next`，但当前 plugin 已提供模型实现、
  注册和 v0.24 patch，TP16 文本基础链路已可运行；不得修改 `/workspace/vllm`。当前环境阻塞
  已从“缺少模型实现”转为 c64 长负载下 plugin kpool decode kernel 非法访存。
- graph 约束：KDA state/conv cache、mHC 固定迭代、Indexer top-k、MoE 动态路由和多模态 token bucket 都必须避免 capture-time host sync、动态 allocation、数据依赖 host control flow 与不稳定地址。

## 可重复验证

- `./scripts/connectivity-check --limit PPU-13`
- `./scripts/accelerator-check --limit PPU-13`
- `./scripts/playbook .local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/inspect-ppu13-glm53-baseline.yml`
- `./scripts/playbook .local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/inspect-ppu13-glm53-architecture.yml`
- `./scripts/playbook models/GLM-5.3-Flash-BF16/ppu/environment/collect-ppu13-environment.yml`

## 结论

硬件、存储、主机内存、容器设备和四个源码边界均已重新核验；目标当前无运行服务，
环境复核未改变远端状态。现有 TP16 BF16 实现足以继续受控诊断，前置条件是保留容器、
保持 vLLM 只读，并把当前 plugin dirty diff 视为待验证实现。下一步只恢复 kpool bounds
诊断服务，先取得真实 slot mapping/capacity 证据，再做最小 plugin 修复。

## 2026-09-07 环境目标与工作区复核

用户明确允许按 `environment → adaptation → accuracy` 补齐新门禁并重跑 19 个截断样本。
`environment-target.yml` 固定唯一 Host 为 `PPU-13`。在修改服务前，先只读确认当前服务、
16 个物理 PPU PCI Bus ID、NFS 在 host/两个容器中的同一挂载、三个 checkout 身份、现有
启动入口和没有活动评测进程：

```bash
./scripts/connectivity-check --limit PPU-13
./scripts/accelerator-check --limit PPU-13
ssh PPU-13 'ppu-smi | grep -E "^\| [0-9]+  PPU-ZW810E|^\| [0-9]+ PPU-ZW810E"; findmnt -T /mnt/nfs/users/jinghao -o TARGET,SOURCE,FSTYPE,OPTIONS; docker exec glm5.3-flash findmnt -T /mnt/nfs/users/jinghao -o TARGET,SOURCE,FSTYPE,OPTIONS; docker exec flageval_llmeval-jinghao findmnt -T /mnt/nfs/users/jinghao -o TARGET,SOURCE,FSTYPE,OPTIONS; docker inspect -f "{{.Id}} {{.Image}} {{.State.Status}} {{.RestartCount}}" glm5.3-flash flageval_llmeval-jinghao; docker exec glm5.3-flash bash -lc '\''pid=$(cat /workspace/glm53-adaptation-runtime/graph-flaggems-db-timeout/service.pid); ps -p "$pid" -o pid,ppid,stat,etime,comm,args; curl -fsS --max-time 3 http://127.0.0.1:8010/health; git -C /workspace/vllm rev-parse HEAD; git -C /workspace/vllm status --porcelain; git -C /workspace/vllm-plugin-FL-glm53-hy4-adaptation rev-parse HEAD; git -C /workspace/FlagGems rev-parse HEAD'\''; docker exec flageval_llmeval-jinghao bash -lc '\''ps -eo pid,ppid,stat,etime,comm,args | grep -E "[l]lmrun.py|[r]erun.*truncated" || true'\''; sed -n "1,240p" /mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph.sh; sed -n "1,240p" /mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph_host.sh'
```

host、服务容器和评测容器均看到 `/mnt/nfs` 的同一 NFSv4.2 挂载。物理设备状态使用
`ppu-smi` 复核；当前 PID `951344` 仍健康、模型长度 50000，没有活动评测进程；
本轮环境复核没有停止或重启服务。

用户此前明确指定、并在本轮再次允许使用的远端工作根为
`/mnt/nfs/users/jinghao/glm5.3-flash`；host、服务容器和评测容器看到同一 NFSv4.2 挂载，
因此 `workspace.roots` 对 `PPU-13` 的 `host_root/container_root` 均登记为该规范绝对路径。
模型权重和三个既有 checkout 只作为外部依赖读取；新的环境文件、acceptance wrapper、
run 日志/结果、tmp 与 cache 都收敛到该根目录。

## 2026-09-07 Hy4 最新基线重整前环境复核

用户授权先执行 environment 复核，并在批准工作根下的
`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL` 创建和修改新插件 checkout。
目标仍为唯一 Host `PPU-13`，适配容器 `glm5.3-flash`；旧
`/workspace/vllm-plugin-FL-glm53-hy4-adaptation`、`/workspace/vllm` 和
`/workspace/FlagGems` 在此轮仅作只读基线。先执行以下命令，不写远端：

```bash
./scripts/connectivity-check --limit PPU-13
./scripts/accelerator-check --limit PPU-13 -e '{"accelerator_query_command":"cd /mnt/nfs/users/jinghao/glm5.3-flash && test \"$(pwd -P)\" = /mnt/nfs/users/jinghao/glm5.3-flash && ppu-smi"}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; printf "HOST_ROOT="; realpath "$root"; findmnt -T "$root" -o TARGET,SOURCE,FSTYPE,OPTIONS; for container in glm5.3-flash flageval_llmeval-jinghao; do docker inspect -f "{{.Name}} {{.Id}} {{.Image}} {{.State.Status}} {{.RestartCount}}" "$container"; docker exec -w "$root" "$container" bash -lc '\''test "$(pwd -P)" = /mnt/nfs/users/jinghao/glm5.3-flash; printf "CONTAINER_ROOT="; realpath .; findmnt -T . -o TARGET,SOURCE,FSTYPE,OPTIONS'\''; done; test ! -e 01-repos/vllm-plugin-FL; test ! -L 01-repos; curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null && echo SERVICE_HEALTHY'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w /workspace/vllm-plugin-FL-glm53-hy4-adaptation glm5.3-flash bash -lc '\''test "$(pwd -P)" = /workspace/vllm-plugin-FL-glm53-hy4-adaptation; echo PLUGIN; git remote -v; git rev-parse HEAD; git branch --show-current; git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}"; git status --short; git diff --stat; git diff --name-status; git diff --binary --no-ext-diff HEAD -- | sha256sum; git ls-files --others --exclude-standard'\''; docker exec -w /workspace/vllm glm5.3-flash bash -lc '\''test "$(pwd -P)" = /workspace/vllm; echo VLLM; git rev-parse HEAD; git status --short'\''; docker exec -w /workspace/FlagGems glm5.3-flash bash -lc '\''test "$(pwd -P)" = /workspace/FlagGems; echo FLAGGEMS; git remote -v; git rev-parse HEAD; git branch --show-current; git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}"; git status --short'\''; git ls-remote https://github.com/ZenithJoyH/vllm-plugin-FL.git refs/heads/support-hy4-preview'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w /workspace/vllm-plugin-FL-glm53-hy4-adaptation glm5.3-flash bash -lc '\''test "$(pwd -P)" = /workspace/vllm-plugin-FL-glm53-hy4-adaptation; find .. -maxdepth 2 -type f \( -name AGENTS.md -o -name CONTRIBUTING.md -o -name README.md \) -print; find . -maxdepth 3 -type f | sort | grep -E "(dispatch|backend|model|contrib|README|AGENTS)" | head -n 240'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w /workspace/vllm-plugin-FL-glm53-hy4-adaptation glm5.3-flash bash -lc '\''test "$(pwd -P)" = /workspace/vllm-plugin-FL-glm53-hy4-adaptation; git ls-remote origin refs/heads/support-hy4-preview; for file in README.md tests/README.md vllm_fl/dispatch/README.md examples/glm5_next/README.md examples/glm5_next/BACKEND_CONTRACTS.md; do echo FILE=$file; test -f "$file" && sed -n "1,360p" "$file" || true; done'\'''
```

若且仅若上述检查确认 root 映射、目标路径未使用、容器健康、vLLM 干净，才进入新 checkout
的创建；实际结果、revision 与差异分类在本节后续补充。

复核结果（2026-09-07）：

- `connectivity-check` 到达 `PPU-13 -> bm-aliyun-wlcb-zonea3-c-810e-96g-10-13`。
- host、`glm5.3-flash` 与 `flageval_llmeval-jinghao` 中的规范 root 都是
  `/mnt/nfs/users/jinghao/glm5.3-flash`，三者均解析到同一 NFSv4.2
  `10.11.0.1:/data/nfs` 挂载；两个容器 running、restart count 0。
- `01-repos/vllm-plugin-FL` 不存在，`01-repos` 不是符号链接；8010 服务 health 200。
- `accelerator-check` 的有效复测确认 16×PPU-ZW810E 可见；服务占用每卡约
  91.7 GiB，说明本轮不能把设备描述为空闲。最初以 key-value extra-vars 传参只执行了
  `cd`，未作为设备证据；JSON extra-vars 复测才是有效结果。
- 外部只读基线：vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`、工作树干净；
  FlagGems `34bd6d68928c8b0039c42987840929da52aa6a62`、工作树干净；旧插件 HEAD
  `5329cb1293f397fd194852496cfcc710c35f1bfc`，tracked diff SHA256
  `a760b27644a02b376b3ca3ac6a79160bb544b767646d1158fea43790e2ef0503`，含 11 个
  tracked 修改及 34 个未跟踪路径。
- 用户指定分支的远端最新 HEAD 为
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`，已明显晚于旧适配基线；旧 checkout
  的 README、dispatch 设计和测试指南已读取，未发现插件自身 `AGENTS.md` 或
  `CONTRIBUTING.md`。

环境结论：新 checkout 可在批准 root 内安全创建，且不会直接改变当前运行服务引用的旧
editable checkout。后续以 `d56f7b2` 为唯一 Hy4 基线，先迁移和审查差异，再决定哪些 GLM
实现仍缺失；vLLM 保持只读。FlagGems 外部 checkout 尚未获写授权，如重整需要检查或接入
其最新算子，必须先另行授权在 `01-repos/` 同步 FlagGems。

新 checkout 使用 Ansible 单 Host、幂等模块创建。先以 check/diff 预演目录和 clone，再执行；
`creates` 防止覆盖意外 checkout：

```bash
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.file -a '{"path":"/mnt/nfs/users/jinghao/glm5.3-flash/01-repos","state":"directory","mode":"0755"}' --check --diff
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.file -a '{"path":"/mnt/nfs/users/jinghao/glm5.3-flash/01-repos","state":"directory","mode":"0755"}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash","glm5.3-flash","git","clone","--branch","support-hy4-preview","--single-branch","https://github.com/ZenithJoyH/vllm-plugin-FL.git","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL"],"creates":"/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL/.git"}' --check --diff
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash","glm5.3-flash","git","clone","--branch","support-hy4-preview","--single-branch","https://github.com/ZenithJoyH/vllm-plugin-FL.git","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL"],"creates":"/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL/.git"}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; repo=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; test "$(realpath "$repo")" = "$repo"; docker exec -w "$repo" glm5.3-flash bash -lc '\''test "$(pwd -P)" = /mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL; git remote -v; git branch --show-current; git rev-parse HEAD; git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}"; git status --short'\'''
```

## 2026-09-08 FlagGems small-head sparse MLA 更新

用户明确要求在当前容器安装 ZenithJoyH 的
`sparse-mla-opt-w8a8-moe-fix` 分支并验证。写入前重新确认唯一 Host `PPU-13`、host/container
root 均为 `/mnt/nfs/users/jinghao/glm5.3-flash`，容器 `/mnt` 映射到 host `/mnt`，目标
FlagGems checkout 位于批准根的 `01-repos/FlagGems` 且为干净的
`master@dcd0cfeae8187dee691656c0616c1ed95899c2ae`；vLLM 保持
`ee0da84ab9e04ac7610e28580af62c365e898389`、工作树干净。

当前 FlagGems 已切换为：

- remote：`https://github.com/ZenithJoyH/FlagGems.git`（remote name `zenith`）；
- branch/upstream：`sparse-mla-opt-w8a8-moe-fix` /
  `zenith/sparse-mla-opt-w8a8-moe-fix`；
- revision：`bca444b8569294e7d4e4deff7ddfec7f05682033`；
- package：`flag_gems 5.4.0rc1.post1+gbca444b85`；
- editable location：`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems`；
- 状态：工作树干净。

安装使用 `python3 -m pip install --no-build-isolation --no-deps -e .`；pip cache/tmp、算子
cache、复现和运行日志均位于批准工作根的 `06-tmp/`、`07-cache/`、`08-bugs/` 和
`05-runs/021-flaggems-sparse-small-head/`。更新期间仅停止并重启本模型服务，容器始终
`running`、restart count 0。终态 TP16 服务使用原启动参数，health 200、16/16 worker；
详细前后对照见 [021](../adaptation/021-flaggems-sparse-small-head-no-padding-20260908.md)。

## 2026-09-08 FULL decode graph 前置环境复核

用户允许按 `environment → adaptation` 顺序重新梳理 graph 适配，目标是删除
`VLLM_USE_BREAKABLE_CUDAGRAPH` 并至少启用 decode 阶段 FULL graph。环境检查使用运行标识
`ppu13-full-decode-environment-20260908`，没有修改或中断当前服务。

- `./scripts/connectivity-check --limit PPU-13`：到达
  `bm-aliyun-wlcb-zonea3-c-810e-96g-10-13`，`changed=0`、`failed=0`、`unreachable=0`。
- `./scripts/accelerator-check --limit PPU-13`：原生 `ppu-smi` 成功，16×PPU-ZW810E 均由
  当前 TP16 服务占用约 88.8 GiB；不能将设备描述为空闲。
- host root 与 container root 均为
  `/mnt/nfs/users/jinghao/glm5.3-flash`，两侧解析到同一 NFSv4.2
  `10.11.0.1:/data/nfs` 挂载。容器 `glm5.3-flash` ID
  `bf3487115c28f4ac45b34667ce7f3853a3eaa9879b54715a6cde5e2bc81ca6b1`，镜像
  `hy4-ppu07-snapshot:20260903` / image ID
  `sha256:29a6712e24ca8e758ac8b33d3412892f0541bff108e2c057445fa671578237f6`，状态
  running、restart 0。
- 当前服务 APIServer PID `2254900`，模型 `/mnt/cpfs/models/GLM-5.3-Flash-BF16`，TP16、
  65,536 context、32 sequences、`PIECEWISE`，health 200。最终启动脚本 SHA-256 为
  `bc780f34d6005cb358ad4a266dedc8c7b7400d8a2513856cbcbf58630e4a335f`；其中仍有
  `VLLM_USE_BREAKABLE_CUDAGRAPH=1`，它是本轮要退出的旧 graph workaround。
- 正式 Plugin checkout 为批准根内
  `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`，branch/upstream
  `support-hy4-preview` / `origin/support-hy4-preview`，HEAD
  `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`；`git ls-remote` 证明远端分支仍为同一
  revision，不需 fetch。editable import 也解析到该 checkout。工作树包含既有 GLM 适配的
  staged 修改和未跟踪产品文件，另有三个 register 文件的 unstaged 收敛；相对 HEAD 的 tracked
  binary diff SHA-256 为
  `7f4fe4c0da49a938713d334b463f378bff3b464ca416574201d4628fb9c8b247`。这些均为继承改动，
  本轮不得丢弃或覆盖。
- vLLM `/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389` 工作树干净，继续
  只读。FlagGems checkout 位于批准根，branch/upstream
  `sparse-mla-opt-w8a8-moe-fix` / `zenith/sparse-mla-opt-w8a8-moe-fix`，revision
  `bca444b8569294e7d4e4deff7ddfec7f05682033`，工作树干净，editable package
  `5.4.0rc1.post1+gbca444b85`。

指定 Hy4 基线的 `README.md`、`tests/README.md` 和 `vllm_fl/dispatch/README.md` 已完整
读取；checkout 没有 `AGENTS.md` 或 `CONTRIBUTING.md`。纯 Hy4 基线已经在 attention、MoE、
normalization、router 和 `hy_v4` indexer 热路径使用 `CachedOp`：首次选定实现后直接调用
`impl.fn`，避免每次进入 `OpManager.call`。当前 GLM 适配给 shape/layout 相关实现增加
`supports` 后，`CachedOp` 发现任一 candidate 带 predicate 即永久设置
`_use_manager_call=True`，每次调用重新进入 `resolve_candidates`/manager/registry 的
`threading.RLock`。这与移除 breakable graph 后 Dynamo 报 unsupported context manager 的
签名相符，是本轮需通过受控负对照确认的首要假设；尚未把它标记为根因。

本轮修改边界：只允许修改上述 Plugin checkout 和批准根内的诊断、运行、cache/tmp 产物；
不得修改 vLLM、权重或容器。若不需要新增/替换 FlagGems 算子，不改 FlagGems；若后续确认
需要 operator integration，则必须先按其当前 tracked branch 做同步检查。graph 目标配置为
`FULL_AND_PIECEWISE`：uniform decode 使用 FULL，prefill/mixed 使用 PIECEWISE；删除旧环境变量
前必须完成无锁 dispatch、state/cache changed-input replay、TP16 服务和并发正确性验证。

## 2026-09-11 compact 记录迁移与终态复核

为解除旧 `deployment-identity.yml` 对已迁移工作区的历史哈希耦合，平台记录改为当前规则的
`record_layout: compact`；作用域直接绑定在 `platform.yml`，没有刷新或伪造旧 runtime 哈希。
2026-09-11 对唯一目标 `PPU-13` 做了最终只读复核：

- host/container root 均为 `/mnt/nfs/users/jinghao/glm5.3-flash`；容器仍为
  `bf3487115c28f4ac45b34667ce7f3853a3eaa9879b54715a6cde5e2bc81ca6b1`，镜像 digest
  `sha256:29a6712e24ca8e758ac8b33d3412892f0541bff108e2c057445fa671578237f6`，running、restart 0。
- Plugin editable checkout 为
  `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL@db09b64afdc222d1c32e4e80f30820a243358e34`；
  FlagGems editable checkout 为
  `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems@4a3cba029d87ec06b5222ed94542f1f1d2e267a0`；
  两个工作树均 clean。
- 当前 TP16 `FULL_DECODE_ONLY` 服务实例
  `PPU-13:bf3487115c28:42996:175243105` 为 health 200、16/16 worker。
- 根级 launcher 的 host/container 路径均为
  `/mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh`，SHA-256
  `5d54dacc5f5af26bd3e4847aad85ae4575b98d7072093aa21ad2ed550b4534ba`。

该复核只迁移记录绑定并确认当前远端事实，不改服务、容器、源码、权重或挂载。
