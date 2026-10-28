# 007：独立容器接入 DSpark draft

## 范围与当前状态

2026-10-08，用户要求在 H100-149 新建容器，尝试通过 vllm-plugin-FL 提供
MiniCPM-V 4.7 1B + DSpark 服务。已通过独立脚本实启和功能试跑，不代表正式精度、性能验收。
原容器 `MinicpmV4.7-1B`、现有服务及启动脚本不属于本轮修改对象。

- 实际运行容器：`MiniCPMV4.7-1B-DSpark-gpu6`，ID
  `8645e61dddfaac3712ec27afaa1efce8b008e9f6f24a263a9e6380dce43cb640`。
- 官方镜像 `vllm/vllm-openai:v0.28.0`，registry digest
  `sha256:61fc8a896b0a4fbbbdc063bc4b0dbc25ce98e02b5050c24aeb7830ac02039b14`。
- vLLM 0.28.0、PyTorch 2.13.0+cu130、Transformers 5.12.1、Triton 3.7.1。
- 仅提供物理 GPU6 的设备节点；CUDA ordinal 0，UUID
  `GPU-21b327d9-c547-49e9-25e6-58c785af00d6`。CUDA 可用且设备数为 1。
- 已核实 host root `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`
  精确映射至新容器 `/work`，设备号/inode 与宿主一致。
- 主模型 `/data/models/MiniCPM-V-4.7/weights/1b`，draft
  `/public/flagos/jinghao/MiniCPM-V-4.7-1B-DSpark`，均只读挂载且容器内路径相同。
- 原生证据分别位于上述 root 的 `01-environment/dspark-20261008/`、
  `02-issues/dspark-20261008/`、`04-runs/dspark-20261008/`。

## 选型与已复现问题

原 vLLM 0.24 无 DSpark 实现；选择包含原生 DSpark 的官方 0.28 镜像。
vLLM 安装保持只读；产品修改仅在新容器内部实际 editable 安装的
`/vllm-workspace/vllm-plugin-FL`，无 PYTHONPATH 或工作根源码副本。
Plugin 继承已验证统一适配器 `aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68`。
FlagGems 继承已安装 `0dddb4628ae215931171a7f6e04a1183777dcd8a`
及既有广播 mask 修复，未同步或修改原容器源码。

| 问题 | 证据与处理 |
|---|---|
| Docker `--gpus` 无可用设备 driver | 初次对象 `MiniCPMV4.7-1B-DSpark` 停留 Created，从未运行，未删除。改建带显式 GPU6/驱动库映射的 `-gpu6` 容器；CUDA 验证成功。 |
| 新容器 DNS 无法解析 PyPI | 初次依赖下载失败；终止本轮安装进程，保留失败。从相同 Python 3.12 环境离线复制 SQLAlchemy/greenlet 及元数据到标准 site-packages。 |
| 官方镜像无 Git，setuptools-scm 无法推导版本 | editable 构建显式使用带已核实 revision 的版本：FlagGems `5.4.0.dev0+g0dddb462`、Plugin `0.3.0rc2+gaa4228e`；这是本轮构建标识，不是上游发布版本。 |
| Plugin 注册访问已移除的 `fused_moe.FusedMoE` | 在实际导入中复现 AttributeError。对旧 MoE 注册按符号能力判断，dense 算子仍走原 OOT/dispatch。新 MoE 接口未验证，不宣称通用兼容。 |
| Triton 找不到 libcuda | 手工驱动库映射后链接器缓存未更新；在新容器运行 ldconfig，后续模型和 Worker 导入成功。 |
| eager-01 processor 导入失败 | checkpoint 引用的文档常量在 Transformers 5.15 已移除。vLLM 约束为 >=5.5.3，故离线安装已验证的 5.12.1；重打包纯 Python wheel SHA-256 为 `ef266772e0c11e13292df61c8e3ff2c3cc443d6f21eae139ad73dca9d0b49e76`。 |
| eager-02 视觉 merger 权重加载失败 | upstream SelfAttn 的 mapper 使用 `.q_proj`，但嵌套 loader 收到相对名称 `q_proj`，未映射到 packed 参数。 |
| eager-03 初版 mapper 修复失败 | 去掉边界后发生连续子串替换，产生 `qkqkv_proj`。最终将完整 merger 路径的 stacking 放在外层模型 mapper，保留 shard id 下传及原视觉塔映射。 |
| eager-04 Triton 缓存启动失败 | 主/draft 均加载成功，但 FlagGems `bitwise_not` 的第二次缓存启动失败。`libentry.py` 三处完整 constexpr 签名分支仅覆盖 Triton 3.3–3.6，3.7 错走旧分支。仅扩展到 3.7；直接算子负对照、修复和测试保存在 `07-bugs/dspark-triton37/`。 |

## 扩展点与验证计划

DSpark 在 0.28 强制选择 V2 runner。旧 Plugin 复制的 Worker/runner 不具备此实现；
新增 NVIDIA V2 Worker 继承 upstream Worker，沿用其调度与 draft 加载，并保留
Plugin 的 MM attention 修补、OOT 注册和 FlagGems 注册。平台按 vendor/V2 能力选择，
不按模型目录或服务名分支；旧路径保留。

MiniCPM 专用 shim 增加 SupportsEagle3，转发目标层隐藏态设置，并显式返回语言模型
以共享 embedding/lm_head。draft `target_layer_ids=[3,7,11,15,19]` 由 upstream 转换为
辅助层索引 `(4,8,12,16,20)`；复用上游 DSpark 权重加载、Markov head 和验证器。
未修改只读 checkpoint 配置。

首轮诊断 eager 使用 GPU6、127.0.0.1:18348、最大长度 4096、最多 4 请求、14 个
speculative token。现已验证主/draft 完整加载、真实生成、草稿接受、文本/图像、
变输入/并发及同版本无 draft 输出对照；图模式与交付启动器结果见下文。

## 中间验证

正常 pytest 入口运行新 DSpark 契约测试和既有 canvas/backbone 测试，22/22 通过，
原生证据 `02-issues/dspark-20261008/unit-after.log`。其中新增 8 项覆盖三个投影的
weight/bias、已 packed 参数与其他视觉层名称不变、旧 separate-projection 守卫，
以及 EAGLE3 能力与指定隐藏层转发。它们仅验证接口，不代替真实模型生成。
`eager-03/flaggems-oplist.txt` 已生成；后续同时核对服务 Worker 身份日志和生成指标。

### eager-05 实际推理

- 自动客户端完成 5 个顺序请求（含纯红图片）与 4 个并发文本请求，9/9 HTTP 成功，
  非空且无替换字符。翻译“苹果”、乘法“84”、图像“红色”；数数在 128 token 上限
  截断，不能据此宣称完整答题正确。固定输入及响应位于 `04-runs/dspark-20261008/eager-05/`。
- 实际 `WorkerFLV2` 初始化并启用 FlagGems；`silu_and_mul`、`rms_norm` 命中
  default.flagos。主/draft 加载约 4.46 GiB，辅助层为 `(4,8,12,16,20)`。
- Prometheus 增量：99 次 draft、1,386 个 draft token、306 个 accepted token，
  token 接受比例 22.08%，每次 draft 平均接受 3.09 个 token。它仅描述本组功能请求，
  不代表正式性能或普遍接受率。
- FlagGems 聚焦回归 10/10 通过，覆盖缓存调用、constexpr 默认值和 CUDA Graph
  变输入 replay；证据 `07-bugs/dspark-triton37/after.log`。
- 为验证 FULL，仅停止本轮 API 进程组 7075，原生关闭日志及 `stop.json` 保留。
  容器持续运行。第一次端口探针发生关闭时序冲突，未创建 run；确认端口无监听后再启动
  `full-01`，无 draft 对照为同容器 `baseline-01`（18349，V2 runner）。

### 图模式与无 draft 对照

- `full-01` 请求 FULL；0.28 原生 `GDNAttentionMetadataBuilder._cudagraph_support`
  为 `UNIFORM_BATCH`，日志明确自动调整为 `FULL_AND_PIECEWISE`。因此 FULL 未通过。
  检查实际能力声明与编译策略后，不伪造 GDN 的全 prefill 图能力，也不修改 vLLM。
  只有该 backend 对非统一 batch 的状态/元数据更新支持完整 capture 后才可重试 FULL。
- 实际 capture：target PIECEWISE 6 档、FULL decode 3 档、DSpark FULL 3 档，
  合计约 13 秒/0.05 GiB。9/9 请求完成，变输入和并发输出与 eager 9/9 逐字一致；
  accepted/drafted 仍为 306/1386。没有额外开启 replay 计数诊断，证据为实际捕获日志、
  V2 原生图调度及对应变输入请求，未将请求的 FULL 名称当作生效模式。
- 无 draft 同版本、同 Plugin/V2、同请求与 greedy 参数的 9/9 请求也完成。
  显存预算改为 0.25 以与另一服务共存；其余采样和模型输入相同。
  与 DSpark eager 7/9 回答逐字一致，两个天空解释仅措辞不同。
  `baseline-01/comparison.json` 保留全部差异；未定位逐 token 差异的根因，
  不宣称 greedy 逐 token 等价或正式精度通过。并存/首次 JIT 时延不用于加速比声明。
- 原生 DSpark 不接收外部 multimodal embedding，使用目标隐藏态及 text-only draft 输入。
  该版本的警告保留；已验证单张纯色图片，复杂图像/视频能力未验收。
- 对照完成后，仅停止本轮 API 9980、10605；对应 EngineCore 均已退出，容器保持运行。

### 独立启动器

原始 `<host_root>/start-model.sh` 属于既有服务，保持原样。本轮单独的容器内启动器为
`/opt/flagos/dspark/start-model.sh`，证据副本位于
`04-runs/dspark-20261008/model-service/start-model.sh`，SHA-256：
`42acfca5fb034d9cb89313d6babcb5e4d6e8d79c5518c9e6b8675049b21e1e2a`。
`bash -n` 通过，已直接启动该脚本，显式选择 `FULL_AND_PIECEWISE`。
2026-10-08 最终核验：该脚本启动 API PID 12778、EngineCore 13319，health=200，
`/v1/models` 返回正确服务名及 max_model_len=50000。9/9 请求完成，全部输出与
DSpark eager 一致，accepted/drafted=306/1386。新容器与该服务保持运行。
证据 `04-runs/dspark-20261008/model-service/final-verification.json`、
`server.log`、`responses.json`、`metrics-after.txt`。

实际导入仍为容器安装的 `/vllm-workspace/vllm-plugin-FL/vllm_fl/__init__.py` 与
`/vllm-workspace/FlagGems/src/flag_gems/__init__.py`；服务环境无 PYTHONPATH，
最终 source manifest 全部匹配。`01-environment/dspark-20261008/final-container.json`
核实 source 与 `/opt/flagos/dspark` 均非 bind mount，权重仍为明确的只读外部输入，
运行证据与缓存使用 `/work` 挂载。未打包新镜像，fresh-image 验证仍待执行。

保留参数的理由：权重与 trust-remote-code 用于 checkpoint 自定义处理器；服务名/回环地址/
18348 端口隔离既有服务；max-model-len=50000 根据 text_config 上限 262144 和项目
初始上限规则设置（前述 4096 仅诊断）；4 并发、1024 batch token、0.4 显存比例约束
本轮 GPU6 资源；image=1/video=0 限定已验证输入和视觉 warmup 预算；DSpark 配置指定
draft 及 14 token；图 capture 档位 `[1,2,4,15,30,60]` 覆盖 4 并发及 15-token 验证块。
两个 FlagGems 环境变量仅将缓存/自动算子记录放入已批准的 06-cache/04-runs。
其他缓存设置由容器创建环境提供；无 PYTHONPATH、安装/探针/评测、自动杀进程或
性能专用的前缀缓存关闭参数。50K 是配置上限，尚未做 50K 长输入功能验收。

### 源码绑定与中间审查

`02-issues/dspark-20261008/source-manifest-final.json` 绑定 8 个 Plugin 文件和 2 个
FlagGems 文件；相对复制前安装的 `candidate-final.patch` SHA-256：
`c09885b77412f44720bfbbcef5c98b68856f4ca6ebfc24716ff89c2cca767753`。
最终审查修正测试中 dtype 转换的顺序，确保 stride=2 真正非连续，并显式断言 stride；
修正后 7/7 通过，`07-bugs/dspark-triton37/after-stride.log`。旧测试证据仍保留。
vLLM 2,455 个 `.py/.so` 文件前后聚合 SHA-256 均为
`f997cc5d0c8fe40230fb9067b88f009c2f87f8c682f9dab27c68c08894618ddc`。
新镜像无 Git 可执行文件，使用安装文件哈希；继承 Plugin revision 与 FlagGems
既有广播 mask 修复不属于本轮新增差异。本轮没有选定 PR base，也未提交或推送。

模型协议与权重映射归属 MiniCPM shim；旧 Qwen/MoE API 兼容 hook 以能力守卫退出；
NVIDIA 平台选择薄 V2 Worker，沿用 upstream runner，不复制调度或 DSpark 算法；
Triton 签名修复归属 FlagGems。当前已验证 NVIDIA H100、BF16、TP1、dense 模型。
其他厂商、MoE、并行拓扑及旧 vLLM 实际运行未验证，不能据此宣称通用兼容。
各文件职责审查：

| 文件 | 必要性、影响与限制 |
|---|---|
| `vllm_fl/__init__.py`、`ops/custom_ops.py` | 新 API 已移除旧 FusedMoE 工厂；能力守卫跳过旧 hook，dense OOT 保留。新 MoE 接入未实现/未验证。 |
| `patches/qwen3_5_text.py`、`models/qwen3_5.py` | 上游已有 text registry/hybrid 协议时保留上游实现，避免旧 shim 覆盖。旧路径保留，真实旧环境未复测。 |
| `platform.py` | NVIDIA 内核导入转交 CUDA 平台；仅 NVIDIA 且 V2 被选择时使用新 Worker，其他选择分支保留。其他平台缺少硬件验证。 |
| `worker/worker_v2.py` | 薄继承 upstream Worker，接入现有 attention/OOT/FlagGems 注册；不复制 runner，未承诺旧 Worker 的 IO dump 等辅助功能。 |
| `models/minicpmv4_7.py` | 模型专属 EAGLE3/共享语言层协议、packed merger stacking；旧 separate-projection 守卫及视觉名称在单测覆盖。 |
| `tests/unit_tests/test_minicpmv47_dspark.py` | 进入正常 pytest 入口，验证真实 mapper 及协议；不替代数值推理。 |
| `src/flag_gems/utils/libentry.py` | Triton 3.7 缓存 launch 签名兼容；旧版本分支保留，未假定未来 3.8+ 兼容。 |
| `tests/test_libentry_triton37.py` | 直接 GPU 算子、constexpr 默认值、非连续布局、变输入 graph replay；无模型依赖。 |

审查结论：当前 H100/BF16/TP1 的功能试跑路径成立，没有改动 vLLM 或绕开 Plugin
dispatch；正式 PR 候选前仍需公共兼容 hook/worker 选择的守卫两侧及其他受影响路径
验证，且需明确 PR base。没有提交 PR，不标记完整适配或正式验收完成。
本地 audit 仍报告已有 12 个 profile revision 不匹配、78 项需复核；本轮不改写历史状态。
