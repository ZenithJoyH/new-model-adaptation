# H100-149 FlagOS 容器环境分析

2026-10-08 按用户要求从最终共用容器创建两个新模型容器，镜像内安装与设备检查通过；
身份、挂载和验证边界见[新容器环境记录](model-containers-2026-10-08.md)。以下保留原容器历史分析。

2026-09-28 只读核实目标 Host 为 `H100-149`（hostname
`p-jn-sz-dell-h1-su8-gpu11-401-11o-12u-208-149`），容器为
`MinicpmV4.7-1B`，ID `4642fce472209069ab927e6bf6af7bc1ccb3443f2fa85d4a6f76b65e92a5c637`，
镜像为 `harbor.baai.ac.cn/flagos-inner-models-release/xingchen4-nvidia003-gems5.3.5-tree0.6.2-cxnone-plugin0.0.0-vllm0.24.0-cp312-pt211-cu129-x64-580.105.08:202609070901`，
image ID `sha256:d0af16489bc171d5434fc225c7afd89d32da7946af53655b9ad6dc7b50c745ca`。
`./scripts/connectivity-check --limit H100-149` 通过。`./scripts/accelerator-check
--limit H100-149 --full-output --show-processes` 显示 8 × H100 80GB、驱动
580.105.08、CUDA 13.0；2026-09-28 11:16（本地时间）八卡均 0 MiB，未见计算进程。
这是启动前时点状态，服务启动前仍需重新核实。

| 对象 | 已验证身份或状态 |
| --- | --- |
| 工作根 | Host 与容器均为 `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`，两边 `stat` 均为设备号:inode `45:232972481026`；`/public` bind mount，起始目录为空，现按规则建有 `01-environment/` 至 `07-bugs/` |
| 权重 | `/data/models/MiniCPM-V-4.7/weights/1b/config.json` 在 Host 和容器的设备号:inode 均为 `64768:14475024`，SHA-256 `0d2f763cf97a0a5beec8f52b13b4cbf7262680df6fd35e1f0e48c09288c4bb12`；外部权重只读 |
| Plugin | `/vllm-workspace/vllm-plugin-FL`，editable 元数据，`main@3a27a6fb2d514cdf55c00481bf813225dac63319`，修改前工作树干净，跟踪 `origin/main`；产品修改只允许在此树 |
| FlagGems | `/vllm-workspace/FlagGems`，editable 元数据，`master` 跟踪 `origin/master`；用户单独授权后从 `1478cefcf2ee304ebb72c2f51acade0d45c82f13` fetch 并 `git pull --ff-only origin master` 至 `da6727e38f6f8eedef6cba43695a87b4996f9eca`，同步后工作树干净 |
| FlagGems-vllm | `/vllm-workspace/FlagGems-vllm`，editable，`main@e13419a429bfba65f4757a7671b1aebfe25c61a2`，工作树干净；本任务未获该源码的单独修改授权 |
| vLLM | wheel `0.24.0+cu129`，导入于 `/usr/local/lib/python3.12/dist-packages/vllm`；始终只读。参考 `minicpmv4_6.py` SHA-256 `fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81` |
| 其他 | PyTorch `2.11.0+cu129`、Transformers `5.12.1`；`triton` 模块可导入，当前 distribution metadata 查询未返回版本 |

## 适配前基线与工作边界

模型 `config.json` 的架构为 `MiniCPMV4_7ForConditionalGeneration`，
`mrope_mode=canvas`，`downsample_mode=16x`，`insert_layer_id=6`。
文本配置 `max_position_embeddings=262144`；按 profile 首次服务长度规则使用
`--max-model-len 50000`，不能为规避故障静默缩小。参考模型与 processor 可通过
`AutoConfig`、`AutoProcessor.from_pretrained(..., trust_remote_code=True)` 加载；
实施后文本、224×224 单图、多图与短视频的功能请求已通过；
full graph 请求被 GDN backend 降为混合模式，显式 decode-full 已通过。
复杂输入的 canvas 位置数值等价性、正式精度和性能仍需验证，详见
[功能报告](../acceptance/functional-validation.md)。

2026-09-28 基线中，已安装 Plugin 的 editable 元数据指向源码，但默认 `python3` 实际解析
`vllm_fl` 为 `/usr/local/lib/python3.12/dist-packages/vllm_fl` 的 namespace package
（`__file__=None`），缺少 `register` 和 `register_model`，平台插件加载失败。
用只作用于目标进程的 `PYTHONPATH=/vllm-workspace/vllm-plugin-FL` 复核后，
`vllm_fl.__file__` 指向已核实源码，`register_model` 存在，平台为 CUDA，
适配前目标架构尚未注册；随后已在 Plugin 的正式注册入口增加模型专用 shim。
当时的运行配置 workaround 见 [001](../adaptation/001-editable-import-shadowing.md)。
2026-09-30 按用户要求在同一容器内从原 checkout 以兼容模式 editable 重装后，
全新进程无需 `PYTHONPATH` 即解析到该源码；安装和验证记录仍见 [001](../adaptation/001-editable-import-shadowing.md)。

vLLM 0.24.0 只注册 `MiniCPMV4_6ForConditionalGeneration`；该 adapter 的
`get_mrope_input_positions` 把顺序位置复制到三个通道，和本模型 canvas 语义不符。
目标 checkpoint 780 个 tensor 的前缀总体匹配 vLLM 4.6 的视觉塔、merger、
语言模型映射；整模权重已成功加载，处理器与位置的边界/数值仍需逐项验证。
相关 [002](../adaptation/002-v47-model-integration.md) 保持 hypothesis 状态。

此前检索 `docs/troubleshooting/`、同机 NVIDIA 模型以及原生 vLLM 的 4.7 问题记录。
现有 TP timeout、Plugin full graph 条目缺少相同的失败签名；原生记录的静态架构差距
可作为候选线索，不能替代本容器的运行证明。
