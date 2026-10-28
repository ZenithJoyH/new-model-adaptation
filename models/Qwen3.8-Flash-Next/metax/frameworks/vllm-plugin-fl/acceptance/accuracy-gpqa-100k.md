# GPQA Diamond full198正式精度验收

mx-101 / qwen3.8-flash；BF16文本TP8，100K上下文，显式FULL_AND_PIECEWISE，prefix caching开启，qwen3 parser。

按全部198题、超时计错的严格指标exact_match,strict-match=0.9242424242424242，183/198正确，达到预先约定≥0.88（至少175题）。原生runner完整结束，198题、396条过滤器记录原样保留；不丢弃超时或错题，不使用重试或挑选子集。原生timeout为1题，均计错并保留在198分母中；详细信息以原生acceptance-result及samples为准。

冻结配置SHA256 6d831a4d81837c44d89cebf620c846102e5a8d675290e35851b87d2be6e65b64；temperature1/top_p0.95/top_k20、xhigh thinking，单题生成上限96000，客户端并发2，timeout21600秒，API/eval retries均0。服务实际观察到2路运行；评测器镜像sha256:1396e5d63553530425db81ebf9a724aa98dc2e11aaf2e677c908f991a9cb7ce3，任务与数据集来源冻结。

原生报告 04-runs/Qwen3.8-Flash-Next-MetaX-BF16-100k/gpqa-full198-c2-100k-20261024/acceptance-result.json SHA256 0ced76db562f76bda80d225152c8f91dabdfe1d5b92995b4fe4b08ebaebe5a71。数据集输入最大2933，98933总预算≤100000。先前C8轮的中途分数显示器因空legacy dataset_path初始化失败，正式评分器和输入未修改；新C2关闭可选显示器，另用官方任务的实际模板/括号目标建立只读strict观察；该观察不作为正式通过证据。原生results显示0.9289340101522843，其聚合排除了1题timeout，未作为本次全198题指标。正式结论使用原样保留的198条strict逐题计分（timeout为0），以完整198为分母，并与至少175题正确的标准同时校验；对应all198-criterion-verification.json及原生绑定回执一并保留。

本结论仅精度；性能按用户选择仅测量报告，未判定业务达标或optimized。
