# Hy4-preview PPU 推理环境

## 2026-09-07 21:51 新服务与 compact 工作区重新核验

本轮用户授权将 environment 纳入执行范围，以便把旧版本地运行记录迁移为现行 compact
平台作用域并继续正式 GPQA。目标精确为 `PPU-07` / `hy4`；宿主批准根目录与容器根目录
均为 `/mnt/nfs/users/jinghao/hy4-preview`。`docker inspect` 现场确认 `hy4` 容器 ID
`550e93f0ba4c3109f05002d3a39c55d10c42eee13d661f3062757d9505535ca2`、状态
`running`，宿主 `/mnt` 以 RW bind 原样映射到容器 `/mnt`。评测容器
`flageval_llmeval-jinghao` 的 ID 为
`b0147718f168aa81f9181b2e7854126b2cfc9f3bf22411396bfbb8e7906c5b30`，镜像 ID
`sha256:bcefa10b9be062ed449ac1e7b7925fa4f9a46e1361fbb25cc6e99616bc59a4f5`，
也将宿主 `/mnt` 以 RW bind 原样映射到容器 `/mnt`。两个容器均为 host network，故评测
容器可按既有约定访问 `http://127.0.0.1:8010`。

用户于 18:16 启动的新 graph 服务加载 W8A8 权重、TP16、`max-model-len=100000`、
`gpu-memory-utilization=0.9` 和 `FULL_DECODE_ONLY`。21:51 现场核验得到 API `/health` 与
`/v1/models` HTTP 200、served model `hy4`、16/16 worker、running/waiting/KV usage 均为
0，51/51 decode graph 已完成捕获。16 张 PPU-ZW810E 各占用约 89,992 MiB；这是空闲时
快照，不作为负载性能结论。当前实例日志尚无 `database is locked`、worker exception、
EngineCore fatal、illegal memory access 或 HTTP error，但尚未承受正式并发负载。

现场代码身份为：vLLM `/workspace/vllm` clean detached
`ee0da84ab9e04ac7610e28580af62c365e898389`；FlagGems `/workspace/FlagGems` clean
`sparse-mla-opt@717a9ef60d38b559d8b4424488ca5cad2fe61a59`；Plugin
`/workspace/vllm-plugin-FL` 为
`support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8`，保留用户已有的
`thead.yaml` 修改和 `PROVENANCE.md` 删除，完整 tracked diff SHA-256 为
`d2a01df0f5d9b85bbb51d3111bde7ceeafef9f563f6be1b151cbfd9616a3943d`。本轮未修改或
清理这些用户变更。`thead.yaml` 当前将 `index` 加入 `flagos_blacklist`，因此该实例不会
走上一轮触发 SQLite 锁的 FlagGems `index` 路径；这只是待受控负载验证的现场 workaround，
不能由静态配置直接宣称已修复。

模型 `config.json` 与权重索引 SHA-256 分别保持
`894bbe4e1dea2ac68993891795d3397f71bd2e4c92aae89ba443c10ebca462c2` 和
`14694cc4639eb2f8c9996d4674ad24927b690b0f8441f3f30d31912988bbb9c1`。三个现有
FlagGems SQLite 文件均只读执行 `PRAGMA integrity_check` 并返回 `ok`；本轮未修改、清理或
人为加锁生产数据库。环境核验只证明当前实例、映射、代码和评测容器身份；后续仍须按
adaptation → execution-mode → sanity → accuracy 的顺序验证 workaround 与整模型行为。

## 2026-09-07 SQLite 锁复现前置环境重新核验

为恢复缺失的 `environment-target.yml` 并在批准根目录打包当前评测崩溃的最小复现，
本轮重新执行了 PPU 原生状态查询和只读现场核验。目标精确限定为 `PPU-07` / `hy4`；
宿主与容器工作根均为 `/mnt/nfs/users/jinghao/hy4-preview`。`docker inspect`
确认容器 ID 仍为
`550e93f0ba4c3109f05002d3a39c55d10c42eee13d661f3062757d9505535ca2`、状态
`running`、宿主 `/mnt` 以 RW bind 原样映射到容器 `/mnt`，镜像为
`harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`
（image ID
`sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f`）。

当前代码身份：vLLM `/workspace/vllm` 为 clean detached
`ee0da84ab9e04ac7610e28580af62c365e898389`；FlagGems `/workspace/FlagGems`
为 clean `sparse-mla-opt@717a9ef60d38b559d8b4424488ca5cad2fe61a59`；Plugin
`/workspace/vllm-plugin-FL` 为
`support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8`，但现场存在一处
本轮未产生且未处理的 tracked 删除：
`vllm_fl/dispatch/backends/vendor/thead/lib/PROVENANCE.md`。复现打包不得修改这三套源码。

`ppu-smi` 在 2026-09-07 16:37:02 成功返回 PPU-SMI 1.28、driver
2.1.1-rbd225；输出所示设备为 PPU-ZW810E、1 MiB/98304 MiB、0% 利用率。
容器内已无 API、EngineCore 或 TP worker，仅保留交互 shell。启动脚本仍使用 W8A8
权重、served name `hy4`、端口 8010、TP16、`max-model-len=100000` 和
`gpu-memory-utilization=0.9`，且没有设置 `FLAGGEMS_DB_URL`。当前环境中的关键包版本为
torch 2.10.0、vLLM 0.24.0+empty、transformers 5.8.1、compressed-tensors
0.17.1、FlagGems `0.0+g717a9ef60`。

现场只读命令为 `./scripts/accelerator-check --limit PPU-07` 和
`./scripts/playbook /private/tmp/revalidate-hy4-environment.yml --limit PPU-07`；两者均
`changed=0`、`failed=0`。这些结果仅重新验证复现所需的目标、映射和运行栈，不表示
模型服务或评测通过。

## 2026-09-07 FlagGems 用户修改后的重新核验

用户说明已修改远端 FlagGems，并授权重新核验 environment 后继续 BF16 Indexer top-k
归属调整。本轮使用以下只读入口重新确认容器映射、FlagGems/Plugin/vLLM revision 与
工作树、实际调用图、服务进程和 PPU 状态：

```bash
./scripts/playbook models/Hy4-preview/ppu/environment/inspect-ppu07-indexer-topk-ownership.yml --limit PPU-07
```

核验结果：容器仍为 `hy4`，ID
`550e93f0ba4c3109f05002d3a39c55d10c42eee13d661f3062757d9505535ca2`，状态
`running`；宿主 `/mnt` 仍以 RW bind 映射到容器 `/mnt`，批准根目录映射不变。
FlagGems 已由用户切换为 clean
`sparse-mla-opt@717a9ef60d38b559d8b4424488ca5cad2fe61a59`，upstream
`origin/sparse-mla-opt`。Plugin 仍为
`support-hy4-preview@11848598449f6d650df64170db4187c387361ce5` 并保留既有
dirty/untracked 适配；vLLM 仍为 clean detached
`ee0da84ab9e04ac7610e28580af62c365e898389`。

16 张 PPU-ZW810E 均为 1 MiB、0% 利用且无 PPU 进程；容器内无模型服务或测试进程。
调用图搜索确认 `vllm_fl/models/hy_v4.py` 的 `_indexer_topk =
CachedOp("bf16_indexer_topk")` 是唯一产品调用点；FlagGems/T-Head backend、各自注册和
`thead.yaml` 是其实现/配置层，没有其他模型、`mla_prefill` 或 attention backend 调用者。
因此环境与调用图前置条件支持将 top-k 收归 BF16 Indexer backend；整模型与性能结论
仍需在修改后单独验证。

## 2026-09-07 FlagGems Sparse MLA 小 head 修复现场

用户确认本轮目标为 `PPU-07` / `hy4`，宿主工作根目录为
`/mnt/nfs/users/jinghao/hy4-preview`，并单独授权修改容器镜像层中的
`/workspace/FlagGems`。`docker inspect` 证明宿主 `/mnt` 以可写 bind 方式
原样映射到容器 `/mnt`，因此容器工作根目录也是
`/mnt/nfs/users/jinghao/hy4-preview`。容器 ID 为
`550e93f0ba4c3109f05002d3a39c55d10c42eee13d661f3062757d9505535ca2`，状态
`running`，镜像与 `runtime-config.yml` 一致。

现场代码基线：FlagGems `/workspace/FlagGems` 为
`codex/fix-w8a8-moe-config@842b19d8ad5bd8bd66cce1e52b26ade54b0b851f`，
upstream `zenith-w8a8/codex/fix-w8a8-moe-config`，工作树干净；Plugin
`/workspace/vllm-plugin-FL-hy4-preview` 为
`support-hy4-preview@11848598449f6d650df64170db4187c387361ce5`，保留历史 dirty
适配工作树；vLLM `/workspace/vllm`
`ee0da84ab9e04ac7610e28580af62c365e898389` 为 clean detached HEAD。

`ppu-smi` 显示 16 张 PPU-ZW810E，基线均为 1 MiB 且 0% 利用，
无 PPU 进程；容器中也无 `vllm serve`/API 服务进程。只读复现命令：

```bash
./scripts/accelerator-check --limit PPU-07
./scripts/playbook models/Hy4-preview/ppu/environment/inspect-ppu07-flaggems-small-head-baseline.yml --limit PPU-07
```

## 当前修复基线：PPU-07 / hy4，2026-09-04

本轮用户授权校准前置环境，目标不是下文历史PPU-13。已用 `verify-ppu07-current-prerequisites.yml`、connectivity-check及accelerator-check实查：容器running，镜像 `harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`，ID `sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f`。

Ubuntu24.04.2；torch2.10.0、transformers5.8.1、compressed-tensors0.17.1、vLLM0.24.0+empty、flash-mla2.0.0+v0.1.0.ppu2.1.0。Triton的distribution元数据缺失，不能以此断言没有Triton。PPU-SMI1.28、driver2.1.1-rbd225，PPU-ZW810E每卡98304MiB；本次查询输出前4卡约92648–92716MiB占用、0%计算利用率，不能推广为所有时刻余量。服务TP16，通信与完整拓扑仍沿用下方已记录基线，未新做通信性能验收。

代码：插件 `/workspace/vllm-plugin-FL-hy4-preview`，support-hy4-preview HEAD `11848598449f6d650df64170db4187c387361ce5`，dirty；vLLM `/workspace/vllm` HEAD `ee0da84ab9e04ac7610e28580af62c365e898389` clean；FlagGems `/workspace/FlagGems` master HEAD `60d043094d0217cad75528cb0e47a606c87ab1e4` clean（同步前）。原生SO与FlashMLA可用但默认分发已调整为FlagGems优先。

服务使用W8A8-linear-moe权重，100K上下文、TP16、0.9显存比例、FULL_DECODE_ONLY。启动脚本 `/mnt/nfs/users/jinghao/hy4-preview/start_hyv4-preview.sh`，日志同目录 `hy4-preview.log`。脚本source PPU SDK，设置OpenMPI/ibverbs、bond IPv6通信、spawn及1800秒执行超时，未设置VLLM_FL_CONFIG override。当前API2415159/Engine2415639。已有日志显示乱码、reference注册缺失方法及KV接近满载；环境可开展独立算子复现，但模型正确性未通过。保留100K复现条件，不以调低负载作为算子修复。

环境分析完成仅表示当前目标、软件、资源和风险已经明确，不表示服务或模型通过验收。以下段落为历史证据。

## 范围及核对方式

2026-08-28 通过 inventory alias `PPU-13` 只读检查运行容器 `hy4-graph`。连接检查使用 `./scripts/connectivity-check --limit PPU-13`，版本/代码/进程比较使用 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-existing-hy4-for-new-bf16.yml`。未执行设备计算、权重加载、升级、缓存清理或服务重启。

## 当日核实的运行环境

| 项目 | 结果 |
|---|---|
| 容器状态 | running |
| 镜像名 | `harbor.baai.ac.cn/flagos-inner-models-release/hyv4-pp001-gems0.0.0-treenone-cxnone-plugin0.2.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:graph` |
| Docker image ID | `sha256:f58f858b59d883df1cf263b52706e3db7b4c1b28b11343fc5c93559d63c5648b`；来自 `.Image`，不冒充 registry RepoDigest |
| PyTorch / Transformers | 2.10.0 / 5.8.1 |
| tokenizers / compressed-tensors | 0.22.2 / 0.17.0 |
| vLLM Python 包 | 0.24.0+empty |
| vLLM 源码 | `/workspace/vllm`，`ee0da84ab9e04ac7610e28580af62c365e898389`，工作树干净 |
| 插件 | `/workspace/vllm-plugin-FL`，`85754c1f7884e2f2c85edf4af52e20211d46c22e`，分支 `030plugin-for-day0`，有已修改/未跟踪文件 |
| FlagGems | `/workspace/FlagGems`，`662ca746b5841c9cb50172951388aa7153977dfe`，工作树干净 |
| Tokenizer 类解析 | `tokenizer_class_from_name('TokenizersBackend')` 成功；尚未执行完整新版 AutoTokenizer 加载/生成 |
| 进程状态 | 观测到 vllm PID 495321、EngineCore PID 495802 及 16 个 TP worker；此为采集时快照，不表示新模型已运行或接口已通过健康检查 |

## 继承的硬件与工具链记录

以下来自旧模型 2026-08-26 的环境采集，本轮没有重新查询动态余量或压测拓扑：16 × PPU-ZW810E，每卡 98,304 MiB；driver `2.1.1-rbd225`，SDK `2.1.0`，ppu-smi `1.28`；Ubuntu 24.04.2、Python 3.12.3、GCC 13.3.0、CMake 3.26.0、Ninja 1.10.0；192 逻辑 CPU、主机内存 2 TiB。Flash MLA wheel 当时为 `2.0.0+v0.1.0.ppu2.1.0.oe`。

历史记录可支持容量和兼容性预判，但不能当作当日空闲资源。后续启动前用 `./scripts/accelerator-check --limit PPU-13` 重新检查，通信拓扑与性能使用 `test/nccl_test/` 验证；不使用 NVIDIA 查询命令替代 PPU 工具。PPU Triton 的独立版本号仍缺乏标准 distribution metadata，需在正式实施时补录可追溯版本。

## 对新版适配的影响

1. 主体结构未变，有希望继续使用 INT8 W8A8 投影/专家 + BF16 Indexer/KV cache；不采用官方示例中的 FP8 路径。
2. 配置中的 Transformers 5.16.2 是保存版本；官方 finetune 的版本下限也不是现有插件推理的直接下限。当前 tokenizer 类可解析，但 config 构建、完整 tokenizer、reasoning/tool parser 仍需测试。不在分析阶段升级共享环境。
3. 新 BF16 分片约 1,452.85 GiB；理想均分 TP16 也约 90.80 GiB/卡，仅剩约 5.2 GiB 给运行时，且存在复制参数、临时 buffer 和 KV 开销。不能默认该容器能用旧参数直接跑 BF16 基线；可采用其他合适环境的参考输出或局部数值参考。
4. 若沿用旧 W8A8 覆盖范围，存储预计仍在约 737 GiB 量级；这是容量估算，不是新产物测量值，也不证明性能。
5. 现有源码有大量插件内补丁，镜像 ID 相同不代表运行时内容相同。正式修改前需再次保存 branch/revision/status 和既有 diff；禁止修改 vLLM 源码或重启容器。

本次没有更改旧启动脚本 `/mnt/nfs/users/jinghao/hy_v4/start_hyv4_final.sh`、服务日志或 blacklists。历史启动参数只作为下文适配计划的候选，不表示本轮重新审计了当前服务的全部参数。

补充核对（2026-08-28）：在后续 BF16 可行性问答中，只读重查了上述脚本的模型/精度/内存/并行参数，仍为 TP16、50K、32 并发、0.8、FULL_DECODE_ONLY；同时确认插件未量化 MoE 的 BF16 代码分支存在。排除 MTP 后的权重均分仍约 89.63 GiB/卡。脚本、容量推导及未实测边界见 `../environment/bf16-direct-run-readiness.md`；服务未改动。

## PPU-07 / hy4 当前静态基线（2026-09-02）

本轮通过 inventory alias `PPU-07` 只读检查运行中容器 `hy4`。容器镜像为 `harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`（image ID `sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f`），服务加载 `/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`，TP16，端口 8010。

| 代码库 | revision / 状态 |
|---|---|
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389`，工作树干净 |
| FlagGems | `38653f94c09a20107525570e2cf2122cbcc1ad7a`，`master`，工作树干净；本轮静态分析未 fetch/pull |
| vllm-plugin-FL | `11848598449f6d650df64170db4187c387361ce5`，`support-hy4-preview`，存在 tracked 及 untracked 修改，当前能力不可只由 commit 或镜像 tag 重建 |

运行参数请求 `FULL_DECODE_ONLY`，但 EngineCore 最终将 cudagraph 覆盖为 `NONE`，实际 decode 仍为 eager。观测时服务空闲，`ppu-smi` 可用，每卡约占用 79.9–80.0 GiB；不用空闲快照推断请求期间利用率。已有日志显示 accl-lite v6 和 4 个 `fic2_soe_bond*` 设备初始化，TP all-reduce 选用 PYNCCL；未做通信微基准，不从 `NCCL_IB_DISABLE=1` 单一变量推断通信故障。

影响适配计划的关键结论：先修复 graph 实际未开启，再按 profile 处理 TP16 下 BF16 sparse MLA 4→64 head padding、21 个 full Indexer 的固定 50K decode logits/top-k 及 prefill host sync。完整证据、优先级和验证顺序见 `../environment/performance-static-analysis-ppu07-20260902.md`。本轮远端 changed=0，没有改动服务或容器。
