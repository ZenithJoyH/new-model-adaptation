# 当前 Graph 回归（2026-10-23）

8001 已恢复 FULL_AND_PIECEWISE，以 Triton GDN prefill 规避停滞。完整 1651 页/30594 请求全部成功，Overall **96.45848131**，较此前 eager 高 **0.06621131** 个百分点。更新后的根脚本实际启动及 11 项固定请求、视频、64 路并发 256 项复验均通过；64/0.55 保持，8000 身份不变。

完整指标、配置规避的诊断边界、当前脚本及原生证据见[Graph 回归报告](graph-triton-8001-20261023.md)。下列 eager 及其他部署记录为历史，不代表当前运行模式。

# 历史 eager 精度测量（2026-10-23）

用户指定8001与复现包的OmniDocBench v1.6测量已完成，eager Overall **96.39227001**，包内历史参考96.42433265，差值−0.03206265个百分点。1651页、30594个裁剪请求全部完成，零请求失败、1次长度截断；3页使用原生匹配超时fallback，未丢页。2352个CDM、665个TEDS案例全部完成，指标超时/错误/异常均为0；离线评分进程池阻塞已通过有界队列恢复，同一预测集及原生指标源码保持不变。

当时两轮FULL_AND_PIECEWISE运行停滞尚未修复；8001暂留明确授权的eager诊断配置，64/0.55保持，脚本未改，8000进程身份与评测前一致。当前checkpoint为 `models/merge_rl_mergedp1_7140_hf5_4x`，结果独立绑定实际服务实例。不重写旧部署的阶段回执，不宣称正式框架验收通过。详见[8001精度记录](omnidoc-v16-8001-20261023.md)。

以下为旧部署历史记录。

# 当前资源调整状态（2026-10-21）

新容器minicpm-ocr-vllm-native-allgpu已验证全部8张GPU和完整/public挂载，适配源码/内部交付保留。此轮未运行模型服务或评测；原根脚本及模型路径在检查前已缺失，原生服务未运行。以下推理结果均为旧部署历史。见[005](../adaptation/005-allgpu-public-mount.md)。

# 当前服务更新：262144上下文（2026-10-20）

8010/MiniCPM-OCR服务已改为262144上下文，64序列和0.55显存比例保持。128项OCR在64客户端并发下全部匹配参考；262143输入+1输出成功、超限请求正确拒绝。正式长上下文质量与满长并发未评测。根脚本有人工作出的8000端口/模型名改动，本次保留；内部8010交付脚本实际重启验证。完整证据见[004](../adaptation/004-context-262144.md)。以下16384上下文和旧脚本一致性结论为历史，不代表当前部署。

# 当前服务：64 序列上限

2026-10-20，按用户要求仅将 max-num-seqs 调至64，gpu-memory-utilization 保持0.55。两份启动脚本均已更新并通过语法和内容一致性校验，当前 API PID 10319，容器仍为原容器且持续运行。端口8010、模型名、上下文16384、前缀缓存及 FULL_AND_PIECEWISE 均保持原配置。

仓库 service-sanity 原生工具先离线预检，再以64路客户端并发发送128个 OCR 请求，128项全部与已冻结参考一致、零请求错误；Prometheus 实际观测到同时运行64条请求。覆盖不同图像尺寸、4x/16x、小图原尺寸/自适应和多图；显存观测峰值45053 MiB（约44.0 GiB）。这是功能回归，不是正式精度/性能验收，也不报告吞吐或延迟结论。

当前脚本：Host/容器根级 /public/flagos/jinghao/MiniCPM-OCR/start-model.sh 与容器内 /opt/minicpm-ocr/start-model.sh。SHA-256 均为 8ce2e2fae3e703e71644f635e26428c5728e19343e7f22bf8212cc16c729f47a；新部署指纹 33822fe64f2ae6450faff4be25e54089a62baba65ff890a2e083c3cef9f47c74。交付配置、持久副本和清单同步更新，旧文件保存在远端 04-runs/seq64-restart-20261020/previous/。

现场取证与完整回归：04-runs/seq64-sanity-20261020/service-observation.json、sanity-result.json、summary.json、monitor.json；启动验证：04-runs/seq64-restart-20261020/verification.json。参考请求与绑定在03-acceptance/seq64-sanity-20261020/。记录见 [003](../adaptation/003-max-seqs-64.md)。

---

# 首次 8 序列交付记录（历史）

2026-10-20。用户明确选择“本轮先交付可用服务，正式评测另安排”。本轮完成架构、环境与适配，验证 eager 和显式 FULL_AND_PIECEWISE 的服务功能；不宣称完整正式验收或 optimized。

容器 `minicpm-ocr-vllm-native` 保持运行，API PID 8618；149 本机接口 `http://127.0.0.1:8010/v1`，模型名 `MiniCPM-OCR`。GPU 0、TP1、BF16、上下文 16384、最多 8 序列；图像/视频限额 4/1。前缀缓存显式开启，Mamba cache 为 align。FULL 因后端能力限制未通过，选择下一档，详见 [002](../adaptation/002-gdn-graph-level.md)。

最终脚本启动后的 11 个文本/图像/多图/小图/混合模式请求及视频请求全部 HTTP 200。七组代表性请求与同构 Transformers 参考的生成文本、prompt token 数及生成 token ID 全部一致。只证明该固定小集合，不代表全量 OCR 指标或所有输入已验证。包内单测原始结果为 21 passed、1 个依赖新版函数身份的断言失败，详见 [001](../adaptation/001-ocr-registration-and-geometry.md)。

## 启动与可恢复材料

Host 与容器工作根均为 `/public/flagos/jinghao/MiniCPM-OCR`。根级可执行脚本 `start-model.sh`，容器内部交付副本 `/opt/minicpm-ocr/start-model.sh`；SHA-256 均为 `776e817eb9ffb0fa1ecc9afd1419504fc247720d2c1f50f86317cd79946c2465`。已用内部副本真实启动并验证健康接口、模型列表、文本/图像/视频推理；未使用 PYTHONPATH 或宿主机源码。

脚本仅含必要启动和缓存/驱动设置。端口 8010 避开已有服务；16384/8/0.55 与 4图/1视频限制固定本次资源预算；显式启用前缀缓存是因为该模型默认关闭；图模式固定本次验证档位。XDG/TRITON/FLASHINFER/CUDA 缓存指向批准根的 06-cache；TRITON_LIBCUDA_PATH 用于找到只读透传驱动。日志追加到 `04-runs/start-model.log`。脚本不安装补丁、不运行测试、不轮询、不停止进程或容器，端口冲突由 vLLM 绑定检查拒绝。

`/opt/minicpm-ocr/` 还包含 config.json、source.patch、requirements.lock、RESTORE.md 与 manifest.json；持久副本位于工作根 `01-environment/delivery/`。源码修改和内部交付副本属于容器文件系统；权重/tokenizer 与运行日志/缓存为已声明外部工作根，NVIDIA 驱动通过宿主注入。尚未打包镜像或测试新镜像容器，image validation 为 pending。

## 证据与后续

全部原始证据在远端工作根：`04-runs/final-launcher-20261020/observation.json`、`04-runs/final-functional-20261020/`、`04-runs/final-video-20261020/`、`04-runs/hf-reference-20261020/`、`04-runs/source-review-20261020/`。部署指纹 `6f917535f6c059470771f54b1928b84053e3bb2bdc3d2bce5c694c8356efde13`，细节见 `01-environment/deployment-identity.json`。

未生成 v2 完整 execution-mode 的数值误差及实际 replay 计数原生回执，也未执行正式 sanity/accuracy/performance。框架状态按已绑定原生证据粒度保留 environment_ready；这不否认已实测的可用服务，也不冒充完整验收。未来评测应冻结数据集、阈值和性能场景，重新取服务身份并按各原生入口执行。

架构、环境和适配阶段已在远端通过仓库原生验证器读取真实产物校验，结果为 `04-runs/adaptation-ocr-20261020/gate-result.json`；对应阶段回执已绑定 framework.yml。本地 `./scripts/audit-workspace --json` 未报告 MiniCPM-OCR 问题；全仓审计仍因原有 XingChen4 失效链接返回失败，另有旧模型历史证据警告，未修改这些无关记录。
