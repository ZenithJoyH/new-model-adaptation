# DeepSeek-V4.1-Flash-W8A8-Text / MetaX / vllm-plugin-fl

最新PR整理：两机实际安装树已完成5文件测试/描述/资产路径收尾，13项隔离真实图与集成回归、8项恢复文本sanity通过。[三仓候选补丁、PR正文与逐块索引](../../../../../deliveries/DeepSeek-V4.1-Flash-W8A8-Text/metax/vllm-plugin-fl/README.md)已准备，未提交、推送或创建PR；D3公开固定依赖、H9高精度质量比较及最终构建/CI仍未完成。原64脚本和基础配置已恢复，当前实例`v41-pr-cleanup-restored-v1-20261105`，详见[016](adaptation/016-final-source-review.md)。

当前更新：GPQA strict-match 171/198＝86.3636%达到用户指定的86%门槛。另按要求将序列上限从16改为64，[有界验证通过](acceptance/max-num-seqs64.md)：实测engine running峰值64，148条请求完成，未见请求错误、OOM、抢占或本轮PP+async挂起。现保持64、FULL、TP8/PP2、V2 runner、async ON、prefix ON运行；根级及容器内部脚本SHA-256 `364d18c989f8ce0e5e1406e714eb79cd8586af95487512b6c39aaf9845f9bce9`。旧GPQA结果对应16配置，未在64下重跑完整精度；v22/16原分数保留历史，正式服务契约已按当前64配置重冻结，完整适配状态仍未通过。

2026-11-05，目标 `mx-102`、`mx-103`，指定0.28镜像。完整权重已加载，最终候选v22以FULL、TP8/PP2、async ON运行；8项并发文本sanity及独立审阅已完成。首轮完整GSM8K在742/1319题时因[Q:截断思考](adaptation/017-reasoning-stop-condition.md)产生空最终答案而终止，原证据保留；仅修正冲突停止词的新v2在保留1318份回答后按用户要求将唯一未完成题计错，[独立汇总](acceptance/accuracy-cutoff-summary.md)为1171/1319=88.78%，未达到原95%门槛。正式性能与完整验收尚未完成，公开固定依赖、高精度质量比较和最终源码审查仍待补齐。
按用户后续指令完成[GPQA Diamond 198题、32客户端并发跑分](acceptance/gpqa-c32.md)，服务引擎16序列并排队。用户授权13条异常计错后，[完整分母得分](acceptance/gpqa-score-summary.md)为strict-match 171/198＝86.3636%，flexible-extract 60/198＝30.3030%；暂不处理GSM8K精度问题，不提升正式验收状态。
V4.1文本编码两机35项及真实tokenizer/同步异步renderer的56组参考对照通过。
FlagEval工具及完整GSM8K数据已准备。用户已恢复服务与评测；初始化遇到的
[CPU clone 分发问题](adaptation/013-clone-autograd-dispatch.md)已通过两机切片回归。[输出异常](adaptation/015-output-health-and-pp-async.md)经元数据修复及移除V4.1不需要的head Q RMSNorm后，失败请求已恢复；最终运行时代码下15组FULL、PP2 async ON/OFF对照均正确，此范围内未复现额外异步问题。
两机适配容器 `deepseek-v41-text-plugin028-20261103` 保持运行，批准根均为
`/public-flash/jinghao/deepseekV4.1`。镜像digest、源码和映射见环境分析。

- [环境分析](environment/environment-analysis.md)：实际安装身份；双机16卡MCCL三项0错误。
- [模型接入](adaptation/001-v41-registration-and-contracts.md)：模型注册、真实配置、16 rank构造与流式加载修复；整模最新证据见015。
- [W8A8接入](adaptation/005-w8a8-checkpoint-format.md)：已注册格式并定位修复真实量化/矩阵乘边界问题，未将局部通过作为整模结论。
- [RDMA兼容](adaptation/002-rdma-provider-abi.md)：用户授权的最小provider处理及通信证据。
- [资源竞争](adaptation/003-gpu-resource-contention.md)：按已授权范围处理竞争worker，适配容器保留；受控测量单独核实资源。
- [验收状态](acceptance/README.md)：共享脚本与服务绑定已冻结；末题计错汇总88.78%，低于95%；正式门禁仍未通过。
- [FlagEval工具环境](environment/flageval-tooling.md)：102镜像与CPU评测容器已就绪，原生入口和本地缓存检查通过。
- [English deployment guide](acceptance/deployment-guide.md)：基于当前证据的草稿，推理镜像未打包发布，不能据此宣称新镜像已验证。

不要在这里保存脚本、源码、补丁、JSON 结果、原始日志、缓存或临时文件。
