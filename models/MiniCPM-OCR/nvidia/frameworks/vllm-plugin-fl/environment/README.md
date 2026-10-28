# MiniCPM-OCR FlagOS 当前环境

2026-10-20，H100-149。用户要求的服务交付范围仍为eager/graph与OCR参考一致性；后续追加FlagTree、两个算子库源码安装及Plugin代码收敛。正式精度、性能另安排。

运行容器minicpm-ocr-flagos-allgpu，ID30f6c5ba638e01ab066682ffc140d81dbeb648a7d7dca318aab953da5689ec05。原适配容器保留运行，旧推理进程在新环境验证成功后停止。Host/container工作根均为/public/flagos/jinghao/MiniCPM-OCR/flagos，实际内核挂载、statvfs与写入已核实RW，权重独立RO；参考输入只读/opt/ocr-reference仅供测试，产品没有该路径依赖。主机此前重新启动导致原安装及原生OCR容器退出；本任务适配容器已恢复，其他容器本轮未操作。

| 组件 | 当前安装身份 | 实际路径 |
| --- | --- | --- |
| vLLM | 0.24.0+empty，v0.24.0@ee0da84ab9e04ac7610e28580af62c365e898389 | /usr/local/lib/python3.12/dist-packages/vllm |
| vllm-plugin-FL | editable，HEAD a696859b9aa528dfd5b21f5da3403fdc16bac4cd，加当前OCR差异 | /opt/vllm-plugin-FL/vllm_fl |
| FlagGems | 0.0+g8200f71f5.d20261020，HEAD8200f71f51d784d54a5a51019cb955acb74d64c1，加既有attention修复 | /opt/FlagGems/src/flag_gems |
| FlagGems-vllm | 0.3.0.dev1，HEADfa78ddee4c3e78ce5047213ff0ef02acff34b2d5，源码未改 | /opt/FlagGems-vllm/src/flaggems_vllm |
| FlagTree | 0.7.0 NVIDIA/Python3.12 wheel，提供triton API3.6.0 | /usr/local/lib/python3.12/dist-packages/triton |

两个算子库的direct_url.json均明确editable=true，实际导入来自上述源码，PYTHONPATH为空。此前已从源码构建普通安装；本轮按用户要求转为源码editable，保留已验证提交，不擅自升级代码。FlagGems的dirty日期版本来自保留的attention修复；不能将浅克隆0.0元数据当成代码旧版本。

为遵守FlagGems pyproject构建约束，以隔离环境使用setuptools>=64,<77、setuptools-scm>=8,<10、wheel0.46.2，离线wheel缓存在06-cache/source-build-wheels；没有降级运行时构建工具。FlagGems-vllm也使用自己的PEP517/660 editable安装。Torch2.11.0+cu129、Transformers5.12.1、NumPy2.2.6、SQLAlchemy2.0.55、FlagTree0.7.0及Plugin原生_C扩展保持。

容器默认可见全部8张H100，服务选择宿主GPU0、逻辑CUDA0，UUID62954cac-bde7-68fe-d74b-3118a92bcdd4。BF16/TP1，长度262144、max-num-seqs64、显存比例0.55、图像4/视频1、TORCH_SDPA视觉后端、FlagGems-vllm开启，前缀缓存开启。最终FULL_AND_PIECEWISE；FULL的GDN限制重新实测。262143输入+1输出的262144边界已实测；长上下文质量、TP8和64峰值并发未测。

安装身份及完整组件文件清单见01-environment/installed-identity-maxctx-20261020.json与04-runs/dedup-20261020/*-installed-files.json。empty vLLM2449文件再次逐项无变化，权重SHA-256仍为cee5e1ac9c37e0b5794e4ba6754bec75d55a553ac1e1418a41d442f0e733fb3b。初次收敛见006，本轮去重详见007；新部署指纹独立绑定，旧FlagTree环境控制快照保留。

最终脚本为工作根start-model.sh及容器内部/opt/minicpm-ocr-flagos/start-model.sh，SHA-256均为066993c36c83080e7d0aeb3fc6c01a1b1c03fcb3b5d10f9888ecdc9e051be5b7。必要缓存TRITON_CACHE_DIR、FLAGGEMS_CACHE_DIR、FLAGTUNE_MODEL_CACHE与XDG均归06-cache，TMPDIR归05-tmp。脚本没有安装、诊断、轮询、自动杀进程或性能关前缀缓存参数；当前已实际启动。配置、完整源码补丁、锁定依赖和恢复说明在01-environment/delivery-maxctx及容器内部/opt/minicpm-ocr-flagos，源码/原生扩展位于容器可打包层。

基镜像为vllm/vllm-openai:v0.24.0-cu129-ubuntu2404，IDsha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4；早期恢复快照sha256:3331198c9ba0191a6bbd259a12ddd535be5fb60ac7a07d0056c7df1a46007cf9不含其后修复/FlagTree/本轮收敛。最终镜像尚未打包或独立验证。

已知依赖提示：FlagTree包名不是triton，pip check报告Torch/humming-kernels/xgrammar缺名为triton的发行包，实际triton模块和整模均验证；未伪造元数据或装回原生Triton。基镜像NIXL1.2.0/nixl-cu12 1.3.0冲突保留，TP1不使用NIXL，不声称验证其传输功能。早期冷编译与超时记录保留，不作为当前源码性能结论。

2026-10-20第二轮仅修改Plugin的image_processing_minicpm_ocr.py、model.py及既有test_minicpm_ocr.py，未合并文件、安装/升级依赖或重新构建_C扩展。两个算子库完整源码清单、FlagTree编译库、vLLM和权重再次核对保持；前轮去重部署指纹747aa6b0dabcc07a8047517573329b3cc05c6dda933bd5e749bc5524ed23c8ee。62项处理器零差异、36项聚焦检查以及新实例的eager/graph与OCR复验通过，完整证据见007与验收索引。

本轮用户要求完整262144长度及全部显卡可见，部署变化和TORCH_SDPA的直接失败/成功对照详见008；旧主机1/50k为历史，当前新部署指纹27581af3bea2ad94f559dd65da49bd84420a65ce0dcf8e4412bc253964ef4940。快照镜像minicpm-ocr-flagos:allgpu-snapshot-20261020（sha256:d268dae8b7cec5aed7c9a11d7be250d788985d896b2dea0f8d5826154c71e059）包括当前源码依赖，早于最终maxctx启动脚本及配置，最终镜像仍待打包验证。
