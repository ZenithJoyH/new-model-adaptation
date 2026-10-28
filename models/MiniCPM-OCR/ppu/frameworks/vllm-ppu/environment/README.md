# PPU-01 原生 vLLM 环境

2026-10-27；用户指定镜像和工作根，选择 experimental `vllm-ppu`，执行环境准备、适配和声明的基础验证。已有架构记录仅作参考；本次 checkpoint 为 `/mnt/nfs/users/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`，不修改模型目录。

容器 `minicpm-ocr-ppu-native`，ID `c7761d51cd375b946bdad104c97ea8c80837e282f86edf1099e713e75b27de82`；镜像为用户指定 `26.04-v2.1.0-vllm0.23.0-torch2.10-cu130-20260710`，image ID `sha256:9168c1a258c5ef3d5a3d3dfdc6dfa32436c5765174d220c527980e0157bd2eca`，repo digest `sha256:fb48fe779ca7b91741b0248cf6cda4ab3785c69dd91dfe88890c7cafdc2996ac`。

Host/容器工作根均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR/ppu-native`；RW bind 和双方 device:inode `41:15135181180` 已核验。父目录只读挂载，外部参考 checkout 和权重保持只读。容器使用 host network、16GiB shm 和本机已有 alixpu/infiniband 设备方式，持续运行。

实际解释器 `/usr/local/bin/python`，vLLM 普通安装于 `/usr/local/lib/python3.12/site-packages/vllm`，版本 `0.23.0+v0.2.0.ppu2.1.0`；Torch 2.10.0、Transformers 5.8.1。未设置 PYTHONPATH。可写组件仅实际安装 vLLM Python 产品代码；不修改 Torch、Transformers、驱动或原生库，不另建源码 checkout。安装修改前哈希和包身份在 `01-environment/installed-before.json`，容器身份在 `01-environment/container-created.json`。

PPU-01 为16×PPU-ZW810E、每卡96GiB，驱动2.1.1-rbd225。本任务使用原先空闲的物理 PPU4、TP1和端口8014；PPU0–3及其他已有任务未干预。最终服务配置为32768上下文、8序列、16384批次token预算、显存比例0.55、图像4/视频1。批次预算显式固定以对齐独立执行测试与HTTP服务；其余显式参数用于设备/端口放置、资源边界和复现。不据引擎容量估算声明已验证满长或满并发。

原始镜像 get_config 抛 minicpm_ocr 未识别，错误已保存。已审阅本模型 NVIDIA 原生记录和 PPU Plugin OCR 模块，确认当前0.23父类另有旧处理器包装接口差异；具体受控修改见问题001。

当前config的视觉塔、Qwen3.5文本骨干、4x/16x与位置编码结构与既有模型级中文架构分析同构；本任务只核对并复用该架构前置，不改写既有架构分析。旧文档中的历史checkpoint哈希不充当本次权重身份，本次以以下实际取证为准。

实际checkpoint权重SHA-256为 `83f4e433b044fd23f9ea7eb3acbc7d59e4fe11a1fdf3c3129b7021d0ab4f8fd4`。所有模型文件、最终安装改动、包版本与启动参数绑定于 `01-environment/deployment.json`，部署指纹 `95c2a90367feeb90fb704543a220c002557eb0d5c571ab95c83c698ec257ab58`。

选定 FULL_AND_PIECEWISE，正常启动显式开启前缀缓存；实际镜像的服务默认值并非 CacheConfig 字段的 True，不能省略该enable参数。最终脚本SHA-256 `fb250cb53139ef7cdc80f3310520ed0217463447ab853e5e222e000084572c2c`。正式性能未执行；性能分支只切换缓存状态。

服务使用已核验的容器默认 `/root/.cache/vllm`、`/root/.triton`、`/root/.cache/torch`、`/root/.cache/flashinfer` 和 `/tmp/torchinductor_root`，这些均属于新容器文件系统且可写，不依赖外部开发挂载。不设置额外磁盘缓存目录环境变量。显式评测缓存留工作根 `06-cache/`。

实际修改11个Python文件，原vLLM其余Python文件未变；普通wheel无Git工作树。源文件和依赖均在容器文件系统，权重在已声明的只读父目录挂载。容器内部交付副本 `/opt/minicpm-ocr-ppu-native` 不在绑定挂载中；持久恢复材料在工作根 `01-environment/delivery/`。未打包或测试新镜像，image validation=pending。
