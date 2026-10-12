# Xing4.0-29B-A4B Plugin 修改设计审查

## 范围、版本与所有权

- 目标：`PPU-13` / `xing4_0` / `/workspace/vllm-plugin-FL`（editable install）。
- 审查日期：2026-09-17。远端分支基线为
  `origin/main@d2d7234aa576a5b6224e99d18500f9b177ebb1e4`；最新 Xing4-only 代码形成
  单一提交 `f888ec82aa913aa7922c12d68dcf20627c41f5de`，已推送到
  `origin/support-Xing4.0`。容器 editable 工作树仍以 `0ef3d87` 为基线并保留 inherited
  dirty，未通过 reset/rebase 改写。
- inherited dirty：5 个 CI/build 文件 mode-only，另有
  `vllm_fl/dispatch/config/thead.yaml` blacklist 修改；本任务均未改动、重置或据为己有。
- vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`，clean、只读。
- FlagGems 从 `3f2989283fb6212fc5e18dba6a52826c0bc02285` fast-forward 到
  `1c8dce74d9843a599a303c2c16b8cbe762f5429d`，clean `master...origin/master`。
- FlagGems-vllm `bbc94043fd35f357e3e41350adce62246ec6d569`，clean detached、只读。

## 最终设计

变更只落在模型/config/parser 注册扩展点，继续通过既有 Plugin dispatch 调用 mHC、MLA 和
MoE；不修改 vLLM core，不在模型模块内启用进程级 FlagGems。Plugin 不再注册或保留
XingChen4 的 config/model/reasoning 文件；`xing4_0` 为独立实现，只接受新 config 与
`hc_fn/hc_scale/hc_base` 权重协议。

| 文件/符号 | 目的 | 公共影响 | 未命中行为 |
|---|---|---|---|
| `vllm_fl/configs/xing4_0.py` / `Xing4_0Config` | 独立 model_type 与严格 config 字段 | 仅 `xing4_0` | 旧 alias 显式 `ValueError` |
| `vllm_fl/models/xing4_0.py` / `Xing4_0ForCausalLM` | 完整独立 architecture/mHC/loader | 仅 Xing4.0 | 其他 architecture 不变 |
| `vllm_fl/reasoning/xing4_0_reasoning.py` | 独立 reasoning key | 新 parser key | 旧 `xingchen4` 不变 |
| `vllm_fl/tool_parsers/xing4_0_tool_parser.py` | PR #57135 的 JSON/tag tool 协议 | 新 tool parser key | 未启用 tool choice 时无影响 |
| `vllm_fl/__init__.py` | config/model/reasoning/tool 懒注册 | fresh/spawn worker 可见 | 其他 registry key 不变 |
| 三个 focused test 文件 | 严格字段、reasoning 与 tool parser 行为 | 无运行时影响 | 不适用 |

新 tool parser 与 PR #57135 算法一致；唯一版本性调整是将新版
`vllm.entrypoints.generate.base.protocol` 导入映射到当前 vLLM 0.24 的
`vllm.entrypoints.openai.engine.protocol`。未复制 PR 的全局 `USE_FLAGOS` 分支，因为 PPU
硬件策略属于 Plugin dispatch；实际服务显式设置 `VLLM_FL_USE_FLAGGEMS_ATTN=1`。

## 实际 diff 与来源区分

最终 `f888ec8` 相对 `main@d2d7234` 的变更为：

- 27 个文件，1739 行增加、90 行删除；main 上不存在 XingChen4 文件，因此无需删除或重命名
  旧 model/config/reasoning。
- 新增独立 Xing4.0 config/model/reasoning/tool parser 与三组 focused tests。
- 同一提交补入 Xing4 必需的 mHC dispatch、FlagGems MLA、T-Head MLA prefill 和 T-Head graph
  支持；保留 main 既有 reference ops，不迁移旧分支删除这些 ops 的无关差异。
- 排除 benchmark/docker mode、NVIDIA MoE 配置、冗余 packaging 和未使用 worker cache 变更。

容器 Plugin `git status` 同时仍显示 inherited 的 5 个 mode-only 文件和 `thead.yaml`。远端
分支在独立的 main 临时克隆中构建，通过带精确 lease 的强制推送替换 `7bb7149`；容器 inherited
改动未包含、重置或据为己有。旧提交 `ed84b6e`、`7bb7149` 均已从分支历史移除；未创建 PR。

## 回归矩阵

| 场景 | 目标 | 模式 | 结果 |
|---|---|---|---|
| fresh-process model/config registry | 新 identity 命中 | 无设备/初始化 | passed |
| fresh-process 旧 XingChen registry | 旧 config/model/reasoning 必须不存在 | 无设备/初始化 | passed；全部 false |
| 新 config 正例与 5 个旧 alias 反例 | 不兼容旧字段 | pytest | 6/6 passed |
| reasoning on/off、流式结束、token 计数 | 对齐 PR #57135 且不继承旧 parser | pytest | 4/4 passed |
| tool parser tag/JSON/partial-token | PR 协议与流式缓冲基本行为 | pytest | 3/3 passed |
| mHC clamp/Sinkhorn focused | FP32 归一化、clamp、20 轮 Sinkhorn | eager focused | 6 passed, 1 deselected |
| 真实 checkpoint config/module | 独立 config、无旧属性、独立模型模块 | fresh process | passed |
| 真实新权重 loader | 41 shards、新 `hc_*` 字段、跳过 MTP | TP4 graph 启动 | 重构前 passed；最新代码待重跑 |
| MLA prefill/decode + MoE + mHC | Plugin/FlagGems-vllm dispatch | graph | 重构前 passed；最新代码待重跑 |
| 最小真实生成 | API → tokenizer → graph decode → parser | graph | 重构前 passed；最新代码待重跑 |
| tool-call API 端到端 | 服务带 `--enable-auto-tool-choice` | graph | not run；仅单测/注册验证 |
| eager、DSA、MTP、量化、其他平台 | 范围外路径 | 未测试 | not claimed |

远端证据位于
`/mnt/nfs/users/jinghao/xingchen4/04-runs/graph-smoke-20260916-03/`：
`server.log`、`chat-response.json`、`plugin-tests.log`。最新静态/focused 收据位于
`/mnt/nfs/users/jinghao/xingchen4/04-runs/xing4-only-20260917-01/`。`git diff --check`
通过；vLLM 前后 revision/status 未变化。当前 PPU 0–15 被四个非本轮 TP4 服务占用，未停止
这些服务，故最新代码的 graph 重跑待资源可用。

## 审查结论

结论：Xing4-only 的源码所有权和 fresh-process 行为符合要求。代码按 ownership 放在 Plugin
扩展点，没有机器名/路径分支、宽泛 fallback 或对共享 vLLM 的修改；main-based 分支没有引入
任何 XingChen4 config/model/reasoning 注册或实现。
最新代码仍缺真实 graph 重跑，因此运行时验证尚未闭环。

本结论不是正式 acceptance：accuracy/performance、tool-call API、eager 与最终生产 launcher
未执行。因为本轮未选择 acceptance，也未创建必需的最终 `start-model.sh`，工作流 adaptation
阶段保持 `in_progress`，但问题 001 的实现缺口已解决。
