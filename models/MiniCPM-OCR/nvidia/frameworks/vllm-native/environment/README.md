# 当前容器资源（2026-10-21）

当前资源容器为minicpm-ocr-vllm-native-allgpu，全部8张H100可见，主机/public完整RW挂载至/public。旧容器保留运行，适配源码和内部交付哈希保持。原生模型服务在本轮检查前已不运行，原根脚本/模型路径缺失，新容器未启动服务；以下8010服务与262144验证记录为历史。完整身份与证据见[005](../adaptation/005-allgpu-public-mount.md)。

# H100-149 原生 vLLM 环境

核实日期：2026-10-20。只涉及 `H100-149`，不操作其他 inventory 主机。

| 项目 | 已核实身份 |
| --- | --- |
| 容器 | `minicpm-ocr-vllm-native`，ID `917cfd5ed14be7e4ee321d7c8db7810e93178cd4c46eadf8025457697bfdf8af`，保持运行 |
| 镜像 | `vllm/vllm-openai:v0.24.0-cu129-ubuntu2404`；image ID `sha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4`；repo digest `sha256:57f2055d534ce925817765a2f0a908027adf4ab6c1f113096a40d38af52f59a6` |
| GPU | 主机 8×H100 80GB HBM3，驱动 580.105.08；容器仅透传 GPU 0，TP1。GPU 4–7 的其他任务未干预 |
| 工作根 | Host/容器均为 `/public/flagos/jinghao/MiniCPM-OCR`，bind mount；双方设备号/inode `45:225185087240` |
| 输入 | `hw_vllm_minicpm_20261016.tar.gz`，完整上传大小 3,214,084,698 字节；选择性解出权重 `MiniCPM-OCR-1.0/`，未展开或切换源码 checkout |
| vLLM | `0.24.0+cu129`，真实导入 `/usr/local/lib/python3.12/dist-packages/vllm/__init__.py`；wheel 安装，非 Git checkout |
| 运行库 | PyTorch `2.11.0+cu129`、Transformers `5.12.1`；CUDA 单卡检查通过 |
| 接口 | OpenAI chat，任务服务端口 8010；容量配置为 262144 token、最多 64 条序列、图像 4 / 视频 1、显存比例 0.55 |

## 修改边界与兼容差距

用户明确允许直接修改容器 vLLM；仓库 AGENTS.md 也要求直接修改实际安装组件，包括普通安装。依此在真实安装路径保存修改前哈希并实现兼容，不另建 checkout 或使用 PYTHONPATH。profile workflow 中旧的 editable-only 措辞不用于否定本次明确授权。Transformers、PyTorch、权重和原始包未修改。

原生 Transformers 不识别 `minicpm_ocr`，权重声明 `5.19.0.dev0`。OCR 的配置与必要图像/视频处理兼容模块置于 vLLM 的标准 `transformers_utils` 扩展目录，并通过现有懒加载注册表接入；OCR 模型复用已安装 4.6/Qwen3.5 骨干。现有 4.6 模型文件和公共执行热路径不改。

该机 Docker 的标准 `--gpus` 失败，故参照已有容器采用单个 GPU 设备直接透传及只读驱动库挂载。第一次失败的创建记录保留，未删除任何容器。Triton 的 ldconfig 缓存未列出透传的 libcuda，启动配置需明确 `TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu`。这与既有 MiniCPM-V 4.7 同镜像的经验一致，并已在本次实际导入及推理中重新核实。

## 原始证据

均在批准远端工作根内：`01-environment/installed-before.json` 保存包身份及修改前全部 vLLM Python 文件哈希；`01-environment/archive-selected.json` 保存所选包内文件的路径、大小、SHA-256；`01-environment/reference/` 为必要源文件参考证据，不作为导入目录；`02-issues/installed-original/` 保存被修改注册文件的原件；`02-issues/patch-manifest.json` 为初次补丁记录，最终部署另生成当前哈希与 diff。

eager 启动与推理、开启前缀缓存复验、HF 同构参考对照分别在 `04-runs/eager-libcuda-20261020/`、`04-runs/eager-prefix-20261020/`、`04-runs/eager-prefix-functional-20261020/`、`04-runs/hf-reference-20261020/`。CUDA Graph 的最终结论另见适配问题和验证记录；缺少正式精度、性能回执时不标记 optimized 或完整验收通过。

## 容量更新（2026-10-20）

用户要求将 max-num-seqs 从 8 提至 64，显存比例继续为0.55。仅更新启动配置和重启本任务服务，vLLM/Transformers/PyTorch 源码与权重均未改变。新 API PID 10319，两份脚本 SHA-256 均为 8ce2e2fae3e703e71644f635e26428c5728e19343e7f22bf8212cc16c729f47a；新部署身份保存在远端 01-environment/deployment-identity-seq64-20261020.json。旧配置、旧身份及回执保留，详见 [003](../adaptation/003-max-seqs-64.md)。

## 当前上下文更新（2026-10-20）

用户要求开到模型声明最大长度，故 max-model-len=262144；64序列与显存比例0.55不变。API PID12337，EngineCore12737，服务仍为8010/MiniCPM-OCR，部署身份为远端01-environment/deployment-identity-context262k-20261020.json。根脚本此前已有人工改动（8000/MiniCPM-OCR-native、nohup与日志）；本次保留，仅改长度。内部交付脚本仍启动8010，二者现不相同，不能相互替代其就绪证据。

当前根脚本SHA-256为c95d796ed95f738837540b8a669bb0a6f0eb261c4ff455c69c9ce2166d4ec9ca；内部交付脚本与持久交付副本均为257f68ae6b0bb2b2ae1fcbeff6cc794020313c747cb07153023387003240594b。源码九文件与既有review逐一哈希匹配；未修改权重、依赖或挂载。详见[004](../adaptation/004-context-262144.md)。上节16384配置和旧回执为历史。
