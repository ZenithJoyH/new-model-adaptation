# MiniCPM-OCR / NVIDIA / vllm-plugin-fl

2026-10-26用户提供的report-2包重新实测：同一GPU4、权重和公共参数，原生交互/批量/较高负载吞吐中位数34.62/67.97/85.49页每分钟，NV-FlagOS为16.47/26.92/29.65。FlagOS批量补测后仍波动16.98%，不作稳定排名；其余场景稳定。两边合计7984请求零失败/空输出/截断，32页官方GT筛查Overall分别97.43446/97.67517。原8012和脚本保持，GPU4/8013已释放，未改组件或阶段状态。详见[当前两环境report-2对比](acceptance/portable-report2-comparison-20261026.md)。

2026-10-26完整v1.1复测：slice黑名单+持久化调优库的交互/批量/较高负载吞吐中位数为16.50/23.66/27.51页每分钟，相对原FlagOS为+15.57%/-0.86%/-2.44%；批量最后两轮仍波动22%，不作稳定排名。4644请求全部成功无截断，同一32页Overall97.63648（原97.63658）。新形状仍产生调优记录，单请求20%改善未转化为批量稳定收益。原8012与脚本保持，临时8013已停，未改源码或阶段状态。详见[完整复测与三方对比](acceptance/slice-blacklist-performance-20261026.md)。

2026-10-26后续缓解：以模型部署配置追加slice黑名单，保留平台默认项。固定213token单请求三轮中位数1.0201→0.8139秒（延迟降低20.22%）；graph/eager各12个六类请求内容及token ID与原参考完全一致，slice数值/alias/graph重放通过。已有调优库的四个真实attention形状跨进程验证无新增benchmark，未知形状仍可能调优。原8012未重启且健康，脚本和安装源码未改；配置供后续启动加载，当前8012未热切换。详见[013后续结果与配置](adaptation/013-performance-profiling.md#后续slice-黑名单与持久化调优缓存)，未重跑完整v1.1性能基准，不升级阶段状态。

2026-10-26 profiling：实际调用栈及无 profiler 算子对照定位到 FlagGems DEBUG 日志/Python 视图主机开销，以及视觉新形状在线调优；同形状 slice 原生3.00µs、FlagGems不记录8.04µs、once记录14.52µs，新形状SDPA首次4.97秒而缓存命中约0.102ms。LM head/GDN GPU计算未显示主要退化。未改产品代码或人工脚本；外部停止后按用户授权恢复两个原容器，原脚本启动的8012健康，隔离8013退出。详见[013诊断与缓存/采样边界](adaptation/013-performance-profiling.md)，不将采样占比当作整套基准差距的精确归因。

2026-10-26原生对比：相同v1.1测试包、权重、GPU4及公共启动参数，原生vLLM三场景吞吐为35.43/72.24/86.38页每分钟，是10月24日FlagOS基线的2.48/3.03/3.06倍；2322个计时请求无失败/截断，输入token逐区域一致。32页官方GT小集Overall原生97.4745、FlagOS97.6366，质量存在小幅差异。原8000/8001/8011/8012与人工脚本保持，独立8013已停止；未改组件或阶段状态。详见[原生与FlagOS对比](acceptance/native-vs-flagos-performance-20261026.md)。

2026-10-24应用性能更新：跨平台固定32页基准v1.1在H100-149单卡BF16/FULL_AND_PIECEWISE完成，完整预热加两轮共7分27秒。交互/日常批量/较高负载吞吐中位数为14.28/23.87/28.20页每分钟，2322个计时请求无失败或截断，三场景均达初始时限目标。32页官方GT小集Overall97.6366（同页历史97.6828）；不等于正式精度或性能验收。原8012及人工启动脚本保持，独立GPU4/8013已停止。详见[便携测试包与首跑结果](acceptance/portable-performance-v1-20261024.md)。

2026-10-23精度更新：用户新启动的GPU3/8012服务，以复现包缓存布局/裁剪、4x和官方OmniDocBench v1.6标注完成1651/1651页。Overall **96.4576705724**（包内参考96.4243326522）；30594个HTTP响应全部200、1个截断保留，公式/表格评分无超时或异常。输入34468文件复核未变，8012进程、脚本及组件保持，收尾health200。详见[8012官方GT精度结果](acceptance/omnidoc-v16-8012-20261023.md)，含分项指标、3页匹配回退和GT/评分环境比较限制；这是原包精度测量，正式FlagEval、性能与阶段状态仍待独立验收。

2026-10-21，H100-149。用户已在 `minicpm-ocr-flagos-public` 自行启动GPU1/8011服务，模型名 `MiniCPM-OCR-FlagOS`，checkpoint为 `/public/flagos/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`。容器完整 `/public` RW，8张H100可见，服务上下文配置262144。

当前 Plugin 已从 a696859b 快进至上游 main `25eddf9a`，保留 OCR 适配，并补充旧 Transformers 能力缺失时的注册隔离。容器与本机11个交付文件完全一致。本机仓库 `/Users/baai/Documents/ChatGPT/vllm-plugin-FL`，交付提交 `06014201f8ea8cd7092a56a945d8fc7998c5a46c`，目标 [support-minicpm-ocr](https://github.com/flagos-day0/vllm-plugin-FL/tree/support-minicpm-ocr)。详见[012：主线同步与源码交付](adaptation/012-upstream-main-and-source-delivery.md)。

新主线最终代码在GPU2/8012隔离验证：处理器62组零差异，28项OCR/已有模型导入测试通过；eager/graph各12请求，token逐项一致，实际FULL286、PIECEWISE6、NONE10。原GPU1/8011再次六请求全部通过，脚本与PID/启动时间不变；未重启该进程或容器，8000保留。8011仍持有更新前已导入的模块，新代码由全新隔离实例验证。人工服务最初六请求见[011](adaptation/011-manual8011-request-checks.md)。

本次不是完整新checkpoint精度或性能验收。旧权重的处理器/eager/graph/OCR结果保留为历史，旧verification已通过人工交回流程退入control.history，当前阶段待复核；结构化状态为environment_ready，不声称原生完整验收通过。

- [最新主线同步、源码交付与验证](adaptation/012-upstream-main-and-source-delivery.md)
- [人工服务六请求结果与原始证据](adaptation/011-manual8011-request-checks.md)
- [完整/public工作容器](adaptation/010-public-directory-mount.md)
- [适配与历史问题索引](adaptation/README.md)
- [原权重验收历史](acceptance/README.md)
- [服务及交付说明](acceptance/adaptation-summary.md)

批准工作根 `/public/flagos/jinghao/MiniCPM-OCR/flagos`。此前人工启动生产实例的观察指纹 `27bd037ae1b9f3d1c1676a49596d3b97230dd4332e296d3eaddb538886b26ea1`（本轮更新源码身份另见012）；最终镜像验证、正式精度/性能和新checkpoint完整验收待安排。Plugin分支已按用户要求提交推送；未创建PR。
