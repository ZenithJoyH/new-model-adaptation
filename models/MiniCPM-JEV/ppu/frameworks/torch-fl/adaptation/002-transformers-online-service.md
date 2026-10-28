# 002：当前 Transformers 优化环境的在线评分服务

2026-10-26，用户明确要求基于当前适配环境启动在线服务。本轮仅包装并部署现有HF Python API，不执行正式accuracy/performance验收，不升级experimental profile或改写既有验收状态。

## 范围、身份和改前计划

PPU-01 / `minicpm-jev`，ID仍为`0ee63bbcec91264acfef52636b7a2983d53bf31ccb976c808fe827646673e069`，control.mode=agent；容器运行且使用host网络。既有批准根`/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt`在Host/容器同路径，dev41/inode18374857198一致。挂载仅/mnt和/data，/opt为容器内部文件系统。原PPU0/1/2服务不受操作，PPU3空闲；8331经bind探针及ss均确认为空闲。

实际Torch-FL与GDN适配未变：`/workspace/PyTorch-Plugin-FL`，适配SHA-256为`a8ae075e006e69b25f5c134282bd3a3bdaa3f12cdcaf716b57d02ecb3bf7137d`；原demo SHA-256为`306869a203b1b9249454529912929c7e14df3da8e3c69a28a92fe3a7a956f8e8`。FastAPI0.136.1、Uvicorn0.46.0、python-multipart0.0.20、Pydantic2.12.0已安装，无需安装或升级依赖。官方torch2.10.0+cpu、Transformers5.10.4、PPU CUDA路径、BF16/SDPA保持已验证配置。

允许新增的运行交付文件限定于此前不存在的容器内部目录`/opt/minicpm-jev-transformers/`：HTTP包装`server.py`、原demo的逐字节交付副本、最小`start-model.sh`及简短恢复/API说明。源demo和模型依赖仍只读；此副本仅用于服务的镜像内代码交付，不是另一个框架checkout或导入覆盖。GDN适配继续从原实际安装Torch-FL导入，无PYTHONPATH。权重仍使用已批准/mnt外部挂载路径。

服务为0.0.0.0:8331，POST `/score`接收multipart原图、渲染图和OCR文本，返回原demo分数/token及判定；GET `/health`提供就绪状态，`/docs`提供API文档。单进程、模型加载一次、18层GDN显式启用、推理用锁串行，保持bs1语义。启动器仅保留必要环境、服务命令和日志重定向；其工作根副本`<ROOT>/start-model.sh`此前不存在，保留父目录既有vLLM脚本原样。

运行计划与结果保存在本根`04-runs/transformers-service-20261026-1/`，验证客户端在`03-acceptance/transformers-service-20261026-1/`，临时文件在`05-tmp/transformers-service-20261026-1/`。启动后外部HTTP逐项验证12例、参考误差≤0.005、与001优化结果/输入token一致，补健康、非法图片、缺失字段、少量并发正确性及服务PID核对。代码与脚本语法/lint检查通过后才启动；不以health200代替实际请求通过。只允许调整本轮新建服务进程，不重启容器或其他服务。

## 已验证结果

服务已启动并保持运行。Host PID2185930，容器PID38442，start ticks572035973；实际命令为`/usr/local/bin/python -B /opt/minicpm-jev-transformers/server.py --checkpoint <ROOT>/qwen35_2b_l2_triple_value_checkpoint-3000 --host 0.0.0.0 --port 8331`。`CUDA_VISIBLE_DEVICES=3`，无PYTHONPATH；Torch-FL direct_url仍指向原editable `/workspace/PyTorch-Plugin-FL`。容器镜像身份`sha256:2b062c82d91f5abd52c7a16de4f2a6f66a7f70eb619fc42ef4567cddafa1de99`，容器未重启。

GET `/health`返回HTTP200及`status=ok, model=minicpm-jev, device=cuda:0, gdn_layers=18`。经过真实HTTP上传的12例全部HTTP200，token数与001结果一致，概率与001优化后输出差≤1e-7；最大参考误差0.004621146 < 0.005，判定与阈值计算一致。另4个并发请求全部成功且概率一致；推理锁使其排队串行执行，没有宣称动态batching或并行吞吐能力。非法图像400、缺失原图422、非法threshold422；`/openapi.json`和`/docs`均HTTP200。

重复启动探针在权重加载前因端口占用退出，日志未出现Loading weights，原服务health仍为200。仅运行本轮新建进程的启动/验证，无服务或容器停止操作。最终Docker top只保留服务和原有shell会话，验证客户端已退出。

语法检查、启动器`bash -n`、Ruff0.15.12 check和format --check通过。服务文件仅新增到此前不存在的交付目录；source demo、模型权重、GDN适配、厂商库和推理依赖未修改。服务端计时`inference_ms`覆盖demo.score及设备同步，不包括排队、HTTP上传和前置图片格式校验；本次仅做功能验证，不将单次HTTP耗时替代001的五轮性能统计。

## 文件与复现

| 交付文件 | SHA-256 |
| --- | --- |
| `/opt/minicpm-jev-transformers/server.py` | `99c2714bf3109a86119606cbce379bfed950703b511a251ba30c799f2fe295a4` |
| `/opt/minicpm-jev-transformers/demo_value_head.py` | `306869a203b1b9249454529912929c7e14df3da8e3c69a28a92fe3a7a956f8e8`，与原demo逐字节一致 |
| `/opt/minicpm-jev-transformers/start-model.sh` | `37c40e4fbcc243b8481f1122e4b18b943c044d5f7cbbc94b07034d236f88bbb2` |
| `<ROOT>/start-model.sh` | 与容器内部启动器相同 |
| `/opt/minicpm-jev-transformers/RESTORE.md` | `21a7f15b858763304e4d4c21902f1cde88005ebc0346e2cee3eecc1f4ad3080a` |

在容器内执行内部`start-model.sh`即可启动；当前已经运行，重复启动会被拒绝。原始证据目录包含`delivery-before-launch.json`（格式化前快照）、最终`service-final.json`、`container-final.json`、`docker-top-final.txt`、服务日志、Ruff结果、HTTP校验和重复启动探针。`http-validation.json` SHA-256为`f6bbcca81ebfcb277d823a4d26e508350ca2e470cd5f6fc080c7dead9e543a37`。

本机调用示例（HTTP客户端位于PPU-01时使用127.0.0.1，其他客户端替换为该机器可达地址）：

```bash
curl http://127.0.0.1:8331/score \
  -F 'orig_image=@orig.png' \
  -F 'render_image=@render.png' \
  -F 'ocr_text=待判断的OCR文本'
```

返回`prob_0/prob_1`、两类logits、输入token数、threshold、pred_label及inference_ms。原图/渲染图需由客户端上传，不将客户端路径当作服务端路径。默认threshold为0.5606135129928589，可作为form字段覆盖。

服务代码、demo交付副本及启动器在容器内部，实际Torch-FL/FlagGems和依赖亦位于非挂载路径；权重及日志/缓存使用声明的/mnt挂载。尚未打包镜像或用新容器验证，不能据当前运行宣称新镜像交付通过。此为用户指定的自定义HTTP包装，不将它当作experimental profile新增正式服务协议或验收runner。
