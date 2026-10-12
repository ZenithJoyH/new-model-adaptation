# 010：纯红图像颜色误判

## 元数据与现象

- 状态：`hypothesis`；首次与最后验证：2026-10-01。
- 模型：`MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`；Host `PPU-07`，容器 `minimaxM3.1`，BF16/TP16、decode-full、prefix cache enabled。Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加既有任务 diff；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`；FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`。
- 256×256 RGB `(255,0,0)` 纯红 PNG 的 SHA-256 为 `ba7fc9794d3db90790d76cdf0b4faf0a1b66ff8acc685667ffb318c06e6d66b6`。请求“这张纯色图片是什么颜色？只回答一个颜色词。”时，API 返回 HTTP 200、非空输出“绿色”，没有请求错误或截断；正确答案应为“红色”。

## 已有经验与受控比较

该现象与[问题 009](009-context-204800-mm-profile.md)的启动阶段 `conv3d_forward_kernel` 非法内存访问不同：本问题发生在正常推理阶段，服务持续健康。暂无线索表明两者同源；不据共同的视觉路径推断根因。

| 服务与变量 | 精确证据 | 红图结果 | 其他模态对照 |
|---|---|---|---|
| 历史 65536、正常多模态预热 | `04-runs/image-smoke-65k-defaults-20261001.json` SHA-256 `e72b84a2c38c044a9feeb88121f5571db9da6bbe940c01d8e94ef41662c2fb04` | “绿色” | 当时只运行此图 |
| 204800、`--skip-mm-profiling` | `04-runs/mm-requests-204800-20261001.json` SHA-256 `b64e721a649f76a4e15247d8491f2178f21cc1d016dfb6c71c6f8348558642e8` | “绿色” | 蓝图“蓝色”、四位数字 OCR“4827”、双图第二张“蓝色”、八帧视频末帧“2”，均 HTTP 200 且正确 |
| 204800、完整多模态预热，排除 FlagGems `conv3d,cudnn_convolution` | `04-runs/mm-requests-204800-no-skip-20261001.json` SHA-256 `857e162a4d8733895d4f2d226a0e425f1ebad2796062b9fbefc8a76c40517e2e` | “绿色” | 同一组输入、提示和采样参数，其他四项仍正确 |
| 204800、最终根脚本，完整多模态预热并排除上述两项 | `04-runs/mm-requests-204800-full-mm-root-20261001.json` SHA-256 `e3951305365ca93bee3ac1770c6d12255b1c9df2d232198e3135dcec2d70a2a7` | “绿色” | 同一组输入、提示和采样参数，5/5 HTTP 200、4/5 答案正确；服务继续健康 |

后两轮使用内容相同的 PNG 和 MP4 字节；`03-acceptance/mm-requests-20261001.py` 与 `03-acceptance/mm-requests-no-skip-20261001.py` 仅使用不同视频临时文件名，避免覆盖。采样 `temperature=0,max_tokens=512`，报告分开记录 HTTP 成功和答案正确；不能把 5/5 请求成功写成 5/5 准确。

## 诊断、限制与下一步

- 已验证：错误先于 204800 的预热规避措施出现；在完整预热且切换 3D 卷积后仍存在。因此不能归因于 `--skip-mm-profiling`，也不能仅归因于 FlagGems 3D 卷积。
- 未验证根因：可能涉及图像预处理、视觉特征、模型本身对纯色样本的判断或回答生成；尚无参考实现或更大颜色集的受控数值对照。不得推断所有颜色、图片或视频均错误，也不得凭四项正确推断多模态整体精度。
- 后续可用同一字节输入比较处理器像素和视觉输出，并在批准的参考服务上复测红、绿、蓝及图文任务；若定位到 Plugin 路径，再按模型/平台扩展点做聚焦修复与回归。当前无产品源码变更，知识库状态 `needs-validation`。
