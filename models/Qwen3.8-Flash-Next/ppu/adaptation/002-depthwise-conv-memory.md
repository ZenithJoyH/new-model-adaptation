# 002：深度卷积通道填充导致显存膨胀

## 元数据与现象

Qwen3.8-Flash-Next / PPU-01，容器 `qwen3.8-flash`；2026-09-04 graph 八并发 sanity 中，
1/8 短请求成功，其余 HTTP 500。WorkerTP3 的 PLE prefill 卷积申请 7.79 GiB 后 OOM。
本页由历史证据整理，未进行新试验；镜像和版本见 [运行配置](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/runtime-config.yml)。

## 诊断与受控尝试

1. 第一次复现错误地把 BatchEncoding 字典键数当作 token 数，未复现；改读 input_ids。
2. 精确输入为 BF16 `[7,10240,3644]`、weight `[10240,1,4]`、dilation=3、groups=10240。
3. 只排除 conv1d 仍进入下层 FlagGems；排除 conv2d 也未覆盖实际 ATen 入口。
4. 调用栈确认实际入口为 `_conv_depthwise2d`，撤回无效 conv2d 黑名单。

## 根因与解决

原复现证明每组一个输入通道被填充到 16，输入临时张量从 522,403,840 B 增至
8,358,461,440 B。通过插件既有黑名单精确排除 conv1d 和 `_conv_depthwise2d`，走平台
原生卷积，是 workaround；未降低上下文或正式并发。原代码、各版失败证据按迁移清单保留。

## 验证与复现

- 容器 `/bug/flaggems-depthwise-conv-padding-20260904/` 保留 `repro-v2.py`、
  `repro-nested-conv.py` 及对应 eager/graph 日志；精确历史命令见归档中的相关打包/验证 Playbook。
- 独立测试覆盖 decode/长 prefill、FP32 参考、graph 变输入和额外显存预算。
- 2026-09-06 原记录中最终 graph sanity 8/8 正确，零错误/OOM/超时；384 项插件回归通过。
- 仅切换当前模型服务，vLLM 未变、容器保持运行；PID 与退出验证见历史进度。

## 限制与下一步

[完整诊断和生命周期](../../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/history/progress.md)、[验收总结](../acceptance/adaptation-summary.md)。
当前版本仍需按阶段门禁绑定证据；
原生回退的最终性能影响待正式评测。知识状态：local-only。

## 2026-09-07 重验

在 clean FlagGems `dcd0cfeae8187dee691656c0616c1ed95899c2ae` 与最终 Plugin
`a5c6f0ca373afa606b68d2daa4bb4a9dcc1833c5` 上，以运行时 append 方式排除 `conv1d` 和
`_conv_depthwise2d`。五组 PPU eager/graph 形状均通过；最大生产形状 `[7,10240,3644]` 的额外峰值
为 521,113,600 bytes（约 497 MiB），未出现旧 7.79 GiB 膨胀。证据位于远端
`05-runs/workaround-probes-dcd0cfe-20260907-1721/`。最终性能影响仍待正式性能验收。
