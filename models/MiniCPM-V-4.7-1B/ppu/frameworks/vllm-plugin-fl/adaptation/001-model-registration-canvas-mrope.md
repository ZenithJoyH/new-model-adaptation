# 001：MiniCPM-V 4.7 注册与 canvas M-RoPE 差距

## 元数据

- 状态：`root-cause fix verified`（仅注册与 canvas 桥接）；当前 Host 的最小推理已核实，正式精度和性能另行验收。
- 首次出现/最后核对：2026-09-28。
- 模型/平台/Host：`MiniCPM-V-4.7-1B` / T-Head PPU-ZW810E / `PPU-13`。
- 容器/镜像：`minicpmV4.7-1B` / `sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f`。
- Plugin / FlagGems checkout / vLLM source：`3a27a6fb2d514cdf55c00481bf813225dac63319` / `80d0000d93dad55320df06687eb088a5b6dad07d` / `ee0da84ab9e04ac7610e28580af62c365e898389`。运行时 FlagGems 是非 editable 5.3.5，vLLM 是只读 `0.24.0+empty` wheel。
- 执行模式：eager 已启动并完成文本、图片请求；图片语义错误，full graph 尚待尝试。

## 现象、证据和假设

权重 `config.json` 声明 `MiniCPMV4_7ForConditionalGeneration`、`mrope_mode=canvas`；当前 Plugin 没有该架构注册，已安装 vLLM 仅有 4.6 adapter。4.6 的 `get_mrope_input_positions` 把顺序位置复制到三个通道，与 checkpoint 的 `mrope_minicpmv4_7.py` 不同。参考 processor 输出 image/video 视觉块的 target sizes 和结构 token，参考位置函数按图像 bounds 与网格计算空间位置。静态证据为环境分析中的准确 SHA 和源码路径；本问题尚未声称 PPU 加载失败的动态签名。

MiniCPM-V-4.7-1B/NVIDIA 同权重的 [002 记录](../../../../nvidia/frameworks/vllm-plugin-fl/adaptation/002-v47-model-integration.md)提供模型专用 shim 和 decode delta 的候选经验；Plugin HEAD 相同，但 PPU vLLM wheel、FlagGems、设备、图捕获环境不同，不能复用其运行结果。MiniMax-M3/PPU 的视觉算子问题、通用 troubleshooting 的 full graph/TP 超时条目也无本模型完整失败签名，暂不套用 workaround。

## 方案与职责

在已核实的 editable `/workspace/vllm-plugin-FL` 中，沿用 `vllm_fl:register_model` 和 `vllm_fl/models/`：独立注册 4.7，不把它仅作为 4.6 别名；复用 vLLM 4.6 的视觉、merger、Qwen3.5 dense 文本和权重映射，覆盖 4.7 的 processor 版本及 canvas 位置接口。模型级语义仅放模型 adapter。视觉 target sizes 从 vLLM 多模态 feature 元数据读取；若缓存消除了必需元数据，应明确失败或配置正确性约束，不能退回错误的顺序位置。vLLM decode delta 需按其 `max(position)+1-seq_len` 契约核对。

先验证注册、处理器和参考位置数值，再做权重加载、文本/图片最小 eager、full graph 尝试及变输入 replay。只有出现实际算子缺口后，才在同步后的 FlagGems 与 Plugin dispatch 中选择实现；不能从静态关键词推断具体算子问题。非 PPU 平台和 4.6/未知架构的注册行为是守卫回归对象。一次性过程脚本留在工作根 `02-issues/`，正式聚焦测试进入 Plugin。

## 基线与结果

环境阶段原生探针 `PPU-13:/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/04-runs/env-ppu13-minicpm47-1b-20260928/environment-probe.json` 的 14 项身份检查通过。Plugin `main` 与 `origin/main` 均在上述 HEAD，起始工作树干净、无继承差异；vLLM source checkout 干净，wheel 只读。FlagGems checkout 经用户授权快进，差异仅为 CI 工作流；本问题没有 FlagGems 算子选择结论。

## 2026-09-28 受控实施与首轮验证

| 轮次 | 唯一变量 | 基线 | 本次设置 | 证据 | 当前结果 |
|---|---|---|---|---|---|
| 1 | 模型注册与 canvas 桥接 | 4.7 未注册；4.6 顺序位置 | Plugin 新增 4.7 专用 adapter 和懒注册 | `04-runs/registration-v1-20260928/result.json`，SHA-256 `b6cab29f42bb4e6a443f7bf5b1212d9c13532e0e368a82ecb40e3552e17ec103` | 七项检查通过；4.6 保留、未知 4.8 未注册 |
| 2 | 位置数值接口 | 尚无 4.7 vLLM 输出 | 与 checkpoint 的 `compute_canvas_rope_index` 对照 | `04-runs/canvas-v1-20260928/result.json`，SHA-256 `d778b8eae742364e97a3ff7aea183c1e262aa6fe1899bb22b69e8f21da932528` | 文本/单图/双帧视频位置和 vLLM decode delta 契约通过；缓存缺元数据、网格数不匹配明确报错 |
| 3 | 首次整模 eager 启动 | 无本模型服务 | 单卡物理 PPU2、TP1、BF16、50,000 token、前缀缓存开启、`--enforce-eager`，端口 8327 | `01-environment/eager-start.sh`、`04-runs/eager-v1-20260928/server.log`、`04-runs/eager-smoke-v1-20260928/result.json`（SHA-256 `c101f378a687140b6efda1d80c3bbaed30185068033a40bfd0b4e4e895f743ee`） | 服务就绪，文本最终答案 `2`；纯红图请求返回 200 但回答白色，见 [002](002-visual-output-corruption.md) |

上述远端相对路径均以 `PPU-13:/mnt/nfs/users/jinghao/MiniCPMV4.7-1B` 为根。启动前 `ppu-smi` 显示 PPU0/1 正由其他任务占用，PPU2 为 9 MiB 空闲；容器 `CUDA_VISIBLE_DEVICES=2` 实测只见一张 `PPU-ZW810E`。Host 端口 8327 空闲，目标容器 ID 及运行状态、脚本语法均由 Ansible 预检后，使用 `docker exec -d -w /mnt/nfs/users/jinghao/MiniCPMV4.7-1B minicpmV4.7-1B bash /mnt/nfs/users/jinghao/MiniCPMV4.7-1B/01-environment/eager-start.sh` 启动本任务服务；容器未停、重启或移除，未操作其他服务。尚不能将 `docker exec` 返回 0 视为服务就绪。

当前 Plugin 未提交差异为 `vllm_fl/__init__.py`，未跟踪产品文件为 `vllm_fl/models/minicpmv4_7.py`；后者 SHA-256 `c7f32cace799f154c060ed88be49760bc02441b3ea41bebd3a6832aa76eca36b`。`git diff --check` 通过；vLLM checkout `ee0da84a` 仍干净，wheel 全程只读。完整设计审查待整模路径稳定后进行。

当前状态：注册和合成位置接口、eager 文本请求已通过；eager 图片请求有语义错误，随后红/蓝对照均输出重复标点，见 [002](002-visual-output-corruption.md)。full graph、正式精度和性能在该轮均未通过。本问题只在本任务范围内保留，不提升为通用知识。

## 2026-09-29 最终源码核对与审查

最终 Plugin HEAD 仍为 `3a27a6fb2d514cdf55c00481bf813225dac63319`，未提交的本任务改动仅为 `vllm_fl/__init__.py`、`vllm_fl/ops/custom_ops.py` 和四个未跟踪文件（4.7 adapter、T-Head attention、两份聚焦测试）；`git diff --check` 通过，无继承工作树改动。当前 adapter SHA-256 `c7f32cace799f154c060ed88be49760bc02441b3ea41bebd3a6832aa76eca36b`，注册入口 SHA-256 `4a3a1e81c8c82c6e9ceeb7e7aa7401a6303bdab0911254725a78fc7af023ee7b`。确认的代码比较基点为该 Plugin HEAD；没有创建分支、提交或 PR。

设计审查：4.7 架构仅经 Plugin 既有 `register_model` 路径注册，4.6 和未知架构守卫在 `04-runs/registration-v1-20260928/result.json` 已核实。canvas 位置只在新模型 adapter 内覆盖，调用者为 vLLM M-RoPE 输入位置接口；视觉 grid 元数据来自现有 `MultiModalFeatureSpec`。与 checkpoint 参考函数在纯文本、单图、双帧视频以及 decode delta 上的数值契约已经对照，见 `04-runs/canvas-v1-20260928/result.json`；缺失 grid 和不匹配明确报错。整体 eager 与 decode-full 服务均完成文本和红蓝图最小推理，最终服务 `04-runs/decodefull-product-smoke-v2-20260929/result.json` 的五类请求正常停止。PPU 视觉算子差距由 [002](002-visual-output-corruption.md) 的厂商 OOT 扩展处理，不把 PPU 分支写入模型语义。未在 NVIDIA、其他硬件、TP>1 或任意形状视频上复核本 Plugin 差异，不能推断跨平台支持；运行中图像缓存若消除必需 grid 元数据，当前设计会明确失败，退出条件是提供经过验证的 metadata 保留接口。

聚焦 7/7 测试的原始回执为 `04-runs/plugin-thead-tests-v3-20260929/result.json`，SHA-256 `332ef7dfffa6b491aaf31206a604eab746d8798a29ce982faa549fd854c07b38`。本问题的模型注册与 canvas 桥接已在当前 Host 的基本服务路径验证；正式验收状态由后续原生回执单独决定。

## 2026-10-08：撤除 FP32 后与统一 Plugin 分支的只读比较

用户询问能否直接采用私有仓库的 [support-minicpmV4.7](https://github.com/flagos-day0/vllm-plugin-FL/tree/support-minicpmV4.7)。本轮只分析源码，没有切换安装、修改远端源码或重启服务。GitHub connector/匿名 API 返回 404 后，使用操作者已有 GitHub CLI 权限确认分支头为 `aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68`；本机已有该提交的 Git 对象，按固定提交读取内容，未使用其他主机的运行权限。

PPU-13 connectivity 成功，随后在当前容器正常路径只读取得实际 Plugin 文件、上游 4.6 constructor、安装 FlagGems 哈希及 `/health=200`。工作根映射仍为 `41:12343819932`；Plugin HEAD 仍为 `3a27a6fb2d514cdf55c00481bf813225dac63319`，未提交差异仅既有注册、模型 adapter 和 canvas 测试，FP32 专用文件已不存在。

### 源码关系与差异

统一分支的直接父提交正是当前 PPU Plugin HEAD。该提交仅改四文件：注册入口、统一模型 adapter、canvas 测试、新增 backbone 测试；没有 PPU attention、公共 dispatch 或 vendor backend 变更。相对目标仓库旧 main 的继承差异见 NVIDIA 的 [006 整合记录](../../../../nvidia/frameworks/vllm-plugin-fl/adaptation/006-unified-dense-moe-adapter.md)，不能把旧 main 当作当前基线。

| 项目 | 当前 PPU 与统一分支比较 |
|---|---|
| `vllm_fl/ops/custom_ops.py` | 逐字节一致，SHA-256 `68406a5fbb37f91ffe1fb7ccaa77eff0bcb75246ca25d8b1852ca55869be28b8`，无专用 FP32 OOT |
| `vllm_fl/models/qwen3_5.py` | 逐字节一致，SHA-256 `a258cf04619b5b03ed8ee467620ec73683c1382a36b4a77f737393f2fe8954b0` |
| 注册入口 | 同架构名、同 lazy adapter 路径；统一分支把注册移到公共兼容 hook 之后，PPU 不走 ARM CPU 提前返回分支 |
| 模型 constructor | PPU 委托上游 4.6 dense constructor；统一分支显式复用初始化协议，并按 text model type 选择 dense/MoE。实际 vpm、vit_merger、merger、空 intermediate tensor 赋值的 AST 与当前上游一致 |
| Canvas | 同 checkpoint 算法与 delta +1 契约；统一分支改为惰性 tokenizer/动态 config 模块加载，要求 Nx2 Tensor geometry，显式纯文本/非 canvas fallback；当前 PPU 版本按权重目录加载 helper，允许递归规范化 grid |
| 测试 | PPU canvas 3 项；统一分支扩展到 canvas 7 项和 backbone 7 项，在 NVIDIA 既有整合验证中 14/14；不视作 PPU 已通过 |

注册入口 SHA-256：PPU `4a3a1e81c8c82c6e9ceeb7e7aa7401a6303bdab0911254725a78fc7af023ee7b`，统一分支 `4082f3a94ff9eb5c928a7b014de2d9d2abc1f8f670b22f01dd199437408e0080`。模型文件 SHA-256：PPU `c7f32cace799f154c060ed88be49760bc02441b3ea41bebd3a6832aa76eca36b`，统一分支 `9a1ad18e4c23d1ea2c63dc9884618c9260b0b4f7aca094f97816bb920ceaf4a7`。

### 结论与替换条件

**源码层面可采用统一分支，未发现必须保留独立 PPU 模型 adapter 的阻断。** 它已提供 1B dense 所需注册、视觉组件和 canvas 桥接；移除的是 FP32 attention 特例，模型适配器与 canvas 本身仍需保留。统一实现还覆盖 MoE，但本次不据此声明 PPU MoE 可用。

实际替换时须保留当前修复后的 FlagGems 安装：Flash API/kernel 哈希分别为 `ffbe6e6aa05940c5586d3fee08644c4eec86044cf220db856d913fcaa6630b15`、`19940f11b4a3de9b77399166fd595498ae6d22da8aa6ef2ff4eb1ddf62f7a3aa`；这些算子修复不在 Plugin 分支中。当前 `index_put.py` 修复哈希 `ee8233b3356db377055c8453ba5b9d60d2312f7f0cc04a5fcc3c072ec441d55a` 亦保持。不得用换 Plugin 推导可移除 index 黑名单。

保留当前 vLLM 0.24.0 与启动参数，固定上述分支提交；已有 dirty/未跟踪适配文件须先备份后受控替换，不能假设 `git checkout` 会完整覆盖。替换后仍需在 PPU 正常安装路径验证 14 项契约、实际 checkpoint canvas 位置、文本/单图/多图/切片/视频及 FULL_AND_PIECEWISE 变输入/并发请求。NVIDIA 既有验证只作为兼容参考；上一轮 PPU 25/25 结果绑定旧 PPU adapter，不覆盖统一 adapter。当前结论为可迁移候选，未声称该分支在 PPU 实机已验证或正式精度通过。

## 2026-10-08：按用户要求切换统一分支并做基础验证

### 冻结输入与实施

用户随后明确要求容器直接使用上述分支并做基础验证。本轮执行 `vllm-plugin-fl` profile v6 的适配诊断，限定 `PPU-13` / `minicpmV4.7-1B`，不执行正式精度/性能或镜像打包。GitHub CLI 再次确认分支头仍为 `aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68`，容器 ID 仍为 `a8861de7fe732bf0e2e469976d0736a17f90bc7de96c65986b5e1e5745bcbf22`、运行中，工作根 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B` 的宿主/容器 device:inode 均为 `41:12343819932`，`/mnt` RW bind。

服务解释器 `/usr/local/bin/python3.12`，当前 Plugin 是 editable `/workspace/vllm-plugin-FL`，FlagGems 普通安装在 `/usr/local/lib/python3.12/site-packages/flag_gems`；FlagGems-vllm 是 editable `/workspace/FlagGems-vllm`。实际版本为 Torch 2.10.0、vLLM 0.24.0+empty、FlagGems 5.3.5、FlagGems-vllm 0.1.0。沿用已安装的 Python 包与 entrypoints，没有重装依赖或设置导入覆盖。Plugin editable 安装元数据仍显示旧构建版本 `0.3.0rc2.post1+g3a27a6fb2`，实际运行代码以新 Git HEAD、导入路径和文件哈希为准，不将元数据后缀冒充源代码提交。

先逐文件验证旧注册、模型 adapter、canvas 测试的完整 SHA-256，备份到远端 `05-tmp/plugin-support-minicpm47-20261008/before/`，同时保存 `tracked.patch` 与 `manifest.json`。当前未提交内容与上节只读比较完全一致，没有无关改动。通过 Git bundle 将指定私有分支的单个提交传入既有 checkout；bundle SHA-256 `2c16d30db3da37d37ca22320e5db70d78980c6c1087fedfdb04cbbec49d9eb83`，父提交依赖由远端 `git bundle verify` 验证。bundle 是过程传输文件，不是另一个源码 checkout。

仅在备份校验完成后恢复旧跟踪注册文件、移出两个旧未跟踪文件，再在**同一实际安装 checkout** `git switch support-minicpmV4.7`。结果为指定 HEAD、工作树干净，四个产品/测试文件哈希与上节统一分支一致；没有 force/reset、没有修改 vLLM/FlagGems、没有创建提交/推送/PR，也没有更改已有 Git remote。分支是固定提交的本地部署分支，不声称设置了新的远端跟踪或自动更新。

过程脚本在远端 `02-issues/plugin-support-*.py`，原生结果统一在 `04-runs/plugin-support-minicpm47-20261008/`。`switch.json`、`switch.log` 记录备份、传输及切换结果。实际任务先做契约和离线验证，通过后才允许精确重启旧 API PID `425141` / start tick `415865981`。

### 已完成的前置验证

- 容器正常 pytest 入口：canvas 7 项、backbone 7 项，共 **14 passed、1 warning**（8.46 秒），见 `unit.log`。
- 当前 1B checkpoint 的 thumbnail、portrait、slice、video 位置对照 **4/4 逐元素一致**，且满足 vLLM decode delta 契约，见 `canvas-reference.json`。
- 空闲 PPU3 使用正常安装的模型类，BF16/TP1、eager、50,000 诊断上下文、前缀缓存开启。224/448 红蓝单图及新 225 双图 **5/5 最终答案正确**，135 次真实 encoder attention 输出均有限，实际命中安装 FlagGems flash 路径；见 `offline-result.json`。客户端 token 上限 192，检查最终答案而非只检查 thinking 文本。没有更改服务上下文。
- 离线退出出现 `destroy_process_group() was not called` 警告，保留在日志，不描述为无警告运行；设备释放及进程退出在最终核对中确认。

旧服务通过两次零在途指标检查后精确 TERM，确认其进程树退出，再使用未修改的根 `start-model.sh` 启动新 API PID `445525` / start tick `416200430`，argv SHA-256 `5ae8f440558e94c9ac47e3288804c0b01df0de0cb4cb7e798681ffe389d2db49` 与旧服务相同。根脚本 SHA-256 仍为 `0c9f9441a02125426ebc799d5eba81d37919db950ed83fa3345a0be985c27a45`；沿用用户当前的 FULL_AND_PIECEWISE、默认 262144 上下文、现有 index 黑名单及关闭前缀缓存设置，以隔离 Plugin 替换。此设置是用户当前服务的诊断对照，不重标为正式验收配置。

### 服务回归与最终结论

新服务实际 BF16、TP1、默认 `max_seq_len=262144`，FULL_AND_PIECEWISE 的混合 prefill/decode PIECEWISE 与 decode FULL 均捕获 **51/51**。沿用当前配置 `compile_mm_encoder=False`、`cudagraph_mm_encoder=False`，不声称视觉 encoder 自身已被捕图。

HTTP 基础验证 **35/35 正确、均 HTTP 200 且 finish_reason=stop**：

- 顺序 15 项：文本、红蓝绿黄 224/448 单图、红蓝双图、绿色 224×672 竖图、1200×900 红→蓝→红切片及红蓝双帧视频。
- 大图每次实际 prompt tokens=490，超过单图 93，且三次最终颜色正确；双帧视频采用 `data:video/jpeg`、prompt tokens=168、最终回答 `Red, Blue`。未覆盖 MP4/PyAV 解码。
- 对前十项文本/单图/双图执行两轮 10 并发，共 20 项；响应和服务身份均稳定。
- 客户端 `temperature=0, seed=0, max_tokens=192, chat_template_kwargs.enable_thinking=False`，逐项检查最终答案及双图/视频顺序，不运行正式评测。首次大图请求约 67.6 秒，后续同形状蓝/红均正确；编译缓存复用和少量请求耗时不能作为性能对比或冷启动指标。

`service-smoke.json` 的前后 API PID/start tick/argv 哈希一致；`restart.log` 最终为 `RESTART AND SMOKE PASSED`。截至 16:00:15（Asia/Shanghai），容器保持原 ID 且运行中，API PID `445525` / start tick `416200430`、端口 8000 `/health=200`；PPU2 EngineCore 宿主 PID `674961`。PPU3 诊断进程已退出、显存回到 1 MiB；PPU0/1 原 Worker PID `330179`、`330180` 保持，本轮未操作其他服务。

最终新进程实际 import 指向同一 `/workspace/vllm-plugin-FL/vllm_fl/`，源代码为指定提交、工作树干净，没有 PYTHONPATH。四文件 SHA 与上节分支记录一致，FP32 专用实现不存在；FlagGems 的 Flash API/kernel、index_put 三个已修复安装文件哈希不变；vLLM HEAD 仍为 `ee0da84ab9e04ac7610e28580af62c365e898389`、工作树干净，根启动脚本哈希不变。普通导入检查仍打印当前 empty vLLM 缺少 `vllm._C` 的警告，保留记录；正常 Plugin 推理及全部基础验证通过，未为此改装 CUDA vLLM。

**结论：已保留 `support-minicpmV4.7@aa4228e`，当前 PPU 服务实际使用统一 Plugin 代码并通过本轮基础验证。** 设计范围仍是当前 PPU 1B BF16/TP1：同一模型级注册/视觉/canvas 协议、原生 attention 加已修复 FlagGems；不新增 PPU 特例、公共 worker/dispatch 改动或重复适配器。MoE、其他并行拓扑、量化和平台没有在本轮验证。index 黑名单保持，不据此声称 index 修复启用后的长负载正常；未执行正式精度、性能、镜像构建或打包验证，`framework.yml` 历史验收状态未更新。

原生证据在远端 `04-runs/plugin-support-minicpm47-20261008/`，最终汇总 `final-verification.json` 为 `passed`，前置控制快照 `preflight-control.txt`；备份在上述 `05-tmp/.../before/`。两个异步任务 `j408841139326.586340`（切换/单测/canvas/离线）、`j271573918987.612636`（重启/服务）均结束且 rc=0，实际时间分别 15:52:43–15:56:28、15:53:53–15:59:32；第二个任务先等待离线完成，没有提前重启。

| 关键证据 | SHA-256 |
|---|---|
| `switch.json` | `d572d0c2876e65186f63d20d2b8f9406a27d599b54b3ec44d511fe064118de3e` |
| `unit.log` | `89154d0621cd06288b0c2e934714efd3de88f27f816ca6eae69bfe2aa7ac411c` |
| `canvas-reference.json` | `73b51d6af238321809298bc4dac8b1b612a0c72544ef43bae395172117d85be0` |
| `offline-result.json` | `f46944e63bd98d3b501840e995d3fedf819adcbc593609e729598ab20dc8d188` |
| `new-startup.log` | `499a779af47cdca9b42a66b49cf14cab728289957931656f0c586d1a05117952` |
| `service-smoke.json` | `ba5a3b459f98f2e60861498429b8ac147d7863335cd337150480961cd31ac037` |
| `restart.log` | `b5554d07e8dbcf5a5b39d40f56eacd9b883582af478910d8f3379486de901ab6` |

本地 AST/Markdown 空白与 `git diff --check` 通过；`./scripts/syntax-check --offline` 的 252 项 workflow 测试（1 skipped）、6 项 operations 测试通过，命令整体仍因既有 workspace audit 的 12 项 profile revision 错误/78 项待复核返回 1，未改写历史绑定以消除错误。
