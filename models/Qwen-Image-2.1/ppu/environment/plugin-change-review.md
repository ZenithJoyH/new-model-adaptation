# Qwen-Image-2.1 PPU Plugin 变更审查

## 基线

- Torch-FL：`/workspace/PyTorch-Plugin-FL`，`main@a3b46f805a91fcb89a6486c8cf3b11384d9c23e8`，`main...origin/main`、clean；editable 安装解析到该目录。
- FlagGems：`/workspace/FlagGems`，`master@454f68853424970deb800290b7d7538a09a0b4bb`，`master...origin/master`、clean。
- vLLM：`0.23.0+v0.2.0.ppu2.1.0`，仅 site-packages，无 `/workspace/vllm` checkout；本轮只读。
- 审查日期：2026-09-17。

## 职责判断

当前首个失败是 Diffusers 0.40.0 不认识权重声明的 `QwenImage21Pipeline`，且同时缺少专用 DiT/VAE 类。用户提供的固定 Diffusers fork 已包含完整实现，因此问题属于上层模型框架依赖，不属于 Torch-FL 设备、dispatch 或 kernel 注册。

将 Qwen-Image-2.1 模型类复制进 Torch-FL、按模型路径在公共 dispatch 中分支，或把权重伪装成旧 `QwenImagePipeline` 都违反所有权边界。本轮以官方 stable Diffusers 0.40.0 wheel 为基线，只移植固定参考提交中的四个 Qwen-Image-2.1 文件并补齐 Diffusers 自身注册项；Torch-FL/FlagGems/vLLM 均无源码 diff。

## 影响与验证

| 检查项 | 当前结论 |
|---|---|
| Torch-FL 公共接口/default policy | 不修改 |
| FlagGems provider/实现 | 不修改；若后续出现需集成的新缺口，重新审查并先同步 |
| vLLM | 不修改、不停止相关进程 |
| 旧 Qwen-Image 调用方 | 已验证旧 `QwenImagePipeline` 仍可导入 |
| 无设备导入 | 已验证 fresh process 不加载 PPU 内存即可导入新旧类，并完成无大权重 pipeline 装配 |
| eager/graph | 本轮目标仅 eager 脚本；graph 未验证，不作支持声明 |

## 当前结论

当前设计结论：`无 Plugin 变更`。最终设备推理后仍须重新记录三个源码树状态与实际运行结果；若产生任何 Plugin diff，本结论立即失效并需按贡献标准重新审查。

## 2026-09-18 PR #342 复审

上述“无 Plugin 变更”结论已失效。Torch-FL editable 源码现位于
`codex/pr-342-ppu-fixes@229386dcb4734334bd695c6aabe24a35b8b491d2`，包含 PR #342
和未提交的审查修复。变更所有权保持清晰：Qwen-Image-2.1 流程约束位于 manual harness，
设备同步位于既有 DeviceGuard 扩展点，PPU `_unsafe_view` 契约例外位于 vendor-conf
生成路径；未加入模型名或机器路径的公共 dispatch 分支。

影响矩阵：Qwen-Image-2.1 manual infer/sweep/bench/numerics 有行为修正；PPU 默认
`_unsafe_view` 从 FlagGems 改走 CUDA boxing；其他模型和平台代码未主动修改。显式
强制 FlagGems 的 A/B 诊断路径仍保留。最小回归为 6 个测试通过，另有 PPU live
alias/error 和 synchronize-device 验证；graph 与完整模型推理未验证。

当前设计审查结论：`适合继续验证，但尚不可提交为完成态`。在完整推理、最终 diff
复审和上游 PR 范围确认前，工作树保持未提交；详细证据见 adaptation 002。
