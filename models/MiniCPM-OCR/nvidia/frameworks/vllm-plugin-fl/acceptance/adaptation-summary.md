# MiniCPM-OCR 当前全长度/全卡部署

2026-10-26原生对比：相同v1.1测试包、权重、GPU4及公共启动参数，原生vLLM三场景吞吐为35.43/72.24/86.38页每分钟，是10月24日FlagOS基线的2.48/3.03/3.06倍；2322个计时请求无失败/截断，输入token逐区域一致。32页官方GT小集Overall原生97.4745、FlagOS97.6366，质量存在小幅差异。原8000/8001/8011/8012与人工脚本保持，独立8013已停止；未改组件或阶段状态。详见[原生与FlagOS对比](native-vs-flagos-performance-20261026.md)。

2026-10-24应用性能更新：跨平台固定32页基准v1.1在H100-149单卡BF16/FULL_AND_PIECEWISE完成，完整预热加两轮共7分27秒。交互/日常批量/较高负载吞吐中位数为14.28/23.87/28.20页每分钟，2322个计时请求无失败或截断，三场景均达初始时限目标。32页官方GT小集Overall97.6366（同页历史97.6828）；不等于正式精度或性能验收。原8012及人工启动脚本保持，独立GPU4/8013已停止。详见[便携测试包与首跑结果](portable-performance-v1-20261024.md)。

2026-10-23精度更新：用户新启动的GPU3/8012服务，以复现包缓存布局/裁剪、4x和官方OmniDocBench v1.6标注完成1651/1651页。Overall **96.4576705724**（包内参考96.4243326522）；30594个HTTP响应全部200、1个截断保留，公式/表格评分无超时或异常。输入34468文件复核未变，8012进程、脚本及组件保持，收尾health200。详见[8012官方GT精度结果](omnidoc-v16-8012-20261023.md)，含分项指标、3页匹配回退和GT/评分环境比较限制；这是原包精度测量，正式FlagEval、性能与阶段状态仍待独立验收。

2026-10-21源码交付更新：容器内 `/opt/vllm-plugin-FL` 已同步上游 main `25eddf9a`，保留 OCR 适配并增加注册能力守卫。本机提交 `06014201f8ea8cd7092a56a945d8fc7998c5a46c` 已交付到 flagos-day0 的 support-minicpm-ocr 分支。11个交付文件与容器一致；处理器62组零差异，28项单测/导入检查通过；最终GPU2隔离实例 eager/graph各12请求均通过、token一致，实际FULL286/PIECEWISE6/NONE10。原GPU1/8011再次6请求通过，脚本和进程未重启，仍持有之前导入的模块。2469个vLLM安装文件未变。逐文件设计审查、源代码与测试证据、依赖限制见[012](../adaptation/012-upstream-main-and-source-delivery.md)。本段是本轮最新状态，以下保留历史记录；不表示新checkpoint完整阶段验收、正式精度/性能或最终镜像完成。

2026-10-21当前状态：用户已在 `minicpm-ocr-flagos-public` 自行启动新checkpoint的GPU1/8011服务。文本、小图、发票4x/16x、双图和视频六请求均通过，脚本与进程身份前后未变，8000保留。仅为固定样例功能检查，见[011](../adaptation/011-manual8011-request-checks.md)。完整 `/public` RW和8卡可见情况见[010](../adaptation/010-public-directory-mount.md)。以下为2026-10-20原部署历史，不表示新checkpoint的完整验收。

H100-149，当前容器minicpm-ocr-flagos-allgpu，ID30f6c5ba638e01ab066682ffc140d81dbeb648a7d7dca318aab953da5689ec05。8011服务健康200，模型MiniCPM-OCR-FlagOS，主机内API http://127.0.0.1:8011/v1。默认CUDA枚举全部8张H100，服务脚本单独选择GPU0/TP1，不代表TP8。

最大上下文按模型配置设为262144，已完成262143输入+1输出的真实边界请求，超长输入400。eager/graph各15项HF参考token与计数一致，最终原生OCR/视频16项通过。当前PID3699，实例11c57a2dd1067e49212097665cfb411cd0af61679cdf9451e692d3e908d8fcc7；新部署27581af3bea2ad94f559dd65da49bd84420a65ce0dcf8e4412bc253964ef4940已重新绑定验证。长上下文质量与正式精度/性能未测。

TORCH_SDPA参数保留：当前empty vLLM视觉FlashAttention的flash_attn_varlen_func=None，小张量直接复现不可调用错误；SDPA路径对照通过。该参数只选择视觉编码器接口，不替代文本骨干后端或关闭Plugin/FlagGems。详见[008](../adaptation/008-maximum-context-and-all-gpus.md)。

根/public/flagos/jinghao/MiniCPM-OCR/flagos/start-model.sh及新容器内部/opt/minicpm-ocr-flagos/start-model.sh实际启动通过，SHA均066993c36c83080e7d0aeb3fc6c01a1b1c03fcb3b5d10f9888ecdc9e051be5b7。参数保持BF16、长度262144、max-num-seqs64、显存比例0.55、FAP、前缀缓存开启、TORCH_SDPA、FlagGems-vllm开启，日志04-runs/start-model.log，缓存06-cache。产品源码仍740行，两个算子库editable与FlagTree0.7.0保持，没有新产品修改。

新交付配置、补丁、依赖锁、恢复说明位于01-environment/delivery-maxctx及容器内部/opt/minicpm-ocr-flagos。快照镜像minicpm-ocr-flagos:allgpu-snapshot-20261020包含源码依赖，但早于本轮最终脚本/配置，最终镜像尚未验证。原适配容器保留运行；仅在新服务验证通过后切换本任务精确推理进程，其他容器未操作。旧eager/graph、收敛与重连证据保留。没有提交、推送或创建PR。
