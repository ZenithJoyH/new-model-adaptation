# GLM-5.3-Flash-BF16 / ppu

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)


旧平台阶段记录按原位置保留（不作为新增执行入口）：
- [环境与设计](environment/README.md)。
- [问题台账](adaptation/README.md)。
- [验收记录](acceptance/README.md)。

## 整理前平台说明（历史原文）

本地工具维护（2026-09-07，未部署远端）：旧 `acceptance/start_gpqa.sh` 已明确停用，
避免固定目录失效后在调用者目录误执行；[原文与替代入口](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/acceptance/historical-entrypoints/README.md)
保留可追溯性。下列模型验证、结果及平台状态没有因此改写。

目录导航：[环境与设计](environment/README.md) · [问题台账](adaptation/README.md) ·
[验收轮次](acceptance/README.md) · [Plugin 设计审查](environment/plugin-change-review.md)。
目录整理不改变以下验证结论；历史路径映射见
[022](adaptation/022-remote-workspace-numbered-layout-20260908.md)。

## 当前状态

- 目标：`PPU-13` 上运行 `/mnt/cpfs/models/GLM-5.3-Flash-BF16`，120 个 BF16
  safetensors 分片；16×PPU-ZW810E。
- 容器：`glm5.3-flash`，镜像 `hy4-ppu07-snapshot:20260903`，适配期间始终保持运行。
- 引擎：vLLM 0.24.0，`/workspace/vllm` 保持未修改；修复版服务健康。
- Plugin：`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`，基于当前
  `support-hy4-preview@4f9630ca0701d5a569d8c8ee7cff6e039f15a9c9` 重放 GLM 适配并
  editable 安装；最终分支为
  `support-glm5.3-flash@db09b64afdc222d1c32e4e80f30820a243358e34`，直接父提交是
  `4f9630c`，两者之间只有一笔 GLM 提交。提交 author/committer 均为 `ZenithJoyH`，
  容器工作树与 fork 远端一致；唯一打开的 GLM PR 为
  [ZenithJoyH/vllm-plugin-FL#2](https://github.com/ZenithJoyH/vllm-plugin-FL/pull/2)。
- FlagGems：`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems`，editable 安装并对齐
  `ZenithJoyH/FlagGems:support-glm5.3-flash@4a3cba029d87ec06b5222ed94542f1f1d2e267a0`；
  直接基于官方 `master@e15b22dc8d16e9a4b7726a6da8191c093507d2fd`，只有一笔 GLM
  算子提交。Qwen3.8 已隔离到 `support-qwen3.8-flash@ffb3a8bf`，不混入 GLM 分支。
  六条原 reference 路径均已切换到 `default.flagos`；专项数值、Plugin dispatch、TP16
  decode FULL graph 7/7、health 和真实请求均通过。
- 执行：TP16、max model len 65536、max seqs 32、`FULL_DECODE_ONLY`；prefill eager、
  decode FULL graph，`VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=1800`，不设置
  `VLLM_USE_BREAKABLE_CUDAGRAPH`。
- 状态：适配阶段已完成，平台能力为 `functional`；graph c8 sanity 已通过，但当前提交的
  全量 GPQA c32/60K 为 172/198（86.87%），10 题达到 60000 tokens 后 length cap，未达
  精度/零无效响应门槛。
  在 198 个唯一有效样本、零 timeout 和原始 strict-match ≥88% 全部核验前，不标记 optimized。
  本轮新 receipt 还被既有 deployment-identity/runtime-config 哈希不一致阻塞；没有通过刷新
  legacy 哈希绕过门禁。

PPU-13 最终启动脚本的 host/container 路径均为
`/mnt/nfs/users/jinghao/glm5.3-flash/start-model.sh`，SHA-256
`5d54dacc5f5af26bd3e4847aad85ae4575b98d7072093aa21ad2ed550b4534ba`。脚本不再创建目录，
只保留最小端口安全检查、必要环境和服务参数；进入容器后运行
`cd /mnt/nfs/users/jinghao/glm5.3-flash && ./start-model.sh`。2026-09-08
已完成真实 graph 拉起：120/120 shard、7/7 decode FULL capture、16/16 worker、health 200；
最终两轮各并发 8，共 16/16 正确并自然停止，容器保持 running/restart 0。本轮最新日志位于
`04-runs/service/service.log`。脚本不设置 `runtime_dir`、`PYTHONPATH` 或
`VLLM_FL_CONFIG`；插件自动读取自带 `vllm_fl/dispatch/config/thead.yaml`。旧启动器已移入
`01-environment/legacy-launchers/`；vLLM、FlagGems/Triton cache 与 tmp 均落在
`06-cache/`、`05-tmp/`。参数及保留理由见
[022](adaptation/022-remote-workspace-numbered-layout-20260908.md)，本轮 graph 根因见
[023](adaptation/023-full-decode-graph-without-breakable-20260908.md)。

## 当前适配结论

2026-09-07 已基于最新 Hy4 preview 干净 checkout 重新整理 GLM-5.3-Flash 适配。保留的
新增代码只覆盖目标权重必需的 `glm5_next` 配置/模型、KDA、KPool/tail、MHC、处理器、
vLLM 0.24 注册桥及对应 PPU/FlagGems adapter；没有复制旧 examples、一次性诊断脚本或
大段设备测试。启动脚本只保留服务参数和受控 cache/tmp 路径，插件自动读取仓库内
`thead.yaml`。

首次真实请求发现旧 FlagGems 的 BF16 sparse MLA 契约与 TP16 本地 `HQ=4` 不一致；4→64
padding 虽恢复功能，但只是 mitigation。2026-09-08 已安装指定的
`sparse-mla-opt-w8a8-moe-fix@bca444b8`：其 `flash_mla_sparse_fwd` 以 Triton head mask 原生
支持 `HQ=4`，不创建 padded tensor。插件侧 BF16 padding/裁剪已删除；算子 eager、graph
changed-input replay、上游 3 项测试、插件 contract、11/11 整模 graph capture 和真实请求
均通过。FP8 的另一 sparse API 仍有限制，不在本结论范围内。

正确 BF16 权重已完成最小服务与 graph 验证。最终 c64 EngineCore 故障根因不是 timeout、
FlagGems clamp/gather 或通信停顿，而是 plugin tail kernel 错把 vLLM padded 物理 slot
`block_id * 768 + offset` 按逻辑 pool size 4 解码。修复后 prefill/decode kernel 从 tail
view stride 推导实际物理页宽；无需新环境变量、额外启动参数、vLLM 修改或 FlagGems
blacklist。

该修复后的首轮正式 c64 又暴露了独立的 FlagGems autotune SQLite 并发建表锁。当前服务
仅在 `docker exec` 边界为原 DB URL 增加 `timeout=1800`，不改精简启动脚本或三方源码。
CPU-only 短/长等待因果复现、DB integrity、两级 spawn 进程内环境继承和 graph c8 均已
验证；正式 c64 新轮证明该 SQLite mitigation 可跨过全量 workload，但暴露了独立的生成
长度耗尽问题。

验证证据：

- tail 专项 4 项、相邻 GLM/graph 49 项，共 53 项通过；包含高 block padded slot 的
  eager/graph replay。
- 无 probe 正常服务完成 11 个 graph shape capture。
- graph c8 冷态 8/8 正确但 17.72 tok/s 未过固定 20 tok/s 门槛，按失败保留；相同配置
  热态复测 8/8、零错误，48.10 tok/s、最大延迟 8.64 秒并通过。
- bounded-wait 服务 graph c8：8/8、零错误，20.54 tok/s、最大延迟 20.35 秒；16/16
  worker、health 和 PPU 采样通过。
- no-padding sparse MLA：旧版 `HQ=4` 负对照报 `Unsupported h_q`；新 FlagGems eager/graph
  最大输出绝对误差 `1.2207e-4`，分支测试 3/3、插件测试 1/1、整模 graph 11/11 和真实请求
  通过；服务 health 200、16/16 worker、容器 restart 0。详见 [021](adaptation/021-flaggems-sparse-small-head-no-padding-20260908.md)。
- 最近一次正式 GPQA 历史包现位于：
  `/mnt/nfs/users/jinghao/glm5.3-flash/05-runs/legacy-accuracy/gpqa-20260906-c64-flaggems-db-timeout`。
  2026-09-06 20:54（UTC+8）启动，runner PID `17741`；198 题、c64、独立空缓存、
  `strict-match >= 0.88`、不允许 timeout。2026-09-07 02:17 结束：正式 strict
  166/198（83.84%），19 题耗尽 30000 tokens 后 `content=None` 并被标为 `<TIMEOUT>`；
  contract/runner 均失败。服务保持健康、16/16 worker、既有故障签名 0。
- 当前提交全量诊断位于
  `/mnt/nfs/users/jinghao/glm5.3-flash/04-runs/glm53-gpqa-full-current-c32-60k-20260910-2125/`：
  198 个唯一题完整，strict 172/198（86.87%）；10 个 `<TIMEOUT>` 均为 60K length cap，
  非 HTTP/RPC 超时。服务全程健康、16/16 worker、容器 restart 0。详见
  [当前提交 GPQA](acceptance/gpqa-current-commits-20260910.md)。

详细记录见 [c64 EngineCore 根因与修复](adaptation/001-graph-c64-enginecore-crash.md)、
[graph sanity](acceptance/graph-sanity-results.md) 和
[正式 GPQA](acceptance/gpqa-full-20260906.md)。结构化环境与服务状态见
[runtime-config.yml](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/runtime-config.yml)。

## Material issues

| 问题 | 诊断与处理 | 当前结论 |
|---|---|---|
| 最新 Hy4 preview 最小重建 | 从 `d56f7b2` 干净 checkout 重新迁移模型必需代码，删除旧基线重复/历史材料 | 服务与 focused regression 通过；见 [020](adaptation/020-hy4-latest-minimal-rebase-20260907.md) |
| TP16 sparse MLA `Unsupported h_q` | 指定 FlagGems 分支以 masked small-head kernel 原生支持 `HQ=4`，已删除插件 BF16 padding | 算子 eager/graph、整模 graph 与真实请求通过；正式性能对照未执行；见 [021](adaptation/021-flaggems-sparse-small-head-no-padding-20260908.md) |
| 远端工作根混有旧顶层目录和脚本 | 按用途无覆盖迁移到 `01-repos`～`08-bugs`，新增规则要求的根级 `start-model.sh` | 顶层仅八个编号目录和最终启动器，真实 graph 拉起及最小推理通过；见 [022](adaptation/022-remote-workspace-numbered-layout-20260908.md) |
| RLock 阻塞 FULL decode，且 FULL+PIECEWISE 静默重复 `!` | 复用 Hy4 的图外 callable 解析；单变量切换为 prefill eager、decode FULL | 无 breakable，7/7 decode FULL、c8×2 共 16/16；见 [023](adaptation/023-full-decode-graph-without-breakable-20260908.md) |
| 早期适配使用错误权重 | 撤销错误快照结论，重新绑定正确 BF16 路径 | 已关闭；见 [016](adaptation/016-withdrawal-20260904.md) |
| 迁移至指定 HY4 基线且改动过多 | 重新审查依赖，保留运行必需代码与正常回归，移除一次性/无效实现 | 已完成；见 [009](adaptation/009-hy4-base-migration-20260904.md)、[010](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/GLM-5.3-Flash-BF16/ppu/environment/history/hy4-glm53-scope-review-20260904.md)、[003](adaptation/003-cleanup-final-20260904.md) |
| 配置/注册、MLA prefill、KPool runner 与参数兼容问题 | 在 plugin 的正常注册和 GLM runtime 路径修复；vLLM 不修改 | 已通过最小服务；见 [002](adaptation/002-bringup-20260904.md)、[005](adaptation/005-fp8-prefix-fix-20260904.md) |
| graph replay 污染 stateful sparse indexer | 历史 workaround 是 breakable eager 边界；本轮证明 decode FULL 可用而 PIECEWISE prefill 组合仍污染 | 008 workaround 已由 023 的 `FULL_DECODE_ONLY` 取代；见 [008](adaptation/008-graph-correctness-fix-20260906.md)、[023](adaptation/023-full-decode-graph-without-breakable-20260908.md) |
| GPQA c64 下 EngineCore 非法访存 | bounds probe 证明 padded physical slot 解码错误；按实际物理页宽修复 tail kernels | 已通过单测、c8 与完整 c64 服务运行；见 [001](adaptation/001-graph-c64-enginecore-crash.md) |
| FlagGems autotune SQLite 锁 | TP16 共享 DB 首次建表竞争；完整 DB URL 增加有界等待，并验证 spawn 继承 | 已通过完整 c64 workload 验证；见 [018](adaptation/018-flaggems-sqlite-autotune-lock-20260906.md) |
| GLM Triton 算子仍在 Plugin | 7 组实现迁入 FlagGems；删除 Plugin `kernels/`；`silu_and_mul_with_clamp` 合入通用 `activation` backend；Plugin 仅保留签名适配和 dispatch | day0 当前 ahead 2 / behind 0；最终 PR 树最新聚焦回归 22/22、TP16 full decode graph 7/7 与真实请求通过；见 [028](adaptation/028-flaggems-kernel-ownership-20260910.md)、[029](adaptation/029-flaggems-dispatch-reclassification-20260910.md) |
| 剩余 6 条模型路径仍走 reference | Qwen/GLM FlagGems 分支隔离；补齐 varlen causal-conv、chunk KDA、pool/tail mapping，复用既有 pack/unpack；Plugin 只增加统一 dispatch 绑定 | FlagGems 11/11、Plugin 9/9、六条 `default.flagos`、TP16 graph 7/7、smoke 通过；见 [031](adaptation/031-flaggems-day0-diverged-sync-blocker-20260910.md) |
| GLM/HY4 row-wise top-k 重复适配 | 抽取通用 prefill/decode capability；HY4 prefill 直接调用共享 capability，decode composite backend 内部复用；二维显式 `seq_lens` flatten 后以 provider `next_n=1` 无损传递 | 22/22 聚焦测试、真实 PPU prefill 集合对照与 decode graph replay、TP16 7/7 capture 和请求 `2`/`5` 通过；HY4 整模未验；见 [030](adaptation/030-shared-rowwise-topk-20260910.md) |
| 19 题长推理耗尽 30000-token 上限 | `finish_reason=length`、reasoning 非空但 content=None；无乱码，一题明确机械重复 | 正式 strict 83.84%，未通过；见 [019](adaptation/019-gpqa-generation-length-exhaustion-20260907.md) |
| 历史 `<TIMEOUT>` 标记 | 旧轮部分请求实际达到 30000 tokens 且 content 为空，不是 HTTP/RPC 计时超时 | 历史结果无效且不复用；见 [007](adaptation/007-gpqa-timeout-marker-diagnosis-20260904.md) |
| FlagGems-vllm KDA 接入 | 曾验证后撤销为当前生产必需路径；库保留 editable 安装但 `kda_integration: withdrawn` | 非当前阻塞；见 [012](adaptation/012-kda-integration-20260904.md) |

## 适配完成后的验收项

- 对当前 10 个 60K length-capped 样本做受控单变量诊断，确定生成配置或数值路径原因；随后使用
  独立正式轮重新核验 198 个唯一题、零 timeout 和 strict-match 88% 门槛。
- 只有 accuracy 通过后才执行正式性能/通信验收、证据汇总与复盘。
- Plugin 与 FlagGems 适配提交均已发布并与容器工作树对齐；FlagGems 已同步到本轮最新官方
  `master@e15b22dc`，后续若 upstream 再次前移，仍需重新评估、同步和验证。
