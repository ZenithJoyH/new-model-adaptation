# MiniCPM-OCR 全长度/全卡容器功能验证

2026-10-26 report-2新包两方重跑：原生交互/批量/较高负载34.62/67.97/85.49页每分钟，NV-FlagOS为16.47/26.92/29.65；FlagOS批量不稳定，其余场景稳定。7984请求零失败/空输出/截断，两边32页Overall分别97.43446/97.67517。原8012和人工脚本未变，临时8013已退出，不推进正式状态。见[最新包与当前两环境结果](portable-report2-comparison-20261026.md)。

2026-10-26当前配置复测：slice黑名单+持久化调优库，完整32页v1.1三场景各补测一轮。吞吐16.50/23.66/27.51页每分钟；仅交互相对原FlagOS有稳定改善，批量不稳定、较高负载未见提升。4644请求零失败/截断，32页Overall97.63648。保留8012和原脚本，不推进正式状态。见[完整性能复测](slice-blacklist-performance-20261026.md)。

2026-10-26原生对比：相同v1.1测试包、权重、GPU4及公共启动参数，原生vLLM三场景吞吐为35.43/72.24/86.38页每分钟，是10月24日FlagOS基线的2.48/3.03/3.06倍；2322个计时请求无失败/截断，输入token逐区域一致。32页官方GT小集Overall原生97.4745、FlagOS97.6366，质量存在小幅差异。原8000/8001/8011/8012与人工脚本保持，独立8013已停止；未改组件或阶段状态。详见[原生与FlagOS对比](native-vs-flagos-performance-20261026.md)。

2026-10-24应用性能更新：跨平台固定32页基准v1.1在H100-149单卡BF16/FULL_AND_PIECEWISE完成，完整预热加两轮共7分27秒。交互/日常批量/较高负载吞吐中位数为14.28/23.87/28.20页每分钟，2322个计时请求无失败或截断，三场景均达初始时限目标。32页官方GT小集Overall97.6366（同页历史97.6828）；不等于正式精度或性能验收。原8012及人工启动脚本保持，独立GPU4/8013已停止。详见[便携测试包与首跑结果](portable-performance-v1-20261024.md)。

2026-10-23精度更新：用户新启动的GPU3/8012服务，以复现包缓存布局/裁剪、4x和官方OmniDocBench v1.6标注完成1651/1651页。Overall **96.4576705724**（包内参考96.4243326522）；30594个HTTP响应全部200、1个截断保留，公式/表格评分无超时或异常。输入34468文件复核未变，8012进程、脚本及组件保持，收尾health200。详见[8012官方GT精度结果](omnidoc-v16-8012-20261023.md)，含分项指标、3页匹配回退和GT/评分环境比较限制；这是原包精度测量，正式FlagEval、性能与阶段状态仍待独立验收。

2026-10-20，H100-149，minicpm-ocr-flagos-allgpu，配置max-model-len262144。容器默认枚举8张H100，生产服务GPU0/TP1/FULL_AND_PIECEWISE、前缀缓存开启。

| 本轮验证 | 结论 | 远端工作根下证据 |
| --- | --- | --- |
| GPU映射 | 8张CUDA设备及UUID与宿主一致 | maxctx-allgpu-20261020/device-visibility.json、new-container.json |
| eager | 15/15生成token、文本与计数精确匹配HF参考 | 04-runs/maxctx-eager-reference-20261020/results.json |
| graph | 15/15同参考，FULL限制重查，实际FAP捕获/运行 | maxctx-full-20261020/service.log、maxctx-graph-reference-20261020/results.json |
| 长度边界 | 262143输入+1输出，总262144；超长输入返回400 | maxctx-allgpu-20261020/long-context-result.json、overflow-rejection.json |
| 最终服务sanity | 原生16/16通过，其中15项HF token复核，视频独立native参考 | 04-runs/maxctx-sanity-20261020/sanity-result.json、token-comparison.json |
| 视觉后端诊断 | FlashAttention callable=None直接失败，SDPA路径对照通过 | maxctx-allgpu-20261020/mm-backend-probe.json |
| 环境/源码 | 13个产品文件、算子库完整清单、vLLM2449文件、权重及FlagTree保持 | installed-identity-maxctx-20261020.json、source-review.json |

表中简写run目录均在04-runs下，安装身份在01-environment。最终PID3699，新实例11c57a2dd1067e49212097665cfb411cd0af61679cdf9451e692d3e908d8fcc7，observer已核实8011监听，health200。部署27581af3bea2ad94f559dd65da49bd84420a65ce0dcf8e4412bc253964ef4940。图捕获19批piecewise和11个full-decode，运行计数{'FULL': 230, 'PIECEWISE': 4, 'NONE': 45}；部分prefill为NONE，不能声称FULL覆盖全部。

源实现保持740行，前轮62项处理器零差异及36项聚焦测试为源码未变的历史验证，本轮未重复。HF参考SHA ed317a7e717c72d48987e5f7d6e555259b4d28609860c584260788e7240db360；token一致不是logit精度。初次临时端口配置错误已保留失败并修正，不充当通过。

正式精度/性能、长上下文质量、TP8、64路峰值并发及最终镜像未验证；额外无卡导入限制及依赖提示保留。详见[008](../adaptation/008-maximum-context-and-all-gpus.md)与[交付说明](adaptation-summary.md)。
