# PPU-13 适配问题索引

- [001：4.7 注册、MoE 骨干与 canvas M-RoPE](001-minicpm47-moe-canvas.md)：
  模型专用 Plugin 实现已安装，注册与 CPU 位置对照、整模 eager/graph
  最小推理通过；正式验收未开始。
- [002：单图请求产生重复标点](002-visual-garbage.md)：
  TP2 视觉第 7 层及以后数值异常已定位；Plugin 候选在缓存开启的
  eager/graph 下单图正确，graph 双图与两帧视频最小请求也正确。
- [003：视觉 data 模式的 fused QKV 权重加载失败](003-vision-data-qkv-loader.md)：
  模型专属加载阶段修正已解除服务启动阻断；单图 eager 请求正确。
- [004：GDN 阻断 prefill 全量图](004-gdn-full-graph-limit.md)：
  PPU-13 上请求 `FULL` 已复现两个 rank 自动降至 `FULL_DECODE_ONLY`；
  缓存开启的新实例再次复现相同降级，decode 图 4/4 捕获，文本、单图、
  双图和两帧视频最小请求通过；正式执行模式回执待签发。
- [005：前缀缓存生效默认与假设不符](005-prefix-cache-effective-default.md)：
  既有 eager/graph 生效配置均为 `False`；新服务显式开启并已重新测试，
  环境回执已重建，适配与验收回执仍待核验。
- [009：GPQA 后半段输出乱码](009-gpqa-late-run-garbled-output.md)：
  用户新文件严格 88/198；第 97 题起多数回复乱码，旧提取式重计仍为
  88/198。同轮双卡 Worker 在宿主机内核记录 `Xid 1155 / L1 Invalid page`；
  同参数全量诊断未复现，首错算子仍待定位。
- [010：ERQA 同题跨平台答案差异](010-erqa-nv-ptg-accuracy-gap.md)：
  用户提供的两份 400 题文件题目完全一致；公开标注诊断计分
  NV 213/400、PPU 198/400。用 630 张已校验真图复测 PPU
  为 200/400、195/400，当前 H100 8020 同输入复测 195/400；
  历史净差未稳定重现。单题 `ERQA_165` 仍有跨框架偏向差异，
  首个数值分歧和产品根因待验证。
- [011：FlagGems split-KV 修复替代视觉 FP32 缓解](011-flaggems-splitkv-vision-fix.md)：
  已应用 PR #6873 的公共内核修复，旧实现数值失败、新实现 34 项回归通过；
  无 FP32 的完整 35B eager 视觉链 9/9 正确，TP2 图服务 25/25 HTTP 回归正确；
  已移除 helper 和专属测试，前缀缓存显式开启，正式精度仍待验证。
- [012：切换用户的 support-minicpmV4.7 分支并验证](012-user-plugin-branch-validation.md)：
  实际安装目录已固定至 `aa4228e`，工作树干净；保留 FlagGems PR #6873 与原启动配置。
  分支单测 14/14、完整 eager 9/9、TP2 图服务 33/33 HTTP 回归通过，8010 保持运行；
  默认视觉 weights 模式适用，正式 ERQA/GPQA 与性能未复测。
- [013：接入 FlagGems-vllm 的 MoE 与 FlashAttention](013-flaggems-vllm-moe-attention.md)：
  历史方案使用 vendor provider 接入，已由 015 恢复原调度；18 项直接算子检查、
  26 项 Plugin 测试和隔离/主服务各 35 项请求通过。8010 保留运行，两类图各 7/7，
  脚本开启前缀缓存；当前 BF16/head_dim 256 不符合平头哥 INT8 attention 的接口条件。
- [014：算子与 Plugin 调用层端到端性能优化](014-e2e-performance-optimization.md)：
  历史目标 Attention 配置和 MoE 直接 out 方案已由 015 替代，撤回收益不稳定的 MoE tile；
  当时三组提升约 5.7%/82.6%/38.8% 的基线已经切换至新库，不能证明优于原 unified 链路。
  43 项回归与 1 项非因果补充通过，正常 8010 服务重启后 35/35 正确、缓存命中生效；
  性能专用服务已停止，正式精度与验收状态未更新。
- [015：恢复原调度并直接替换 FlagGems-vllm 调用](015-direct-flaggems-vllm-long-context.md)：
  factory、注册、policy、registry 与原 PPU staged MoE 已恢复；只在三处 Plugin 计算接口
  替换库来源，使用既有 attention 开关，无 PER_OP。库内 BF16 paged Flash 复用 GQA
  在线 softmax 内核以修复 mixed 批次计算浪费；66 项回归通过，c64/n128/output1024、
  三轮去首轮后4K/16K/32K吞吐1532.71/594.22/269.62 tok/s，1152/1152请求成功。
  根级脚本启动8010正常服务后35/35定向请求通过，前缀命中4896 tokens；正式验收状态不变。
- [016：长生成的 paged attention 页面地址溢出](016-paged-attention-address-overflow.md)：
  全量 GPQA 的长请求触发 int32 页面偏移回绕；旧安装内核可复现，
  物理页号提升为 int64 后复现解除。随机参考及图重放 4 项通过；
  新轮三项全量精度完成核验，见 [精度记录](../acceptance/accuracy-optimized-20261010.md)；
  正式验收状态不变。
