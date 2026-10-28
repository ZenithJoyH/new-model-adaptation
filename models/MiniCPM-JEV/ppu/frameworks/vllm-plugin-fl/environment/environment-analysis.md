# MiniCPM-JEV / PPU-01 / vllm-plugin-fl 环境与实施记录

## 范围与身份

2026-10-23，用户要求以 `minicpm-ocr` 为基础创建 `minicpm-jev-vllm`，适配现有 value head checkpoint。目标 Host 仅 `PPU-01`，选择 active profile v7，vLLM 只读，可修改新容器内实际安装的 Plugin、FlagGems、FlagGems-vllm。旧 `minicpm-ocr`、`minicpm-jev` 和其他服务不属于本任务可停范围。

新容器 ID `2f1cde3f3c36963b0e5fe86e0fd76fd7af764209252408b5a8b838d7e591a5f8`，来自 `docker commit --pause=false minicpm-ocr` 的快照 `sha256:eacd8301d83a799656cd6253c9bea0cb924e4f4e661fe2e1949d22e65a04a563`。源容器保持运行，PPU0 的 OCR 服务未停。新容器使用空闲物理 PPU1，容器 `CUDA_VISIBLE_DEVICES=1`，计划服务端口 8330，host network / host IPC，继承 PPU 设备访问方式。

批准工作根（Host/容器同路径）为 `/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt/vllm-plugin-fl`，由 `/mnt:/mnt` RW bind 提供；两侧 stat 为 `41:8384415189`。原始创建命令、容器/镜像身份与映射证据在该根 `04-runs/container-create-20261023/container-identity.json`。工作产物按 01–07 目录保存；产品源码位于容器自身 `/workspace/`，没有挂载或第二份源码导入覆盖。

## 实际组件基线

| 组件 | 安装与源码身份 | 边界 |
|---|---|---|
| vLLM | `0.24.0+empty`，实际导入 `/usr/local/lib/python3.12/site-packages/vllm`；源码 `/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389`，起始干净 | 全程只读，已冻结全部 Python 安装文件哈希 |
| Plugin | editable `/workspace/vllm-plugin-FL@06014201f8ea8cd7092a56a945d8fc7998c5a46c` | 保留 OCR 继承 dirty；本任务增量见最终源码审查 |
| FlagGems | editable `/workspace/FlagGems`，初始 `367d19367880eaf8843449abe11db4cfb7d47e03`、master、干净 | 仅在新容器 fetch + ff-only 至 `722854072a3329c6c33ea2850afe368c9b4f63bc`；旧容器未改变 |
| FlagGems-vllm | `/workspace/FlagGems-vllm@db220e684094896c0e4a038bb2a44ab6e8c95aea`，main，起始干净 | 按当前安装集成 |
| PyTorch / Transformers / FlagTree | `2.10.0` / `5.8.1` / `0.7.0+ppu3.6` | 当前沿用源容器环境，不能把旧 HF 容器升级结果视为本容器已验证 |

组件 metadata/direct_url/import、Git 状态、diff 哈希和 vLLM 文件清单见 `04-runs/environment-baseline-20261023/identity.json`。Plugin 的继承差异包括脚本权限、MoE 配置类型及 TXDA 后端文件，保留原样，不能归为本模型新增修复。目标 Plugin 无独立 AGENTS/贡献文件，已阅读其 README、测试入口、模型注册、Qwen3.5 shim 及相关 vLLM adapter/pooler 实现。

## 经验检索与差距计划

现有 MiniCPM-OCR 与 MiniCPM-V 4.7 记录仅提供 PPU 容器、Plugin 与 GDN/视觉定位的候选经验。当前模型是 Qwen3.5 的二分类 value head，不复用 OCR 模型注册、生成 prompt 或未经本轮确认的 workaround。

| 路径 | 已有扩展点与选择 | eager/graph 验证 |
|---|---|---|
| 模型结构与权重 | vLLM Qwen3.5 多模态骨干 + 原生 `as_seq_cls_model`；`--runner pooling --convert classify` | 先确认 `score.weight` 和视觉权重正确加载，避免按 config 的生成架构加载 lm_head |
| 分类输出 | 原生 LAST pooler、二分类激活 | 与随包 12 个参考概率及已有 HF 结果比较；不能误用 vocab head 口径 |
| 图像处理/prompt | 原生 Qwen3.5 多模态 processor，保持双图顺序和 value prompt | 检查 token/grid、一致性和换图负对照 |
| PPU 执行 | Plugin 已有 worker/dispatch/FlagGems 接入 | 记录实际 backend 与调用；缺失时只修改已声明组件，不改 vLLM |
| 图模式 | 按 full → full-and-piecewise → decode-full → piecewise | 核实 pooling 路径实际支持和运行模式，记录每级阻塞及修复，不默认跳级 |

配置位置上限 262144，首次服务依 profile 使用 `--max-model-len 50000`。TP1、BF16、8 个最大并发序列、双图上限；非性能验证启用前缀缓存。训练 max_length 12000 与位置编码上限不能混为一谈。正式 FlagEval/生成性能工具是否适用于 classification endpoint 尚未建立，不能用 12 样本代替正式整体验收。

## 首轮启动诊断

原生 pooling 转换通过配置识别后，第一轮因工作根较长导致 ZeroMQ IPC 路径超过 107 字节失败。实测 Linux 抽象 IPC 收发正常，增加原生 `VLLM_RPC_BASE_PATH=@minicpm-jev-vllm`。后续 clone、异步池化和视觉插值问题分别见 002、003、006。

## 最终环境与证据

eager/PIECEWISE 及 4/8 并发已完成固定参考的数值对照。最终 PIECEWISE + EagerAdaptor、prefix caching 开启；实际参数和环境在 `04-runs/final-launcher-20261023/runtime-process.json`，当前服务经原生 observer 核验。没有 PYTHONPATH、诊断日志环境或性能禁缓存参数。

包元数据为 Torch 2.10.0、Transformers 5.8.1、Plugin 0.0.0+g06014201f.d20261021、FlagGems 5.5.0.dev0+g367d19367、FlagTree 0.7.0+ppu3.6；FlagGems 实际 editable 代码为 7228540 加本任务 patch。Triton 由 FlagTree 提供。

完整身份及源码锁定位于 `01-environment/deployment-identity.json` 和 `04-runs/source-review-final-20261023/manifest.json`。1886 个 vLLM 安装文件、FlagGems-vllm 和 Plugin 继承改动保持原状。最终审查见 [008](../adaptation/008-source-review.md)。源码、依赖及 `/opt/minicpm-jev-vllm` 交付文件位于容器文件系统；外部输入、日志和缓存使用 `/mnt:/mnt` 挂载。镜像打包验证 pending。
