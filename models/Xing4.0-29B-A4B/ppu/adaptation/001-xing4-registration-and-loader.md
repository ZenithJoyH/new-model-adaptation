# 001：新 Xing4_0 身份注册与严格新权重加载

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-16
- 最后验证时间：2026-09-16
- 模型：`Xing4.0-29B-A4B`
- 平台与 Host：PPU / `PPU-13`
- 容器：`xing4_0`；镜像见环境分析
- 容器 Plugin 工作树基线：`0ef3d87`。远端分支基线 / 最新提交：
  `origin/main@d2d7234` / `support-Xing4.0@f888ec8`。FlagGems / FlagGems-vllm /
  vLLM：`1c8dce7` / `bbc9404` / `ee0da84`。
- 执行模式与负载：TP4、BF16、graph、max model len 50000、prefix caching enabled，
  `CUDA_VISIBLE_DEVICES=0,1,2,3`

## 问题现象与根因

新权重配置声明 `Xing4_0ForCausalLM`、`model_type=xing4_0`，起始 Plugin 只注册
`XingChen4ForCausalLM/xingchen4`。新权重索引只包含 `hc_fn/hc_base/hc_scale`，用户明确
不要求旧权重兼容。

实现后真实启动又暴露两个独立前置条件：

1. checkpoint 带 `auto_map`，当前 vLLM 0.24 仍要求 `--trust-remote-code`，即使最终模型类由
   Plugin registry 解析；缺少该参数时在 worker 创建前退出。
2. PPU dispatch 的 `attention_backend` 首选 FlagGems。MLA 下若未设置
   `VLLM_FL_USE_FLAGGEMS_ATTN=1`，当前 FlagGems backend 返回一个 `ValueError` 对象，vLLM
   随后把它误当类路径并在 `rsplit` 处失败。加入用户旧命令中的该开关后，4 个 rank 均命中
   `vllm_fl.dispatch.backends.flaggems.impl.mla.MLAFLBackend` 和 CUSTOM MLA prefill。

## 参考与设计决定

| 参考 | 复用内容 | 未复制内容 | 决定 |
|---|---|---|---|
| vLLM PR #57135（head `25aa52a`，draft） | `xing4_0` identity、think/tool 协议、新 `hc_*` 权重语义 | 模型内进程级 `USE_FLAGOS` 和对 vLLM core 的修改 | 用 Plugin registry/dispatch 实现 |
| PR #54051 / 旧 XingChen4 适配 | DeepSeek-V2 MLA/MoE 组装、Plugin mHC dispatch、PPU 启动形态 | 旧 identity、checkpoint alias/fallback | 仅迁移必要通用能力；main-based 分支只新增 Xing4 identity |
| 当前 FlagGems-vllm | clamp `[-30,30]`、20 次 Sinkhorn、CUSTOM MLA backend | 无新算子复制 | 直接复用并做 focused/真实 graph 验证 |

## 实现

直接修改容器内 verified editable Plugin `/workspace/vllm-plugin-FL`：

- `vllm_fl/configs/xing4_0.py`：独立 `Xing4_0Config`，直接继承 `DeepseekV3Config`，只接受
  `hc_mult/hc_sinkhorn_iters/hc_eps`，不再生成旧 alias 属性。
- `vllm_fl/models/xing4_0.py`：包含完整 Xing4.0 architecture/mHC/loader 实现，不再继承或导入
  XingChen4；loader 只接受 `hc_fn/hc_scale/hc_base`，跳过未启用的 MTP 层。
- `vllm_fl/reasoning/xing4_0_reasoning.py`：按 PR #57135 独立实现 think-token 协议，不再继承旧
  parser。
- `vllm_fl/tool_parsers/xing4_0_tool_parser.py`：采用 PR #57135 的 JSON/tag 双格式 parser；仅将
  协议类型导入改到当前 vLLM 0.24 的 `openai.engine.protocol`。
- `vllm_fl/__init__.py`：只注册 `xing4_0` config converter、model、reasoning parser 和 tool
  parser；删除 `xingchen4` 的三个注册入口。
- 删除 `vllm_fl/{configs,models,reasoning}/xingchen4*.py`，增加独立 reasoning focused tests。
  未改 vLLM、FlagGems-vllm、权重或 inherited dirty 文件。

## 受控尝试

| 轮次 | 唯一变量 | 结果 | 结论/证据 |
|---|---|---|---|
| 0 | 只读 identity/index 检查 | 新身份未注册；新 hc 键完整 | 需 Plugin 扩展点变更 |
| 1 | 新 config/model/reasoning 注册 | 4 个 config tests、fresh registry/config load 通过 | 新 identity 与严格 config 生效 |
| 2 | graph smoke，无 `--trust-remote-code` | vLLM 拒绝 checkpoint `auto_map` | 保留该启动参数；`graph-smoke-20260916-01` |
| 3 | 仅增加 `--trust-remote-code` | MLA backend 返回 `ValueError` 对象，worker 初始化失败 | 缺少 FlagGems MLA 开关；`graph-smoke-20260916-02` |
| 4 | 增加 `VLLM_FL_USE_FLAGGEMS_ATTN=1` | 41/41 权重、KV cache、mixed/full graph、最小生成全部成功 | graph 主路径通过；`graph-smoke-20260916-03` |
| 5 | 增加 PR tool parser | PR 新版协议 import 在 vLLM 0.24 不存在 | 仅调整 import；parser tests 3/3 通过 |
| 6 | 移除 XingChen4，改为 Xing4-only 独立实现 | 13/13 focused tests；fresh registry 旧键全 false；真实 checkpoint config/module 通过 | config/model/reasoning 不再继承旧实现；`xing4-only-20260917-01` |

## 验证结果

- 最新 Plugin config/reasoning/tool parser tests：13/13 通过；收据
  `/mnt/nfs/users/jinghao/xingchen4/04-runs/xing4-only-20260917-01/plugin-tests.log`。
- FlagGems-vllm clamp/Sinkhorn focused tests：6 通过、1 deselected；测试源
  `/workspace/FlagGems-vllm/tests/test_mhc_pre_clamp_sinkhorn.py`。
- fresh process：`xing4_0` config/model/reasoning/tool 全部注册；`xingchen4` config/model/reasoning
  全部未注册。真实 checkpoint 解析为独立 Plugin `Xing4_0Config`，且不存在
  `num_residual_streams` 旧属性；模型模块只导出 Xing4.0 identity。收据为同目录
  `registry.log` 与 `checkpoint-module.log`。
- 真实模型：41/41 safetensors 分片加载；KV cache 1,391,296 tokens；50k 上下文理论并发
  27.83x；mixed PIECEWISE 51/51（冷启动 22:10）与 FULL decode 51/51（00:31）capture 完成。
- 最小 chat 请求成功生成 16 tokens，reasoning parser 返回结构化 `reasoning`；响应
  `/mnt/nfs/users/jinghao/xingchen4/04-runs/graph-smoke-20260916-03/chat-response.json`，服务日志
  同目录 `server.log`。
- 2026-09-16 的真实图模式结果属于独立化重构前基线：`server.log` =
  `ff51bcc489f61c21a179bd73ee9d9a397d8bd497db6714ebad3a80f3a5f2ec11`；
  `chat-response.json` = `5ba58ca7ae85a7b299496f1bdcac36fcc8863a97d02bf56436990259256f1e98`；
  旧 `plugin-tests.log` = `9cd4dff177e534f0fc36a3ebb9eaf2d8b76db8a6bd6fc27b6d2dee88c8864e00`。
- 2026-09-17 最新收据 SHA-256：`plugin-tests.log` =
  `4cfcccf35b00b9d374ae66a861a9f83d82eb91937099f8a6076fa5cb4d6d48c2`；
  `registry.log` = `4377452f3dabec1321a77b344c76b97bf2a1cf747d98cac89b81c24a2423a57d`；
  `checkpoint-module.log` = `1e1c162cef392cfd8451b18ebbea1b199ea2e62d3188771a128ab41357241535`。
- vLLM 仍为 `ee0da84ab9e04ac7610e28580af62c365e898389` 且 clean；FlagGems 为
  `1c8dce74d9843a599a303c2c16b8cbe762f5429d` 且 clean。Plugin inherited mode-only 文件与
  `thead.yaml` 修改保持原样。
- 2026-09-17 已再次按用户要求重写 `origin/support-Xing4.0`：不再以
  `origin/support-Xingchen4` 为父链，旧提交 `ed84b6e`、`7bb7149` 均已从该分支历史移除。
  当前唯一提交为 `f888ec82aa913aa7922c12d68dcf20627c41f5de`，唯一父提交是
  `origin/main@d2d7234aa576a5b6224e99d18500f9b177ebb1e4`。
- main 本身没有 Xing4 所需的 mHC dispatch、FlagGems MLA、T-Head MLA prefill 和 T-Head graph
  能力；这些必要基础设施与 Xing4 adapter 被合并为同一提交。benchmark/docker mode、NVIDIA
  MoE 配置、冗余 packaging 和未使用 worker cache 改动均未迁移。提交不包含容器 inherited
  dirty 文件，未创建 PR。

## 限制与退出条件

- 本轮没有选择 acceptance，未运行正式 sanity/accuracy/performance，也未创建最终
  `start-model.sh`；因此适配工作流阶段不标记 complete/optimized。
- 当前 8040 smoke 服务已退出。PPU 0–15 均被后来启动的四个非本轮 TP4 服务占用，本轮没有
  停止这些服务，因此 Xing4-only 独立化后的 fresh graph/load 尚未重跑；2026-09-16 graph
  结果只作为重构前基线，不作为最新代码的完整运行时收据。
- tool parser 由独立单测和 fresh-process 注册验证，尚未做带 tools 的 API 端到端测试。
- MTP、DSA、量化、eager 和其他平台未验证；新入口只承诺该 BF16、非 DSA、TP4 PPU 路径。
- `VLLM_FL_USE_FLAGGEMS_ATTN=1` 是当前 PPU graph 启动的必要条件；若 dispatch 修复为合法
  vendor fallback，可重新评估该显式变量。
- 当前知识保留为该模型/PPU 的本地适配记录，不推广成跨平台 troubleshooting 条目。
