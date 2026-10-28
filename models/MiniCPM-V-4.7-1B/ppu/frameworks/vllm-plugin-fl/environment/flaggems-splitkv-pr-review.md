# FlagGems split-KV 输出寻址修改审查

## 范围与版本

2026-10-08 agent 自审，范围为 MiniCPM-V-4.7-1B / PPU / `vllm-plugin-fl` profile v6，Host `PPU-13`、容器 `minicpmV4.7-1B`。用户明确要求提交 issue 和关联 PR；上游审查和合并由维护者决定。

目标仓库 `flagos-ai/FlagGems`，base `master` / `0958d2da98055f1e2198a56201e3eea6f7591981`。既有 `/workspace/FlagGems` 初始 clean、`master → origin/master`，按用户此前授权快进到该基点；当前工作树三项 tracked 修改及一项新增测试均属本任务。安装包 5.3.5 实际位于 `/usr/local/lib/python3.12/site-packages/flag_gems`；直接修改其中两个公共算子文件，没有 PYTHONPATH 覆盖或整体升级。vLLM 0.24.0+empty 保持只读；Plugin `3a27a6fb2d514cdf55c00481bf813225dac63319` 的既有未提交适配差异保留。

发布提交 `b0009abd20531db1a4dd1d1ee60dc9f28055713c`，仅比 base 多一个提交、四个文件（+237/-4）；逐文件 Git blob 与已测试候选一致。无 inherited diff；未继承 #6871 mask 修复。详细 SHA-256、原生回执和命令见 [问题 002](../adaptation/002-visual-output-corruption.md)。

## 问题、职责与接口

触发签名：BF16/FP16 FlashAttention split-KV，partial 按 `[split,B,H,S,D]` 排列，输出为 BSHD view。原实现混合 flattened head-major 基址与 sequence stride，造成漏写、重叠写和逻辑输出外写入；head stride 参数另传错轴。

沿现有 `ATen flash → flash_attention_forward → mha_fwd → split/combine` 修复公共 combine 的寻址契约。禁用 split 或强制 FP32 可绕开，但不修复该算子的合法布局错误，故不作为本 PR 方案。没有新增模型名判断、dispatch/backend 体系或 SDK 依赖。

| 文件/符号 | 修改目的及影响边界 |
|---|---|
| 公共 `flash_kernel.py::flash_fwd_splitkv_combine_kernel` | 按 B/H/S 解 flattened row，使用输出 batch/head/query stride；只改最终写回，不改 partial/LSE 归约 |
| 公共 `flash_api.py::mha_fwd` | 更正 head stride，传 H/Q；只有 split-KV combine 分支新增参数 |
| Enflame GCU400 `flash_api.py` | 此调用方导入公共 combine，必须同步参数；独立厂商内核不变 |
| 新增测试 | 独立 CPU 参考、真实内核、足量保护存储；只替换 split 选择所需的 SM 数元数据 |

公共 API、dtype、输出 shape/alias、末轴连续要求、split heuristic、partial buffer、注册和缓存行为不变；新增 constexpr H/Q 自然参与 Triton 特化。不影响未命中 split 的分支；无量化、KV cache 协议或 optional SDK 接口变更。

## 回归与未验证范围

| 场景 | 平台与执行方式 | 结果 |
|---|---|---|
| 修复前 guarded 公共入口 | PPU3，原安装包，真实 split/combine | 81.1% 元素不匹配，最大误差 123.3125 |
| 三种 layout、多 batch/head、尾块、32/64/96/128 维、2/3/5 splits | PPU3，FP16/BF16 eager，CPU 加权输出/LSE 参考 | 24/24；孔洞和尾部哨兵不变 |
| 公共 mha_fwd、out alias、真实 split 命中 | PPU3，三 layout、两 dtype | 6/6 |
| combine graph capture，两次更换 partial/LSE 后重放 | PPU3，连续与 head-major、两 dtype | 4/4 |
| 捕获的视觉 Q/K/V、原始 stride、72→96 自动补齐 | ATen flash 单算子注册，真实两路 split | 3/3 有限，最大误差均 0.0087063313 |
| Enflame GCU400 caller | 源码 import/callsite 检查、Python 语法 | 接口匹配；未做硬件数值验证 |
| NVIDIA/其他厂商、完整视觉链、服务图、正式精度/性能 | 未执行 | 不作通过声明 |

旧 wheel 缺少最新源码 conftest 依赖 `cli_override`，原生测试入口收集失败已保留；最终用同一测试文件的自包含 pytest 入口执行，实际 import 仍为原安装包。首个 SM 元数据夹具未保留设备属性的失败亦保留，最终已委托原属性。无扩大 skip/xfail 或吞异常；graph 的 CUDA 兼容设备条件明确，不声称其他设备支持。容差按低精度归约误差设置，旧实现的 123 量级错误不可能被容差覆盖。

Python 语法、Black、isort、flake8、`git diff --check` 通过。项目离线测试通过，workspace audit 仍有原来的 12 项 profile revision 错误，不改历史验收状态。未重启服务或容器；末次 8000 `/health=200`，现有 Plugin FP32 缓解保留；没有正式性能基线或新镜像验证。

## 结论

### isort 补充审查（2026-10-08）

最新 HEAD 为 `c13d2aba866e46b235a7bcae88a68e7ec2090e04`，仅在前一 HEAD 上修正两份测试的第一方 import 分组，严格对应 code-style job `113143976550` 的 isort diff，生产源码与测试函数不变。临时目录未还原仓库第一方包识别曾使本地 isort 漏检；现已以 `-p flag_gems` 显式分类复核，isort/Black/Flake8 通过。最新 HEAD 的 code-style、rule-check-required、NVIDIA、Enflame、unittest-required 与 CLA 均已 success；NVIDIA 正常/quick CPU 各 34 passed，Enflame 各 30 passed/4 skipped，其余平台按既有工作流跳过。完整模型精度/性能未验证。详细证据见问题 002 的 isort 补充记录；下方历史 CI 失败记录保留。

### CI 修复补充审查（2026-10-08）

当前发布 HEAD 更新为 `27f8001e54f5e6474c54566e07776f7f87ef723a`；相对 base 为两个提交、五个文件（+257/-4）。第二个提交只把原测试拆成 `test_flash_kernel.py`（28 项）和 `test_flash_api.py`（6 项），沿用上游 CI 的模块名/测试文件名对应契约。API 测试仅相对导入 kernel 测试中的常量与辅助函数，不导入测试函数；tests 是既有 Python package。无 CI 工作流修改或新增产品依赖；全部原函数、参数化 decorators、断言通过 AST 等价核对。三项产品源码保持初始修复内容。

实际 Actions 日志新增硬件证据：初始 NVIDIA job 34 passed；Enflame job 30 passed、4 CUDA graph skipped。其后失败分别来自无匹配辅助模块 marker、全目录收集触发无关 GCU FP8 导入 abort；格式/规则 job 则在拉取代码时超时。此次调整消除本 PR 的错误 marker 收集，本地执行原路由脚本验证正常/quick CPU 路由和失败传播均符合预期，本地格式检查通过。新 HEAD 的 NVIDIA 与 Enflame job 均 success：正常/quick CPU 各 NVIDIA 34 passed、Enflame 30 passed/4 skipped。code-style/rule-check 仍在 checkout 连续五次超时而失败，检查未执行；请求重跑返回 GitHub 403，需维护者处理 runner 网络/代理与重跑，不能声明全部 CI 通过。原“其他厂商未测”只代表发布前人工验证；完整模型与性能未测的限制仍成立。详见 [问题 002 的 CI 修复记录](../adaptation/002-visual-output-corruption.md)。

可作为上游 PR 候选，已提交 [Issue #6872](https://github.com/flagos-ai/FlagGems/issues/6872) / [PR #6873](https://github.com/flagos-ai/FlagGems/pull/6873)，GitHub 关联已核实，PR 未合并，当前 HEAD 的已启用 CI 检查均通过，维护者审查待完成。贡献 diff 不含日志、权重、环境快照、机器路径或诊断脚本。算子修复的通过不等于完整模型适配或精度验收。

### 撤除 FP32 OOT 后续验证（2026-10-08）

用户要求尝试撤除后，已删除 Plugin 专用 FP32 attention 文件、测试及注册，`custom_ops.py` 恢复为当前 Git HEAD 内容。正常模型加载验证上游 MMEncoderAttention 类型、BF16 Q/K/V 及真实 FlagGems flash 调用，离线 7/7 正确、162 次 attention 输出无非有限值。原脚本重启服务，FULL_AND_PIECEWISE 的混合 PIECEWISE/decode FULL 各捕获 51/51，HTTP 文本/单图/双图 25/25 正确（含两轮 10 并发），保留移除。视觉 encoder 本身仍按当前配置不编译/不捕图；正式精度、性能、长负载和镜像打包未验证。首轮双图 token 截断及补测过程均保留，详见 [问题 002 撤除与服务验证](../adaptation/002-visual-output-corruption.md)。
