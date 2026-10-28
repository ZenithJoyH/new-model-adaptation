# 适配摘要：FlagGems 算子修复补充

最后验证：2026-10-08。本次仅执行用户请求的黑名单算子复现、修复与上游贡献。
完整适配验收仍未完成，`framework.yml` 的 `model_loading` 状态保持不变；
历史服务功能结果见 [functional-validation.md](functional-validation.md)。

## 结果

- `H100-149` / `MinicpmV4.7-1B`，安装源 `/vllm-workspace/FlagGems`；
  最新 base `0dddb4628ae215931171a7f6e04a1183777dcd8a`。
- 两个黑名单入口在 `[2,16,1024,72]` BF16 QKV、`[2,1,1,1024]` additive mask 下
  分别复现 CUDA illegal memory access。原生 PyTorch 通过；显式展开 mask 的对照通过。
- 根因是共享 forward 未将广播轴 stride 置零。复用 `broadcasted_stride` 修复，
  不分配完整 mask，不增加模型或设备特判；容器实际安装已直接修改，无路径覆盖。
- 新增 56 项测试均已执行通过（48 eager、6 graph、2 GQA）；原有 4 项无 mask
  测试通过；两个 S=1024 原崩溃用例修复后 eager 和两次变输入 graph replay 均通过，
  eager max abs 0.001953125。
- [Issue #6869](https://github.com/flagos-ai/FlagGems/issues/6869)；
  [PR #6871](https://github.com/flagos-ai/FlagGems/pull/6871)，以 `Fixes #6869` 关联。

## 最终差异审查

base 为上游 `master@0dddb4628ae215931171a7f6e04a1183777dcd8a`，无 inherited diff；
提交 `f76b5503e694660aa3586a520428f527a4cd0032` 仅包含共用 `attention.py`
和维护用例 `tests/test_attention_mask_broadcast.py`，总计 +136/-4。
容器中的未提交差异与 PR 文件 blob 完全一致，`git diff --check` 通过。
安装源 HEAD 仍为 base 加两个本轮差异；未改写历史。

| 影响面 | 验证 / 边界 |
|---|---|
| 两个 cuDNN wrapper | public API 数值回归、原崩溃用例及 eager/graph 通过。 |
| 共用 SDPA / GQA | public API 回归通过。 |
| 无 mask 分支 | 源码分支保持原样；原有及独立对照通过。 |
| 布局、边界 | FP16/BF16、head_dim=72、65/97 非整 tile 长度、广播及非连续 mask/QKV。 |
| 其他平台、backward/LSE/dropout、其他 mask 数值语义 | 未验证；不作兼容通过声明。 |

结论：可作为上述 forward mask 寻址范围的 PR 候选；上游 CI 已启动，结果待确认。
格式化/CI 工具在适配镜像中不可用，未声称本地执行这些 hooks。
Plugin 原有模型 shim 差异和 FlagGems-vllm 干净状态保持；vLLM、权重和启动脚本未修改。

## 证据和未完成项

Host 与容器工作根均为 `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`，
映射与容器 ID 已重新核实。独立脚本及 manifest 位于
`07-bugs/003-flaggems-cudnn-attention/`；原始失败与修复后日志位于
`04-runs/attention-repro-20261008/`。命令、环境、源码 blob 与逐项结果见
[问题 003](../adaptation/003-flaggems-cudnn-attention.md)。

现有服务 PID 19200 / EngineCore 19405 未停止或重启，模型列表端点 HTTP 200。
本轮保留服务黑名单；需后续验证去过滤后的整模 eager/graph、图片/视频与精度，
再移除 workaround。没有执行完整模型精度、性能、最终 launcher 实启或镜像打包。

`./scripts/audit-workspace --json` 仍提示本框架旧记录的 profile revision 已变化，
另有仓库既有问题；本轮没有重绑历史验收或升级框架状态，不将审计记为通过。
原生证据 manifest 的 SHA-256 为
`701662eb44d127ddc3b01bc88a3b375f4489a104948e6982317c764f8a9181da`。

## 2026-10-09：独立 DSpark 容器 Plugin 分支纠正

`H100-149` / `MiniCPMV4.7-1B-DSpark-gpu6` 的实际安装源已切换为
`0.4.0-dev@e88e4db75ece36e482a5fcc288929d4461d53184`，采用该分支原生
NVIDIA Worker/V2 runner，仅追加 MiniCPM 模型注册、模型 shim 与三个维护测试。
原改动保存在补丁、归档及 stash 中；vLLM 0.28.0 与 FlagGems 全部 `.py/.so`
哈希未变，无 `PYTHONPATH`，未提交或推送代码。

33 项聚焦回归通过；eager 与独立编译缓存的 `FULL_AND_PIECEWISE` 各完成
9/9 文本、单图与并发请求，最终启动器实际启动后 health=200。
服务保持在 `127.0.0.1:18348`，容器运行中且 restart_count=0。
当前启动器 `/opt/flagos/dspark/start-model.sh` SHA-256 为
`b7f21d0274b2810204cb03d21f3a5ad1ce2f3642fd8fa1b766c2d3778188c36c`。

两个数数回复受客户端长度上限截断；eager/graph 两条措辞差异未定位，
不作逐 token 等价结论。此前 MATH500 71.6%、MMLU-Pro 原生 40.0% 与
人工复核 45.57% 均属于旧 Plugin 环境；本轮未执行新分支完整精度、性能或镜像验证。
不升级 `framework.yml` 历史状态。源码范围、组件身份、原生证据及限制见
[问题 008](../adaptation/008-dspark-plugin04.md)。

## 2026-10-09：Plugin 0.4 的 128 客户端并发测量

上述 DSpark 服务保持运行，完成 MATH500 362/500（72.4%）与 MMLU-Pro
14 科每科 50 题共 294/700（原生 42.0%），两项超时均为 0，完整性验证通过。
客户端上限 128，服务仍最多执行 4 条序列；观测峰值在途数分别为 128/50。
首轮响应缓存挂载消失后，保全失败证据并仅停止本轮客户端，改用新评测容器
本地 overlay 缓存从零重跑；未改动模型服务/组件，前后进程、启动器与文件哈希相同。
长度截断 31/17 条，MMLU-Pro 91 条提取失败按原生规则计错；未追加人工恢复计分。
完整记录见[测量报告](dspark-c128-plugin04-20261009.md)。
此为用户指定子集测量，正式精度、性能及镜像验收未升级。
