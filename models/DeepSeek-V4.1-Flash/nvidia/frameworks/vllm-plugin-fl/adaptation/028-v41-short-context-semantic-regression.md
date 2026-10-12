# 028：超过约 160 token 后整模回答失真

## 元数据

- 状态：`verified`（2048-token eager 固定请求已由单变量前后对照修复；18K 与 graph 另验）
- 首次出现／最后验证：2026-09-24
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- 平台与 Host：NVIDIA H100 × 8，`H100-149`
- 容器与镜像：`deepseek-v41-plugin-adapt-20260923`，`deepseek-v41-plugin-fl:h100145-20260923-r1`
- Plugin / FlagGems / FlagGems-vllm / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `7cd137ccaf09f25ce3012ba86438682072a69bc9` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8 eager、FP8 KV、前缀缓存启用、`max_model_len=18000`、`max_num_batched_tokens=512`、`max_num_seqs=16`；默认非思考聊天模板、temperature 0、最多 32 输出 token。

## 问题现象

18K eager 服务可加载真实权重、通过 `/health` 并对短请求输出 `2`，但对较长提示会输出填充内容、错误数字或道歉文本。所有错误样本都由服务正常返回，不能将 HTTP 成功或无算子异常当作语义正确性。相同格式的“忽略无关填充，只回答末尾 1+1”请求在 156 prompt token 答对；190 token 返回 `1` 后续写填充；即使换掉“记录”格式，184–1050 prompt token 也不稳定。17,037-token 多样记录提示同样失真。原始回执均在 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-candidate-eager-20260924/`：`long-varied-smoke.json`、`length-sweep/`、`boundary-sweep/`、`window-sweep/`、`neutral-sweep/`。一-off 输入脚本在同根 `02-issues/h100149-candidate-20260923/`，没有写入产品源码。

## 已有经验匹配

已检索 `docs/troubleshooting/` 与本模型问题 005、012、024、025、027；没有与“真实权重 H100 eager 在约 160-token 附近语义失真且请求成功”完整匹配的已验证条目。问题 012 的候选块过滤先前只在超过 16,384 个压缩位置时可能改变结果，本次失真远早于该范围；问题 027 是 graph 预热/捕获路径分歧，当前复现于 eager，不能套用。

## 诊断与假设

已验证：在 18K 配置下，前缀不同的 100/128-token 用户消息分别得到 134/156-token 服务提示，均输出 `2`；160-token 用户消息对应 190-token 服务提示，首先输出 `1` 并继续生成错误内容。256–15,000-token 多个长度均失败。无“记录”格式的普通词语和数字填充也失败：`words-160` 初始 `2` 后又生成道歉，`digits-160/256` 输出 `1`，`words-1024` 开始续写填充。256-token 级失败低于 512-token 单步预填充上限，也低于候选块过滤容量，因此两者目前没有独立解释力。模型声明 `sliding_window=128`，失真区间与越过该窗口后的 SWA／压缩缓存／稀疏索引组合有关，但这只是待验证假设。

FlagGems-vllm 预填充算子的 TLE 与普通 Triton 路径已用 100、160、224、288、352 个有效索引的 H100 随机 BF16 输入比较：最大差 `0.0001221`，两者相对 PyTorch 参考最大差小于 `0.00014`，见 `04-runs/h100149-candidate-eager-20260924/flashmla-compare.json`。这仅排除该算子在上述孤立形状中的明显数值错误，不能排除真实 metadata、KV 缓存内容或其他层的错误。

另对 FlagGems-vllm `bucket_sort_topk` 的“有效键少于 `K=512`”场景做隔离试验。生产默认选用的 TLE 路径在宽度 64–512、有效数 20–250 的 23 个组合中，前缀恰好是所有有效索引、尾部全为 `-1`，回执在 `04-runs/h100149-fullcoverage-512-20260924/topk-short-tle-only.json`。直接调用同库旧 Triton 路径时触发 CUDA illegal memory access，失败命令和栈由 `02-issues/h100149-candidate-20260923/topk-short-compare.py` 的 Ansible 执行保留；这不是当前默认 TLE 路径的失败证据，也不能单独解释运行中服务的语义失真。后续若产品需要该库的 fallback，应单列原库缺陷与最小复现，不应无证据修改 Plugin。

Plugin 候选块实现另以 100、156、190、256 个有效位置及非零起点做 8 行受控测试：每行所有合法候选块均被选择，掩码保留的有限元素恰好等于合法区间；回执在 `04-runs/h100149-fullcoverage-512-20260924/candidate-fullcoverage.json`。该检查覆盖失真边界的候选预算，但不覆盖实际索引 logits、KV 内容或多层组合。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 设置与证据 | 结果 | 结论 |
|---|---|---|---|---|---|
| 1 | 用户消息长度 | 同一记录格式、100 token | 1024–15000 token；`length-sweep/` | 100 正确，其余失败 | 错误不只在 >16K |
| 2 | 首段前缀及长度 | 记录格式、不同请求共享前缀 | 每长度不同开头；`boundary-sweep/`、`window-sweep/` | 156 prompt token 正确，190 起失败 | 共享前缀不足以解释 |
| 3 | 填充内容 | 记录式填充 | 普通词与数字；`neutral-sweep/` | 184–1050 prompt token 均未严格正确 | 不是单一提示格式问题 |
| 4 | 稀疏预填充实现 | FlagGems-vllm TLE | 同库普通 Triton，孤立随机输入；`flashmla-compare.json` | 最大差 `1.2e-4` | 未发现该孤立算子失真 |
| 5 | top-k 内核 | 默认 TLE | 同库旧 Triton，键数少于 `K=512` | TLE 23/23 数组合同通过；旧 Triton 发生非法访存 | 旧路径需独立报告，当前整模根因仍待定 |
| 6 | 候选块完整覆盖 | 2048 块预算 | 100–256 位置、起点 0/64，8 行；`candidate-fullcoverage.json` | 8/8 掩码合同通过 | 单独候选过滤未解释短提示失真 |
| 7 | 索引路径 | 18K 服务、正常 sparse indexer | `max_model_len=512`，同样的 160/256-token 中性提示，见 `01-environment/h100149-plugin-20260923/start-fullcoverage-512.sh` | 4/4 错误输出与 18K 服务逐字一致；`04-runs/h100149-fullcoverage-512-20260924/probe/` | 候选筛选不是本次失真的充分原因 |
| 8 | 前端思考强度 | 512 服务、相同四个输入、`reasoning_effort=none` | 仅改请求 `reasoning_effort=high`，最多 200 生成 token；`04-runs/h100149-fullcoverage-512-20260924/effort-high-probe/` | 4/4 到长度上限，响应正文包含思考文本且无 `reasoning_content` | Plugin 尚未注册 V4.1 reasoning parser；不足以判断模型输出的最终答案 |
| 9 | 框架实现 | Plugin 512-token 全覆盖服务 | 同机 NV 原生 vLLM 2048-token 服务，其他关键执行条件一致；`04-runs/h100149-native-control-2048-20260924/probe/` | 四个相同提示在原生服务全部正确，Plugin 全部错误；输入 token 数完全相同 | 聚焦 Plugin/锁定版 vLLM 的整模集成；服务上限差异仍需考虑 |
| 10 | 混合 KV 缓存管理 | Plugin 512-token 全覆盖服务 | 仅增加 `--disable-hybrid-kv-cache-manager`；`01-environment/h100149-plugin-20260923/start-hma-disabled-512.sh`，`04-runs/h100149-hma-disabled-512-20260924/service.log` | 权重加载后在缓存初始化报 `No common block size for 64`，API 从未就绪，未运行四个提示 | 锁定版 vLLM/Plugin 的该诊断配置本身不兼容，不能判断 HMA 是否导致语义失真 |
| 11 | 服务长度上限 | 原生 vLLM 2048-token 对照、Plugin 512-token 对照 | Plugin 保留 HMA、改为 `max_model_len=max_num_batched_tokens=2048`，其他执行条件保持；`01-environment/h100149-plugin-20260923/start-matched-2048.sh`、`04-runs/h100149-plugin-2048-20260924/probe/` | 四个输入 token 数与原生完全一致（184、281、186、282）；Plugin 4/4 错且与其 512 服务逐字相同，原生 4/4 对 | 排除服务长度上限差异作为两边结果不同的原因；聚焦整模实现或运行时集成 |
| 12 | 真实预填充各层隐状态 | Plugin 2048-token 错误样本 | 只在 `02-issues/h100149-candidate-20260923/sitecustomize.py` 注入一次性层输出采样，不改产品源码；`04-runs/h100149-plugin-layertrace-20260924/` | 固定 `digits-160` 为 186 prompt token，仍输出 `1`；40/40 层 rank 0 文件齐全 | 追踪没有消除错误；须与相同请求的原生逐层输出对照，不能只凭 Plugin 自身张量定根因 |
| 13 | 同机原生分层对照及完整 token ID | Plugin 第 12 轮 | 原生同样 TP8 eager、FP8 KV、2048-token、前缀缓存及固定请求；`04-runs/h100149-native-layertrace-20260924/`、`h100149-layertrace-compare-20260924/summary.json` | 原生返回 `2`，Plugin 返回 `1`；两边 186 个完整 prompt ID SHA-256 都是 `c5cf81ab83e83cf422631c061c2cf162b15dc28106b5bc53d331cece7afe61a8`；第 0 层 position 63/127 的 `x` 余弦分别仅约 0.869/0.646 | 输入编码相同，失真在纯 SWA 第 0 层已可观测；ratio-2 压缩器不可能是最早分叉点，需查第 0 层注意力与相关权重/算子 |
| 14 | 第 0 层真实 SWA 元数据与 FlashMLA 数值 | 第 13 轮第 0 层分叉 | Plugin 固定请求上只附加同一 `q/kv/indices` 的 FlagGems-vllm 普通 Triton 和 PyTorch 对照，不替换原输出；`04-runs/h100149-plugin-flashmla-oracle-r2-20260924/` | 仍输出 `1`；186 个 SWA 槽均有效，位置 63/127/128/185 的索引区间符合 128-token 窗口；默认与同库 Triton 最大差不超过 `0.00390625`，相对 PyTorch 的五处均值绝对误差最高约 `0.000126` | 第 0 层 FlashMLA 计算和 SWA 索引未复现足以解释大幅隐状态失真的错误；继续查上游 q/kv 值 |
| 15 | 首层真实权重 mHC 预混合 | 第 13–14 轮 | 从同一 checkpoint 读取首层 mHC 权重及完整 prompt embedding，空闲 H100 单卡分别运行 Plugin Triton 与原生 TileLang；`04-runs/h100149-layer0-mhc-realweight-20260924/{plugin,native}.pt` | 五个位置的 embedding 与 BF16 `layer_input` 逐元素相同；混合系数最大差约 `1.8e-5` | 首层 mHC 预混合不是该层大幅分叉来源；差异在后续注意力投影、KV 内容或其关联元数据中 |
| 16 | 真实首层注意力 Q/KV 与算子协议 | 第 13–15 轮 | 两容器顺序运行同一 186-token 请求，采集 rank 0 首层完整 `q/kv/indices/lengths/output`；`04-runs/h100149-{plugin,native}-attnraw-20260924/` | Plugin 回答 `1`、原生回答 `2`；186 行有效索引与长度完全一致，五个采样位置 KV 逐元素相同；Q 整体余弦约 `0.9765`，Plugin 每个有效 head RMS 恰为 1，原生约 1.4–2.6；按 token/head 标量拟合后 Q 平均相对残差约 `0.00216` | Q 被多做一次 RMSNorm；原生 `_C` 新协议有 `apply_q_norm` 参数且 V4.1 调用为 `False`，现用 FlagGems-vllm 旧协议总做 QNorm |
| 17 | 复用已有库构成 V4.1 skip-QNorm 路径 | 第 16 轮接口差异 | FlagGems-vllm 现有融合算子负责 KV 写入，输入一头零值 Q；FlagGems 通用 interleaved RoPE 仅处理真实 Q 的后 64 维；与原生 `apply_q_norm=False` 直接对照 1/17/33/64/186 token | 同一确定性输入哈希逐项一致；五个长度的 Q 输出及 KV cache 均逐元素相同；`04-runs/h100149-v41-qrope-contract-20260924/{plugin,native}.pt` | 两库已有算子可组合实现当前缺失的 skip-QNorm 语义，无需新增 Triton |
| 18 | Plugin 产品修补与聚焦测试 | 第 17 轮算子合同 | 仅在可写 Plugin 的 `vllm_fl/models/deepseek_v4_1/attention.py` 中将 H100/uint8 缓存导向新 `nvidia/q_rope_kv.py`；其他路径维持原 dispatch；新增 `tests/models/deepseek_v4_1/test_skip_qnorm_q_rope.py` | PyTorch oracle 的 1/17/33/64/186-token 测试及 CUDA graph 捕获/两次变输入 replay 共 6/6 通过，`04-runs/h100149-v41-qrope-contract-20260924/plugin-pytest.log`；`git diff --check` 通过 | Plugin 层局部实现已验证单算子和 graph replay 合同；整模回归仍在执行，尚不能宣称语义修复 |
| 19 | 相同 2048-token 配置的整模前后回归 | 修补前 Plugin 4/4 错、同机原生 4/4 对；保持 TP8/eager/FP8 KV、前缀缓存与四个提示不变 | 修补后启动 `01-environment/h100149-plugin-20260923/start-skip-qnorm-2048.sh`，运行相同 160/256-token 词语/数字提示及 1024/1800-token 扩展；`04-runs/h100149-plugin-skip-qnorm-2048-20260924/{probe,long-probe}/` | 8/8 回复严格为单个 `2` 且 `finish_reason=stop`；总 prompt token 为 184/186/281/282/1048/1050/1824/1825 | 额外 Q RMSNorm 是先前短上下文回归的根因；当前修补已恢复这些固定请求，18K、graph、并发和正式精度另验 |
| 20 | 原始 18K 分块服务和超过候选预算的长提示 | 第 19 轮 2048-token eager 通过；原 18K 服务同样提示错误 | 修补后以 `max_model_len=18000`、`max_num_batched_tokens=512`、其余 TP8/eager/FP8 KV/前缀缓存不变启动；复用原提示脚本，仅改新输出目录；`04-runs/h100149-plugin-skip-qnorm-18k-20260924/` | 四个 160/256、四个 1024/1800 用户 token 提示 8/8 严格输出 `2`；17,037-prompt-token 多样记录提示也输出 `2`、`stop`，回执 SHA-256 `7e4a0321b67a0b171b5fec0fcc5ad0bdf81bd371016ccc4782e41cf3c20f3744` | QNorm 修补覆盖此前错误的 18K 配置、512-token 分块和该 17K 真实提示；不能由单样本推出任意长上下文或 graph 正确性 |

第 7 轮只改变配置的 `max_model_len`，使压缩后所有位置都在 `index_topk=512` 内，Plugin 使用全覆盖索引捷径；前缀缓存与其余启动参数保持一致。18K 服务 PID `62385` 已按路径、模型、端口和 eager 参数核对后发送 `SIGTERM`，端口空闲且 8 张 GPU 均为 0 MiB；未停止容器。512-token 诊断服务 PID `70792` 已核对真实权重加载、启动参数和 `/health`，四个中性提示与 18K 服务的错误输出逐字一致；随后已按精确 PID 和命令核对并停止，容器保持运行。

同机 NV 原生容器 `deepseekV4.1-flash-native-driverfix` 对照服务以同一模型、H100 TP8、FP8 KV、eager 和启用前缀缓存启动；因原生多模态预算下限，设置 `max_model_len=max_num_batched_tokens=2048`。复用同一提示脚本，四个中性提示的输入 token 数分别与 Plugin 完全一致（184、281、186、282），全部输出 `2` 并正常停止，回执在 `04-runs/h100149-native-control-2048-20260924/probe/`。原生服务 PID `55703` 在验证后已按精确进程核对并停止；两个容器均未重启。先前原生 512-token 服务在加载权重前因预算小于 1025 而拒绝启动，见 `04-runs/h100149-native-control-512-20260924/service.log`，不是模型正确性失败证据。该对照确认问题位于 Plugin/锁定版 vLLM 路径，而非提示或权重本身；随后第 11 轮 Plugin 2048 同长度对照也排除了服务上限差异，但仍不能单独定位某个模块。

HMA 诊断服务从 2026-09-24 14:59:40 CST 启动，TP8 真实权重加载后于 15:31:20 在 `ModelRunnerFL.initialize_kv_cache → prepare_kernel_block_sizes → select_common_block_size` 失败。`--disable-hybrid-kv-cache-manager` 将异构缓存规格合并，当前 Plugin worker 与锁定版 vLLM 找不到共同的 64-token 内核块大小。API 未开放，探针未执行；失败服务已自行退出，8 张 GPU 显存均归零，容器仍运行。该失败属于诊断配置的启动阻断，不是关闭 HMA 后的模型精度结果，也不能作为原语义失真的根因证据。

随后 Plugin 2048-token 服务 PID `78174` 于 2026-09-24 16:15:24 CST 完成启动并通过 `/health`；与原生对照保持相同的 `max_model_len=max_num_batched_tokens=2048`，TP8、FP8 KV、eager、前缀缓存启用。固定四个输入的 prompt token 数与原生逐项完全相同，Plugin 四个输出则与其 512 服务逐字一致并全部判错，原生四个均为严格 `2`。回执 `04-runs/h100149-plugin-2048-20260924/probe/{words,digits}-{160,256}.json` 与 `probe-summary.jsonl`。该服务在四份回执核对后按精确 PID／模型／端口／参数发送 `SIGTERM`，端口空闲、8 张 GPU 显存均为 0 MiB；容器仍运行。两边长度配置已匹配，不能再把服务上限差异当成解释。

2026-09-24 17:16 CST 的 Plugin 分层诊断服务仍使用相同的 TP8 eager、FP8 KV、2048-token 上限和前缀缓存；`sitecustomize.py` 只对 186-token 固定请求在每层保存 rank 0 的少量隐状态，服务启动前无追踪文件。该请求得到 `completion="1"`、`prompt_tokens=186`，40 层输出均保存于 `04-runs/h100149-plugin-layertrace-20260924/layers/`。已在回执及文件核对后按 PID `81763`、命令、模型和端口停止该服务；端口空闲、8 张 GPU 均为 0 MiB，两容器保持运行。注入前后 Plugin 错误一致，尚未获得原生层级对照，不能据此判定最早失真层。

同机原生分层服务于 2026-09-24 17:55 CST 使用相同固定请求，得到 `completion="2"`、`prompt_tokens=186`，40 层文件完整，见 `04-runs/h100149-native-layertrace-20260924/`。在两边已注册的 V4.1 tokenizer 上离线重建这条请求，完整 186 个 token ID 序列的 SHA-256 都为 `c5cf81ab83e83cf422631c061c2cf162b15dc28106b5bc53d331cece7afe61a8`；不是仅靠 token 数一致推断输入相同。rank 0 层输出逐位置比较见 `04-runs/h100149-layertrace-compare-20260924/summary.json`：第 0 层 `x` 在 position 0 的余弦为 `0.999953`，但 position 63/127/128/185 分别为 `0.869059`、`0.646162`、`0.844952`、`0.869424`；`residual` 在 position 63/127 的余弦也仅 `0.930515`、`0.899401`。第 0 层是纯 SWA，尚无 ratio-2 压缩器，因此其环形槽实现不能解释最早分叉。差异也不能只归因于超过 128-token 窗口，因为 position 63 已明显不同。原生服务在采样后按 PID `63316`、模型和端口核对并停止，端口空闲；两容器保持运行。

为进一步隔离第 0 层 FlashMLA，使用只读产品源码的一次性真实请求钩子：保留原 FlagGems-vllm 输出，并对相同的 `q/kv/indices` 追加调用同库普通 Triton 路径及 PyTorch 参考，不将对照输出送入模型。第一次诊断钩子误按位置参数读取实际为关键字参数的 `_forward_prefill`，在权重加载前即发现并停止服务；对应未完成的启动日志保留在 `04-runs/h100149-plugin-flashmla-oracle-20260924/`，不能当作模型/算子错误。修正版使用单独的 `flashmla-oracle-r2` 目录和 `04-runs/h100149-plugin-flashmla-oracle-r2-20260924/`，仅在 rank 0 固定请求采样；验证结果如下。

修正版于 19:00 CST 后通过真实固定请求，仍返回 `completion="1"`，见 `04-runs/h100149-plugin-flashmla-oracle-r2-20260924/probe.json`。`layer0-metadata.json` 显示第 0 层 186/186 个位置均有有效 SWA 槽，32-token 页，单个预填充请求；第 0 层位置 0、63、127、128、185 的实际索引数量分别为 1、64、128、128、128，窗口起点符合预期，最后位置的索引为 58–185。`layer0-flashmla-oracle.json` 对这些真实 q/kv/indices 的默认 FlagGems-vllm TLE、同库普通 Triton 和 PyTorch 分别计算：两实现最大绝对差不超过 `0.00390625`，五处默认输出相对 PyTorch 的均值绝对差不超过约 `0.000126`；最大绝对差约 `0.00394` 处于 BF16 输出舍入量级。未发现足以解释第 0 层 0.35–0.44 residual 相对 RMS 差的算子或索引问题。诊断钩子 SHA-256 为 `a65ff221028d52e07e6dc16f256d8fc7f307a2df05a837db9e03c7dbd78e580d`，启动脚本 SHA-256 为 `d2be38951df38d7ee37b75a62d9cd0eeb4affc3235eb57386bea0afc3081ac45`；服务 PID `85765` 在完整回执后经命令核对并停止，端口空闲、8 张 GPU 均为 0 MiB，容器保持运行。由于 SWA 所有槽有效，前述“复用 SWA 有效位导致压缩状态缺失”的源码假设在此样本也没有支持证据。

空闲 GPU 上使用完整 186-token 输入和检查点 `embed.weight`、`layers.0.hc_attn_*`、`layers.0.attn_norm.weight` 做首层 mHC 预混合对照：Plugin Triton 与原生 TileLang 的输入 embedding 和 BF16 `layer_input` 在五个采样位置逐元素相同，`post`/`comb`/`next_pre` 系数最大差分别约 `6.5e-6`、`2.6e-6`、`1.8e-5`，见 `04-runs/h100149-layer0-mhc-realweight-20260924/{plugin,native}.pt`。用相同首层嵌入与系数从分层 `residual` 反推注意力输出，在 position 63/127 的估算余弦约 `0.785/0.689`；BF16 反推有舍入误差，不能替代直接捕获注意力 q/kv，但进一步支持分叉位于 mHC 预混合之后、FFN 之前。下一步需直接比较两边第 0 层注意力投影与缓存写入/读取值，不能因孤立算子通过就宣布整模正确。

对独立算子补充测试：FlagGems-vllm SWA 写入对其 PyTorch oracle 在 32/33/128/156/190/282 token 的 32-token 页边界均通过；FlagGems 解量化 gather 在 156/190/282 token 的跨页随机输入均通过，回执分别为 `04-runs/h100149-native-control-2048-20260924/qnorm-cross-page.json`、`gather-cross-page.json`。FlagGems-vllm INT8 scaled-mm 在 64–282 行与量化 FP32 参考逐元素一致，见同目录 `scaledmm-shape-check.json`。Plugin mHC 预混合与原生 TileLang 对相同随机输入的误差在各长度平稳（系数最大绝对差小于 `3.5e-4`；BF16 层输入均值绝对差小于 `2e-7`），见 `mhc-compare.json`。FlagGems-vllm 稀疏预填充以 184 个变长查询、压缩区和 SWA 区重复键比较 TLE、Triton 与 PyTorch，最大 TLE/Triton 差 `2.45e-4`，见 `sparse-realshape.json`。MoE top-k 的 FlagGems-vllm 与原生算子在 64–282 行的所有专家 ID 完全一致、权重最大差小于 `9e-8`，输出张量保存在 `02-issues/h100149-candidate-20260923/topk-{plugin,native}.pt`。FlagGems W8A8 专家计算与同机原生 vLLM 使用相同随机 INT8 权重／输入作 64–282 行比较，输入摘要一致，输出平均绝对差约 `2.0–2.2e-4`、原生 RMS 约 `0.027–0.029`，各长度没有明显跳变，原始张量在同一 `02-issues/` 下的 `moe-{plugin,native}.pt`。两种 INT8 量化在同种子 4096 宽输入上的 scale 差小于 `5e-10`，极少数量化元素因舍入边界相差一档，见同目录 `int8quant-{plugin,native}.pt`。这些测试排除了对应孤立算子的明显形状阈值错误，但不证明真实缓存内容、权重加载和整模元数据正确。

另对 Plugin 的完整 W8A8 O 投影（逆 RoPE、分组、动态 INT8 量化、FlagGems-vllm scaled-mm）在 H100 上用单 rank 实际维度 `8×512 → 4096×1024` 及 64、128、156、184、190、282 行比对量化 PyTorch oracle：分组输出与 O 投影 BF16 输出逐元素一致，六种长度的最大／均值绝对差均为 0；`02-issues/h100149-candidate-20260923/oproj-shape-check.py`、`04-runs/h100149-plugin-2048-20260924/oproj-shape-check.json`。这仍不是实际模型权重／整模隐状态对照。

另与模型随附只读 `encoding/encoding.py` 对照发现 Plugin 原 `reasoning_effort` 映射 `low=25/high=50` 与资料 `low=50/high=75` 不同。已仅在可写 Plugin `vllm_fl/tokenizers/deepseek_v41_encoding.py` 修正，保留兼容扩展 `xhigh=75`；用相同 system/user 文本比较非思考及 high 思考编码，提示字符串与模型资料完全相同，Plugin `git diff --check` 通过。该源码更正不影响已运行服务的内存中配置，也不解释非思考模式的短上下文失真，不能因此宣称根因修复。

同机进一步直接比较 Plugin 与 NV-native 的 `deepseek_v41_encoding.py` 源码：除 `low/high` 思考强度映射外逐行相同，非思考提示编码函数没有实现差异；四个固定请求的服务端 prompt token 数逐项相同。这支持继续聚焦模型执行路径，但 token 数相同本身并非完整 token ID 数组的哈希回执。

新的待验证差异：NV 原生服务的 V2 model state 从完整请求 token 历史向 Engram 传入 `lookback_token_ids`；Plugin 锁定的 V1 runner 只从 `DeepseekV41LegacyModelState` 传入稳定 `request_slots`，Engram 因而用 SWA 页关联的 slot cache 回退读取跨 chunk n-gram 历史。它可能在滑动窗口页回收、前缀缓存或 chunk 边界与 V2 路径不同，但 184–282-token 请求低于 512-token 单步预算，若确为单次预填充，其首个生成 token 的 Engram n-gram 直接读当前输入，该差异不足以解释首 token 已错误的样本。尚无实际哈希差异回执；不能仅凭源码差异将其定为根因，也不应为本问题直接发布未经证明的修补。

真实请求第 0 层 Q/KV 原始张量分别见 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-plugin-attnraw-20260924/layer0-attention.pt`（SHA-256 `b4f8885ced8098b11c1e8950a223a912b05916b3f6d2f0270b83e9cbcfbfe5e9`）和同根 `h100149-native-attnraw-20260924/layer0-attention.pt`（`199b04bad7ed065abb19c3389918bded573eeb67c69bd557e875eeab5a77a147`）。结构化对比和产物 SHA 见 `04-runs/h100149-attnraw-compare-20260924/summary.json`：两边 186 个位置与有效索引完全一致；Plugin 有效 Q head 的 RMS 约为 1，原生为 1.37–2.62，按每 token/head 比例拟合后平均相对残差约 `0.00216`。两次请求分别由当前任务的 `01-environment/h100149-plugin-20260923/start-{plugin,native}-attnraw.sh` 发起；固定请求脚本在 `02-issues/h100149-candidate-20260923/layertrace-digits160-probe.py`。诊断钩子 SHA-256 为 `42320de300a6770c59c1c6b09b3178c69ca9f78156191dd9d76ef01f94d37f8d`。采样后 Plugin PID `89201` 与原生 PID `71426` 均按进程命令、模型和端口核对并停止，两容器保持运行。

单算子对照复用 FlagGems-vllm 的 `fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert` 写入 KV，同时把其 Q 输入限制为一头零值；真实 Q 的后 64 维由 FlagGems `apply_rotary_pos_emb(..., rotary_interleaved=True, inplace=True)` 旋转，前 448 维不归一化。原生端直接调用 `_C.fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert(..., apply_q_norm=False)`。1/17/33/64/186-token 的输入哈希相同，Q 及缓存逐元素相同；原始张量 SHA-256 分别为 `2188b3abbe15b5c3252cf6b177009cc0bd9ea9bf3a50bc92407e60f0bc884d06`、`fd4caef1136310d12145ffa8da53a4bfed6a524966dba658924b46663138c8b2`。这验证算子组合，不代替修改后的整模推理验证。

## 根因及实现边界

已验证的首个数值协议差异位于 V4.1 H100 `fp8_ds_mla` 的 Q RoPE/KV 写入边界：现用 FlagGems-vllm V4 融合算子总做 Q RMSNorm，原生 V4.1 明确关闭该操作。已在 Plugin 的 V4.1 H100/uint8 分支组合现有 KV 写入和 FlagGems 通用 interleaved RoPE，不改锁定版 vLLM、FlagGems 或 FlagGems-vllm 源码。模型专用语义留在 V4.1 attention adapter；其他平台、BF16/普通 FP8 缓存与 V4 调用保持原路径。聚焦测试和相同 2048-token eager 整模前后对照均通过，证明该差异解释本问题的固定短提示；18K 长上下文与整模 graph 仍需独立验证。

## 验证与下一步

- eager：修补前 160-token 起语义回归、512-token 全覆盖对照同样失败；修补后 2048-token 和 18K 服务对 160/256/1024/1800 用户 token 的词语/数字提示各 8/8 严格通过。18K 的 17,037-prompt-token 多样记录请求也返回 `2` 且正常停止。原始响应在 `04-runs/h100149-plugin-skip-qnorm-{2048,18k}-20260924/`，各份 SHA-256 已核对。服务 PID `92242`、`96049` 分别在样本完整、命令核对后 SIGTERM 停止，8012 端口空闲、8 张 GPU 均回到 0 MiB，容器保持运行。
- graph：问题 026/027 另有阻断，尚未完成整模验证；本问题不得据孤立 TLE 对照宣称 graph 通过。
- 正式精度和性能：不在本次已选阶段，尚未运行。
- 知识库处理状态：`needs-validation`；根因和跨模型适用范围未确定，不推广。
