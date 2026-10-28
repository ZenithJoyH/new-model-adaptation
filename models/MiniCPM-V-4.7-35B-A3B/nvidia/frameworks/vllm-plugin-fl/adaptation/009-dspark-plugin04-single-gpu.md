# 009：现有 Plugin 0.4 容器的 35B-A3B DSpark 推理

## 范围与环境

2026-10-09，用户要求当前 DSpark 容器同时具备 35B-A3B DSpark 推理支持。
本轮是服务适配与功能验证，不运行正式精度、性能或镜像发布。
主权重为 `/data/models/MiniCPM-V-4.7/weights/35b-a3b`，草稿为
`/public/flagos/jinghao/MiniCPM-V-4.7-35B-A3B-DSpark`；主模型沿用本目录记录的
35B MoE 架构，不能把此前 1B DSpark 验证当作本模型已通过。

- Host：`H100-149`，实际连接主机为 `p-jn-sz-dell-h1-su8-gpu11-401-11o-12u-208-149`。
- 容器：`MiniCPMV4.7-1B-DSpark-gpu6`，ID
  `8645e61dddfaac3712ec27afaa1efce8b008e9f6f24a263a9e6380dce43cb640`。
- 工作根：Host `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos` 对应容器 `/work`，
  实查设备号/inode 均为 `45:232972481026`。本轮在当前容器的批准根下另建独立 run。
- 只映射物理 GPU6，一张 H100 80GB；GPU0–3 已有其他服务，不操作其进程。
- vLLM `0.28.0`、Torch `2.13.0+cu130`、Transformers `5.12.1`；
  继承已适配的 Plugin `0.4.0-dev@e88e4db` 和 FlagGems `5.4.0.dev0+g0dddb462`。
  vLLM 源码只读，安装组件与导入路径遵循 1B [问题 008](../../../../../MiniCPM-V-4.7-1B/nvidia/frameworks/vllm-plugin-fl/adaptation/008-dspark-plugin04.md)。

## 权重可见性与受控复制

原容器仅挂载 1B 主/草稿权重，两个 35B 路径均不可见。远程操作政策要求复制权重单独授权；
用户明确允许将两份权重复制至 `/work/06-cache/dspark-35b-weights/`，并暂停当前 1B
服务释放 GPU6。未停止、重建容器或更改挂载。

主模型 18 个 BF16 shard，checkpoint 参数数据 70,425,751,648 字节；完整目录
70,446,181,013 字节。草稿单个 safetensors 778,452,858 字节。
复制至 `main/` 和 `draft/`，总计 34 个文件、71,224,635,415 字节。
每个文件复制时计算源 SHA-256，落盘 fsync 后重读目标验证同一 SHA-256，并核对源大小/mtime
未变化。`weights-manifest.json` 保存完整映射与哈希；源权重保持只读。

## 接口核对与验证计划

主骨干 `qwen3_5_moe_text`：40 层、隐藏维 2048、256 专家/每 token 8 专家。
草稿 `Qwen3DSparkModel`：5 层、隐藏维 2048、词表 248144、block_size 15、
`target_layer_ids=[3,11,19,27,35]`，`fc.weight=[2048,10240]`，两条 Markov 权重
均为 `[248144,256]`，confidence 输入 2304。与主模型隐藏维、词表及层数匹配。

现有 MiniCPM shim 根据 text_config 选择原生 `Qwen3_5MoeForCausalLM`，通过
`get_language_model`/`set_aux_hidden_state_layers` 委托隐藏状态接口。草稿沿用 vLLM
原生 DSpark 实现；优先验证现有路径，不预先在公共 worker 或 backend 增加模型特例。

先 TP1 eager 加载和固定图文请求，再核实 GDN graph 能力后验证
`FULL_AND_PIECEWISE` 捕获/变输入重放与十客户端并发。初始资源配置：50K 上下文上限、
max_num_seqs 1、batched_tokens 1024、显存比例 0.94、草稿 token 14、单图/无视频。
这些值是启动候选；成功加载不等于 50K 长输入或一般并发能力通过。

## 证据定位

所有本轮原生产物在上述 Host 根下，以 `dspark-35b-20261009` 为 run 名：

- `01-environment/`：`container-baseline.json`、`components-before.json`。
- `02-issues/`：`copy-weights.py`、`launch-service.py`。
- `03-acceptance/`：固定图文与十客户端功能脚本 `functional.py`。
- `04-runs/`：权重清单/复制进度、精确进程 argv/env、服务日志、功能响应和 metrics。

尚未完成本轮推理验证时，不提升 `framework.yml` 历史状态。

## 首次整模失败与 padding 协议修复

首次 eager API PID 26760、EngineCore 27963，主模型/草稿加载完成，报告 67.49 GiB。
预热失败表面调用栈位于 FlagGems fused MoE GEMM 启动。直接 BF16 对照覆盖
`M=1024,H=2048,I=512,E=256,top_k=8` 的低编号 int32/int64 和高编号 248–255，
三组均与 PyTorch 参考一致，最大绝对误差分别约 `7.9e-7/7.9e-7/8.5e-7`。
这些合法索引对照不能证明 padding 协议兼容。

同步诊断 API 29147、EngineCore 30434，保持相同模型/资源参数，使用
`CUDA_LAUNCH_BLOCKING=1` 及远端临时入口包装，未改 vLLM 或模型 shim。
首两次 MoE 实参均是 `[1024,8]` int32 `topk_ids`，全部为 `-1`；无 expert_map。
第一项同步失败为 FlagGems `moe_align_block_size_stage4` 非法访存。
vLLM 0.28 的 router 在 `VLLM_MOE_SKIP_PADDING` 开启且 forward context 提供
is_padding 时，用 `-1` 标记填充；Plugin router 已遵循此接口，但 NVIDIA fused
experts 快速路径没有相应保护。独立调用 `padding-align.py -1` 单次可能未报错，
不能当作该未支持协议安全；保留其结果，整模同步调用栈是本次故障定位证据。

修复仅在已安装 Plugin `vllm_fl/ops/fused_moe/fused_moe_utils.py` 专家入口：
CUDA 且存在 padding metadata 时，委托现有 `TritonExperts.apply` 完整契约；
其他原有路径不变。按 metadata 判断，不读取 GPU tensor 判定是否含负数，不引入主机同步、
异常后回退或模型名称特例。由于不读取 mask 内容，全 false 的 mask 也走兼容实现；
本轮不声称性能收益。兼容实现的归约仍可能通过 Plugin dispatch，不能称为禁用全部 FlagGems。

FlagGems `master@0dddb462` 含 inherited `attention.py`/`libentry.py` 修复和两份测试，
不满足 profile 的干净 checkout 同步条件；未 stash/reset/pull 或新增 FlagGems 改动，
也未检索新算子替代方案。此次修复是 Plugin 适配已有接口，未更换任一依赖版本。
退出条件是 FlagGems fused experts 正式支持 vLLM 的 padding sentinel 协议并完成同样设备回归。

维护测试放在 Plugin `tests/unit_tests/ops/test_fused_moe_padding.py`。
最终聚焦回归 5/5 通过：完整参数委托、无 padding 的 FlagGems 快速路径、
混合/全 padding GPU 执行、变化输入/路由/有效行数的两次 CUDA 图 replay。
有效行按固定 `atol=0.004,rtol=0.03` 对照，输出 view 外的 canary 保持不变。
首次测试错误要求已被 vLLM 丢弃的 padding 行必须为零，导致 3/5 失败；
按接口改为有效行数值和内存边界验证，没有放宽有效行容差。
两次测试日志分别为 `padding-tests.log`、`padding-tests-r2.log`。

一次性同步入口首次遗漏 CLI `serve`，未加载整模；修正入口后使用新 run 名保存诊断。
诊断入口与同步环境变量仅用于定位，普通服务恢复正式 CLI 启动。

## 整模验证与最终服务

修复后普通 eager API 31872、EngineCore 33416 完成 9/9 固定请求：文本、红/蓝/绿/黄图、
重复红图、变化算式和多轮记忆。共同 MoE factory/router 与 MiniCPM backbone/DSpark
维护测试另有 24/24 通过。随后只停止本任务 eager 进程，启动最终图服务。

当前 GDN backend 声明 `AttentionCGSupport.UNIFORM_BATCH`，不支持 mixed prefill/decode
的 FULL；该能力文件 SHA-256 为
`fda86b96ab5daaf50bd02d022518779c220401dbedc7b28cf478f4c48e72d3d3`。
据此选 `FULL_AND_PIECEWISE`，没有修改 vLLM backend 或用自动降级冒充 FULL 成功。
图服务 API 34347、EngineCore 35550 完成目标分段图 2/2、纯 decode 全图 1/1 和
DSpark 草稿全图 1/1 捕获；固定请求 9/9、十客户端同时提交 10/10 正确。
草稿计数 20、生成草稿 token 280、接受 token 40，证实真实执行 DSpark。
十客户端由 `max_num_seqs=1` 排队，不代表十个驻留序列或正式并发性能。

最终服务从容器内 `/opt/flagos/dspark/start-35b-model.sh` 实际启动，专用工作根入口
`/work/start-dspark-35b.sh` 和 run 中证据副本内容相同，SHA-256：
`1e1964fad3ae24064c60cc2782fa129e83c4916f25fe66bca1d1442cdc3f843b`。
脚本不含安装、诊断包装、`PYTHONPATH` 或 `CUDA_LAUNCH_BLOCKING`。
只保留服务参数、批准根下缓存/算子记录位置及日志重定向；原 1B 启动器保持原样。
本轮最后 `/health=200`，GPU6 使用 76,025 MiB，容器仍运行且 restart count 为 0。

源码前后全量 `.py/.so` 指纹证实 vLLM、FlagGems 不变，Plugin 包内仅专家入口改变；
新增维护测试单独保存哈希。原 MiniCPM shim 哈希仍为
`71c1cbe325dbbef42c12a66a76b3a226360a612f8ac3923896ae9795a21bcbbc`。
专家文件哈希 `42940a5be998470f5fbf38a8d90b586883803fb01a178285e8f43ce9bcfbca97`，
新增测试哈希 `5ceda29ebd2c6bc11db929e36bf0b8c935b6a8cbe76cc34ec3970af01c2997aa`。
没有提交、推送或新建 PR；完整运行边界见[服务验证](../acceptance/dspark-service-validation-2026-10-09.md)。

最终 native 证据新增 `components-after.json`、`plugin-after.json`、
`shared-moe-regression.log`、`eager-fixed-functional.json`、`graph-functional.json`、
`graph-server.log`、`graph-metrics-before/after.txt`、`final-verification.json` 和
`evidence-manifest.json`。功能客户端在 graph 分支执行前修正了遮蔽 `concurrent` 模块的
结果变量，原脚本保留为 `functional-before-graph.py`；没有把客户端问题写成服务故障。

本次结论限定 BF16、TP1、GPU6、单图、短输出。50K 是配置上限，未实测长输入；
未评测精度/性能、视频、多 GPU、量化、LoRA、其他硬件或新镜像部署。
框架历史状态保持原样，不能将本次功能验证写成完整适配验收通过。

本轮新增/更新 Markdown 的本地链接与空白检查通过。只读 `audit-workspace` 仍报告
既有 12 项 profile revision 错误和 78 项历史警告；本 profile 同样需要历史证据复核，
未通过改写 `framework.yml` 消除审计结果。该审计不替代以上现场服务验证。
