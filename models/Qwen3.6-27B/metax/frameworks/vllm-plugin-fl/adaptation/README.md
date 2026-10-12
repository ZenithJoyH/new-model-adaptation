# 适配问题索引

- [001：FlagOS dispatch 接入 FlagGems-vLLM Flash Attention 与 GDN](001-flagos-flaggems-vllm-attention-gdn.md)
- [002：纠正 FlagOS 所有权与 Flash Attention 重复分发](002-correct-flagos-ownership.md)
- [003：移除 FlagGems-vLLM 导出探测](003-remove-fgv-export-probes.md)
- [004：移除 FlagOS attention 注册门控和 GDN 环境变量](004-remove-flagos-registration-gates.md)
- [005：MetaX GDN 的 vendor / FlagOS 双路由](005-dual-route-metax-gdn.md)
- [006：GDN 仅以高层算子进入全平台 FlagOS dispatch](006-global-flagos-gdn-high-level.md)
- [007：GDN 黑名单回原链路与公共 patch 安装入口](007-gdn-blacklist-shared-patch.md)
- [008：FULL_AND_PIECEWISE 旧编译缓存形状失配](008-fa-full-piecewise-shape.md)
- [009：FlagOS GDN 非连续分页状态写回错误](009-gdn-paged-state-stride.md)
- [010：已取消的GDN decode优化计划](010-fla-paged-recurrent-optimization.md)
- [011：MetaX Flash Attention GQA decode Split-KV](011-flash-attention-splitkv.md)
- [012：适配镜像保存与 mx-59 容器交付](012-image-delivery-mx59.md)
- [013：mx-57 容器交付](013-image-delivery-mx57.md)
- [014：mx-59 补齐 MetaX 连续 KV 单请求 prefill 优化](014-metax-contiguous-prefill-mx59.md)
- [015：mx-59 排序算子与 Plugin 调度吞吐优化](015-mx59-sort-dispatch-throughput.md)
- [016：mx-59 sortopt 剩余差距与紧凑排序索引](016-mx59-sort-compact-payload.md)
- [017：mx-59 白名单过滤 KV-cache 唯一实现导致启动失败](017-mx59-whitelist-kv-cache-missing.md)
- [018：mx-59 更新兼容 Plugin 分支并恢复原生 KV-cache](018-mx59-plugin-compatible-release-upgrade.md)

018更新mx-59已安装Plugin至官方release/0.2@8b059122，兼容当前vLLM0.20.2。
MetaX vendor FA恢复mcoplib原生KV写入，保留已有GDN/attention/prefill/ready-PID适配。
280项dispatch及8组实际GPU cache eager/图重放验证通过；TP2 FULL_AND_PIECEWISE
mixed/decode捕获均11/11，4条短请求正确。临时18001服务已释放，容器仍运行。
FG/vLLM和共享launcher未改，未进行正式验收或重新打包镜像；最新现场身份见018。

017为升级前只读诊断GPU2/3、8001启动：白名单未包含 `reshape_and_cache_flash`，
且当前dispatch无vendor/reference替代候选，图预热时报注册列表为空，模型服务退出。
容器仍运行；未改脚本/源码、重启或清理缓存。追加白名单为待验证workaround，
不能宣称所有白名单外算子已有原生回退；后续修复与验证见018。

016在mx-59当前容器、固定7599dd13继续优化公共sort中间索引载荷，小batch保留原路径。
60项数值/索引/图回放回归通过；当前8192批处理设置，同配置4K/1K/并发64，
三轮跳过首轮，总吞吐2717.51 -> 2758.78 tok/s（+1.52%），中位ITL下降2.39%，
平均TTFT基本持平。当轮容器/服务保持运行，未改Plugin/vLLM/黑名单/共享launcher，
未重测16K/64K、正式精度或重新打包镜像。016为当轮身份；后续Plugin更新见018。

015此前在同一容器中优化公共FlagGems排序直方图与Plugin ready-PID初始化检查。
排序51项、dispatch280项回归通过；同配置4K输入/1K输出/并发64，三轮跳过首轮，
总吞吐2419.18 -> 2742.15 tok/s（+13.35%），平均TTFT增加5.01%。服务8002保持运行，
未改黑名单/图模式/vLLM/共享launcher，未跑16K/64K、正式精度或重新打包镜像。
015为其当轮身份，不将011/012旧镜像身份套用于已变更的容器安装。

014仅在mx-59当前 `qwen3.6-27B` 中迁移base的vendor prefill连续KV分支，
默认关闭，使用原 `VLLM020_CONTIGUOUS_SINGLE_PREFILL` 开关。23项GPU数值/guard/mixed
及decode图变输入replay回归通过；未重启服务、改共享脚本、重测性能或重新打包镜像。
014当时的现场组件身份以014为准；后续身份及测量见015/016。

013在mx-57复用012归档启动 `qwen3.6-27B`，完整读写挂载 `/public-flash`，
默认GPU `4,5`；镜像/源码身份、组件导入、设备及两项FA eager/graph回归通过。
mx-57驱动为3.3.12；本轮未启动模型服务或执行全模型验收，不扩大正式适配结论。

012已将011后的当前容器保存为 `flagos/qwen3.6-27b-metax:adapted-20261008`，
在mx-59启动同名容器；镜像身份/关键文件、组件导入、设备及两项FA eager/graph回归通过。
未启动mx-59模型服务，未扩大模型或正式验收结论；mx-58原容器保持运行。
随后按用户要求，mx-59同名容器已改为完整读写挂载 `/public-flash`，保留权重只读别名；
新旧组件身份/关键文件一致，导入和设备smoke通过。旧容器改名
`qwen3.6-27B-before-public-flash-20261008` 并保持运行，已有终端需重新进入新容器。

011按用户最新范围只优化FA：FGV MetaX BM16/BN16 Split-KV及partial stride修复，
78+4项算子回归通过，B64/K4096同卡算子基准4.81x；未重启服务或执行全模型/正式验收。
最新FGV源码身份以011为准，Plugin/GDN本轮未修改。下面009相关结果为历史模型验证。

当前源码身份及数值修复以 [009](009-gdn-paged-state-stride.md) 为准；007为继承基线。默认
`gdn_prefill/gdn_decode` 经通用 FlagOS 名单过滤后选择 FlagGems-vLLM；将两者加入
`VLLM_FL_FLAGOS_BLACKLIST` 后，MetaX prefill 选 `vendor.metax` 原 vLLM/FLA，
decode 保留原 packed 快路径。GDN 调用点 hook 位于公共 `vllm_fl/patches/`，
由 WorkerFL 在模型构建前安装，不再依赖 FlagGems/vendor 注册函数。FA 仍只经已有
`attention_backend` 接入，低层 GDN kernel 不单独 dispatch，无 GDN 专属开关。
007只核对HTTP 200/非空文本，不能证明其默认GDN数值正确，009已发现并纠正该问题。
修复后graph使用`FULL_AND_PIECEWISE`，mixed51/51和decode FULL35/35捕获完成，
8条文本与vendor黑名单对照完全一致；GPU数值/图重放6/6、dispatch单测276/276。
原8000服务和容器未中断。历史环境身份未覆盖本次source diff，不用于正式验收。
非 MetaX 硬件、其它模型、正式准确率与
性能未验收；第 4 阶段未选择，适配保持 `in_progress`。历史适配原始产物在 `mx-58`
批准工作根；后续容器部署证据见012/013的逐Host记录。
