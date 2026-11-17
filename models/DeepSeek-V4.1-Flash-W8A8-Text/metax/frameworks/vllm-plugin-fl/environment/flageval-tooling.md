# FlagEval工具环境

2026-11-04，按用户安排先完成评测工具准备，之后用户已恢复模型启动和评测。
此记录只证明工具和数据环境，不构成整模型、精度或性能验收；冻结评测配置与服务预检仍待完成。

- Host：`mx-102`。
- 镜像：`harbor.baai.ac.cn/flageval/flageval-llmeval:v1`，linux/amd64，约4.37GB。
- 实际镜像ID及RepoDigest：`sha256:1396e5d63553530425db81ebf9a724aa98dc2e11aaf2e677c908f991a9cb7ce3`。
- CPU评测容器：`deepseek-v41-flageval-20261104`，ID
  `d483e8a98db40ba5532a95054c0c3506f8f0e79c94189a4a5e19fe26a227ce18`，保持Running。
  无GPU device/request，非privileged；host network供后续访问本机模型API。
- 批准工作根：`/public-flash/jinghao/deepseekV4.1`。该容器只读挂载根下`03-acceptance`，
  读写挂载`04-runs`；`06-cache`位于容器私有overlay，没有绑定共享NFS。
- 响应缓存：容器内`06-cache/flageval-response-cache`，SQLite WAL写入、提交及读取检查通过。
  该缓存依赖保留本评测容器；原始结果保存在挂载的`04-runs`。

实际解释器为`/usr/local/bin/python3`，Python3.10.20；lm_eval0.4.8、datasets4.8.5、
Transformers4.57.6、Torch2.12.0+cpu及requests/aiohttp/tenacity/tqdm/sqlitedict导入通过。
真实`openai-chat-completions`客户端构造与thinking/effort请求体生成通过，未发送模型请求。
该版本客户端使用requests/aiohttp，不依赖openai SDK；首轮探针误将SDK列为必需项的失败保留，
核对实际客户端依赖后修正探针，未安装无关依赖或修改镜像内第三方源码。

`gsm8k_cot_zeroshot`、`gsm8k`、`ifeval`、`gpqa_diamond_generative_cot`任务配置可发现，
尚未据此声称数据集已缓存或完整性已通过。原生三个入口文件部署在
`03-acceptance/native-flageval-runner-20261104/`，`llmrun.py --help`通过；文件清单SHA-256
为`78cfffbad56c8fe4cf983cf004f2ecefcd23fcd5b66feaf47dab3370617f3425`。

完整工具检查：`04-runs/mx-102/flageval-tooling-prep-v2-20261104.json`，SHA-256
`d6ede72eddb04ba64c5f38d5ee4beb082f34f339e30775715fb4209f0e602b31`。
容器身份：`02-issues/mx-102/flageval-tooling-prep-v1-20261104/container.json`，SHA-256
`58fe8139afc8f9d2562adb8d66430c74ccac26936cf3460a8033f274ff0ed6d3`。

暂停交接时两台原适配容器均核验Running且仅保留`sleep infinity`；当时eager-service-v4
在开始真实载荷读取后按用户要求停止，停止记录为各Host的
`02-issues/<Host>/postpone-service-v4-20261104/result.json`。当前已按用户后续指令恢复开发服务，正式评测待执行。

## GSM8K 离线数据准备

工具镜像自带的 GSM8K/main Arrow 数据已核对：训练7473条，测试1319条。
为使派生缓存留在评测容器私有 `06-cache/gsm8k-arrow-dataset`，使用
`03-acceptance/gsm8k-v41-cached-20261104/gsm8k_cot_zeroshot_v41_cached.yaml`，
SHA-256 `70bddfe968df3ffa2f270ab31ff9420fb814f063e0fdc209e9af934b6a9c0d6c`。
该任务只改变数据传输/缓存和任务ID，原题目顺序、prompt、target、过滤器、评分及生成配置保持一致；
所有训练/测试记录与镜像原缓存逐行相等。完整测试集规范行哈希为
`32c548f08195e19e33408b844dd7be6aa4bcae457d957bc05909ff4bd4a00595`。
证据为 `04-runs/mx-102/gsm8k-dataset-prepare-v1-20261104/result.json`。
这只是数据准备通过，尚未发出正式评测请求，也未形成精度结论。
