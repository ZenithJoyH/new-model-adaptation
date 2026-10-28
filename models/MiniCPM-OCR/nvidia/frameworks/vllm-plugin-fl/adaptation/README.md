# MiniCPM-OCR FlagOS 适配问题索引

当前人工服务与六请求结果见[011](011-manual8011-request-checks.md)。2026-10-20的源码收敛、处理器和eager/graph验收属于原权重历史，不能视为2026-10-21新checkpoint的完整验收。源码实现历史见[006](006-source-install-and-convergence.md)。

- [001：OCR模型与处理器注册](001-ocr-plugin-registration.md)：初次接入历史。
- [002：empty构建、GPU编号及挂载](002-empty-build-and-device-mapping.md)：原始问题与恢复历史。
- [003：FlagGems广播mask](003-attention-mask-broadcast.md)：已验证修复，当前迁回实际源码并重新验证。
- [004：graph能力与最终服务](004-graph-and-service.md)：原始FULL限制与服务记录。
- [005：追加FlagTree](005-flagtree-installation.md)：此前编译器切换的固定证据。
- [006：源码安装与代码收敛](006-source-install-and-convergence.md)：当前源码路径、逐文件设计审查及新结果。

完整补丁及恢复材料存放在远端01-environment/delivery-source和容器内部/opt/minicpm-ocr-flagos。未提交、推送或创建PR，正式精度/性能和最终镜像另安排。

- [007：复用图像预处理与占位符生成](007-reuse-preprocessing-and-prompt-updates.md)：保持文件边界，生产代码825→740；62项处理器零差异及eager/graph/OCR复验。

- [008：模型完整上下文与全卡可见部署](008-maximum-context-and-all-gpus.md)：262144边界实测、8卡可见，TP1服务及视觉SDPA依据。

- [009：TORCH_SDPA实际调用证据](009-torch-sdpa-runtime-evidence.md)：完整OCR请求中34次vLLM视觉SDPA包装调用、共61次SDPA，均关联到FlagGems forward及GPU `_attn_fwd`；生产服务保持在线。

- [010：完整/public工作容器](010-public-directory-mount.md)：新增minicpm-ocr-flagos-public，整目录RW及8卡可见；保留人工脚本与原8011服务，新checkpoint未切换。

- [011：人工8011服务六请求检查](011-manual8011-request-checks.md)：用户GPU1服务，文本/4x/16x/双图/视频6项均匹配预期，脚本与服务进程未改动。

- [012：主线同步与源码交付](012-upstream-main-and-source-delivery.md)：最新main加OCR适配，本机独立仓库、fork分支提交，处理器零差异和新进程eager/graph复验，原8011保留。

- [013：性能差距的实际调用与耗时](013-performance-profiling.md)：定位日志/Python视图主机开销及视觉新形状在线autotuning；后续部署级slice排除使固定单请求延迟降低20.22%，eager/graph各12请求参考一致，四个已知attention形状调优库跨进程复用通过。含原始调用、缓存边界和配置路径；未改源码或脚本，原8012保留。
