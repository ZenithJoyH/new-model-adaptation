# Qwen-Image-2.1 PPU 推理环境分析

## 目标与写入边界

- 验证日期：2026-09-17。
- SSH Host：`PPU-07`；实际主机名 `bm-aliyun-wlcb-zonea3-c-810e-96g-10-7`。
- 目标容器：`qwen-image`，状态 `running`。禁止停止、重启或删除该容器。
- Host 工作根：`/mnt/nfs/users/jinghao/qwen-image`。
- 容器工作根：`/mnt/nfs/users/jinghao/qwen-image`。
- 容器以 RW 方式把 Host `/mnt` 绑定到容器 `/mnt`；两侧工作根 `realpath` 相同，且 `stat` 均为 device/inode `41:20472824312`，映射已现场核实。
- 模型权重 `/mnt/cpfs/models/Qwen-Image-2.1` 只读使用；不移动、不复制、不改权重。
- 新的环境、诊断、运行、临时和缓存产物分别放在工作根的 `01-environment/`、`02-issues/`、`04-runs/`、`05-tmp/`、`06-cache/`。参考 ZIP 是用户预先提供的既有文件，不在工作根新增源码 checkout。

## 容器与平台

| 项目 | 已验证值 |
|---|---|
| 容器镜像 | `harbor.baai.ac.cn/flagos-inner-models-release/qwen-image-pp001-gems0.0.0-tree0.6.2-cxnone-pluginnone-vllm0.23.0-cp312-pt210-hggc130-x64-2.1.1-rbd225:202609170906` |
| Image ID | `sha256:aa5dc7bf93655926de00618935813430beca846371b1e3279321e019604ad0a8` |
| 容器 OS | Ubuntu 24.04.2 LTS |
| Python | 3.12.14 |
| PyTorch | 2.10.0 |
| 平台 | 16 × T-Head PPU-ZW810E，每卡 98,304 MiB |
| PPU-SMI / Driver | PPU-SMI 1.28；Driver `2.1.1-rbd225` |

2026-09-17 20:41 的现场状态不是空闲：16 张 PPU 均被另一组 `VLLM::Worker_TP0..15` 占用，每卡约 93,035 MiB、利用率 100%。这些进程不属于 `qwen-image` 容器；本轮不得停止或干扰它们。依赖安装和无设备导入可继续，模型搬运与推理验证必须等待资源释放。

## 框架与源码基线

| 组件 | 版本/路径 | revision 与状态 | 修改边界 |
|---|---|---|---|
| Diffusers | 0.40.0，`/usr/local/lib/python3.12/site-packages/diffusers` | 非 editable 安装；基线缺少全部 `QwenImage21*` 类 | 保留 stable 0.40.0，只允许最小移植固定参考实现；必须备份并保留回滚证据 |
| Transformers | 5.8.1 | 已包含 `Qwen3VLProcessor`、`Qwen3VLForConditionalGeneration` | 不修改 |
| Torch-FL | 0.1.0+ppu，editable `/workspace/PyTorch-Plugin-FL` | `main@a3b46f805a91fcb89a6486c8cf3b11384d9c23e8`，`main...origin/main`、clean | 本轮预计无 Plugin 代码变化 |
| FlagGems | 0.0.0，editable `/workspace/FlagGems` | `master@454f68853424970deb800290b7d7538a09a0b4bb`，`master...origin/master`、clean | 本轮不修改；若后续进入算子集成，需另行确认同步授权并先 fast-forward |
| vLLM | `0.23.0+v0.2.0.ppu2.1.0`，site-packages | 无 `/workspace/vllm` checkout | 全程只读、不修改；本模型脚本不依赖 vLLM |

Torch-FL README 将 PPU 标为 experimental，执行路径是针对 PPU CUDA-13-compatible SDK 的 CUDA boxing，可与 per-op FlagGems Python 路由混用。当前 Torch-FL 已按 `FLAGGEMS_PYTHON=ON` 构建，先前通过 `abs -> flagos_python` 和集成测试验证了 Python 路径。

## 参考实现与依赖兼容性

- 参考 ZIP：`Qwen-Image-2.1-ref-qwen-image-2.1.zip`，SHA-256 `0f788ee6b453d223903d1bd88bac0a7108d71bf627f2453b44c0409c75ad62f3`，源码提交 `9511e982f22ea8fcc64faf277d90b3a21f8a83f6`，Diffusers `0.41.0.dev0`。
- ZIP 是完整 Diffusers 源码包，包含 `QwenImage21Pipeline`、`QwenImage21Transformer2DModel`、`AutoencoderKLQwenImage21`、文档和单元测试，不是仅修改类名的补丁。
- 已安装 `accelerate 1.13.0`、`huggingface-hub 1.31.0`、`safetensors 0.8.0`、`numpy 1.26.0`，满足参考 fork 对这些包的最低要求；Transformers 5.8.1 也已覆盖 Qwen3-VL。
- `peft 0.20.0` 已在容器中。`torchao 0.11.0` 缺少 Transformers 5.8.1 TorchAO 集成可选使用的 `FqnToConfig`；模型配置没有 `quantization_config`，本轮仍避免安装整套 0.41.0.dev0，以收窄兼容面。
- 基线 `pip check` 本就报告 vLLM/flashinfer/tilelang/xgrammar 等若干镜像级依赖不一致。它们不是本次 Diffusers 适配产生的，安装必须使用 `--no-deps`，避免为了 Qwen-Image 修改或“修复”这组无关依赖。

## 已验证兼容性缺口

1. 权重 `model_index.json` 要求 `QwenImage21Pipeline`，当前 Diffusers 0.40.0 在 `from_pretrained` 入口立即抛出 `AttributeError`。
2. 当前 Diffusers 同时缺少 `QwenImage21Transformer2DModel` 和 `AutoencoderKLQwenImage21`，因此修改 `model_index.json` 为旧类不成立。
3. 参考 fork 与权重的专用类、配置字段和默认推理路径一致；最终方案以官方 stable 0.40.0 wheel 为基线，只移植专用实现和注册项，而不是向 Torch-FL 添加模型特例或覆盖整套开发分支。
4. 既有 Qwen-Image-2512 实测表明 FlagGems `slice.Tensor` 不支持 `torch.complex64`。Qwen-Image-2.1 同样使用 complex RoPE；若负对照复现，只允许精确单算子回退并记录，不能全局禁用 FlagGems 或吞掉任意异常。
5. 当前 PPU 被无关 vLLM 服务占满，尚不能验证设备搬运、attention、KV cache、VAE 或完整图像生成。

## 适配计划与职责

| 缺口 | 所有者/扩展点 | 计划 | 回归范围 |
|---|---|---|---|
| Qwen-Image-2.1 类缺失 | stable Diffusers + 固定参考实现 | 备份当前包，在官方 0.40.0 wheel 中只加入四个专用文件和注册项，使用 `--no-deps` | 新三个类导入；旧 `QwenImagePipeline` 导入；`pip check` 与基线对比 |
| 权重加载 | Diffusers Pipeline | fresh process 加载组件；不改权重/模型索引 | 无设备配置读取 → 完整 `from_pretrained` → `.to(flagos:0)` |
| complex slice | Torch-FL per-op policy / FlagGems 能力边界 | 先跑负对照；必要时仅 `FLAGOS_OP_slice__Tensor=cuda` | complex64 slice 负对照、整模最小推理、既有 Qwen-Image-2512 路径 |
| block-causal attention | Diffusers 默认 processor + Torch-FL native/boxing | 先用默认非 flex processor，不启用 compile | 低分辨率 1-step、2-step KV cache on/off、有限值检查 |
| VAE decode | Diffusers VAE + Torch-FL operator coverage | latent-only 先通过，再启用 decode/PIL | 低分辨率 decode 后完整分辨率 |

本轮预计不修改 Torch-FL、FlagGems 或 vLLM，因此 Plugin 设计结论为“依赖环境适配，无 Plugin diff”。如果后续实际失败证明需要公共 dispatch 或算子变更，必须新建编号问题、同步/核对 FlagGems 并重新做影响面审查。

## 环境结论

身份、路径、镜像和源码边界均已核实，stable 最小兼容构建已通过无依赖安装、导入、配置解析和无大权重 pipeline 装配。当前唯一现场资源阻塞是全部 PPU 被无关任务占用；不能据此宣称模型已在 PPU 上可推理。平台保持 `model_loading`，直到设备实际推理完成。
