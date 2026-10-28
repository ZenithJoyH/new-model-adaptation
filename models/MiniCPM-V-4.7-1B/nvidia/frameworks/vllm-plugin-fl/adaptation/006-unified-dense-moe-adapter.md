# 006：1B 与 35B 共用 MiniCPM-V 4.7 Plugin 适配器

## 范围与身份

- 日期：2026-10-08；状态：`functional-passed`，仅本次代码整合及功能回归，不代替正式精度、性能验收。
- Host：`H100-149`；新增容器 `MinicpmV4.7-unified-20261008`，ID
  `9013fa8b0a35c97db645d8bd57ec7bbc055bda1b8fab758a2f294907ff5804d3`。
- 从原 1B 容器执行不暂停的快照，基础镜像
  `minicpmv47-unified:base-20261008`，ID
  `sha256:dc705e7c5ee7f8a2f363f4ca23000918ff2938360a577afe082fadf98a5b0fa8`。
  此镜像是修改前基础快照；整合后的文件当前在新容器文件系统中，未声称发布镜像验证通过。
- 两模型权重 `/data/models/MiniCPM-V-4.7/weights/{1b,35b-a3b}` 只读挂载。
  两原工作根分别精确挂载到新容器同路径，已核实设备号与 inode：
  `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`、
  `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`。
- 只提供物理 GPU 6/7 设备节点；新容器 CUDA ordinal 0/1 的 UUID 分别为
  `GPU-21b327d9-c547-49e9-25e6-58c785af00d6`、
  `GPU-d508af44-d081-7d8d-0ebe-1a2d15266369`，对应宿主机 GPU 6/7。
  服务使用 `CUDA_VISIBLE_DEVICES=0,1`、两模型均 TP2。
- `/usr/bin/python3` 的 editable Plugin 实际导入
  `/vllm-workspace/vllm-plugin-FL/vllm_fl/__init__.py`，源码非挂载；无 `PYTHONPATH`。
  Plugin `main@3a27a6fb2d514cdf55c00481bf813225dac63319`。
- FlagGems 继承 1B 环境的 `0dddb4628ae215931171a7f6e04a1183777dcd8a`
  及问题 003 的广播 mask 修复；本轮未改算子或同步源码。
  FlagGems-vllm `e13419a429bfba65f4757a7671b1aebfe25c61a2`；vLLM `0.24.0+cu129` 只读。
- 两原容器、原 Plugin 安装及现有 8001/8021 服务未更改。

## 差距与职责选择

原 1B 适配器继承 4.6 constructor，其语言骨干固定 dense；原 35B 适配器重新
初始化同一视觉塔，但语言骨干固定 MoE。因此，两边虽然 Git HEAD 一致，模型文件
却不相同，不能任选一个直接覆盖另一个。两边 canvas checkpoint 算法一致；
35B 的 `max(position)+1-seq_len` 与 1B 的 `reference_delta+1` 在该接口中等价，
不是两种不同的位置基准。

采用既有模型 registry 与模型专用 shim：按 `text_config.model_type` 选择
`qwen3_5_text` → `Qwen3_5ForCausalLM` 或
`qwen3_5_moe_text` → `Qwen3_5MoeForCausalLM`，未知结构显式拒绝。
共用上游 4.6 视觉组件、processor、权重加载和状态接口；仅因上游 constructor
没有语言骨干工厂参数而复用其初始化协议，不复制整个模型、不修改 vLLM 或公共 worker。
临时切换外层 model_type 后以 finally 恢复，保留 upstream 初始化语义。

canvas 路径共用 1B 的 feature geometry 校验、图像/视频字段选择、bounds/grid 数量校验，
保留纯文本与非 canvas fallback；采用 tokenizer 声明的特殊 token，惰性加载 tokenizer
及 checkpoint 自带 M-RoPE，不在公共调度热路径按模型名/权重路径分支。

## 真实 diff 与设计审查

继承差异为 1B 的 `vllm_fl/__init__.py` 懒注册、模型文件及 canvas 测试。
本轮只改模型文件、扩展 canvas 测试、新增 backbone 测试；注册和
`vllm_fl/models/qwen3_5.py` 不变。当前 HEAD 与观察到的 origin/main 相同，
本轮未确认新的 PR base、未提交/推送/建 PR。

| 文件 | 职责 / SHA-256 |
|---|---|
| `vllm_fl/__init__.py` | 继承的 4.7 懒注册；`4082f3a94ff9eb5c928a7b014de2d9d2abc1f8f670b22f01dd199437408e0080` |
| `vllm_fl/models/minicpmv4_7.py` | 双骨干与公共 canvas 桥接；`9a1ad18e4c23d1ea2c63dc9884618c9260b0b4f7aca094f97816bb920ceaf4a7` |
| `tests/unit_tests/test_minicpmv47_backbones.py` | 配置选择、未知结构、初始化成功/异常后的恢复；`30e32e545344a61c2a18614654699449220f8796869da67b293cd22cf7890095` |
| `tests/unit_tests/test_minicpmv47_canvas.py` | 文本、canvas、视频字段、缺失/非法 geometry 及 delta；`9d328c314273d075f76d7ec3426698a7c6da7823e708c2ff8539865d3524be5e` |

完整候选包含继承注册，共四文件；patch SHA-256
`36525f62034c73fa6758f754e40d34c531f567fe4dcca8c78d5c9000f800c4aa`。
`git diff --check` 通过；原版备份与本轮源码清单在下列原生证据目录。

## 受控尝试、过程文件与缓存

以下 `<root>` 均为已核实的 35B 工作根，所有运行输出集中在
`<root>/04-runs/unified-adapter-20261008/`；一次性代码位于
`<root>/02-issues/unified-adapter-20261008/`，没有第二份产品 checkout。

| 尝试 | 结果与处理 |
|---|---|
| Docker 快照创建 | 快照成功；Docker 弃用提示混入 stdout，首次解析 image ID 失败。改为 image inspect 读取结构化 ID 后成功建容器。 |
| `1b-eager-ipc-path-failed` | TMPDIR 加 UUID 超过 UNIX socket 107 字符限制；缩为 `<root>/05-tmp` 后继续。 |
| `1b-eager-uuid-failed` | 当前平台整数设备映射拒绝 UUID；新进程核实 CUDA 0/1 的实际 UUID 对应 GPU6/7，改为容器 ordinal 后继续。 |
| `CUDA_VISIBLE_DEVICES=6,7` 探针 | 因新容器仅有两个设备节点，CUDA 枚举只含 0/1，探针检测到 0 GPU；没有修改公共设备映射代码。 |
| `1b-eager-client-av-failed` | 服务完成初始化，但客户端在发请求前因缺少 PyAV 退出；改用 vLLM 已支持的 `data:video/jpeg` 双帧输入，不安装无关依赖，失败日志保留。 |
| `client-budget-interruption.json` | 1B 冷编译请求逼近旧客户端 180 秒预算；只停止 controller，保留已核实 API 进程，改用 600 秒请求预算继续；旧在途预热不计入通过数。 |
| `slicing-coverage-controller-transition.json` | 为补充真实大图切片回归，只替换 controller，保留 1B graph API 及其图捕获状态；最终 `resume-v6.py` 从原进程继续，未重放服务启动。 |
| `cache-isolation-invalid-test-key.log` | 首次隔离探针使用了非十六进制缓存 key，被 Triton 构造器拒绝；改用合法 key 后完成真实文件写入隔离验证。 |

使用 `XDG_CACHE_HOME=<root>/06-cache/unified-adapter-20261008`，保持缓存写入边界。
复用 35B 问题 003 的逐进程 Triton 缓存隔离经验，在新容器内部安装
`/usr/local/lib/python3.12/dist-packages/minicpm_triton_cache.pth` 及同目录
`minicpm_triton_cache_runtime.py`：仅在
`MINICPM_TRITON_CACHE_BASE` 存在时设置 `pid-<pid>` 子目录，不导入工作根 Python 文件，
不使用 PYTHONPATH，也不改变 Plugin/FlagGems dispatch。
这是当前 Parastor 环境的已知规避，未证明或修复底层文件系统竞态。
初次 1B 已完成编译但客户端失败；随后将已结束 worker 的缓存合并为只用于读取的 seed，
新进程在导入编译器前将 seed 硬链接到自身 PID 目录。已检查真实 Triton cache 和 autotuner
写入使用临时文件与原子替换；`cache-isolation.log` 验证初始 inode 共享、真实 cache.put
后新 PID 文件 inode/内容改变、seed 内容保持不变。各轮结束后一次性 controller 仅合并
新增 key；不修改编译器或内核代码、不据此报告冷启动或 benchmark 性能。
对应来源见 `seed-provenance.json`；最终执行代码为 `validate-v6.py`、`resume-v6.py`。
1B 首次真实形状编译出现最长约 154 秒请求，本轮仅做功能判定，不作为性能数据。
只有在当前共享文件系统上复验多 worker 并发写缓存无 `Errno 16`、且两模型的 cold start / graph
回归通过后，才可移除逐 PID helper；seed 仅用于复用编译结果，缺少 seed 不改变模型语义。

历史 FULL 被 GDN `UNIFORM_BATCH` 能力降级的证据见问题 004 / 35B 问题 005。
本轮遵守用户选择，复验 `FULL_AND_PIECEWISE`；不把分段 prefill 写成全量 FULL。

## 已执行验证

- 原适配器运行新增 backbone 测试失败，缺少 `_get_language_model_class`；
  合并后正常 pytest 入口 14/14 通过，见 `backbones-before.log`、`unit-after.log`。
- `canvas-reference.json`：两个真实 checkpoint 各 4 例（thumbnail、portrait、slice、video），
  8/8 位置张量与参考算法逐元素一致，delta 满足 `context_len+delta=max(position)+1`。
- 无 GPU 导入隔离检查：新/原 1B 安装均在未进入模型模块前，因未改动的
  Plugin `utils → FlagGems DeviceDetector` 报 `No device were detected`。
  这是继承限制，不能声称 CPU 导入或其他平台已验证；证据 `no-gpu-import*.log/json`。
- 两模型各 eager 6/6、graph 19/19，合计 50/50 API 请求通过。
  两模型 graph 均已捕获 mixed PIECEWISE 7/7、decode FULL 5/5；大图输入均为 489 prompt token。
  以各 run 的 `command.json`、`server.log`、`checks.json` 和总 `result.json` 为准；
  汇总见[共同功能验证](../acceptance/unified-code-validation-2026-10-08.md)。

## 最终设计审查

结论：在本次 NVIDIA BF16、TP2、两种 4.7 text architecture 范围内，整合实现可用，
可作为限定该范围的 PR 候选。没有新增公共 dispatch/worker 分支、全局算子策略或 vLLM 修改；
初始化仅在模型 shim 内选择语言类，parent 方法继续拥有视觉前向、processor、权重映射和状态协议。
四文件候选 diff 与最初 inherited diff 已分开记录，部署缓存 helper/启动器不混入 Plugin patch。
异常路径显式报错或 finally 恢复配置；没有 catch-all 静默 fallback。

两个真实骨干均在 eager/graph 下加载并完成 prefill/decode、变输入重放、多图、视频字段与
十并发回归，文本/关闭 canvas 守卫由契约测试覆盖。正常 pytest 14 项与 checkpoint 8 项
位置对照补充接口证据，不冒充整模精度。未知模型结构显式拒绝，未测试的 dtype/量化、
其他平台/并行拓扑不在支持声明内。无 GPU 导入失败已用旧安装对照证明为继承限制。
整合验证阶段未执行提交、推送或建 PR。随后用户授权提交到指定仓库的新分支，结果见下节。

运行后重新核对四文件、公共 Qwen3.5 实现、内部缓存 helper 与共用启动器哈希，均与冻结
输入一致；`git diff --check` 通过。vLLM 2057 个 `.py/.so` 文件的内容/路径聚合 SHA-256
前后均为 `8fb38bcb183ed0d912e9ce107a1269865dca66a67d849f5f4469d4c53117ba8d`。
最终 `final-validation.json` 与 `final-host-state.json` 均为 `passed`：新容器仍运行，
验证服务停止、18347 关闭、物理 GPU6/7 空闲；原两适配器哈希未变、8001/8021 API 返回 200。
最终证据哈希见共同功能验证报告；不将本地 audit 或自建功能摘要当作正式框架验收回执。

## 2026-10-08：提交到指定仓库

按用户后续授权，已在新容器的实际安装 checkout 创建 `support-minicpmV4.7` 并提交，
推送到私有仓库 [flagos-day0/vllm-plugin-FL](https://github.com/flagos-day0/vllm-plugin-FL)。
远端[分支](https://github.com/flagos-day0/vllm-plugin-FL/tree/support-minicpmV4.7)头为
[`aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68`](https://github.com/flagos-day0/vllm-plugin-FL/commit/aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68)，
标题 `feat(models): support MiniCPM-V 4.7 dense and MoE backbones`。
该提交仅包含上表四个适配/测试文件，共 354 行新增；提交身份取自操作者本机既有 Git 配置，
GitHub 确认作者 `ZenithJoyH`。

目标 `main` 为 `d2d7234aa576a5b6224e99d18500f9b177ebb1e4`，是已验证基线
`3a27a6fb2d514cdf55c00481bf813225dac63319` 的祖先。新分支以已验证基线为父版本，
因此相对目标 main 还保留 26 个已有上游提交（215 文件差异），不能把这些继承变化
当成本次四文件适配提交。目标 main 在推送核验时仍为上述旧 SHA。
不将本轮已验证结果推广到旧 main 上重新移植的版本。

通过操作者已有 GitHub CLI 权限推送；远端创建要求分支尚不存在。
`git ls-remote` 与认证 GitHub API 均核验分支头、父提交和四文件清单。
提交后实际 checkout 干净，适配文件及公共 Qwen3.5 文件哈希与整模验证时一致；
没有重跑内容未变化的服务矩阵。过程记录为原生证据目录中的
`git-publication.json`、`git-publication-verified.json`；历史功能验证 JSON 保持原快照。

本轮是 NVIDIA 双模型整合，mock 仅用于 constructor 选择/恢复契约，不作为设备数值验证。
不扩展到未授权平台，不运行正式 GPQA/FlagEval 精度或性能测试，不升级 framework 状态。
知识库处理：`local-only`。原容器继续运行，临时验证服务仅由本轮 controller 管理。

本地 `./scripts/audit-workspace --repository-only` 返回 12 个已有 profile revision 错误及
78 项历史待复核（包括两模型 profile_version=4 与当前 profile_version=6 的差异）；
不以修改历史指纹消除错误。新增内容仅 Markdown，未扩展迁移或修复其他模型的工作范围。
