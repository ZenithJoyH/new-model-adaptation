# 框架适配记录

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

## Flash 优化迁移（2026-10-12）

已将 35B 验证的 FlagGems-vllm paged Flash 优化迁移至实际安装组件，支持
1B 的 H8/HKV2/D256、block288，并同步 int64 页偏移修复。66 项相关回归通过；
正常缓存、FULL_AND_PIECEWISE 下 12 项实际文本/图片检查正确，确认真实 helper 命中。
当前现用启动脚本已启用已有 attention 开关，API538632 / 8000端口 / GPU2
健康200，两类图各51/51；用户性能配置的缓存关闭参数保留。
算子 prefill/mixed 对照约1.85–2.20倍，不能视为整模端到端收益。
正式数据集精度和优化后整模性能未重跑，framework.yml 与正式验收状态不变。
配置、源码、测试、结果、限制及当前服务身份见
[问题008](adaptation/008-flaggems-vllm-flash-attention.md)。下文其他服务 PID 均为历史记录。

本目录只保存当前模型、平台和 framework profile 的精简记录。框架定义见 `framework.yml`
引用的仓库级 profile；远端运行产物仍保存在该框架独立的已批准工作根目录。

- `environment/`：框架、容器、组件、Host 和平台环境分析。
- `adaptation/`：仅保存编号问题记录及解决结论。
- `acceptance/`：仅保存验收计划、结果、总结和复盘。

不要在这里保存脚本、源码、补丁、JSON 结果、原始日志、缓存或临时文件。

## 当前诊断结论（2026-10-03）

**最新接续入口：[双索引写入黑名单 700 题报告](acceptance/mmlu-pro-dualindex-limit50-20261003.md)**。按用户要求，根 `start-model.sh` 已改为黑名单 `nonzero_numpy,index,index_put_,_index_put_impl_`，去掉原 whitelist，并从脚本启动无 int64 诊断挂钩的新实例。MMLU-Pro 14 科各 50 题全部完成，使用已确认的最终答案提取规则，**331/700（47.29%）、0 超时、12 条无效提取**。全部题目和提示哈希与此前基线一致；相同提取规则的上一轮为 313/700（44.71%）。本轮未复现跨请求持续乱码，700 条后的独立短题正常。

23:55 核验服务 API PID `362280` / 启动 tick `375624965`，PPU2、8000 端口、`/health=200`、running/waiting 均为 0。**当前服务与根脚本配置一致**；脚本 SHA-256 `5c84a8206a0d5f6e7895887180a293ba4c7b30c7c4f1b4c4635f1a16d9b405d2`。保留前缀缓存、默认服务上下文 `262144` 和 `FULL_AND_PIECEWISE`；32768 仅是客户端最大新生成 token。双黑名单作为当前已验证缓解保留运行，容器未重启，产品源码未修改。原始结果和最终摘要路径见报告；正式 GPQA、图级别及性能/summary 状态未改变，整体仍为 `functional`。

## 此前诊断与 17:48 交接快照（历史状态）

**新会话接续入口：[问题 007 的交接快照](adaptation/007-long-accuracy-output-corruption.md)**（文末“接续定位快照”一节）。该节汇总视觉数值异常、GPQA 严格提取/截断/超时、MMLU 正则差异、index 非法页崩溃、长负载乱码的现象与证据边界，并列出截至 2026-10-03 17:48（Asia/Shanghai）的服务身份、远端产物与哈希、未完成工作。2026-10-08 的视觉续查见下段；本次未刷新 007 的服务身份或精度回执。

**视觉问题最新结论（2026-10-08）：** [问题 002](adaptation/002-visual-output-corruption.md) 已定位并修复实际安装 FlagGems 的 `flash_fwd_splitkv_combine_kernel` 输出布局/步幅错误。无权重最小复现确认连续 BSHD 漏写及逻辑输出外哨兵改写；修复后 34 项布局、数值和算子 graph 回归通过，真实蓝图第 7 层 Q/K/V 三次对照均有限、最大误差 0.008706。已提交关联的 [Issue #6872](https://github.com/flagos-ai/FlagGems/issues/6872) / [PR #6873](https://github.com/flagos-ai/FlagGems/pull/6873)，最新提交 `c13d2aba866e46b235a7bcae88a68e7ec2090e04` 的已启用 CI 均通过。按用户要求已移除 Plugin FP32 mm encoder 实现、专用测试及 OOT 注册，实际原生类/BF16/FlagGems flash 调用确认；离线 7/7 正确、162 次 attention 无非有限值。PPU2 按原启动脚本重启，FULL_AND_PIECEWISE 的混合 PIECEWISE/decode FULL 各捕获 51/51；服务 25/25 文本/单图/双图请求通过，含两轮 10 并发。该撤除轮 API PID `425141` 为历史实例，后续统一分支部署见下段；保留此次移除。启动参数与 index 黑名单未改，视觉 encoder 本身未启用编译/捕图，正式精度、性能、长负载及镜像打包仍未验证。该修复不替代 007 的 GDN 索引问题定位。

**统一 Plugin 当前部署（2026-10-08）：** 已按用户要求将容器实际安装 checkout 切换到 [support-minicpmV4.7@aa4228e](https://github.com/flagos-day0/vllm-plugin-FL/commit/aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68)，工作树干净，旧适配完整备份。14 项单测、4 项真实 checkpoint canvas 对照、5 项 BF16 离线视觉（135 次 attention 均有限）通过；原脚本 FULL_AND_PIECEWISE 服务两类图各捕获 51/51，35/35 请求通过，包含竖图、1200×900 红蓝红切片、双帧视频及两轮 10 并发。当前 API PID `445525` / start tick `416200430`、端口 8000、健康检查 200，服务与容器保持运行。vLLM、FlagGems 修复和启动参数未改，无 FP32 专用 attention。正式精度、性能、长负载及镜像验证未执行；详见 [001 的统一分支切换与基础验证](adaptation/001-model-registration-canvas-mrope.md)。

用户要求的 `FULL_AND_PIECEWISE` 服务在 32 并发 MMLU-Pro 长生成后可出现跨请求持续乱码。已独立确认 FlagGems `index_put_` / `_index_put_impl_` 共享内核在 int32 索引的大偏移地址乘加中溢出：紧凑 FP32 用例索引 8192 起写错位置，原生 PyTorch int32 和 FlagGems int64 正常。实际 GDN 状态为 **BF16** `[23275,16,128,128]`，stride0 `294912`，槽号 7281 的尾部即开始跨界；已捕获 int32 槽号 7415、9108 的真实调用。只在诊断进程中扩展索引为 int64 后，**400/400 长请求返回、8 次批后短题均正常**；相同黑名单的未扩展对照在 300 题后乱码。这形成具体算子缺陷与模型现象的受控证据，2026-10-08 已修复实际安装 FlagGems 共享写入内核：完整独立对照修复前 8 个 int32 用例失败、8 个 int64 对照通过，修复后 16/16 通过，含真实 BF16 步幅和图重放。已更新同根因的 [Issue #6411](https://github.com/flagos-ai/FlagGems/issues/6411) / [PR #6413](https://github.com/flagos-ai/FlagGems/pull/6413)，提交 `330dd99d5c661f4d6a9745b68c5dd1e30773210a`；服务黑名单未改，重启启用后的长负载及正式精度仍待验证，完整 checkout 测试受安装包缺少 `cli_override` 阻塞。详见 [问题 007](adaptation/007-long-accuracy-output-corruption.md)。

此前 `VLLM_FL_FLAGOS_WHITELIST=attention_backend` 的全部 Aten 关闭缓解完成原生 14 科各 50 题，267/700（38.14%）、0 超时，700 条后短题仍连贯。全关结果见 [完整诊断报告](acceptance/mmlu-pro-atenoff-limit50-20261003.md)。

随后按用户提供的 `final-answer-extract` 正则（最后一次匹配）对同一批 700 条响应重计分，得分 **313/700（44.71%）**，无效提取 **10** 条；原提取规则为 267/700、119 条无效。未重新生成模型输出，原始证据保持不变；逐科对照和派生文件哈希在上述完整报告中。

Host `PPU-13` / 容器 `minicpmV4.7-1B` 同路径启动脚本 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/start-model.sh` 仍为全部 Aten 关闭缓解，2026-10-03 已验证映射、语法、真实启动和短题，SHA-256 `baee3f4658befa9598b81104d5c30fcd51601cefb2b5be5b6e1e428e7da219f9`。**当前运行的服务不是该脚本配置**：API PID `358882`（启动 tick `373529528`）/ EngineCore `359391`，物理 PPU2、8000 端口，黑名单 `nonzero_numpy,index,_index_put_impl_`，额外加载进程内 int64 诊断挂钩。17:48 核对 `/health=200`、running/waiting 为 0，400 请求 controller 已结束；日志在 `04-runs/mmlu-corruption-int64-service-20261003/`。后续恢复根脚本会切回全部 Aten 关闭配置，必须先核对当前进程；不得直接重复启动占用同一端口的服务。适配容器未重启，服务保留默认上下文 `262144`，32768 仅在客户端设置。正式 GPQA、图级别及性能/summary 的验收限制未改变，整体仍为 `functional`。

## 历史结论（2026-10-01）

`PPU-13` 的 `minicpmV4.7-1B` 容器已在 PPU2 完成模型加载、多模态最小推理、`eager` 与 `decode-full` 图模式验证；固定 10 并发科学题全部答对。完整 `full` 图尝试因 GDN 的 `UNIFORM_BATCH` 限制未达到 prefill 全图，阻塞证据见 [执行模式](acceptance/execution-mode.md)。Plugin 适配差异和验证见 [适配索引](adaptation/README.md)，vLLM、FlagGems 仍保持只读。

正式 GPQA Diamond 198 题首次运行的严格匹配得分 `0.197`，低于冻结门槛 `0.25`，故 [精度验收](acceptance/accuracy.md) 失败；样本存在长输出截断、严格解析无效和终态超时，原因分解仍待受控验证，见 [问题 004](adaptation/004-gpqa-strict-accuracy.md)。用户曾要求暂停该轮重测；2026-10-01 又进行了另一轮精度负载，其故障请求 `max_tokens=28000` 与前次冻结方案不同，完整评测配置未核对，见 [问题 006](adaptation/006-gdn-index-invalid-page-under-accuracy-load.md)。

按用户要求，普通服务在 PPU2 使用显式 `FULL_AND_PIECEWISE`：mixed prefill-decode 捕获 PIECEWISE 11/11、decode FULL 7/7，正常前缀缓存开启。v2 [启动脚本](acceptance/launcher-precheck.md)已实际启动服务，健康检查、最小文本与 224 像素图片请求通过；未运行精度测试。省略前缀缓存参数会改变有效服务配置，受控修正见 [问题 005](adaptation/005-piecewise-service-prefix-cache.md)。

按用户进一步要求，先前已将缓存改为容器默认位置并验证新根目录脚本；用户随后亲自修改该脚本，改为 `nohup vllm serve`、端口 `8000`，并省略上下文长度及并发上限。2026-10-01 已核对旧服务身份、请求空闲和新端口后精确停止 PID `216706`，直接从当时脚本启动 API PID `246468`。当时 `/health=200`，文本与图片不计分连通性均通过；缓存位于容器默认 `/root/.cache/vllm/torch_compile_cache/`。当时脚本 SHA-256 为 `b8248ed0dcf1775b0e6840713568bc4e693c1287b0e47a850d1269b996b992a7`，映射、权限、语法和真实启动均已验证，详见 [启动脚本验证](acceptance/launcher-precheck.md)。有效最大上下文为 `262144`，图捕获 `51+51` 个，初始化约 474 秒；PPU2 占用 `94283/98304 MiB`，资源余量有限。脚本日志位于工作根 `service.log`，尚未遵守项目 `04-runs/` 约定。

用户之后再次修改同一路径脚本，当前 SHA-256 `0bb6618fa01fe65536fea9c407dca9c92b85d737325d6fb62af069ee418c0f12`。其后一次精度负载中，16:45:22 PPU 首报 `invalid page`，EngineCore 报非法显存访问并退出，API `8000` 不再监听；当前服务未恢复。只读定位见 [问题 006](adaptation/006-gdn-index-invalid-page-under-accuracy-load.md)。此前低负载启动检查不能代替该长时 32 并发场景的稳定性验证，也不改变正式精度失败及后续验收状态。

正式 execution-mode 与 sanity 回执属于此前 `decode-full` 实例，不能用当前 PIECEWISE 服务替代。当前混合图不满足 profile 的正式 `full` 或 `decode-full` 图级别；性能与最终 summary 未通过，整体仍为 `functional`，不能标为 `optimized`。待用户恢复正式精度工作，先按 profile 重新核对图级别、前置身份和冻结方案，再依序处理精度及后续步骤。
