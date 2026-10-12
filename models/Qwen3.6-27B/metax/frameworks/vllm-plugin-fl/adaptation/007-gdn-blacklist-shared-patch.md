# 007：GDN 黑名单回原链路与公共 patch 安装入口

## 元数据

- 状态：`implementation_verified`（正式 acceptance 未开始）
- 首次出现与最后验证时间：2026-09-24
- 模型 / 平台 / Host / 容器：Qwen3.6-27B / MetaX / `mx-58` / `qwen3.6-27B`
- 执行模式与负载：TP2、BF16、GPU0/1、隔离端口 8001；eager 与 graph 短请求
- 源码：editable Plugin `/workspace/vllm-plugin-FL`；vLLM、FlagGems、FlagGems-vLLM 保持只读

## 问题现象与根因

此前 FlagGems 注册函数显式把 `gdn_prefill/gdn_decode` 排除在通用
`use_flaggems_op` 过滤之外，因此 `VLLM_FL_FLAGOS_BLACKLIST=gdn_prefill,gdn_decode`
不能移除其 `default.flagos` 候选。GDN 调用点 hook 又由 FlagGems 的
`register_ops.py` 安装，使调用点接入与某个 backend 的算子注册耦合。
该签名与历史 [006](006-global-flagos-gdn-high-level.md) 的「全平台注册无门槛」
设计一致；此次目标变为保留全平台调用点覆盖，但允许通用黑名单移除 FlagOS
候选并回到原推理链路。其它 troubleshooting 条目未发现匹配签名。

## 修改与职责

- FlagGems 高层 `gdn_prefill/gdn_decode` 与其它算子一样经过
  `use_flaggems_op(op_name)`；无新增环境变量或低层 dispatch。
- 幂等 GDN hook 从 `vllm_fl/dispatch/backends/flaggems/impl/` 移至公共
  `vllm_fl/patches/gdn_linear_attn.py`；`WorkerFL.load_model()` 在模型构建前安装。
  两套 `register_ops.py` 只注册候选，不再安装调用点 patch。
- 有候选时仍通过 `call_op`。MetaX 黑名单后选择 `vendor.metax`，惰性委托
  vLLM/FLA；纯非 speculative packed decode 保留原快速路径。无 vendor 候选的
  平台在 registry 确实为空时调用捕获的原 vLLM 函数；已有候选但不可用或执行
  失败时不静默回退，decode 原位 state 更新仍使用 strict dispatch。
- FA 仍只走既有 `attention_backend`，没有二次注册。vLLM 的
  `ChunkGatedDeltaRule` 支持 prefill CustomOp OOT，完整
  `GatedDeltaNetAttention` 支持 PluggableLayer OOT；单独 prefill OOT 不覆盖
  普通和 packed decode。用户选择保留本轮最小 patch + dispatch 改动。

## 受控验证

| 轮次 | 唯一变量 | 结果 | 原始证据 |
|---|---|---|---|
| 1 | 默认 FlagOS，迁移前 | eager HTTP 200 / 16 token；两 worker 的 prefill、decode 均选 `default.flagos` | `04-runs/gdn-blacklist-flagos-eager-20260924/` |
| 2 | 仅将两个 GDN 名称放入 FlagOS 黑名单，迁移前 | eager HTTP 200 / 16 token；prefill 选 `vendor.metax`，decode 保留原 packed 路径 | `04-runs/gdn-blacklist-blacklist-eager-20260924/` |
| 3 | patch 迁移后的单测 | GDN 聚焦 9/9、全部 dispatch 276/276 通过 | Plugin `tests/unit_tests/dispatch/test_metax_gdn.py` |
| 4 | 最终源码默认 FlagOS | eager、graph 各 HTTP 200 / 16 token；TP0/TP1 的 prefill、decode 均选 `default.flagos` | `04-runs/gdn-blacklist-flagos-{eager,graph}-patch-20260924/` |
| 5 | 仅将两个 GDN 名称放入 FlagOS 黑名单 | eager、graph 各 HTTP 200 / 16 token；TP0/TP1 的 prefill 选 `vendor.metax`，decode 保留原 packed 路径 | `04-runs/gdn-blacklist-blacklist-{eager,graph}-patch-20260924/` |

四组启动脚本同一 SHA-256 `2f9cae58d93e5c8756457c4cbd93421d84e46d25a3d9b6e956320708b24cc523`，
仅在运行参数 `route`、`mode` 上变化；缓存保留开启。顺序均为同一 Host 的隔离
8001 服务，停止前核对 PID、命令、端口和模型名，未同时运行。四组
`service.log` / `completion-response.json` 的 SHA-256 按默认 eager、默认 graph、
黑名单 eager、黑名单 graph 顺序分别为：

| 路由/模式 | service.log | completion-response.json |
|---|---|---|
| FlagOS/eager | `359ea6b0a73f75ba86a8696bae534fe2c21062f88d8d7f689ea4985ad4c62f1a` | `48b47f683e79fc2379cd0eacd43910815bd8954d84063e90ddb092c10b0e543f` |
| FlagOS/graph | `673ee2923be2ee48e48abf7c47f0b589b08a0111dc5f111ec89fc4e652b1846f` | `5d460ef423ed58f0100693e0318f6ba0eb9409b0e0681f1bf20541363139d16c` |
| blacklist/eager | `71e71412a86f03bdcd893bf7f5c208d430c1b76d90c87f758df7795072a58251` | `fa9bb229639bf9c75d60ed8f431ea20fb3652581502625b95a72cd245bd9080b` |
| blacklist/graph | `8992846b5569b89a4132ece5d85c393bd258782a371e658a8f7000334c733fc7` | `8ed3a73fe22db4244811dbd21f70ff3d67e7f754a1c15c0181352640e4c590eb` |

两组 graph 均请求 `FULL`，stock GDN metadata 报 `UNIFORM_BATCH` 后自动调整为
`FULL_DECODE_ONLY`，decode 图 3/3 捕获，短请求完成。黑名单下 packed decode
不经过普通 `gdn_decode` dispatch，因此日志无该选择记录；这是原快速路径而非
漏装 hook。现存 8000 服务和适配容器未停止、重启或移除；结束时 8000 `/health`
返回 200。前轮非最终版本的 graph 进程在用户调整入口要求后停止，不能作为
最终验收证据。

最终部署身份为 Host/容器同路径
`01-environment/deployment-identity-gdn-blacklist-shared-patch-20260924.json`，
SHA-256 `8f24b75565c1ec521581fcc31d181365ef515eb372036dcd886983410fbd5e37`。
Plugin HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa` 未变，tracked diff
SHA-256 `8871947198ded21d3c3c8446193007fd667a2ebde655037ffacc1ca125d7a899`；
两个 untracked 的公共 hook 和聚焦测试 SHA-256 分别为
`023834bea19381b171d787138c5bbd953df5a792629040d35d4231a86507b5b9`、
`c203ba20087fbf556a457e032ee8b57082484dcfb28e35c4bf50bc9944040246`。
`git diff --check` 通过。远端 one-off 编辑、身份与请求脚本均在 `05-tmp/`，
日志/响应在 `04-runs/`；vLLM、FlagGems 和 FlagGems-vLLM 未编辑。
原生 environment 回执为
`01-environment/framework-check-gdn-blacklist-shared-patch-20260924.json`，
SHA-256 `4d03205d529b500109495524b258550cf3e8a159168a91248b47e676bbaad29f`；
远端已验证工具包对 `adaptation --check-only` 的环境前置门槛返回 passed。
本地 `audit-workspace --repository-only` 仍报告一个与本模型无关的
`DeepSeek-V4-Flash/metax` profile revision 错误及 78 条历史警告；
未修改这些不属于当前任务的记录。

## 限制与下一步

本轮仅 MetaX Host 的短请求与 Plugin 单测；非 MetaX 硬件、其它 GDN 模型、
数值精度、chunked/mixed batch、正式准确率与性能均未完成。vLLM 整层 OOT
虽然可用，但需要维护 `_forward_core` 与 packed decode 的控制流，不在这次
最小改动范围。正式第 4 阶段 acceptance 未选择，适配保持 `in_progress`。
本轮只审阅相对 006 的变更：FlagOS 两高层改回通用名单过滤，patch 文件迁移和
WorkerFL 模型加载入口，MetaX vendor 旧路由未改变；PR base 尚未确认，不能声称
完成 PR 范围审阅或跨平台验收。知识库状态：`local-only`。
