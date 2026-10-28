# FlagOS 中启用 PPU Flash Attention

2026-10-27，PPU-01 / minicpm-ocr：独立 PPU5 实例已启用视觉 PPU FA2 和语言 vendor.thead FA3，并保持运行。57 项聚焦测试通过，6 个冻结 OCR 案例均完整返回且逐字匹配参考。该轮功能验证未包含 portable 三场景性能或全量精度，不签发正式框架验收。

后续按用户授权完成 [portable 三场景性能重测](005-portable-v11-ppu-flash-performance.md)：中位数 7.13/9.86/10.72 页每分钟，未观察到提速；32 页质量 Overall 97.5632。该测量与本条功能验证分开保留，正式框架状态不变。

## 当前服务与启动

- 容器 `minicpm-ocr`，ID `7bad43aab32e6386c34c9e46ec602ab4df955b0198997503886043bed055c6c3`；物理 PPU5，API 容器 PID 738021。
- PPU-01 endpoint：`http://127.0.0.1:8015/v1`；模型别名 `MiniCPM-OCR-FlagOS`。
- 新入口：Host/container 同路径 `/mnt/nfs/users/jinghao/MiniCPM-OCR/start-model-ppu-flash.sh`。当前服务已运行，无需再次执行。原 `start-model.sh` 保留。
- 脚本 SHA-256：`097fcdfe612e361aa56fad0fa311d081e5313aefb6d8b3c9d5045f7993aa403b`；语法和实际启动已验证。
- 关键设置：`VLLM_FL_PER_OP='attention_backend=vendor:thead'`、`--mm-encoder-attn-backend FLASH_ATTN`；继续加载 Plugin 和 FlagGems-vllm，未全局更改其他算子的后端优先级。
- 单卡 BF16、TP1、上下文 262144、max_num_seqs 64、显存比例 0.55、图像/视频上限 4/1、FULL_AND_PIECEWISE；实际默认批次 token 预算 8192。
- 正常启动显式开启 prefix cache；脚本的 `--performance` 分支只关闭 prefix cache。MM processor cache 保持默认，当前不是满足 portable 双缓存关闭要求的性能实例。
- TMPDIR 使用批准根下短路径 `05-tmp/fa1027`，满足临时文件边界和 ZMQ socket 路径长度约束；未增加服务缓存目录覆盖。脚本不安装依赖、停止进程或操作容器。

模型仍为 `/mnt/nfs/users/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`。9 个模型、tokenizer 和处理器文件重新核对大小和 SHA；规范化身份为 `7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`。

## 实现与验证

环境：PPU-ZW810E 96 GiB，驱动 2.1.1-rbd225；vLLM 0.24.0+empty、Plugin 0.0.0+g06014201f.d20261021、Torch 2.10.0、FlagTree 0.7.0+ppu3.6、厂商 flash-attn 2.7.4.post1、flash_attn_3 3.0.0b1。

语言侧通过已有单算子 dispatch 使用 TheadFlashAttentionBackend，实际实现调用 `torch.ops.flash_attn_3.fwd`。修复旧导入与 vLLM 0.24 参数协议；需要 FA4 的非默认参数明确拒绝。

视觉侧原 OOT 默认路径在选择 FLASH_ATTN 后仍会进入 SDPA，设备负对照已复现。通过已有 `patch_mm_encoder_attention()` 的 PPU 分支接入厂商叶子 provider；真实图像请求后的引擎日志出现 `Using installed T-Head flash_attn FA2 for MMEncoderAttention`。MMEncoderAttention 自身始终启用，无需额外 `+mm_encoder_attn`。

| 验证 | 结果 |
|---|---|
| 聚焦回归 | 57 passed、0 skipped；2 条既有 unittest duration 警告 |
| 视觉 FA2 BF16 | 16 heads × 72、3D/4D、变长序列，独立 CPU FP32 对照通过 |
| 语言 FA3 BF16 | GQA 8/2 heads × 256，causal/non-causal varlen 和 paged decode 对照通过 |
| 算子 graph | warmup、capture、两次变输入 replay，rtol 0.025、atol 0.003 |
| 路由/能力边界 | 非 Flash 视觉路径保持 native；FA4 特性拒绝；全局 custom_ops none 下视觉仍执行 FA2 |
| 实际模型图 | mixed prefill/decode PIECEWISE 和 decode FULL 捕获完成 |
| 真实 OCR | 数字、标题、正文、长正文、公式、长表格共 6 例，6/6 完整且逐字匹配 |

六例从原版 portable 输入及生成参数中冻结，参考选取此前 FlagOS 和原生均逐字相同的响应；首例串行、后五例最多 4 并发。它是兼容性验证，不是稳定性能测量；保留每次 response、usage、finish_reason 和耗时，不据此报告提速倍率。

## 范围与证据

产品改动只在实际 editable Plugin `/workspace/vllm-plugin-FL`：两个已有源文件、一个新增厂商叶子模块、一个新增测试模块。vLLM 安装及 checkout、FlagGems、FlagGems-vllm 和继承 dirty diff 均核验未变，没有 PYTHONPATH 覆盖。见[问题002与设计审查](../adaptation/002-ppu-flash-attention.md)。

Host/container 批准根均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR`，同一可写绑定目录 dev:inode `41:5457325353`。以下均为该根下路径：

- 工具、计划、冻结功能案例：`03-acceptance/flagos-ppu-flash-20261027/`，成功控制器 `run-model-r3.py`。
- 基线、57 项测试和最终源码审查：`04-runs/flagos-ppu-flash-20261027/`，重点为 `source-before.json`、`source-final.json`、`focused-tests-final.log`、`focused-tests-final-result.json`。
- 最终补丁：`02-issues/flagos-ppu-flash-20261027/task-source-final.patch`，SHA-256 `6082ff5c6c3673bf8b02e8876743cdb7dde82b7d096e6c5241f31ce88d0b2601`。
- 成功模型 run：`04-runs/flagos-ppu-flash-model-20261027-r3/`，保存 `model-state.json`、`service-instance.json`、`functional-results.json`、`verified-service.log`、原服务前后身份和 `completion.json`。
- 完成记录 SHA-256：`385595b3b1cd2ff4616f0687346f37beae7caab135337bc2a847c7027e636cec`。

前两次模型启动及错误测试保留：首次缺少 vLLM 新参数；第二次在图像请求之前过早检查调用日志。曾提出全局 custom_ops none 禁用该层的解释，已被专用层 enabled() 契约否定并撤回额外参数，没有把错误假设当成修复结论。

最终核验：原 8011/9999 的 PID、启动标识及 argv 未变；8011、9999、原生 8014、新 8015 的 health 均为 HTTP 200。两个容器均 running=true、restart count=0。

未验证其他模型/硬件、FP16 全矩阵、量化、FA4 特性或完整上下文容量。视觉 graph 数值测试使用静态 host max-length 元数据，未扩大到 GPU 动态 max-length 捕获。未打包镜像；Plugin 在容器文件系统，启动脚本在 NFS bind mount，不能据此声称新镜像可部署。没有 commit/push/PR，framework.yml 正式状态不变。

本地链接和空白检查通过。`./scripts/audit-workspace` 返回 3 个错误、14 条历史复核提示，来自无关 XingChen4 链接、GLM 部署指纹及其他模型证据，无本次 MiniCPM-OCR 新增记录错误；未修改无关记录。远端功能结论来自本次实际请求、设备测试和完成记录。
