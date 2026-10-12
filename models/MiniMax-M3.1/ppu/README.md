# MiniMax-M3.1 / ppu

本地索引整理于 2026-10-12；本次没有核验或改变远端服务。

[模型概览](../README.md) · [历史状态与归档说明](../_shared/local-record-maintenance.md)

当前 framework 记录：
- [vllm-plugin-fl](frameworks/vllm-plugin-fl/README.md)（v2；历史结论不自动成为新门禁通过）。

## 整理前平台说明（历史原文）

**当前项目进展：已完成（2026-10-08 用户验收确认）。** 范围为 PPU-07 / minimaxM3.1 / vllm-plugin-fl，TP16、BF16、204800 上下文、64 序列、FULL_DECODE_ONLY。

- GPQA **168/198 = 84.8484% ≥ 80.9%**，通过。
- 4K/16K/32K 输入、1K 输出、64 并发的输出吞吐 **113.97 / 98.62 / 170.02 token/s**，九轮零失败，结果已核验并由用户接受。
- 外部 ERQA **228/400 = 57.0%**，回答及推理无 U+FFFD。
- [完整适配总结](frameworks/vllm-plugin-fl/acceptance/adaptation-summary.md) · [框架进展](frameworks/vllm-plugin-fl/README.md) · [验收记录](frameworks/vllm-plugin-fl/acceptance/README.md)

平台 `project_completion` 与框架工作区已同步完成结论。`platform.yml` 的旧五阶段字段是模板兼容记录，不能代替显式框架工作区；原生回执和已知限制在总结中保留。

## 历史服务与平台验证

以下为记录日期当时的状态，最新用户验收结论以上述完成进展为准。

**2026-10-01 14:58 更新：**用户已原位修改 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh`，现文件 SHA-256 为 `5bd834658772572f5ebc39ff56be5bb168ca9cf255d8cd299e56fb7120aca124`，仍使用 TP16/204800/64，但改为 `nohup` 后台启动并把日志写到工作根 `service.log`。下文的 `c03db886...`、服务就绪和请求结果属于此前已验证版本；新文件的日志位置不符合 `04-runs/` 规则，尚不能继承该版本的最终启动脚本验证。用户要求自行启动；本任务启动的服务已于 14:58 退出，8025 端口空闲，适配容器仍运行。TP8 探索性启动曾完成权重加载、完整多模态预热、6/6 decode 图捕获并健康 200，KV cache 为 411520 tokens（约 2.01 条 204800-token 请求）；按用户指令停止，未执行 TP8 请求验证，也未修改最终脚本的 TP16 配置。

- Inventory group: `ppu`
- Hardware query: `ppu-smi`

平台根目录保留本索引、`platform.yml` 和显式 `frameworks/` 工作区。新任务先运行
`scripts/new-framework <model> ppu <framework-id>`，再把环境、适配和验收记录分别放入该
framework 目录的 `environment/`、`adaptation/` 和 `acceptance/`。平台根目录已有的三个
同名目录只作为历史隐式 `vllm-plugin-fl` 记录保留。
容器没有暴露 `ppu-smi` 时必须记录为环境阻塞，不得回退到其他平台命令。

2026-10-01，`PPU-07` 的 `minimaxM3.1` 容器与 Host 共用已核实的工作根 `/mnt/nfs/users/jinghao/minimaxM3.1`。当前根目录启动脚本 Host/容器同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh`，mode `0755`、同 inode `29236341840`、SHA-256 `c03db886fc93600b0ab1202bc70629ec3d66476f4382cdccb2996cbe264d3bdc`，验证日期 2026-10-01。容器内语法与占用端口拒绝退出码 1 通过；该根脚本已独立启动 BF16/TP16、`max_model_len=204800`、`max_num_seqs=64`、prefix cache enabled、`FULL_DECODE_ONLY` 服务，自动激活唯一外部平台插件 `fl`，完成完整多模态预热与 6/6 decode 图捕获、`/health` 200、`/v1/models` 报 204800。两道短题正确，报告 `04-runs/service-smoke-204800-full-mm-root-20261001.json` SHA-256 `2dc9bb269817475c90e2b7ac9c59512e811050fcf525ba2732b936af179efbdc`；约 201652 prompt tokens 的长请求也正确，报告 `04-runs/context-natural-202k-full-mm-root-20261001.json` SHA-256 `64333785c9348705e26ba74cc117c64185279bc18d52f1e58ca8c04d650cbbe6`。日志追加到 `04-runs/model-service.log`，验证后服务及容器仍运行。既有正式精度 167/198＜0.88，且 204800 配置尚未重跑正式 GPQA，因此不标记整项适配完成。

脚本采用已实测的 128 block、8192 batched tokens、0.90 显存利用率和 1/2/4/8/16/32 decode 图尺寸。16 张可见卡、SDK/MPI、TP 网络变量与 `spawn` 固定已通过的设备和通信环境。脚本与实际 API 进程都不设置 `VLLM_PLUGINS`、`TMPDIR`、`XDG_CACHE_HOME`、`FLAGGEMS_CACHE_DIR`、`TRITON_CACHE_DIR` 或 `TORCH_EXTENSIONS_DIR`；缓存与临时文件使用容器默认位置。首次默认缓存编译较慢，见[问题 008](frameworks/vllm-plugin-fl/adaptation/008-default-cache-cold-start.md)。源码身份为 Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加已记录任务 diff、vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`、FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`；本轮未改产品源码。

204800 的默认多模态视频预热在 FlagGems `conv3d_forward_kernel` 报 PPU 非法内存访问；仅排除 `conv3d` 后，FlagGems 的 `cudnn_convolution` 仍把 5D 输入送回同一 kernel。同时排除 `conv3d,cudnn_convolution` 后，完整预热通过，当前脚本不再使用 `--skip-mm-profiling`。这是当前 PPU/软件版本的 workaround，确切内核故障条件尚未定位，详见[问题 009](frameworks/vllm-plugin-fl/adaptation/009-context-204800-mm-profile.md)。最终服务的 5 个图像、双图、OCR 和八帧视频请求均 HTTP 200，其中 4 个答案正确；纯红图误答“绿色”，旧 65k 服务也有同一错误，见[问题 010](frameworks/vllm-plugin-fl/adaptation/010-red-image-color-error.md)。极端多模态显存和 64 条满长请求同时驻留尚未验证。先前的 100k 失败尝试是历史证据，见[问题 007](frameworks/vllm-plugin-fl/adaptation/007-context-100k-capacity.md)。当前 64 是调度上限，decode 图捕获尺寸止于 32，不代表 64 条满长请求的容量。
