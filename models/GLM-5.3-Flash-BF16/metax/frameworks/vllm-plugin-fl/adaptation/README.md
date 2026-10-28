# 适配问题索引

| 问题 | 已核实状态 |
|---|---|
| [001 GLM模型接入](001-glm-model-runtime-gap.md) | 两机81项、同源eager、显式full-and-piecewise及四并发sanity通过，GPQA198运行中 |
| [002 通信图生命周期](002-communication-lifecycle.md) | 单机8卡探针释放graph后正常销毁通信组 |
| [003 卷积shuffle与KDA数值](003-metax-shuffle-toolchain.md) | 两机卷积eager/graph和GLM基础数值回归通过；工具链诊断失败完整保留 |
| [004 双机MCCL接口](004-dual-node-mccl-interface.md) | 正确网卡变量后16卡eager与变输入graph通信通过，实际Socket路径；RDMA未验证 |
| [005 KDA prefill对照](005-kda-prefill-reference.md) | 已核实并修复真实MetaX worker的USE_EXP2协议；两机24项图回归通过，原冷路径差异保留 |
| [006 mHC语义extent](006-mhc-semantic-block.md) | 固定reduction extent移出调优参数后，两机各28项mHC/模型维度graph回归通过 |
| [007 FP8 MQA prefill](007-fp8-mqa-portable.md) | 软件E4M3解码/BF16 dot修复；两机各22项数值与图回归通过 |
| [008 Sparse MLA共享内存](008-sparse-mla-shared-memory.md) | MetaX候选及默认TLE选择修复；两机各28项TOPK80/128/2048、512/576维数值与图回归通过 |
| [009 clone设备注册](009-clone-device-registration.md) | 设备专属Autograd pair修复；两机31项CPU/GPU/layout/梯度/graph回归及原生embedding compile helper通过 |
| [011 稀疏Top-K重复性](011-sparse-topk-reproducibility.md) | 真实同分集合变化已复现；两机各38项可选确定路径和57项GLM接入回归通过，v9整模idle控制通过，跨组差0.039359保留 |
| [012 mHC编译边界](012-mhc-compilation-boundary.md) | mHC和SwiGLU边界修复，受影响局部严格编译和变输入图验证、同源整模eager/graph已通过 |
| [013 MetaX编译产物接口](013-metax-compiled-artifact-api.md) | 两机各四例及独立新进程恢复通过；后续实际整模编译/AOT与显式graph通过 |
| [014 整模型图模式](014-whole-model-graph.md) | 两机81项及v13 eager通过；FULL受MLA/indexer能力限制，显式下一档四请求/16rank数值与重放通过 |
| [015 双机服务取证](015-distributed-service-evidence.md) | 新严格参与节点绑定，本地101项相关回归通过；现场sanity/GPQA绑定通过，sanity取证1426对互逆连接 |

脚本、原始日志和最小复现保留在批准远端根，不保存到本目录。

[源码设计审查](010-source-review.md) 绑定实际安装的Plugin、FlagGems和FlagGems-vllm全部35文件；
阶段3原生gate已通过。正式GPQA、性能与镜像验证的后续结果单独记录。
