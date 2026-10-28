# 002：单图请求产生重复标点

## 元数据与现象

- 首次出现：2026-09-28；最后验证：2026-09-29；状态：`mitigated`，
  底层 BF16 SDPA 错误机制尚未完全确定。
- 目标：`PPU-13` / `minicpmV4.7-35B` / PPU-ZW810E，镜像
  `sha256:52536a088a055b2c24cdfca21d0ea9e8d68c1f5f82fee7a40f7ec8f72e4a`。
- Plugin 基准 HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`，
  当前未提交适配改动；vLLM 源码 HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`；
  FlagGems checkout HEAD `1a38df24f72ca5a4a6a24650b5d66356709750ba`，未同步。
- eager TP2、PPU 设备 0/1、50,000 token 上限；前缀缓存当时未显式设置，
  后查明生效值为 `False`，见[005](005-prefix-cache-effective-default.md)。
  64×48 红色 PNG 图像的聊天请求收到 HTTP 200，90 个 prompt token、128 个
  completion token；正文连续 128 个 `!`，`finish_reason=length`，耗时 86.035 秒。
  原始结果：`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/04-runs/eager-tp2-v1/image-smoke.json`
  （SHA-256 `dfc74279185e7242f38603ec8b15a51a23f88a267269414f293495e98825649a`），
  同目录 `image-probe.log`、`service.log`。同一服务纯文本请求返回 `42` 且正常停止，
  `text-smoke.json` SHA-256 `465125808573aae42ba42f557c2ed413d01e41ac04dd1e666b49f66cf1189426`。

## 已有经验及假设

NVIDIA 同权重的[历史问题](../../../../../MiniCPM-V-4.7-35B-A3B/nvidia/frameworks/vllm-plugin-fl/adaptation/002-minicpmv47-moe-canvas-mrope.md)
涉及相同模型结构和 canvas M-RoPE，但硬件、镜像、Plugin revision 不同；
只能作为接口假设。当前 `docs/troubleshooting/` 没有完整匹配签名。

已验证：合成位置向量与 checkpoint 参考函数一致、纯文本解码正常；
合成测试未覆盖真实图像处理或视觉数值。待验证假设包括真实图像预处理、
视觉占位符与 target sizes、视觉权重映射、位置增量、PPU 视觉算子数值。
尚无已验证根因，不能将 HTTP 200 视为图像路径通过。

## 受控尝试与下一步

| 轮次 | 单一检查 | 结果 |
| --- | --- | --- |
| 1 | 同一 eager 服务的纯文本最小请求 | `42`，正常停止；作为文本基线。 |
| 2 | 增加单张 64×48 红色 PNG 的图像请求 | 连续 128 个 `!`，长度截止；视觉失败。 |
| 3 | 同图只渲染、不推理 | `image-render-summary.json`：90 个 token、图像占位 offset 13 / 长度 68；参考处理器给出 patch 网格 `[[28,36]]`。两者视觉 token 相同，差异仅在 assistant 模板结尾；尚不能据此证明视觉张量正确。 |
| 4 | 111-token 纯文本请求 | `long-text-smoke.json`：返回 `42` 且正常停止；排除一般性的长 prompt 失效。 |
| 5 | 同图仅解码首 token 并取 logprobs | `image-first-token.json`：输出 token ID 0（`!`），其及另一个候选的返回 logprob 均为 `-9999.0`；支持非有限 logits 假设，但 API 的占位值不是直接的 NaN 证明。 |
| 6 | 只加载 checkpoint 的 453 个视觉权重，在空闲 PPU 2 运行 HF 视觉塔 BF16/SDPA | `hf-vision-finite-ppu2.json`：各层和末端均无非有限值，目标网格 `[[28,36]]`；表明相同硬件上的 checkpoint 参考视觉路径可产生有限激活，但不证明 vLLM 视觉路径。初版诊断脚本未加载动态模型模块而失败；v2 修正导入后成功，均保留在 `02-issues/`。 |

原 eager 服务在启动日志中选择 `FLASH_ATTN` 作为
`MMEncoderAttention` 后端。2026-09-28 16:43（Asia/Shanghai），为对比视觉
后端，用单 Host Ansible 在确认 API PID 2852、EngineCore 3637、Worker 3922/3923、
权重路径、TP2、端口和启动脚本 SHA-256 后，对该任务的 API 执行
`docker exec minicpmV4.7-35B kill -TERM 2852`。四个进程均确认退出，容器未停止。
随即从 `01-environment/start-eager-tp2-sdpa-v1.sh` 启动相同权重、设备 0/1、
TP2、eager、50,000 上下文和前缀缓存配置，只增加
`--mm-encoder-attn-backend TORCH_SDPA`；独立日志在
`04-runs/eager-tp2-sdpa-v1/service.log`，缓存仍只在 `06-cache/`。
启动日志已显示该参数进入有效配置。

SDPA 服务 `/health` 返回 200，日志也确认实际 `MMEncoderAttention` 使用
`TORCH_SDPA`。相同红图首次回答“白色”并正常停止，仍为语义错误；同一红图
第二次及一张蓝图均再次产生 128 个 `!`，以长度上限结束。对应原始结果为
`04-runs/eager-tp2-sdpa-v1/image-smoke.json`、`image-red-repeat.json`、
`image-blue.json`。这推翻“只切换后端即可修复”的假设。三次请求的服务日志
`Prefix cache hit rate` 均为 0%，因此目前没有前缀缓存命中导致该异常的证据。
HF 参考视觉塔的有限激活不能直接推断到 TP2 服务。

`02-issues/vllm_vision_finite_minicpm_v5.py` 随后在空闲 PPU 2、TP1、BF16、
`TORCH_SDPA` 下，按 Plugin 的权重映射加载同一视觉塔、窗口合并器和 MLP
（459 个源键经 QKV 合并后为 351 个加载名），以相同红图逐层检查：
`04-runs/eager-tp2-sdpa-v1/vllm-vision-finite-ppu2-v5.json` 各阶段均为有限值，
且 embedding、层 6、窗口合并、层 26、post norm 的最小/最大值与 HF 参考探针一致。
这支持 TP1 视觉路径的数值一致性；尚未覆盖服务的 TP2 视觉分片、视觉嵌入注入、
canvas 位置和 MoE 后续计算。v1–v4 是探针构建过程中的未通过尝试，
分别因缺少 vLLM config、模型注册、QKV 合并计数误判以及诊断环境默认 BF16
使视觉位置 arange 长度不匹配；均未修改产品源码或服务。
在该 SDPA 服务上，三次失败图像请求后再发送纯文本最小请求，
`04-runs/eager-tp2-sdpa-v1/text-smoke.json` 仍返回 `42` 且正常停止，
进一步将问题限定在视觉输入参与的路径。

为区分 TP2 视觉权重分片与后续模型路径，2026-09-28 17:24（Asia/Shanghai）
确认 SDPA API PID 85654、EngineCore 86439、Worker 86724/86725 与启动脚本
SHA-256 `4b10d3141a215b357086a4b36cd0ce8cbdad22e8b57fdd2f41f46eacb2f4d162`
后，仅向该 API 发送 TERM，并验证上述四个进程全部退出。容器未停止。
新实例 `01-environment/start-eager-tp2-sdpa-data-v1.sh` 保留权重、设备 0/1、
TP2、eager、SDPA、50,000 上下文和缓存设置，仅把视觉编码器 TP 模式从默认
`weights` 改为 `data`，独立记录在 `04-runs/eager-tp2-sdpa-data-v1/`。
有效参数已在启动日志中确认，但两个 Worker 均在视觉权重加载时触发
`KeyError: 'encoder.layers.0.self_attn.k_proj.bias'`，API 未就绪。
vLLM `idefics2_vision_model.py` 的 data 模式在构造注意力时仍创建 fused
`qkv_proj`，加载函数却在该模式跳过 `q_proj/k_proj/v_proj` 到 fused 参数的映射，
随后查找不存在的独立 `k_proj`。这属于独立的加载阻断，尚不能从该次启动判断
数据并行推理是否修复图像输出。

已在 4.7 Plugin 适配层加入仅在 `load_weights` 期间关闭视觉塔 data 标记、
并在 `finally` 中恢复原值的局部修正；vLLM 本体未修改。原文件 SHA-256
`910c551d4f2694534c7f8046842781ac6a48020c5c4ce7b94c59d7a89e011b61`，
新文件 SHA-256 `db2bc92342d81f7877759e6565d5bf3a9339fa652e54526c738bb817acab206b`。
受控安装在确认 Plugin HEAD 和仅有本任务改动、预览 12 行差异后完成。
2026-09-28 17:35（Asia/Shanghai）以相同模型、TP2、eager、SDPA、视觉 data
设置启动 `01-environment/start-eager-tp2-sdpa-data-v2.sh`，独立日志及结果保存在
`04-runs/eager-tp2-sdpa-data-v2/`。两个 Worker 均加载完整 17 个 shard，
`/health` 返回 200，证明上述加载阻断已解除；但同一红图请求仍返回
连续 128 个 `!`、`finish_reason=length`（112.308 秒；
`04-runs/eager-tp2-sdpa-data-v2/image-smoke.json`）。因此视觉 data 模式也未
修复图像回答，不能将加载修正等同于视觉适配成功。该模式下的 4.6 视觉路径
直接逐层调用视觉塔，并不调用 `Idefics2VisionTransformer.forward` 的数据切分
包装；此参数对实际视觉执行的作用仍需进一步核实。

17:49 左右，核对 API PID 168053、EngineCore 168826、Worker 169117/169118、
权重/TP2/data/SDPA/eager 参数及旧脚本 SHA-256
`bb28e05beee0e358825cdef740447614073e407f7da7b1cc3b8c91a4d1fd361d`
后，只向该 API 发送 TERM，并确认全部退出，容器未停止。为查找首次非有限值，
从 `01-environment/start-eager-tp2-sdpa-data-debug-v1.sh` 启动参数相同的
独立诊断实例；仅通过 `PYTHONPATH` 注入
`02-issues/vision-debug-v1/sitecustomize.py`，在正式图像请求时记录视觉输出、
嵌入合并、前向输出与 logits 的有限值摘要到
`04-runs/eager-tp2-sdpa-data-debug-v1/`。诊断结果待完成。

该首轮诊断实例在加载前被 vLLM IPC 地址长度检查拒绝：`TMPDIR` 下生成的
Unix socket 路径超过 107 字符；日志保留在上述目录。确认 API 和 EngineCore
均退出、端口空闲后，保留相同权重及推理参数，改用工作根内较短的
`05-tmp/vdbg2`，另起 `01-environment/start-eager-tp2-sdpa-data-debug-v2.sh`，
诊断结果与缓存分别写入 `04-runs/eager-tp2-sdpa-data-debug-v2/` 和
`06-cache/eager-tp2-sdpa-data-debug-v2/`。新 Unix socket 路径预计 88 字符，
仍在批准的工作根内。`/health` 返回 200 后才创建 `trace-enable`，用相同红图
仅生成一个 token。`image-smoke.json` 记录 HTTP 200、输出 `!`、52.195 秒；
`finite-trace.jsonl` 在两个 Worker 上均显示视觉塔最终特征
`[63,2048]` 的 129,024 个值中**有限值为零**。多模态合并前纯文本部分仍有
55,296 个有限元素；合并后的 `[90,2048]` 嵌入只有 55,296/184,320 个有限值，
随后前向输出和 logits 均为零个有限值。实际位置张量 `[3,90]` 全部有限，
范围 0–34。由此可确认视觉塔输出先于语言模型污染输入，ID 0 采样是后果；
TP2 视觉路径的首次非有限位置仍需细分。

随后核对诊断 API PID 238677、EngineCore 239733、Worker 240295/240296、
旧脚本 SHA-256 `43e1f602da002fddce315672c01ddc4b5c297e710c679cb59f08b095b3f89ffb`
和相同启动参数，只停止本任务服务并确认进程全部退出。新实例
`01-environment/start-eager-tp2-sdpa-data-debug-v3.sh` 在
`04-runs/eager-tp2-sdpa-data-debug-v3/` 记录视觉嵌入、逐层 encoder、首层
QKV/attention/MLP 与合并器的有限值；源码仍为同一 Plugin revision，
诊断钩子仅从 `02-issues/vision-debug-v3/` 注入。`/health` 通过后同图单 token
探针的 `finite-trace.jsonl` 在两个 Worker 上均显示：视觉 embedding
1,161,216/1,161,216 有限；encoder 层 0–6 及窗口合并器全部有限；
**第 7 层首次出现非有限值**（TP0 仅 186,624/290,304 有限，TP1 仅
146,304/290,304 有限，部分有限值绝对值达约 `1e37`）；第 8 层起全非有限。
有效日志显示 `MMEncoderAttention` 选择 `TORCH_SDPA`。这把问题收窄到
窗口合并之后的首个视觉编码层，尚未确定是该层权重、注意力、MLP，还是
数值布局。容器保持运行。

已核对上述实例的 API PID 301453、EngineCore 302509、Worker
303071/303072 与脚本 SHA-256
`51964b040096b363787ab3b26aaee15e0040ad331892a9ada701a01adfc7292b`，
只停止该任务服务并确认进程退出。新实例
`01-environment/start-eager-tp2-sdpa-data-debug-v4.sh` 保留所有模型与推理
参数，仅从 `02-issues/vision-debug-v4/` 注入针对第 7 层子模块输入、输出和
权重有限值的钩子；原始证据位于 `04-runs/eager-tp2-sdpa-data-debug-v4/`。
同图单 token 的两张 Worker 记录一致：第 7 层输入、norm1、fused QKV
投影输出及其权重/偏置均**全部有限**；首次非有限出现在
`self_attn.attn`（vLLM `MMEncoderAttention` 的 `TORCH_SDPA` 路径）输出，
TP0 仅 290,084/290,304 有限，TP1 仅 290,101/290,304 有限，部分有限
值达到 BF16 约 `3.39e38` 极限。后续 out projection 和层输出扩大污染。
因此本次问题可定位为 post-window、长度 252 的视觉注意力调用或其下层
SDPA 算子；已排除该层输入、QKV 投影以及相应权重本身直接非有限。

对照实验不改服务：`02-issues/vllm_vision_finite_ppu0.py` 在同一物理 PPU 0
以 TP1、同 checkpoint、BF16、红图及 SDPA 运行，351 个映射后的视觉权重名
均加载，第 7 层注意力输出范围约 `[-1.98, 1.78]`、全有限，最终 63×2048
视觉特征亦全有限，结果
`04-runs/eager-tp2-sdpa-data-debug-v4/vllm-vision-standalone-ppu0-tp1.json`。
另在事先确认空闲的 PPU 3/4 上，通过 `02-issues/vllm_vision_finite_tp2_ppu34.py`
执行最小 TP2/data 双 rank 视觉路径；初次 `torchrun --standalone` 因容器 hostname
不可解析，在创建 rank 前停于 rendezvous，明确 PID 432316 经 TERM 停止并确认
退出。改用已验证空闲的 `127.0.0.1:29517` 后，两 rank 均完成相同 351 个
视觉加载名，注意力及最终特征**全部有限**，独立结果为同目录
`vllm-vision-standalone-ppu34-tp2-rank0.json` 和 `rank1.json`。
这说明权重、红图、BF16、TP2/data 和 SDPA 的最小组合本身可用；非有限现象
还依赖完整 vLLM 服务的运行上下文。不得据此推断 PPU 3/4 上的完整服务正确。

为检验完整服务内 SDPA 的因果作用，已核对诊断 API PID 366708、EngineCore
367770、Worker 368332/368333 与旧脚本 SHA-256
`4f5eb730e6a357e7676dda6e7c40c0b8019f500c625a2296be55975ad0b27222`，
只停止该任务服务并确认退出。`01-environment/start-eager-tp2-sdpa-data-debug-v5.sh`
保留同一模型、设备、TP2/data、eager、SDPA 声明和正常前缀缓存；仅通过
`02-issues/vision-debug-v5/sitecustomize.py` 在诊断标记出现后，把窗口合并之后
的视觉注意力替换为显式 FP32 matmul/softmax/matmul，结果写入独立
`04-runs/eager-tp2-sdpa-data-debug-v5/`。启动脚本 SHA-256
`21d00481c081281a99840b2d15055e621b99f710a4388f39dcc2452f8b12cd6c`，
两个 Worker 完成 17/17 个 shard 加载，`/health` 为 200。首次红图单 token
请求返回“红色”，耗时 250.349 秒，原始结果 `image-smoke.json` SHA-256
`02795d3d0a0b5380ba769f80f45ddca6a1849859046dac02f6bfcbdc7ae43013`；
两 Worker 的第 7 层注意力输出均为 290,304/290,304 有限，最终视觉特征
129,024/129,024 有限，合并嵌入、语言模型输出与 logits 亦全部有限。
`finite-trace.jsonl` SHA-256
`ac452404b2524c3b53560bee4da3aaa8834f6b8ee3f77c5e4b7e8ac686913b9d`。
同实例蓝图单 token 请求返回“蓝色”，耗时 0.525 秒；
`image-blue-smoke.json` SHA-256
`11a6ede34ff1ddd408335744c35719dd67890759c19ebc3099e5a4a109def4c1`。
首次请求延迟包含新路径的首次执行开销，不能推断稳定性能。
这组同服务受控对照证明，原注意力调用导致非有限视觉激活及颜色回答失败；
显式计算仅用于诊断，尚不是可接受的产品修正。

进一步只在第 7 层及之后的视觉注意力入口把 Q/K/V 变为连续布局，保留原
BF16 `TORCH_SDPA` 算子。新实例
`01-environment/start-eager-tp2-sdpa-data-debug-v6.sh` SHA-256
`16dfafdff41f4d3ce9f192a02da207a2e7ba4e7fb5dec685fa9e391cfbb4d711`，
仅由 `02-issues/vision-debug-v6/sitecustomize.py` 注入本次变量；原任务服务
API PID 433023、EngineCore 434079、Worker 434641/434642 经核对后只停止
这些进程，容器未停止。v6 加载 17/17 shard、健康检查 200；同一红图单 token
回答“红色”，54.091 秒，`04-runs/eager-tp2-sdpa-data-debug-v6/image-smoke.json`
SHA-256 `88e99b528877e8fe97a0fe8770a563f7ae952dc17134a35e45cea4999b710016`。
第 7 层注意力及最终视觉特征在两 Worker 上都全有限，`finite-trace.jsonl`
SHA-256 `4db6bd8f8f0bf03336a7b2e7473158f081e13efc0a3091f31ec988af3fc5da57`。
但该层注意力输出 TP0 范围约 `[-1.90,1.74]`，TP1 为
`[-7.72,9.81]`；显式 FP32 参考两 Worker 均约 `[-1.98,1.77]`。
两 rank 的后续视觉特征范围也不同。连续布局抑制了 NaN，但不足以证明
BF16 SDPA 数值正确，单题答对不能当成正式正确性通过。

再保持模型、设备、TP2/data、eager、SDPA、前缀缓存和红图不变，仅在该注意力
入口将 Q/K/V 转为 FP32 连续布局，调用原 `MMEncoderAttention` 后把输出转回
BF16。诊断脚本位于 `02-issues/vision-debug-v7/sitecustomize.py`，
独立启动脚本 SHA-256
`4a08d4ab6141ef3c24e588124e69ff3dce2356656e778fc639ca3929d13c31b0`；
确认旧实例 API PID 503154、EngineCore 504214、Worker 504782/504783 后，
只停止本任务服务进程并验证退出，容器未停止。v7 加载完整 17 shard、`/health`
为 200；但同一红图首 token 请求从 19:56:19 至 20:01:20 持续约 300 秒，
最终 HTTP 500。两个 Worker 都记录到完全有限且范围一致的第 7 层 Q/K/V
输入，之后没有注意力输出；EngineCore 报
`RPC call to sample_tokens timed out`，API 随之退出。请求结果
`04-runs/eager-tp2-sdpa-data-debug-v7/image-smoke.json` SHA-256
`857c6641dcab05980f413e1ead2aaf514dfcdd8de72a07b1bdca389fda1904f5`，
追踪文件 SHA-256
`d1eff52bdacbbbf98aeab34b4368dbf41e4ef2b528fb262da577c8bd2d53938b`。
FlagGems/Triton 首次调优提示出现，但未看到更早的 Python 异常；等待期间设备
利用率曾为 0%，因此不能认为 FP32 SDPA 正常工作，也不通过加长 RPC 超时
掩盖失败。[分布式超时经验](../../../../../../docs/troubleshooting/distributed-sample-tokens-timeout.md)
仅作为候选参考：本次未观察到其中必需的通信 work 序号分叉，不能直接套用其
完整签名。该路径列为失败的诊断，不重复请求。

据此已在可编辑 Plugin 源码增加**候选** PPU 视觉修正，而未改 vLLM 或同步
FlagGems：模型适配器只在 `current_platform.vendor_name == "thead"` 时，
给该模型自己的 Idefics2 视觉注意力实例绑定
`vllm_fl/dispatch/backends/vendor/thead/vision_attention.py`；vendor helper
保持原 `qkv_proj`、`out_proj`、BF16 输入/输出和可广播加性 mask 接口，
内部以 FP32 matmul/softmax/matmul 计算，并按 128 个 query 分块限制分数张量。
此选择限定到当前模型与 PPU；NVIDIA、其他模型和共享 vLLM 路径不受改动。
候选 adapter SHA-256
`5e4e9f13e434adf33c4ee1d6b0e75c86cad60af75a5553b30cc97add5ff94d40`，
vendor helper SHA-256
`0fba92cd39a34f202befc808c2f421e6b23e5f68866c71a0e70224e7e748c3db`。
helper 初置于 `thead/impl/` 时，pytest 收集触发该目录既有 `__init__` 对当前
vLLM 不兼容的 `flash_attn_supports_fp8` 导入；已仅将本任务新增 helper 移到
`thead/` 上层，并更新两处本任务引用。未修改既有 attention 模块。
聚焦数值测试 `tests/unit_tests/dispatch/test_thead_vision_attention.py` SHA-256
`2310f409f3e760550c7c51bafcc2d98d99749d09e6be82264a70ca8df8338388`，
比较 5/133 序列、有/无填充 mask 对 FP32 PyTorch 参考，4/4 通过。
这只是 CPU 数值契约和导入验证，真实 PPU 服务、复杂图像、graph 与性能均
待验证；若出现图执行、mask 或性能问题需继续修正，不能据此完成适配。

首个无诊断注入的产品候选实例已用
`01-environment/start-eager-tp2-sdpa-data-product-v1.sh` 启动（SHA-256
`43a9057b21d23f27abd462ce2a31de0063ad0fce361a18828da442b0b7ae838d`），
独立结果在 `04-runs/eager-tp2-sdpa-data-product-v1/`。两 Worker 加载 17/17
shard，`/health` 返回 200。文本探针首次因诊断脚本只允许 1 token 而返回“4”，
该结果保留为长度受限证据，不算正确性失败或通过；补充的 4-token 探针返回
“42”、`finish_reason=stop`，`text-full-smoke.json` SHA-256
`de6b07086bfe7eab060f3df23075be3234c709d284aacb61176e49ca3a680610`。
同实例红图单 token 返回“红色”，HTTP 200，但首请求耗时 287.401 秒，距
EngineCore 300 秒超时线过近；`image-smoke.json` SHA-256
`dc652fe5f0b41c27c88717872141dfe44dc763dc83540ce48ef87264a2175f51`。
接着蓝图单 token 返回“蓝色”，耗时 0.566 秒，`image-blue-smoke.json`
SHA-256 `48e76ca3893ba4b71665611c98c99c3a180c3791751e8fa0b1cceb608571b314`。
这些是最小 eager 样本通过，不是正式精度、graph 或性能通过。
首图冷路径风险要求缩小修正范围；当前 helper 被绑定到全部视觉层，而原异常
首次只在窗口合并后的第 7 层出现，前 0–6 层在原 SDPA 路径均为有限。
2026-09-28 21:24 左右确认该实例 API PID 632131、EngineCore 632912、
Worker 633197/633198 与启动脚本 SHA-256，只停止本任务服务并验证四进程
退出，容器未停止。adapter 现只从配置 `insert_layer_id + 1` 开始绑定 PPU
FP32 helper，其余视觉层保留原 vLLM 注意力；新 adapter SHA-256
`31fbd56b0b92c4ef5d702e64d9fadb131b489b0bf3a30b9175b7a13bfd8c7759`。
`01-environment/start-eager-tp2-sdpa-data-product-v2.sh` SHA-256
`bb76fd3ce2ed284e3b511e9a8891d7676c283ded83807ec76638cbade86b864f`
已在同一设备/端口、独立 `04-runs/...product-v2/` 与 `06-cache/...product-v2/`
启动。17/17 shard、`/health` 200。完整文本请求返回“42”且正常停止，
`text-full-smoke.json` SHA-256
`e47515f0da0ee8285e80723e36f6f0c61326ed60c10fff103d3c8a6048739e37`；
冷路径红图单 token 返回“红色”，220.346 秒，`image-smoke.json` SHA-256
`8ed893006bcb8f8fdf4df7e30f0243e8b0c2c25caba062303f0db1a201efe741`；
同服务热路径蓝图返回“蓝色”，1.040 秒，`image-blue-smoke.json` SHA-256
`7e8eb4bd72a1e162b15938d7c44b01b07b402243df253bcc8c5e1deaebfe3d0b`。
v2 只缩小绑定范围，红图冷请求比 v1 少 67.055 秒；这是各一次的受控样本，
不足以建立性能分布或正式精度通过。保留原始日志，单次只调整一个实质变量。

2026-09-29 在确认 v2 API PID `713629`、EngineCore `714402`、TP0/TP1
`714687`/`714688` 与原启动脚本哈希后，仅停止本任务推理进程并确认退出，
容器保持运行。随后启动相同源码、模型、TP2/视觉 data、普通前缀缓存的 graph
试验，唯一实质变量为执行模式；full 图被 GDN 自动降为 decode-full，详见
[004](004-gdn-full-graph-limit.md)。该实例红图“红色”且 `stop`，218.085 秒；
蓝图“蓝色”且 `stop`，0.551 秒；红蓝双图“红色 蓝色”且 `stop`，
157.199 秒；红蓝两帧视频“红色，蓝色”且 `stop`，9.525 秒。
分别见 `04-runs/graph-tp2-full-v1/` 下的 `image-full-smoke.json`、
`image-blue-full-smoke.json`、`two-images.json`、`video-red-blue.json`。
这为已测 eager 与 decode-full 的短视觉路径提供诊断证据；因缓存生效值
`False`，不能计入正式执行模式验收。高分辨率、十并发和正式精度/性能仍待验收。
知识库状态 `local-only`，复盘时决定是否推广。
# 2026-10-08 后续：退出 FP32 缓解

用户要求尝试 FlagGems PR #6873 后，已在当前 35B 容器的实际安装包修复
split-KV 输出寻址。旧实现公共入口数值失败，修复后 34 项回归通过；完整
35B BF16 eager 9/9 正确、189 次实际 attention 全有限，并命中原 252-token
形状的两路 split。TP2 `FULL_AND_PIECEWISE` 两类图各 7/7，HTTP 25/25
正确。已移除原 `vision_attention.py`、专属测试和模型绑定，服务保持运行。
详细证据、一次前缀缓存缺省检查失败及其修正、最终文件哈希和限制见
[011](011-flaggems-splitkv-vision-fix.md)。正式 ERQA/GPQA 与性能未复测。
